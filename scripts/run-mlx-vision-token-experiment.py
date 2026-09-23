#!/usr/bin/env python3
"""Run E019: MLX default versus constrained vision-token pixel budgets."""

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
ARMS = ("default", "64", "48")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default="../glance")
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--raw", default="research/runs/e019-mlx-vision-tokens.json")
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
    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in ("dog", "receipt", "invoice")}
    scorer = direct.MlxStatementScorer(Path(args.core).resolve(), MODEL, REVISION)
    image_processor = scorer.processor.image_processor
    default_max_pixels = int(image_processor.max_pixels)
    pixels_per_token = int(image_processor.patch_size) ** 2 * int(image_processor.merge_size) ** 2
    max_pixels = {"default": default_max_pixels, "64": 64 * pixels_per_token, "48": 48 * pixels_per_token}

    rows: list[dict[str, Any]] = []
    for image_name, image in fixtures.items():
        for repeat in range(args.warmups + args.repeats):
            warmup = repeat < args.warmups
            order = ARMS[repeat % len(ARMS):] + ARMS[:repeat % len(ARMS)]
            for arm in order:
                image_processor.max_pixels = max_pixels[arm]
                result = scorer.score(image, direct.QUESTIONS)
                row = {
                    "arm": arm,
                    "nominal_token_cap": None if arm == "default" else int(arm),
                    "max_pixels": max_pixels[arm],
                    "image": image_name,
                    "warmup": warmup,
                    "repeat": repeat,
                    **result,
                }
                rows.append(row)
                print(f"{arm} {image_name} {repeat + 1}/{args.warmups + args.repeats}: {row['wall_ms']:.1f} ms, {row['image_tokens']} image tokens", flush=True)
    image_processor.max_pixels = default_max_pixels

    measured = [row for row in rows if not row["warmup"]]
    aggregate: dict[str, Any] = {}
    for arm in ARMS:
        selected = [row for row in measured if row["arm"] == arm]
        aggregate[arm] = {
            "wall_ms": summary([float(row["wall_ms"]) for row in selected]),
            "prefix_ms": summary([float(row["timing_ms"]["prefix"]) for row in selected]),
            "suffix_ms": summary([float(row["timing_ms"]["suffix"]) for row in selected]),
            "peak_memory_gb": max(float(row["peak_memory_gb"] or 0) for row in selected),
            "realized_image_tokens_by_image": {
                image: sorted({int(row["image_tokens"]) for row in selected if row["image"] == image})
                for image in fixtures
            },
        }
    default_p50 = float(aggregate["default"]["wall_ms"]["p50"])
    default_p95 = float(aggregate["default"]["wall_ms"]["p95"])

    keyed = {(row["image"], row["repeat"], row["arm"]): row for row in measured}
    guardrails: dict[str, Any] = {}
    for arm in ("64", "48"):
        decisions_equal = True
        max_probability_delta = 0.0
        max_z_delta = 0.0
        for image_name in fixtures:
            for repeat in range(args.warmups, args.warmups + args.repeats):
                reference = keyed[(image_name, repeat, "default")]
                candidate = keyed[(image_name, repeat, arm)]
                for qid in direct.QUESTIONS:
                    left, right = reference["answers"][qid], candidate["answers"][qid]
                    decisions_equal = decisions_equal and direct.decision(left) == direct.decision(right)
                    left_values, right_values = direct.answer_vector(left), direct.answer_vector(right)
                    max_probability_delta = max(
                        max_probability_delta,
                        *(abs(left_values.get(label, 0.0) - right_values.get(label, 0.0)) for label in set(left_values) | set(right_values)),
                    )
                    max_z_delta = max(
                        max_z_delta,
                        *(abs(float(a) - float(b)) for a, b in zip(reference["z"][qid], candidate["z"][qid])),
                    )
        candidate_p50 = float(aggregate[arm]["wall_ms"]["p50"])
        candidate_p95 = float(aggregate[arm]["wall_ms"]["p95"])
        speedup = default_p50 / candidate_p50
        aggregate[arm]["speedup_vs_default"] = round(speedup, 4)
        aggregate[arm]["latency_reduction_percent"] = round((1 - candidate_p50 / default_p50) * 100, 1)
        guardrails[arm] = {
            "decisions_equal": decisions_equal,
            "max_probability_delta": round(max_probability_delta, 8),
            "max_z_delta": round(max_z_delta, 8),
            "quality_passed": decisions_equal and max_probability_delta <= 0.10,
            "p95_passed": candidate_p95 <= default_p95 * 1.05,
            "advances": decisions_equal and max_probability_delta <= 0.10 and candidate_p95 <= default_p95 * 1.05 and speedup >= 1.05,
        }

    output = {
        "schema_version": 1,
        "experiment": "E019",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 10-core GPU, 32 GB unified memory",
            "platform": platform.platform(),
            "mlx_model": f"{MODEL}@{REVISION}",
            "mlx_load_ms": round(scorer.load_ms, 3),
        },
        "processor": {
            "patch_size": int(image_processor.patch_size),
            "merge_size": int(image_processor.merge_size),
            "min_pixels": int(image_processor.min_pixels),
            "max_pixels_by_arm": max_pixels,
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
