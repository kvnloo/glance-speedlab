#!/usr/bin/env python3
"""Run E012 sub-128 image-token sweep for one pinned Glance tier."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


QUESTIONS: dict[str, dict[str, Any]] = {
    "content": {"type": "choice", "instructions": "What kind of content is shown in `img0`?", "criteria": {"animal photo": None, "receipt": None, "invoice": None, "other": None}},
    "text": {"type": "noul", "instructions": "Is readable text visible in `img0`?"},
    "photo": {"type": "noul", "instructions": "Is `img0` primarily a natural photograph?"},
    "tone": {"type": "choice", "instructions": "What is the overall visual tone of `img0`?", "criteria": {"mostly light": None, "mostly dark": None, "mixed": None}},
}
BUDGETS = (32, 48, 64, 96, 128)


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", required=True, choices=["apple_8gb", "apple_32gb"])
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", str(Path.cwd().parent / "glance")))
    parser.add_argument("--repeats", type=int, default=7)
    return parser.parse_args()


def stats(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {"n": len(values), "p50": round(statistics.median(values), 3), "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95 + .999999) - 1)], 3), "mean": round(statistics.mean(values), 3)}


def vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1 - value}
    return {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}


def decision(answer: dict[str, Any]) -> str:
    return ("yes" if float(answer["noul"]) >= .5 else "no") if answer["type"] == "noul" else str(answer["choice"])


def main() -> int:
    parsed = cli()
    root, core = Path.cwd(), Path(parsed.core).resolve()
    sys.path.insert(0, str(core))
    os.environ.setdefault("GLANCE_ROOT", str(core))
    from glance.config import load_config  # pylint: disable=import-error,import-outside-toplevel
    from glance.pipeline import Engine  # pylint: disable=import-error,import-outside-toplevel

    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in ("dog", "receipt", "invoice")}
    cfg = load_config(overrides={"models": {"tier_override": parsed.tier, "image_token_budget_override": 128}, "vlm": {"prefix_cache": True}, "paths": {"logs": str(root / "research/runs/core-sub128-calls")}})
    engine = Engine(cfg, source="speedlab-sub128")
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
    for image_index, (image, path) in enumerate(fixtures.items()):
        for repeat in range(parsed.repeats):
            shift = (repeat + image_index) % len(BUDGETS)
            for budget in BUDGETS[shift:] + BUDGETS[:shift]:
                backend.image_token_budget = budget
                try:
                    rows.append({"image": image, "repeat": repeat, "budget": budget, **run(path)})
                except Exception as error:  # arm failures are outcomes; continue the preregistered sweep
                    rows.append({"image": image, "repeat": repeat, "budget": budget, "error": f"{type(error).__name__}: {error}"})
    environment = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "glance_commit": subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip(), "tier": parsed.tier, "model": f"{backend.model_id}@{backend.revision}", "device": backend.device, "dtype": backend.dtype}
    raw = {"environment": environment, "rows": rows}
    (root / "research/runs" / f"e012-{parsed.tier}.json").write_text(json.dumps(raw, indent=2) + "\n")
    summary = summarize(rows)
    (root / "research/results" / f"e012-{parsed.tier}.json").write_text(json.dumps({"environment": environment, "summary": {"E012": summary}}, indent=2) + "\n")
    write_combined_report(root)
    print(json.dumps(summary, indent=2))
    return 0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    paired: dict[tuple[str, int], dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[row["budget"]].append(row)
        paired[(row["image"], row["repeat"])][row["budget"]] = row
    result: dict[str, Any] = {}
    for budget in BUDGETS:
        all_items = grouped[budget]
        items = [row for row in all_items if "error" not in row]
        failed = [row for row in all_items if "error" in row]
        result[str(budget)] = {"attempted": len(all_items), "failures": len(failed), "first_error": failed[0]["error"] if failed else None}
        if items:
            result[str(budget)].update({
            "wall_ms": stats([float(row["wall_ms"]) for row in items]),
            "prefix_ms": stats([float(row["timing_ms"]["prefix"]) for row in items]),
            "score_ms": stats([float(row["timing_ms"]["score"]) for row in items]),
            "image_tokens": stats([float(row["usage"]["image_tokens"]) for row in items]),
            })
    for budget in BUDGETS[:-1]:
        usable = {key: pair for key, pair in paired.items() if "error" not in pair.get(budget, {}) and "error" not in pair.get(128, {})}
        if not usable:
            result[f"guardrail_{budget}_vs_128"] = {"passed": False, "unavailable": "No successful paired requests."}
            result[f"speedup_{budget}_vs_128"] = None
            continue
        requests_equal = questions_equal = questions_total = 0
        max_delta = 0.0
        by_image: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for (image, _), pair in usable.items():
            all_equal = True
            for qid, answer in pair[budget]["answers"].items():
                reference = pair[128]["answers"][qid]
                equal = decision(answer) == decision(reference)
                all_equal = all_equal and equal
                questions_equal += int(equal)
                questions_total += 1
                by_image[image][0] += int(equal)
                by_image[image][1] += 1
                lv, rv = vector(answer), vector(reference)
                max_delta = max(max_delta, *(abs(lv.get(label, 0) - rv.get(label, 0)) for label in set(lv) | set(rv)))
            requests_equal += int(all_equal)
        result[f"guardrail_{budget}_vs_128"] = {"request_decision_agreement": round(requests_equal / len(usable), 6), "question_decision_agreement": round(questions_equal / questions_total, 6), "question_agreement_by_image": {image: round(v[0] / v[1], 6) for image, v in by_image.items()}, "max_probability_delta": round(max_delta, 8), "passed": requests_equal == len(usable) and max_delta <= .10}
        result[f"speedup_{budget}_vs_128"] = round(result["128"]["wall_ms"]["p50"] / result[str(budget)]["wall_ms"]["p50"], 4)
    return result


def write_combined_report(root: Path) -> None:
    results = {}
    for tier in ("apple_8gb", "apple_32gb"):
        path = root / "research/results" / f"e012-{tier}.json"
        if path.is_file():
            results[tier] = json.loads(path.read_text())["summary"]["E012"]
    report = ["# E012 result — Sub-128 image-token budget", "", "Generated by `scripts/run-sub128-experiment.py`. Detailed paired rows remain ignored in `research/runs/`.", "", "```json", json.dumps(results, indent=2), "```", ""]
    (root / "research/experiments/012-sub128-token-budget/result.md").write_text("\n".join(report))


if __name__ == "__main__":
    raise SystemExit(main())
