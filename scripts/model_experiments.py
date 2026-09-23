#!/usr/bin/env python3
"""Run E001/E002/E003/E006 against the local Glance checkout in one model load.

This script writes detailed rows to ignored research/runs/ and aggregate, privacy-safe
results to research/results/. It never invokes a hosted model.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image


QUESTIONS: dict[str, dict[str, Any]] = {
    "content": {
        "type": "choice",
        "instructions": "What kind of content is shown in `img0`?",
        "criteria": {"animal photo": None, "receipt": None, "invoice": None, "other": None},
    },
    "text": {"type": "noul", "instructions": "Is readable text visible in `img0`?"},
    "photo": {"type": "noul", "instructions": "Is `img0` primarily a natural photograph?"},
    "tone": {
        "type": "choice",
        "instructions": "What is the overall visual tone of `img0`?",
        "criteria": {"mostly light": None, "mostly dark": None, "mixed": None},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", str(Path.cwd().parent / "glance")))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--batch-repeats", type=int, default=7)
    parser.add_argument("--order-repeats", type=int, default=10)
    parser.add_argument("--raw", default="research/runs/model-experiments.json")
    parser.add_argument("--summary", default="research/results/model-experiments.json")
    return parser.parse_args()


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) * q) + 0.999999) - 1))
    return round(ordered[index], 3)


def stats(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "min": round(min(values), 3) if values else 0.0,
        "p50": round(statistics.median(values), 3) if values else 0.0,
        "p90": pct(values, 0.90),
        "p95": pct(values, 0.95),
        "max": round(max(values), 3) if values else 0.0,
        "mean": round(statistics.mean(values), 3) if values else 0.0,
    }


def answer_vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1.0 - value}
    return {str(key): float(value) for key, value in (answer.get("probabilities") or {}).items()}


def answer_decision(answer: dict[str, Any]) -> str:
    if answer["type"] == "noul":
        return "yes" if float(answer["noul"]) >= 0.5 else "no"
    return str(answer["choice"])


def compare_answers(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    decisions_equal = True
    max_delta = 0.0
    for key in left:
        decisions_equal = decisions_equal and answer_decision(left[key]) == answer_decision(right[key])
        lv, rv = answer_vector(left[key]), answer_vector(right[key])
        for label in set(lv) | set(rv):
            max_delta = max(max_delta, abs(lv.get(label, 0.0) - rv.get(label, 0.0)))
    return {"decisions_equal": decisions_equal, "max_probability_delta": round(max_delta, 8)}


def save_variant(source: Path, target: Path, long_edge: int, quality: int) -> dict[str, Any]:
    with Image.open(source) as image:
        image = image.convert("RGB")
        image.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
        image.save(target, "JPEG", quality=quality, optimize=False)
    payload = target.read_bytes()
    return {
        "path": str(target),
        "width": Image.open(target).width,
        "height": Image.open(target).height,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def encode_bench(source: Path, long_edge: int, quality: int, iterations: int = 50) -> dict[str, Any]:
    values, sizes = [], []
    with Image.open(source) as original:
        prepared = original.convert("RGB")
        prepared.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
        for _ in range(iterations):
            buffer = io.BytesIO()
            started = time.perf_counter()
            prepared.save(buffer, "JPEG", quality=quality, optimize=False)
            values.append((time.perf_counter() - started) * 1000)
            sizes.append(buffer.tell())
    return {"encode_ms": stats(values), "bytes": int(statistics.median(sizes))}


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    core = Path(args.core).resolve()
    sys.path.insert(0, str(core))
    os.environ.setdefault("GLANCE_ROOT", str(core))

    from glance.config import load_config  # pylint: disable=import-error,import-outside-toplevel
    from glance.pipeline import Engine  # pylint: disable=import-error,import-outside-toplevel

    output_logs = (root / "research/runs/core-calls").resolve()
    output_logs.mkdir(parents=True, exist_ok=True)
    cfg = load_config(overrides={"vlm": {"prefix_cache": True}, "paths": {"logs": str(output_logs)}})
    engine = Engine(cfg, source="speedlab")
    backend = engine.backend("vlm")

    sources = {
        "dog": core / "samples/dog.jpg",
        "receipt": core / "samples/receipt.jpg",
        "invoice": core / "samples/invoice.jpg",
    }
    raw_rows: list[dict[str, Any]] = []

    def decide(path: Path, questions: dict[str, Any], clear: bool = True) -> dict[str, Any]:
        if clear:
            backend._prefix_cache.clear()  # experiment control: force one cold image prefix
        started = time.perf_counter()
        trace = engine.decide({
            "model": "vlm",
            "state": {"images": [{"id": "img0", "path": str(path)}], "context": {"source": "speedlab experiments"}},
            "questions": questions,
            "options": {"choice_method": "independent", "calibrated": False},
        })
        wall_ms = (time.perf_counter() - started) * 1000
        payload = trace.response.model_dump()
        return {
            "wall_ms": round(wall_ms, 3),
            "timing_ms": payload["timing_ms"],
            "answers": payload["answers"],
            "usage": payload["usage"],
        }

    with tempfile.TemporaryDirectory(prefix="glance-speedlab-") as temporary:
        variants = Path(temporary)
        encoded: dict[tuple[str, int, int], dict[str, Any]] = {}
        for name, source in sources.items():
            for edge in (224, 320):
                for quality in (40, 60, 90):
                    target = variants / f"{name}-{edge}-q{quality}.jpg"
                    encoded[(name, edge, quality)] = save_variant(source, target, edge, quality)

        # Two unmeasured warmups stabilize model/MPS setup.
        for _ in range(2):
            decide(Path(encoded[("dog", 320, 60)]["path"]), {"content": QUESTIONS["content"]})

        # E001: resolution, paired and order-balanced.
        for image_name in sources:
            for repeat in range(args.repeats):
                order = (224, 320) if repeat % 2 == 0 else (320, 224)
                for edge in order:
                    meta = encoded[(image_name, edge, 60)]
                    result = decide(Path(meta["path"]), QUESTIONS)
                    raw_rows.append({"experiment": "E001", "image": image_name, "repeat": repeat, "variant": str(edge), "input": meta, **result})

        # E002: quality; local encoder is measured independently from model inference.
        encoder_results = {
            f"{name}-q{quality}": encode_bench(source, 320, quality)
            for name, source in sources.items() for quality in (40, 60, 90)
        }
        qualities = (40, 60, 90)
        for image_name in sources:
            for repeat in range(args.repeats):
                rotated = qualities[repeat % 3:] + qualities[:repeat % 3]
                for quality in rotated:
                    meta = encoded[(image_name, 320, quality)]
                    result = decide(Path(meta["path"]), QUESTIONS)
                    raw_rows.append({"experiment": "E002", "image": image_name, "repeat": repeat, "variant": str(quality), "input": meta, **result})

        # E003: one cold batch versus four cold single requests. Arm order alternates.
        for image_name in sources:
            path = Path(encoded[(image_name, 320, 60)]["path"])
            for repeat in range(args.batch_repeats):
                arm_order = ("batch", "sequential") if repeat % 2 == 0 else ("sequential", "batch")
                arm_results: dict[str, Any] = {}
                for arm in arm_order:
                    if arm == "batch":
                        arm_results[arm] = decide(path, QUESTIONS)
                    else:
                        singles = [decide(path, {key: question}) for key, question in QUESTIONS.items()]
                        arm_results[arm] = {
                            "wall_ms": round(sum(item["wall_ms"] for item in singles), 3),
                            "timing_ms": {
                                key: sum(float(item["timing_ms"].get(key, 0)) for item in singles)
                                for key in {key for item in singles for key in item["timing_ms"]}
                            },
                            "answers": {key: singles[index]["answers"][key] for index, key in enumerate(QUESTIONS)},
                            "usage": {
                                key: sum(float(item["usage"].get(key, 0) or 0) for item in singles)
                                for key in singles[0]["usage"]
                            },
                        }
                comparison = compare_answers(arm_results["batch"]["answers"], arm_results["sequential"]["answers"])
                for arm, result in arm_results.items():
                    raw_rows.append({"experiment": "E003", "image": image_name, "repeat": repeat, "variant": arm, "comparison": comparison, **result})

        # E006: same cold batch, reverse insertion order. Arm order alternates.
        forward = QUESTIONS
        reverse = dict(reversed(list(QUESTIONS.items())))
        for image_name in sources:
            path = Path(encoded[(image_name, 320, 60)]["path"])
            for repeat in range(args.order_repeats):
                arm_order = ("forward", "reverse") if repeat % 2 == 0 else ("reverse", "forward")
                arm_results = {}
                for arm in arm_order:
                    arm_results[arm] = decide(path, forward if arm == "forward" else reverse)
                comparison = compare_answers(arm_results["forward"]["answers"], arm_results["reverse"]["answers"])
                for arm, result in arm_results.items():
                    raw_rows.append({"experiment": "E006", "image": image_name, "repeat": repeat, "variant": arm, "comparison": comparison, **result})

    summary = summarize(raw_rows, encoder_results)
    environment = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": "Apple M5, 32 GB unified memory",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "glance_commit": subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip(),
        "model": f"{backend.model_id}@{backend.revision}",
        "device": backend.device,
        "dtype": backend.dtype,
        "prefix_cache": True,
        "images": {name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source": f"samples/{path.name}"} for name, path in sources.items()},
    }
    raw_path, summary_path = root / args.raw, root / args.summary
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"environment": environment, "rows": raw_rows, "encoder": encoder_results}, indent=2) + "\n")
    summary_path.write_text(json.dumps({"environment": environment, "summary": summary}, indent=2) + "\n")
    write_reports(root, summary)
    print(json.dumps(summary, indent=2))
    return 0


def summarize(rows: list[dict[str, Any]], encoder: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["experiment"], row["variant"])].append(row)

    result: dict[str, Any] = {}
    for experiment in ("E001", "E002", "E003", "E006"):
        result[experiment] = {}
        variants = sorted({variant for exp, variant in grouped if exp == experiment})
        for variant in variants:
            items = grouped[(experiment, variant)]
            result[experiment][variant] = {
                "wall_ms": stats([float(item["wall_ms"]) for item in items]),
                "model_total_ms": stats([float(item["timing_ms"].get("total", sum(item["timing_ms"].values()))) for item in items]),
                "prefix_ms": stats([float(item["timing_ms"].get("prefix", 0)) for item in items]),
                "score_ms": stats([float(item["timing_ms"].get("score", 0)) for item in items]),
            }
            if "input" in items[0]:
                result[experiment][variant]["input_bytes"] = stats([float(item["input"]["bytes"]) for item in items])

    for experiment in ("E001", "E002"):
        by_pair: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            if row["experiment"] == experiment:
                by_pair[(row["image"], row["repeat"])][row["variant"]] = row["answers"]
        reference = "320" if experiment == "E001" else "90"
        comparison = "224" if experiment == "E001" else "40"
        checks = [compare_answers(pair[comparison], pair[reference]) for pair in by_pair.values()]
        result[experiment]["guardrail"] = {
            "decision_agreement": sum(check["decisions_equal"] for check in checks) / len(checks),
            "max_probability_delta": max(check["max_probability_delta"] for check in checks),
            "passed": all(check["decisions_equal"] and check["max_probability_delta"] <= 0.10 for check in checks),
        }

    result["E002"]["encoder"] = encoder
    for experiment in ("E003", "E006"):
        checks = [row["comparison"] for row in rows if row["experiment"] == experiment and row["variant"] in ("batch", "forward")]
        result[experiment]["guardrail"] = {
            "decision_agreement": sum(check["decisions_equal"] for check in checks) / len(checks),
            "max_probability_delta": max(check["max_probability_delta"] for check in checks),
            "passed": all(check["decisions_equal"] and check["max_probability_delta"] <= 0.02 for check in checks),
        }

    result["E001"]["speedup_224_vs_320"] = round(result["E001"]["320"]["wall_ms"]["p50"] / result["E001"]["224"]["wall_ms"]["p50"], 4)
    result["E003"]["speedup_batch_vs_sequential"] = round(result["E003"]["sequential"]["wall_ms"]["p50"] / result["E003"]["batch"]["wall_ms"]["p50"], 4)
    result["E006"]["forward_vs_reverse_delta_pct"] = round(100 * (result["E006"]["forward"]["wall_ms"]["p50"] - result["E006"]["reverse"]["wall_ms"]["p50"]) / result["E006"]["reverse"]["wall_ms"]["p50"], 3)
    return result


def write_reports(root: Path, summary: dict[str, Any]) -> None:
    reports = {
        "001-resolution": ("E001", "Resolution"),
        "002-jpeg-quality": ("E002", "JPEG quality"),
        "003-native-batch": ("E003", "Native batching"),
        "006-question-order": ("E006", "Question order"),
    }
    for directory, (experiment, title) in reports.items():
        payload = summary[experiment]
        lines = [f"# {experiment} result — {title}", "", "Generated by `scripts/model_experiments.py`. Aggregate values are committed; detailed rows remain ignored in `research/runs/`.", "", "```json", json.dumps(payload, indent=2), "```", ""]
        (root / "research/experiments" / directory / "result.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
