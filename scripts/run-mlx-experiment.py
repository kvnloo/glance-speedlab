#!/usr/bin/env python3
"""Run E013 against the active Glance service and a pinned MLX-VLM model.

Install the isolated candidate environment first with the command documented in
research/experiments/013-mlx-4bit/plan.md. Raw rows remain under research/runs/.
"""

from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import platform
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

from mlx_vlm import apply_chat_template, generate, load


MODEL = "mlx-community/Qwen3-VL-2B-Instruct-4bit"
REVISION = "9c4f5209e57b31f4b9dfba735de3fb983739c9cc"
PROMPT = "Classify this image. Reply with exactly one label: animal photo, receipt, invoice, or other."
LABELS = ("animal photo", "receipt", "invoice", "other")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="http://127.0.0.1:8787")
    parser.add_argument("--core", default=str(Path.cwd().parent / "glance"))
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--raw", default="research/runs/e013-mlx.json")
    return parser.parse_args()


def request_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def classify(text: str) -> str:
    normalized = " ".join(text.lower().strip().split())
    for label in LABELS:
        if normalized == label or normalized.startswith(f"{label} "):
            return label
    return "unparsed"


def jpeg_with_comment(data: bytes, comment: str) -> bytes:
    """Change the byte hash without changing decoded pixels, simulating a new camera frame."""
    if not data.endswith(b"\xff\xd9"):
        raise ValueError("Expected a JPEG end-of-image marker")
    encoded = comment.encode("ascii")
    segment = b"\xff\xfe" + (len(encoded) + 2).to_bytes(2, "big") + encoded
    return data[:-2] + segment + data[-2:]


def summary(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    percentile = lambda q: ordered[min(len(ordered) - 1, max(0, int(len(ordered) * q + 0.999999) - 1))]
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(percentile(0.95), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
    }


def main() -> int:
    args = parse_args()
    root, core = Path.cwd(), Path(args.core).resolve()
    fixtures = {name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg" for name in ("dog", "receipt", "invoice")}
    missing = [str(path) for path in fixtures.values() if not path.exists()]
    if missing:
        raise SystemExit(f"Missing E011 fixtures: {', '.join(missing)}")

    health = request_json(f"{args.gateway.rstrip('/')}/api/health")
    raw: list[dict[str, Any]] = []
    question = {
        "id": "content",
        "type": "choice",
        "instructions": "What kind of content is shown in `img0`?",
        "criteria": list(LABELS),
    }

    for backend, cache_bust in (("glance-mps-fp16-cache-hit", False), ("glance-mps-fp16-new-frame", True)):
        for image_name, path in fixtures.items():
            source = path.read_bytes()
            for index in range(args.warmups + args.repeats):
                image = jpeg_with_comment(source, f"e013-{time.time_ns()}-{index}") if cache_bust else source
                payload = {"imageBase64": base64.b64encode(image).decode(), "questions": [question]}
                started = time.perf_counter()
                response = request_json(f"{args.gateway.rstrip('/')}/api/decide", payload)
                elapsed_ms = (time.perf_counter() - started) * 1000
                answer = response["answers"]["content"]
                row = {
                    "backend": backend,
                    "image": image_name,
                    "warmup": index < args.warmups,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "label": answer["choice"],
                    "timing_ms": response.get("timing_ms", {}),
                }
                raw.append(row)
                print(f"{backend} {image_name} {index + 1}/{args.warmups + args.repeats}: {elapsed_ms:.1f} ms", flush=True)

    load_started = time.perf_counter()
    model, processor = load(MODEL, revision=REVISION)
    load_ms = (time.perf_counter() - load_started) * 1000
    formatted_prompt = apply_chat_template(processor, model.config, PROMPT, num_images=1)

    for image_name, path in fixtures.items():
        for index in range(args.warmups + args.repeats):
            started = time.perf_counter()
            result = generate(
                model,
                processor,
                formatted_prompt,
                image=str(path),
                max_tokens=8,
                temperature=0.0,
                verbose=False,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            row = {
                "backend": "mlx-4bit",
                "image": image_name,
                "warmup": index < args.warmups,
                "elapsed_ms": round(elapsed_ms, 3),
                "label": classify(result.text),
                "text": result.text,
                "prompt_tokens": result.prompt_tokens,
                "generation_tokens": result.generation_tokens,
                "prompt_tps": round(result.prompt_tps, 3),
                "generation_tps": round(result.generation_tps, 3),
                "peak_memory_gb": round(result.peak_memory, 3),
            }
            raw.append(row)
            print(f"MLX {image_name} {index + 1}/{args.warmups + args.repeats}: {elapsed_ms:.1f} ms -> {result.text!r}", flush=True)

    measured = [row for row in raw if not row["warmup"]]
    aggregate = {}
    for backend in ("glance-mps-fp16-cache-hit", "glance-mps-fp16-new-frame", "mlx-4bit"):
        rows = [row for row in measured if row["backend"] == backend]
        aggregate[backend] = {
            "elapsed_ms": summary([float(row["elapsed_ms"]) for row in rows]),
            "labels_by_image": {
                image: sorted({str(row["label"]) for row in rows if row["image"] == image})
                for image in fixtures
            },
        }
    expected = {"dog": "animal photo", "receipt": "receipt", "invoice": "invoice"}
    guardrail = {
        backend: all(aggregate[backend]["labels_by_image"][image] == [label] for image, label in expected.items())
        for backend in aggregate
    }
    output = {
        "schema_version": 1,
        "experiment": "E013",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 32 GB unified memory",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "candidate_model": f"{MODEL}@{REVISION}",
            "candidate_quantization": "4-bit, checkpoint metadata",
            "candidate_load_ms": round(load_ms, 3),
            "glance_health": health,
            "glance_core": str(core),
        },
        "protocol": {
            "warmups_per_image": args.warmups,
            "repeats_per_image": args.repeats,
            "fixture_long_edge": 320,
            "jpeg_quality": 60,
            "known_mismatch": "Glance direct choice scoring versus MLX greedy text generation",
            "new_frame_control": "A unique JPEG COM segment changes Glance's byte-hash cache key without changing decoded pixels",
        },
        "aggregate": aggregate,
        "guardrail": guardrail,
        "rows": raw,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"aggregate": aggregate, "guardrail": guardrail, "raw": str(raw_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
