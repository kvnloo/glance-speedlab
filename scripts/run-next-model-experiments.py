#!/usr/bin/env python3
"""Run E008-E010 against one local Glance model load.

Detailed paired rows stay in ignored research/runs/. Aggregate results and the
human-readable experiment reports are committed. No frames leave the machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
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
CHOICE_QUESTIONS = {key: value for key, value in QUESTIONS.items() if value["type"] == "choice"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", str(Path.cwd().parent / "glance")))
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--batch-repeats", type=int, default=10)
    parser.add_argument("--raw", default="research/runs/next-model-experiments.json")
    parser.add_argument("--summary", default="research/results/next-model-experiments.json")
    return parser.parse_args()


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * q + 0.999999) - 1))
    return round(ordered[index], 3)


def stats(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "min": round(min(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": pct(values, 0.95),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
    }


def vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1.0 - value}
    return {str(key): float(value) for key, value in (answer.get("probabilities") or {}).items()}


def decision(answer: dict[str, Any]) -> str:
    return ("yes" if float(answer["noul"]) >= 0.5 else "no") if answer["type"] == "noul" else str(answer["choice"])


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    same = True
    delta = 0.0
    shared = set(left) & set(right)
    for key in shared:
        same = same and decision(left[key]) == decision(right[key])
        lv, rv = vector(left[key]), vector(right[key])
        for label in set(lv) | set(rv):
            delta = max(delta, abs(lv.get(label, 0.0) - rv.get(label, 0.0)))
    return {"decisions_equal": same, "max_probability_delta": round(delta, 8)}


def main() -> int:
    args = parse_args()
    root, core = Path.cwd(), Path(args.core).resolve()
    sys.path.insert(0, str(core))
    os.environ.setdefault("GLANCE_ROOT", str(core))

    from glance.config import load_config  # pylint: disable=import-error,import-outside-toplevel
    from glance.pipeline import Engine  # pylint: disable=import-error,import-outside-toplevel

    logs = (root / "research/runs/core-next-calls").resolve()
    logs.mkdir(parents=True, exist_ok=True)
    cfg = load_config(overrides={"vlm": {"prefix_cache": True}, "paths": {"logs": str(logs)}})
    engine = Engine(cfg, source="speedlab-next")
    backend = engine.backend("vlm")
    fixture_dir = root / "research/runs/fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    sources: dict[str, Path] = {}
    for name in ("dog", "receipt", "invoice"):
        source = core / "samples" / f"{name}.jpg"
        target = fixture_dir / f"{name}-320-q60.jpg"
        with Image.open(source) as image:
            prepared = image.convert("RGB")
            prepared.thumbnail((320, 320), Image.Resampling.LANCZOS)
            prepared.save(target, "JPEG", quality=60, optimize=False)
        sources[name] = target
    rows: list[dict[str, Any]] = []

    def run(path: Path, questions: dict[str, Any], choice_method: str = "independent") -> dict[str, Any]:
        backend._prefix_cache.clear()  # a live frame has a new image hash
        started = time.perf_counter()
        trace = engine.decide({
            "model": "vlm",
            "state": {"images": [{"id": "img0", "path": str(path)}]},
            "questions": questions,
            "options": {"choice_method": choice_method, "calibrated": False},
        })
        payload = trace.response.model_dump()
        return {
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
            "timing_ms": payload["timing_ms"],
            "answers": payload["answers"],
            "usage": payload["usage"],
        }

    # Stabilize model and MPS before measurement.
    backend.image_token_budget = 768
    for _ in range(2):
        run(sources["dog"], QUESTIONS)

    # E008: rotate the budget order per repetition and image.
    budgets = (128, 192, 256, 768)
    for image_index, (image_name, path) in enumerate(sources.items()):
        for repeat in range(args.repeats):
            shift = (repeat + image_index) % len(budgets)
            for budget in budgets[shift:] + budgets[:shift]:
                backend.image_token_budget = budget
                result = run(path, QUESTIONS)
                rows.append({"experiment": "E008", "image": image_name, "repeat": repeat, "variant": str(budget), **result})

    # E009: fixed full budget, rotate candidate order.
    backend.image_token_budget = 768
    batch_sizes = (4, 8, 16, 32)
    for repeat in range(args.batch_repeats):
        shift = repeat % len(batch_sizes)
        for batch_size in batch_sizes[shift:] + batch_sizes[:shift]:
            backend.suffix_batch_size = batch_size
            result = run(sources["dog"], QUESTIONS)
            rows.append({"experiment": "E009", "image": "dog", "repeat": repeat, "variant": str(batch_size), **result})

    # E010: two choice questions; letter rotations are a Glance config parameter.
    backend.suffix_batch_size = 16
    methods = ("independent", "letter1", "letter4")
    for image_index, (image_name, path) in enumerate(sources.items()):
        for repeat in range(args.repeats):
            shift = (repeat + image_index) % len(methods)
            for method in methods[shift:] + methods[:shift]:
                cfg.vlm.letter_rotations = 1 if method == "letter1" else 4
                result = run(path, CHOICE_QUESTIONS, "independent" if method == "independent" else "letter")
                rows.append({"experiment": "E010", "image": image_name, "repeat": repeat, "variant": method, **result})

    summary = summarize(rows)
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
        "images": {name: {"source": f"derived from samples/{name}.jpg at 320 px, JPEG q60", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in sources.items()},
    }
    raw_path, summary_path = root / args.raw, root / args.summary
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"environment": environment, "rows": rows}, indent=2) + "\n")
    summary_path.write_text(json.dumps({"environment": environment, "summary": summary}, indent=2) + "\n")
    write_reports(root, summary)
    print(json.dumps(summary, indent=2))
    return 0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["experiment"], row["variant"])].append(row)
    result: dict[str, Any] = {}
    for experiment in ("E008", "E009", "E010"):
        result[experiment] = {}
        for variant in sorted(v for exp, v in grouped if exp == experiment):
            items = grouped[(experiment, variant)]
            result[experiment][variant] = {
                "wall_ms": stats([float(item["wall_ms"]) for item in items]),
                "model_total_ms": stats([float(item["timing_ms"]["total"]) for item in items]),
                "prefix_ms": stats([float(item["timing_ms"].get("prefix", 0)) for item in items]),
                "score_ms": stats([float(item["timing_ms"].get("score", 0)) for item in items]),
                "image_tokens": stats([float(item["usage"].get("image_tokens", 0)) for item in items]),
                "forward_passes": stats([float(item["usage"].get("forward_passes", 0)) for item in items]),
            }

    e008_pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["experiment"] == "E008":
            e008_pairs[(row["image"], row["repeat"])][row["variant"]] = row["answers"]
    for budget in ("128", "192", "256"):
        checks = [compare(pair[budget], pair["768"]) for pair in e008_pairs.values()]
        result["E008"][f"guardrail_{budget}_vs_768"] = guardrail(checks, 0.10)
        result["E008"][f"speedup_{budget}_vs_768"] = round(result["E008"]["768"]["wall_ms"]["p50"] / result["E008"][budget]["wall_ms"]["p50"], 4)

    e009_pairs: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["experiment"] == "E009":
            e009_pairs[row["repeat"]][row["variant"]] = row["answers"]
    for batch in ("4", "8", "32"):
        result["E009"][f"guardrail_{batch}_vs_16"] = guardrail([compare(pair[batch], pair["16"]) for pair in e009_pairs.values()], 0.02)

    e010_pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["experiment"] == "E010":
            e010_pairs[(row["image"], row["repeat"])][row["variant"]] = row["answers"]
    for method in ("letter1", "letter4"):
        checks = [compare(pair[method], pair["independent"]) for pair in e010_pairs.values()]
        result["E010"][f"guardrail_{method}_vs_independent"] = guardrail(checks, 0.10)
        result["E010"][f"speedup_{method}_vs_independent"] = round(result["E010"]["independent"]["wall_ms"]["p50"] / result["E010"][method]["wall_ms"]["p50"], 4)
    return result


def guardrail(checks: list[dict[str, Any]], limit: float) -> dict[str, Any]:
    return {
        "decision_agreement": round(sum(check["decisions_equal"] for check in checks) / len(checks), 6),
        "max_probability_delta": max(check["max_probability_delta"] for check in checks),
        "passed": all(check["decisions_equal"] and check["max_probability_delta"] <= limit for check in checks),
    }


def write_reports(root: Path, summary: dict[str, Any]) -> None:
    for directory, experiment, title in (
        ("008-image-token-budget", "E008", "Image-token budget"),
        ("009-suffix-batch", "E009", "Cached suffix batch size"),
        ("010-choice-scoring", "E010", "Compressed choice scoring"),
    ):
        payload = summary[experiment]
        lines = [f"# {experiment} result — {title}", "", "Generated by `scripts/run-next-model-experiments.py`. Detailed paired rows remain ignored in `research/runs/`.", "", "```json", json.dumps(payload, indent=2), "```", ""]
        (root / "research/experiments" / directory / "result.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
