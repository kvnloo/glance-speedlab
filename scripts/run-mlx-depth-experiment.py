#!/usr/bin/env python3
"""Run E020: full versus truncated MLX language-model depth."""

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
DEFAULT_DEPTHS = (28, 24, 20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default="../glance")
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--depths", nargs="+", type=int, default=list(DEFAULT_DEPTHS))
    parser.add_argument("--experiment", default="E020")
    parser.add_argument("--raw", default="research/runs/e020-mlx-depth.json")
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
        "n": len(values), "min": round(min(values), 3), "p50": round(statistics.median(values), 3),
        "p95": round(p95, 3), "max": round(max(values), 3), "mean": round(statistics.mean(values), 3),
    }


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    direct = load_direct_module(root)
    depths = tuple(args.depths)
    if not depths or depths[0] != 28 or any(depth < 1 or depth > 28 for depth in depths) or len(set(depths)) != len(depths):
        raise SystemExit("--depths must be unique values from 1–28 with 28 first")
    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in ("dog", "receipt", "invoice")}
    scorer = direct.MlxStatementScorer(Path(args.core).resolve(), MODEL, REVISION)
    language = scorer.model.language_model.model
    full_layers = list(language.layers)
    if len(full_layers) != 28:
        raise RuntimeError(f"Expected 28 decoder layers, found {len(full_layers)}")

    rows: list[dict[str, Any]] = []
    for image_name, image in fixtures.items():
        for repeat in range(args.warmups + args.repeats):
            warmup = repeat < args.warmups
            rotation = repeat % len(depths)
            order = depths[rotation:] + depths[:rotation]
            for depth in order:
                language.layers = full_layers[:depth]
                result = scorer.score(image, direct.QUESTIONS)
                row = {"depth": depth, "image": image_name, "warmup": warmup, "repeat": repeat, **result}
                rows.append(row)
                print(f"{depth} layers {image_name} {repeat + 1}/{args.warmups + args.repeats}: {row['wall_ms']:.1f} ms", flush=True)
    language.layers = full_layers

    measured = [row for row in rows if not row["warmup"]]
    aggregate: dict[str, Any] = {}
    for depth in depths:
        selected = [row for row in measured if row["depth"] == depth]
        aggregate[str(depth)] = {
            "wall_ms": summary([float(row["wall_ms"]) for row in selected]),
            "prefix_ms": summary([float(row["timing_ms"]["prefix"]) for row in selected]),
            "suffix_ms": summary([float(row["timing_ms"]["suffix"]) for row in selected]),
            "peak_memory_gb": max(float(row["peak_memory_gb"] or 0) for row in selected),
        }
    reference_p50 = float(aggregate["28"]["wall_ms"]["p50"])
    reference_p95 = float(aggregate["28"]["wall_ms"]["p95"])
    keyed = {(row["image"], row["repeat"], row["depth"]): row for row in measured}
    guardrails: dict[str, Any] = {}
    for depth in depths[1:]:
        decisions_equal = True
        max_probability_delta = 0.0
        max_z_delta = 0.0
        changed: set[str] = set()
        for image_name in fixtures:
            for repeat in range(args.warmups, args.warmups + args.repeats):
                reference = keyed[(image_name, repeat, 28)]
                candidate = keyed[(image_name, repeat, depth)]
                for qid in direct.QUESTIONS:
                    left, right = reference["answers"][qid], candidate["answers"][qid]
                    equal = direct.decision(left) == direct.decision(right)
                    decisions_equal = decisions_equal and equal
                    if not equal:
                        changed.add(f"{image_name}:{qid}")
                    left_values, right_values = direct.answer_vector(left), direct.answer_vector(right)
                    max_probability_delta = max(
                        max_probability_delta,
                        *(abs(left_values.get(label, 0.0) - right_values.get(label, 0.0)) for label in set(left_values) | set(right_values)),
                    )
                    max_z_delta = max(
                        max_z_delta,
                        *(abs(float(a) - float(b)) for a, b in zip(reference["z"][qid], candidate["z"][qid])),
                    )
        candidate_p50 = float(aggregate[str(depth)]["wall_ms"]["p50"])
        candidate_p95 = float(aggregate[str(depth)]["wall_ms"]["p95"])
        speedup = reference_p50 / candidate_p50
        aggregate[str(depth)]["speedup_vs_28"] = round(speedup, 4)
        aggregate[str(depth)]["latency_reduction_percent"] = round((1 - candidate_p50 / reference_p50) * 100, 1)
        quality = decisions_equal and max_probability_delta <= 0.10
        p95_ok = candidate_p95 <= reference_p95 * 1.05
        guardrails[str(depth)] = {
            "decisions_equal": decisions_equal,
            "changed_decisions": sorted(changed),
            "max_probability_delta": round(max_probability_delta, 8),
            "max_z_delta": round(max_z_delta, 8),
            "quality_passed": quality,
            "p95_passed": p95_ok,
            "advances": quality and p95_ok and speedup >= 1.05,
        }

    output = {
        "schema_version": 1,
        "experiment": args.experiment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 10-core GPU, 32 GB unified memory",
            "platform": platform.platform(),
            "mlx_model": f"{MODEL}@{REVISION}",
            "mlx_load_ms": round(scorer.load_ms, 3),
        },
        "protocol": {"warmups": args.warmups, "repeats_per_image": args.repeats, "statements": 9},
        "aggregate": aggregate,
        "guardrails": guardrails,
        "rows": rows,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"aggregate": aggregate, "guardrails": guardrails}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
