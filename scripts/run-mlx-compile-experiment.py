#!/usr/bin/env python3
"""Run E018: eager versus fixed-shape compiled MLX statement scoring."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import statistics
import time
from pathlib import Path
from typing import Any


MODEL = "mlx-community/Qwen3-VL-2B-Instruct-8bit"
REVISION = "b0338e0e843d8e1befe873d144b81fefdc47efa6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default="../glance")
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--images", nargs="+", choices=("dog", "receipt", "invoice"), default=["dog", "receipt", "invoice"])
    parser.add_argument("--raw", default="research/runs/e018-mlx-compile.json")
    return parser.parse_args()


def load_direct_module(root: Path):
    path = root / "scripts" / "run-mlx-direct-experiment.py"
    spec = importlib.util.spec_from_file_location("speedlab_mlx_direct", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scorer from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summary(values: list[float]) -> dict[str, float | int]:
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


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    direct = load_direct_module(root)
    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in args.images}
    missing = [str(path) for path in fixtures.values() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing fixtures: {', '.join(missing)}")

    scorer = direct.MlxStatementScorer(Path(args.core).resolve(), MODEL, REVISION, enable_compile=True)
    rows: list[dict[str, Any]] = []
    for image_name, image in fixtures.items():
        for repeat in range(args.warmups + args.repeats):
            warmup = repeat < args.warmups
            arms = (False, True) if repeat % 2 == 0 else (True, False)
            for compiled in arms:
                result = scorer.score(image, direct.QUESTIONS, compiled=compiled)
                row = {
                    "arm": "compiled" if compiled else "eager",
                    "image": image_name,
                    "warmup": warmup,
                    "repeat": repeat,
                    **result,
                }
                rows.append(row)
                print(f"{row['arm']} {image_name} {repeat + 1}/{args.warmups + args.repeats}: {row['wall_ms']:.1f} ms", flush=True)

    measured = [row for row in rows if not row["warmup"]]
    aggregate: dict[str, Any] = {}
    for arm in ("eager", "compiled"):
        selected = [row for row in measured if row["arm"] == arm]
        aggregate[arm] = {
            "wall_ms": summary([float(row["wall_ms"]) for row in selected]),
            "prefix_ms": summary([float(row["timing_ms"]["prefix"]) for row in selected]),
            "suffix_ms": summary([float(row["timing_ms"]["suffix"]) for row in selected]),
            "cache_copy_ms": summary([float(row["timing_ms"]["cache_copy"]) for row in selected]),
            "peak_memory_gb": max(float(row["peak_memory_gb"] or 0) for row in selected),
        }
    eager_p50 = float(aggregate["eager"]["wall_ms"]["p50"])
    compiled_p50 = float(aggregate["compiled"]["wall_ms"]["p50"])
    aggregate["compiled"]["speedup_vs_eager"] = round(eager_p50 / compiled_p50, 4)
    aggregate["compiled"]["latency_reduction_percent"] = round((1 - compiled_p50 / eager_p50) * 100, 1)

    keyed = {(row["image"], row["repeat"], row["arm"]): row for row in measured}
    decisions_equal = True
    max_probability_delta = 0.0
    max_z_delta = 0.0
    for image_name in fixtures:
        for repeat in range(args.warmups, args.warmups + args.repeats):
            eager = keyed[(image_name, repeat, "eager")]
            compiled = keyed[(image_name, repeat, "compiled")]
            for qid in direct.QUESTIONS:
                left, right = eager["answers"][qid], compiled["answers"][qid]
                decisions_equal = decisions_equal and direct.decision(left) == direct.decision(right)
                left_values, right_values = direct.answer_vector(left), direct.answer_vector(right)
                max_probability_delta = max(
                    max_probability_delta,
                    *(abs(left_values.get(label, 0.0) - right_values.get(label, 0.0)) for label in set(left_values) | set(right_values)),
                )
                max_z_delta = max(
                    max_z_delta,
                    *(abs(float(a) - float(b)) for a, b in zip(eager["z"][qid], compiled["z"][qid])),
                )
    guardrail = {
        "decisions_equal": decisions_equal,
        "max_probability_delta": round(max_probability_delta, 8),
        "max_z_delta": round(max_z_delta, 8),
        "passed": decisions_equal and max_probability_delta <= 0.001 and max_z_delta <= 0.01,
    }
    first_compile_by_image = {
        image: next(row["wall_ms"] for row in rows if row["image"] == image and row["arm"] == "compiled")
        for image in fixtures
    }
    p95_ok = float(aggregate["compiled"]["wall_ms"]["p95"]) <= float(aggregate["eager"]["wall_ms"]["p95"]) * 1.05
    output = {
        "schema_version": 1,
        "experiment": "E018",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 10-core GPU, 32 GB unified memory",
            "platform": platform.platform(),
            "mlx_model": f"{MODEL}@{REVISION}",
            "mlx_load_ms": round(scorer.load_ms, 3),
        },
        "protocol": {"warmups": args.warmups, "repeats_per_image": args.repeats, "images": list(fixtures), "statements": 9},
        "first_compile_wall_ms_by_image": first_compile_by_image,
        "aggregate": aggregate,
        "guardrail": guardrail,
        "p95_gate_passed": p95_ok,
        "keep_compilation": guardrail["passed"] and p95_ok and compiled_p50 <= eager_p50 * 0.95,
        "rows": rows,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in ("first_compile_wall_ms_by_image", "aggregate", "guardrail", "p95_gate_passed", "keep_compilation")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
