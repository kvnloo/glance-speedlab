#!/usr/bin/env python3
"""Run one E011 model tier, then summarize when both tier files exist."""

from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


QUESTIONS: dict[str, dict[str, Any]] = {
    "content": {"type": "choice", "instructions": "What kind of content is shown in `img0`?", "criteria": {"animal photo": None, "receipt": None, "invoice": None, "other": None}},
    "text": {"type": "noul", "instructions": "Is readable text visible in `img0`?"},
    "photo": {"type": "noul", "instructions": "Is `img0` primarily a natural photograph?"},
    "tone": {"type": "choice", "instructions": "What is the overall visual tone of `img0`?", "criteria": {"mostly light": None, "mostly dark": None, "mixed": None}},
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", required=True, choices=["apple_8gb", "apple_32gb"])
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", str(Path.cwd().parent / "glance")))
    parser.add_argument("--repeats", type=int, default=7)
    return parser.parse_args()


def stats(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {"n": len(values), "p50": round(statistics.median(values), 3), "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95 + 0.999999) - 1)], 3), "mean": round(statistics.mean(values), 3)}


def vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1.0 - value}
    return {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}


def decision(answer: dict[str, Any]) -> str:
    return ("yes" if float(answer["noul"]) >= 0.5 else "no") if answer["type"] == "noul" else str(answer["choice"])


def main() -> int:
    parsed = args()
    root, core = Path.cwd(), Path(parsed.core).resolve()
    sys.path.insert(0, str(core))
    os.environ.setdefault("GLANCE_ROOT", str(core))
    from glance.config import load_config  # pylint: disable=import-error,import-outside-toplevel
    from glance.pipeline import Engine  # pylint: disable=import-error,import-outside-toplevel

    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in ("dog", "receipt", "invoice")}
    if not all(path.is_file() for path in fixtures.values()):
        raise SystemExit("Run scripts/run-next-model-experiments.py first to create controlled fixtures.")
    log_dir = root / "research/runs/core-tier-calls"
    log_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(overrides={
        "models": {"tier_override": parsed.tier, "image_token_budget_override": 384},
        "vlm": {"prefix_cache": True},
        "paths": {"logs": str(log_dir)},
    })
    engine = Engine(cfg, source="speedlab-tier")
    backend = engine.backend("vlm")

    def run(path: Path) -> dict[str, Any]:
        backend._prefix_cache.clear()
        started = time.perf_counter()
        trace = engine.decide({"model": "vlm", "state": {"images": [{"id": "img0", "path": str(path)}]}, "questions": QUESTIONS, "options": {"choice_method": "independent", "calibrated": False}})
        payload = trace.response.model_dump()
        return {"wall_ms": round((time.perf_counter() - started) * 1000, 3), "timing_ms": payload["timing_ms"], "answers": payload["answers"], "usage": payload["usage"]}

    for _ in range(2):
        run(fixtures["dog"])
    rows = []
    for image, path in fixtures.items():
        for repeat in range(parsed.repeats):
            rows.append({"image": image, "repeat": repeat, **run(path)})
    payload = {
        "environment": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "glance_commit": subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip(),
            "tier": parsed.tier,
            "model": f"{backend.model_id}@{backend.revision}",
            "image_token_budget": backend.image_token_budget,
            "device": backend.device,
            "dtype": backend.dtype,
        },
        "rows": rows,
    }
    path = root / "research/runs" / f"e011-{parsed.tier}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(summarize_one(payload), indent=2))
    del engine, backend
    gc.collect()
    summarize_pair(root)
    return 0


def summarize_one(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload["rows"]
    return {
        "model": payload["environment"]["model"],
        "wall_ms": stats([float(row["wall_ms"]) for row in rows]),
        "model_total_ms": stats([float(row["timing_ms"]["total"]) for row in rows]),
        "prefix_ms": stats([float(row["timing_ms"].get("prefix", 0)) for row in rows]),
        "score_ms": stats([float(row["timing_ms"].get("score", 0)) for row in rows]),
        "image_tokens": stats([float(row["usage"]["image_tokens"]) for row in rows]),
    }


def summarize_pair(root: Path) -> None:
    paths = {tier: root / "research/runs" / f"e011-{tier}.json" for tier in ("apple_8gb", "apple_32gb")}
    if not all(path.is_file() for path in paths.values()):
        return
    payloads = {tier: json.loads(path.read_text()) for tier, path in paths.items()}
    summaries = {tier: summarize_one(payload) for tier, payload in payloads.items()}
    left = {(row["image"], row["repeat"]): row for row in payloads["apple_8gb"]["rows"]}
    right = {(row["image"], row["repeat"]): row for row in payloads["apple_32gb"]["rows"]}
    same, deltas, question_same, question_total = 0, [], 0, 0
    by_image: dict[str, dict[str, int]] = {}
    for key in left:
        row_same, row_delta = True, 0.0
        image_counts = by_image.setdefault(key[0], {"same": 0, "total": 0})
        for qid, answer in left[key]["answers"].items():
            reference = right[key]["answers"][qid]
            equal = decision(answer) == decision(reference)
            row_same = row_same and equal
            question_same += int(equal)
            question_total += 1
            image_counts["same"] += int(equal)
            image_counts["total"] += 1
            lv, rv = vector(answer), vector(reference)
            row_delta = max(row_delta, *(abs(lv.get(label, 0) - rv.get(label, 0)) for label in set(lv) | set(rv)))
        same += row_same
        deltas.append(row_delta)
    result = {
        **summaries,
        "speedup_2b_vs_4b": round(summaries["apple_32gb"]["wall_ms"]["p50"] / summaries["apple_8gb"]["wall_ms"]["p50"], 4),
        "guardrail": {
            "request_decision_agreement": round(same / len(left), 6),
            "question_decision_agreement": round(question_same / question_total, 6),
            "question_agreement_by_image": {image: round(counts["same"] / counts["total"], 6) for image, counts in by_image.items()},
            "max_probability_delta": round(max(deltas), 8),
            "passed": same == len(left) and max(deltas) <= 0.10,
        },
    }
    output = {"environment": {tier: payload["environment"] for tier, payload in payloads.items()}, "summary": {"E011": result}}
    (root / "research/results/e011-model-tier.json").write_text(json.dumps(output, indent=2) + "\n")
    report = ["# E011 result — Qwen3-VL-2B fast tier", "", "Generated by `scripts/run-model-tier-experiment.py`. Detailed paired rows remain ignored in `research/runs/`.", "", "```json", json.dumps(result, indent=2), "```", ""]
    (root / "research/experiments/011-2b-fast-tier/result.md").write_text("\n".join(report))


if __name__ == "__main__":
    raise SystemExit(main())
