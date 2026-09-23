#!/usr/bin/env python3
"""Run E014: exact-image MLX vision and prompt cache comparison."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import statistics
import time
from pathlib import Path
from typing import Any

from mlx_vlm import VisionFeatureCache, apc, apply_chat_template, generate, load
from mlx_vlm.generate import PromptCacheState


MODEL = "mlx-community/Qwen3-VL-2B-Instruct-4bit"
REVISION = "9c4f5209e57b31f4b9dfba735de3fb983739c9cc"
PROMPT = "Classify this image. Reply with exactly one label: animal photo, receipt, invoice, or other."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--raw", default="research/runs/e014-mlx-cache.json")
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


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    image = root / "research/runs/fixtures/dog-320-q60.jpg"
    if not image.exists():
        raise SystemExit(f"Missing E011 fixture: {image}")

    started = time.perf_counter()
    model, processor = load(MODEL, revision=REVISION)
    load_ms = (time.perf_counter() - started) * 1000
    prompt = apply_chat_template(processor, model.config, PROMPT, num_images=1)
    rows: list[dict[str, Any]] = []

    apc_manager = apc.from_env(
        model_namespace="e014",
        overrides={"enabled": True, "disk_enabled": False, "num_blocks": 256, "checkpoint_entries": 2},
    )
    apc_small_blocks = apc.from_env(
        model_namespace="e014-block4",
        overrides={"enabled": True, "disk_enabled": False, "block_size": 4, "num_blocks": 512, "checkpoint_entries": 2},
    )
    arms = (
        ("none", None, None, None),
        ("vision", VisionFeatureCache(max_size=2), None, None),
        ("vision_prompt", VisionFeatureCache(max_size=2), PromptCacheState(), None),
        ("apc_block16", None, None, apc_manager),
        ("apc_block4", None, None, apc_small_blocks),
    )
    for arm, vision_cache, prompt_cache_state, arm_apc_manager in arms:
        for index in range(args.warmups + args.repeats):
            call_started = time.perf_counter()
            result = generate(
                model,
                processor,
                prompt,
                image=str(image),
                max_tokens=8,
                temperature=0.0,
                verbose=False,
                vision_cache=vision_cache,
                prompt_cache_state=prompt_cache_state,
                apc_manager=arm_apc_manager,
                apc_tenant="e014" if arm_apc_manager is not None else None,
            )
            elapsed_ms = (time.perf_counter() - call_started) * 1000
            row = {
                "arm": arm,
                "warmup": index < args.warmups,
                "elapsed_ms": round(elapsed_ms, 3),
                "text": result.text,
                "label": normalize(result.text),
                "prompt_tokens": result.prompt_tokens,
                "cached_tokens": result.cached_tokens,
                "prompt_tps": round(result.prompt_tps, 3),
                "generation_tps": round(result.generation_tps, 3),
                "peak_memory_gb": round(result.peak_memory, 3),
                "vision_cache_entries": len(vision_cache) if vision_cache is not None else 0,
            }
            rows.append(row)
            print(
                f"{arm} {index + 1}/{args.warmups + args.repeats}: "
                f"{elapsed_ms:.1f} ms, cached_tokens={result.cached_tokens}, text={result.text!r}",
                flush=True,
            )

    measured = [row for row in rows if not row["warmup"]]
    summary = {}
    for arm, _, _, _ in arms:
        selected = [row for row in measured if row["arm"] == arm]
        summary[arm] = {
            "elapsed_ms": summarize([float(row["elapsed_ms"]) for row in selected]),
            "cached_tokens": sorted({int(row["cached_tokens"]) for row in selected}),
            "labels": sorted({str(row["label"]) for row in selected}),
            "vision_cache_entries": sorted({int(row["vision_cache_entries"]) for row in selected}),
        }
    baseline = float(summary["none"]["elapsed_ms"]["p50"])
    for arm in ("vision", "vision_prompt", "apc_block16", "apc_block4"):
        candidate = float(summary[arm]["elapsed_ms"]["p50"])
        summary[arm]["speedup_vs_none"] = round(baseline / candidate, 4)
        summary[arm]["latency_reduction_percent"] = round((1 - candidate / baseline) * 100, 1)

    continuation_rows: list[dict[str, Any]] = []
    for index in range(args.warmups + args.repeats):
        state = PromptCacheState()
        first_messages = [{
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": PROMPT}],
        }]
        first_prompt = apply_chat_template(processor, model.config, first_messages, num_images=1)
        first_result = generate(
            model,
            processor,
            first_prompt,
            image=str(image),
            max_tokens=8,
            temperature=0.0,
            verbose=False,
            prompt_cache_state=state,
        )
        messages = [
            *first_messages,
            {"role": "assistant", "content": first_result.text},
            {"role": "user", "content": "Reply with exactly yes or no: is this an animal photo?"},
        ]
        continued_prompt = apply_chat_template(processor, model.config, messages, num_images=1)

        def run_continuation(arm: str, cache_state: PromptCacheState | None) -> None:
            turn_started = time.perf_counter()
            result = generate(
                model,
                processor,
                continued_prompt,
                image=str(image),
                max_tokens=4,
                temperature=0.0,
                verbose=False,
                prompt_cache_state=cache_state,
            )
            elapsed_ms = (time.perf_counter() - turn_started) * 1000
            continuation_rows.append({
                "arm": arm,
                "warmup": index < args.warmups,
                "elapsed_ms": round(elapsed_ms, 3),
                "text": result.text,
                "label": normalize(result.text),
                "prompt_tokens": result.prompt_tokens,
                "cached_tokens": result.cached_tokens,
                "prompt_tps": round(result.prompt_tps, 3),
                "generation_tps": round(result.generation_tps, 3),
                "peak_memory_gb": round(result.peak_memory, 3),
            })
            print(
                f"continued-{arm} {index + 1}/{args.warmups + args.repeats}: "
                f"{elapsed_ms:.1f} ms, cached_tokens={result.cached_tokens}, text={result.text!r}",
                flush=True,
            )

        if index % 2 == 0:
            run_continuation("cold", None)
            run_continuation("prompt_cache", state)
        else:
            run_continuation("prompt_cache", state)
            run_continuation("cold", None)

    measured_continuations = [row for row in continuation_rows if not row["warmup"]]
    continuation_summary = {}
    for arm in ("cold", "prompt_cache"):
        selected = [row for row in measured_continuations if row["arm"] == arm]
        continuation_summary[arm] = {
            "elapsed_ms": summarize([float(row["elapsed_ms"]) for row in selected]),
            "cached_tokens": sorted({int(row["cached_tokens"]) for row in selected}),
            "labels": sorted({str(row["label"]) for row in selected}),
        }
    cold_p50 = float(continuation_summary["cold"]["elapsed_ms"]["p50"])
    cached_p50 = float(continuation_summary["prompt_cache"]["elapsed_ms"]["p50"])
    continuation_summary["prompt_cache"]["speedup_vs_cold"] = round(cold_p50 / cached_p50, 4)
    continuation_summary["prompt_cache"]["latency_reduction_percent"] = round((1 - cached_p50 / cold_p50) * 100, 1)

    output = {
        "schema_version": 1,
        "experiment": "E014",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 32 GB unified memory",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "model": f"{MODEL}@{REVISION}",
            "load_ms": round(load_ms, 3),
        },
        "protocol": {
            "image": "dog-320-q60.jpg",
            "warmups": args.warmups,
            "repeats": args.repeats,
            "exact_image_and_prompt_repeated": True,
        },
        "summary": summary,
        "continued_chat_summary": continuation_summary,
        "guardrail_passed": (
            all(row["label"] == "animal photo" for row in measured)
            and all(row["label"] == "yes" for row in measured_continuations)
        ),
        "apc_stats": {
            "block16": apc_manager.stats_snapshot() if apc_manager is not None else None,
            "block4": apc_small_blocks.stats_snapshot() if apc_small_blocks is not None else None,
        },
        "rows": rows,
        "continued_chat_rows": continuation_rows,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"summary": summary, "continued_chat_summary": continuation_summary, "guardrail_passed": output["guardrail_passed"], "raw": str(raw_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
