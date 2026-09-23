#!/usr/bin/env python3
"""Run E015: full-vocabulary normalization versus selected-logit-only statement scoring."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


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
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", "../glance"))
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--raw", default="research/runs/e015-selected-logit.json")
    return parser.parse_args()


def summarize(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, max(0, int(len(ordered) * 0.95 + 0.999999) - 1))]
    return {
        "n": len(values),
        "min": round(min(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(p95, 3),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
    }


def answer_vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1.0 - value}
    return {str(key): float(value) for key, value in (answer.get("probabilities") or {}).items()}


def decision(answer: dict[str, Any]) -> str:
    if answer["type"] == "noul":
        return "yes" if float(answer["noul"]) >= 0.5 else "no"
    return str(answer["choice"])


def main() -> int:
    args = parse_args()
    root, core = Path.cwd(), Path(args.core).resolve()
    sys.path.insert(0, str(core))
    os.environ.setdefault("GLANCE_ROOT", str(core))

    from glance.config import load_config  # pylint: disable=import-error,import-outside-toplevel
    from glance.pipeline import Engine  # pylint: disable=import-error,import-outside-toplevel

    fixtures = {
        name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg"
        for name in ("dog", "receipt", "invoice")
    }
    missing = [str(path) for path in fixtures.values() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing controlled fixtures: {', '.join(missing)}")

    log_dir = (root / "research/runs/e015-core-calls").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(overrides={
        "models": {"tier_override": "apple_8gb", "image_token_budget_override": 128},
        "vlm": {"prefix_cache": True, "suffix_batch_size": 16, "compute_statement_off_mass": True},
        "paths": {"logs": str(log_dir)},
    })
    engine = Engine(cfg, source="speedlab-e015")
    backend = engine.backend("vlm")
    rows: list[dict[str, Any]] = []

    def run(path: Path, questions: dict[str, dict[str, Any]], arm: str, workload: str, warmup: bool, pair: int) -> None:
        backend.compute_statement_off_mass = arm == "reference"
        started = time.perf_counter()
        trace = engine.decide({
            "model": "vlm",
            "state": {"images": [{"id": "img0", "path": str(path)}]},
            "questions": questions,
            "options": {"choice_method": "independent", "calibrated": False},
        })
        wall_ms = (time.perf_counter() - started) * 1000
        payload = trace.response.model_dump()
        raw_z = {
            qid: [float(value) for value in trace.scoring.scores[qid].z]
            for qid in questions
        }
        off_mass = [
            statement.get("off_mass")
            for qid in questions
            for statement in trace.scoring.scores[qid].statements
        ]
        rows.append({
            "workload": workload,
            "image": path.stem.split("-")[0],
            "pair": pair,
            "warmup": warmup,
            "arm": arm,
            "wall_ms": round(wall_ms, 3),
            "timing_ms": payload["timing_ms"],
            "answers": payload["answers"],
            "z": raw_z,
            "off_mass": off_mass,
            "warnings": payload["warnings"],
        })

    workloads = (
        ("nine-statements", QUESTIONS, fixtures),
        ("four-statements", {"content": QUESTIONS["content"]}, {"dog": fixtures["dog"]}),
    )
    for workload, questions, workload_fixtures in workloads:
        for _, path in workload_fixtures.items():
            for pair in range(args.warmups + args.repeats):
                # Populate the exact-image KV prefix before either measured arm.
                backend.compute_statement_off_mass = False
                engine.decide({
                    "model": "vlm",
                    "state": {"images": [{"id": "img0", "path": str(path)}]},
                    "questions": questions,
                    "options": {"choice_method": "independent", "calibrated": False},
                })
                order = ("reference", "selected") if pair % 2 == 0 else ("selected", "reference")
                for arm in order:
                    run(path, questions, arm, workload, pair < args.warmups, pair)
                    print(f"{workload} {path.stem} pair {pair + 1}: {arm} {rows[-1]['wall_ms']:.1f} ms", flush=True)

    measured = [row for row in rows if not row["warmup"]]
    aggregate: dict[str, Any] = {}
    all_equal = True
    max_probability_delta = 0.0
    max_z_delta = 0.0
    diagnostic_shape_valid = True
    for workload, _, _ in workloads:
        selected_rows = [row for row in measured if row["workload"] == workload]
        aggregate[workload] = {}
        for arm in ("reference", "selected"):
            arm_rows = [row for row in selected_rows if row["arm"] == arm]
            aggregate[workload][arm] = {
                "wall_ms": summarize([float(row["wall_ms"]) for row in arm_rows]),
                "score_ms": summarize([float(row["timing_ms"]["score"]) for row in arm_rows]),
                "total_ms": summarize([float(row["timing_ms"]["total"]) for row in arm_rows]),
            }
        reference_p50 = float(aggregate[workload]["reference"]["score_ms"]["p50"])
        selected_p50 = float(aggregate[workload]["selected"]["score_ms"]["p50"])
        aggregate[workload]["selected"]["score_speedup"] = round(reference_p50 / selected_p50, 4)
        aggregate[workload]["selected"]["score_reduction_percent"] = round((1 - selected_p50 / reference_p50) * 100, 1)

        keyed = {(row["image"], row["pair"], row["arm"]): row for row in selected_rows}
        for image, pair, _ in {(row["image"], row["pair"], row["arm"]) for row in selected_rows}:
            reference = keyed[(image, pair, "reference")]
            selected = keyed[(image, pair, "selected")]
            for qid in reference["z"]:
                max_z_delta = max(max_z_delta, *(abs(a - b) for a, b in zip(reference["z"][qid], selected["z"][qid])))
                left, right = reference["answers"][qid], selected["answers"][qid]
                all_equal = all_equal and decision(left) == decision(right)
                lv, rv = answer_vector(left), answer_vector(right)
                max_probability_delta = max(
                    max_probability_delta,
                    *(abs(lv.get(label, 0.0) - rv.get(label, 0.0)) for label in set(lv) | set(rv)),
                )
            diagnostic_shape_valid = diagnostic_shape_valid and all(value is not None for value in reference["off_mass"])
            diagnostic_shape_valid = diagnostic_shape_valid and all(value is None for value in selected["off_mass"])

    primary = aggregate["nine-statements"]
    guardrail = {
        "decisions_equal": all_equal,
        "max_probability_delta": max_probability_delta,
        "max_z_delta": max_z_delta,
        "diagnostic_shape_valid": diagnostic_shape_valid,
        "passed": all_equal and max_probability_delta == 0.0 and max_z_delta == 0.0 and diagnostic_shape_valid,
    }
    keep = (
        guardrail["passed"]
        and float(primary["selected"]["score_reduction_percent"]) >= 5.0
        and float(primary["selected"]["score_ms"]["p95"]) <= float(primary["reference"]["score_ms"]["p95"]) * 1.05
    )
    output = {
        "schema_version": 1,
        "experiment": "E015",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 10-core GPU, 32 GB unified memory",
            "platform": platform.platform(),
            "glance_base_commit": subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip(),
            "model": f"{backend.model_id}@{backend.revision}",
            "device": backend.device,
            "dtype": backend.dtype,
            "image_token_budget": backend.image_token_budget,
            "suffix_batch_size": backend.suffix_batch_size,
        },
        "protocol": {"warmup_pairs": args.warmups, "measured_pairs": args.repeats, "prefix_cache_hits": True},
        "aggregate": aggregate,
        "guardrail": guardrail,
        "keep_fast_path": keep,
        "rows": rows,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"aggregate": aggregate, "guardrail": guardrail, "keep_fast_path": keep, "raw": str(raw_path)}, indent=2))
    return 0 if guardrail["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
