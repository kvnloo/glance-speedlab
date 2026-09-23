#!/usr/bin/env python3
"""Loopback-only HTTP adapter for the validated MLX direct scorer.

The benchmark remains the executable specification for the scoring algorithm.
This adapter imports that exact implementation so the live demo cannot silently
diverge from the measured E016/E017 path.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Load the project's simple KEY=VALUE file without adding a dependency."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_local_env()
CORE = Path(os.environ.get("GLANCE_CORE", "../glance")).resolve()
HOST = os.environ.get("SPEEDLAB_MLX_HOST", "127.0.0.1")
PORT = int(os.environ.get("SPEEDLAB_MLX_PORT", "8079"))
MODEL = os.environ.get("SPEEDLAB_MLX_MODEL", "mlx-community/Qwen3-VL-2B-Instruct-8bit")
REVISION = os.environ.get("SPEEDLAB_MLX_REVISION", "b0338e0e843d8e1befe873d144b81fefdc47efa6")
MAX_BODY_BYTES = 5_000_000


def load_benchmark_module():
    path = ROOT / "scripts" / "run-mlx-direct-experiment.py"
    spec = importlib.util.spec_from_file_location("speedlab_mlx_direct", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scorer from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


print(f"Loading {MODEL}@{REVISION}…", flush=True)
benchmark = load_benchmark_module()
scorer = benchmark.MlxStatementScorer(CORE, MODEL, REVISION)
print(f"MLX scorer loaded in {scorer.load_ms:.0f} ms", flush=True)


def score_request(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("state")
    images = state.get("images") if isinstance(state, dict) else None
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
        raise ValueError("Exactly one image is required.")
    encoded = images[0].get("base64")
    if not isinstance(encoded, str):
        raise ValueError("The image must be plain base64.")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(image_bytes)) as opened:
            opened.load()
            image = opened.convert("RGB")
    except Exception as error:
        raise ValueError("The image payload is not a supported image.") from error

    questions = payload.get("questions")
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 16:
        raise ValueError("questions must contain 1–16 items.")
    options = payload.get("options") or {}
    if options.get("choice_method", "independent") != "independent":
        raise ValueError("The MLX candidate supports independent choice scoring only.")

    result = scorer.score(image, questions)
    answers = result["answers"]
    for answer in answers.values():
        if answer.get("type") == "choice":
            answer["confidence"] = answer["probabilities"][answer["choice"]]
    timings = result["timing_ms"]
    score_ms = timings["cache_copy"] + timings["suffix"] + timings["head"]
    return {
        "request_id": str(uuid.uuid4()),
        "model": "mlx-8bit-direct",
        "answers": answers,
        "timing_ms": {
            "prepare": timings["prepare"],
            "prefix": timings["prefix"],
            "score": round(score_ms, 3),
            "total": result["wall_ms"],
        },
        "diagnostics": {
            "shared_prefix_tokens": result["shared_prefix_tokens"],
            "image_tokens": result["image_tokens"],
            "suffix_widths": result["suffix_widths"],
            "peak_memory_gb": result["peak_memory_gb"],
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GlanceSpeedlabMLX/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self.send_json(404, {"error": "Not found."})
            return
        self.send_json(
            200,
            {
                "online": True,
                "backend": "mlx-8bit-direct",
                "model": MODEL,
                "revision": REVISION,
                "load_ms": round(scorer.load_ms, 3),
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/decide":
            self.send_json(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            if length < 2 or length > MAX_BODY_BYTES:
                raise ValueError(f"Request must be between 2 and {MAX_BODY_BYTES} bytes.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be an object.")
            self.send_json(200, score_request(payload))
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception as error:  # keep the local lab alive after a failed frame
            self.send_json(500, {"error": f"MLX inference failed: {error}"})

    def log_message(self, format_string: str, *args: Any) -> None:
        if args and str(args[0]).startswith("GET /healthz "):
            return
        print(f"{self.address_string()} - {format_string % args}", flush=True)

    def send_json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"MLX direct scorer: http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
