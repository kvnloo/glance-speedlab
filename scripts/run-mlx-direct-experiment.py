#!/usr/bin/env python3
"""Benchmark Glance-compatible direct statement scoring on MLX Qwen3-VL."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import platform
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import mlx.core as mx
import numpy as np
from mlx_vlm import load
from mlx_vlm.models import cache as mlx_cache
from mlx_vlm.utils import prepare_inputs, should_add_special_tokens


DEFAULT_MODEL = "mlx-community/Qwen3-VL-2B-Instruct-4bit"
DEFAULT_REVISION = "9c4f5209e57b31f4b9dfba735de3fb983739c9cc"
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
    parser.add_argument("--glance", default="http://127.0.0.1:8077")
    parser.add_argument("--core", default=os.environ.get("GLANCE_CORE", "../glance"))
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--backend", default="mlx-4bit-direct")
    parser.add_argument("--experiment", default="E016")
    parser.add_argument("--raw", default="research/runs/e016-mlx-direct.json")
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


def request_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def jpeg_with_comment(data: bytes, comment: str) -> bytes:
    if not data.endswith(b"\xff\xd9"):
        raise ValueError("Expected a JPEG end marker")
    encoded = comment.encode("ascii")
    segment = b"\xff\xfe" + (len(encoded) + 2).to_bytes(2, "big") + encoded
    return data[:-2] + segment + data[-2:]


def logsumexp(values: np.ndarray, axis: int) -> np.ndarray:
    peak = np.max(values, axis=axis, keepdims=True)
    return (peak + np.log(np.exp(values - peak).sum(axis=axis, keepdims=True))).squeeze(axis)


def softmax(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    array -= array.max()
    exp = np.exp(array)
    return (exp / exp.sum()).tolist()


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


def decision(answer: dict[str, Any]) -> str:
    if answer["type"] == "noul":
        return "yes" if float(answer["noul"]) >= 0.5 else "no"
    return str(answer["choice"])


def answer_vector(answer: dict[str, Any]) -> dict[str, float]:
    if answer["type"] == "noul":
        value = float(answer["noul"])
        return {"yes": value, "no": 1.0 - value}
    return {str(key): float(value) for key, value in answer["probabilities"].items()}


def find_call_log(log_path: Path, request_id: str) -> dict[str, Any]:
    # The local server appends the complete scoring trace before returning.
    with log_path.open() as rows:
        for line in rows:
            if request_id in line:
                row = json.loads(line)
                if row.get("request_id") == request_id:
                    return row
    raise RuntimeError(f"Could not find Glance call log {request_id}")


class MlxStatementScorer:
    def __init__(self, core: Path, model: str, revision: str, *, enable_compile: bool = False):
        sys.path.insert(0, str(core))
        from glance import prompts  # pylint: disable=import-error,import-outside-toplevel

        self.prompts = prompts
        started = time.perf_counter()
        self.model, self.processor = load(model, revision=revision)
        self.load_ms = (time.perf_counter() - started) * 1000
        self.tokenizer = self.processor.tokenizer
        self.yes_ids = self._single_token_ids(prompts.YES_VARIANTS)
        self.no_ids = self._single_token_ids(prompts.NO_VARIANTS)
        token_ids = self.yes_ids + self.no_ids
        # The tied output head is a quantized embedding. Looking up only these rows
        # dequantizes eight vectors instead of projecting over the whole vocabulary.
        self.output_rows = self.model.language_model.model.embed_tokens(mx.array(token_ids))
        mx.eval(self.output_rows)
        # Qwen3-VL's multimodal prefix path performs an eager evaluation inside
        # input preparation, which MLX correctly rejects during transformation.
        # E018 therefore compiles only the fixed-shape cached suffix call.
        self.compiled_suffix = mx.compile(self._compiled_suffix_forward) if enable_compile else None

    def _compiled_suffix_forward(
        self,
        input_ids: mx.array,
        mask: mx.array,
        position_ids: mx.array,
        cache_states: tuple[tuple[mx.array, mx.array, mx.array, mx.array], ...],
    ) -> mx.array:
        batch = int(input_ids.shape[0])
        cache = []
        for state in cache_states:
            entry = mlx_cache.BatchKVCache([0] * batch)
            entry.state = state
            cache.append(entry)
        return self.model.language_model.model(
            input_ids,
            inputs_embeds=self.model.language_model.model.embed_tokens(input_ids),
            mask=mask,
            cache=cache,
            position_ids=position_ids,
        )

    def _single_token_ids(self, variants: list[str]) -> list[int]:
        ids = []
        for text in variants:
            encoded = self.tokenizer.encode(text, add_special_tokens=False)
            if len(encoded) == 1:
                ids.append(encoded[0])
        if not ids:
            raise RuntimeError(f"No single-token variants among {variants}")
        return ids

    def _statement_plan(self, questions: dict[str, dict[str, Any]]) -> tuple[list[str], dict[str, tuple[int, int, list[str]]]]:
        blocks: list[str] = []
        plan: dict[str, tuple[int, int, list[str]]] = {}
        for qid, question in questions.items():
            start = len(blocks)
            if question["type"] == "noul":
                blocks.append(self.prompts.render_noul(question["instructions"]))
                keys = ["true"]
            else:
                keys = list(question["criteria"])
                for key, description in question["criteria"].items():
                    candidate = self.prompts.candidate_text(key, description)
                    blocks.append(self.prompts.render_candidate(question["instructions"], candidate))
            plan[qid] = (start, len(blocks), keys)
        return blocks, plan

    def _render(self, block: str) -> str:
        content = [
            {"type": "text", "text": self.prompts.image_label("img0")},
            {"type": "image"},
            {"type": "text", "text": block},
        ]
        return self.processor.apply_chat_template(
            [{"role": "user", "content": content}],
            tokenize=False,
            add_generation_prompt=True,
        )

    def score(
        self,
        image: Path,
        questions: dict[str, dict[str, Any]],
        *,
        group_by_question: bool = False,
        compiled: bool = False,
    ) -> dict[str, Any]:
        if compiled and self.compiled_suffix is None:
            raise RuntimeError("Construct the scorer with enable_compile=True before requesting compiled execution")
        if hasattr(mx, "reset_peak_memory"):
            mx.reset_peak_memory()
        wall_started = time.perf_counter()
        blocks, plan = self._statement_plan(questions)
        rendered = [self._render(block) for block in blocks]

        prepare_started = time.perf_counter()
        first = prepare_inputs(
            self.processor,
            images=str(image) if isinstance(image, (str, Path)) else image,
            prompts=rendered[0],
            image_token_index=self.model.config.image_token_index,
            add_special_tokens=should_add_special_tokens(self.model.config.model_type, self.processor),
        )
        first_ids = first["input_ids"][0].tolist()
        image_tokens = first_ids.count(self.model.config.image_token_index)
        ids: list[list[int]] = []
        for text in rendered:
            raw = self.tokenizer(text, add_special_tokens=False).input_ids
            expanded: list[int] = []
            for token in raw:
                expanded.extend([token] * image_tokens if token == self.model.config.image_token_index else [token])
            ids.append(expanded)
        if ids[0] != first_ids:
            raise RuntimeError("MLX prompt expansion did not reproduce processor input IDs")
        shortest = min(map(len, ids))
        shared = 0
        while shared < shortest - 1 and all(row[shared] == ids[0][shared] for row in ids):
            shared += 1
        vision_end = max(i for i, token in enumerate(ids[0]) if token == self.model.config.image_token_index) + 1
        if shared < vision_end:
            raise RuntimeError("Statements do not share the complete image prefix")
        prepare_ms = (time.perf_counter() - prepare_started) * 1000

        prefix_started = time.perf_counter()
        prefix_ids = mx.array([ids[0][:shared]])
        prefix_mask = mx.ones(prefix_ids.shape, dtype=mx.int32)
        feature_kwargs = {
            key: value
            for key, value in first.items()
            if key not in ("input_ids", "pixel_values", "attention_mask")
        }
        features = self.model.get_input_embeddings(
            prefix_ids,
            first["pixel_values"],
            mask=prefix_mask,
            **feature_kwargs,
        )
        prompt_cache = mlx_cache.make_prompt_cache(self.model.language_model)
        self.model.language_model.model(
            prefix_ids,
            inputs_embeds=features.inputs_embeds,
            cache=prompt_cache,
            position_ids=features.position_ids,
            visual_pos_masks=features.visual_pos_masks,
            deepstack_visual_embeds=features.deepstack_visual_embeds,
        )
        mx.eval([entry.state for entry in prompt_cache])
        prefix_ms = (time.perf_counter() - prefix_started) * 1000

        suffixes = [row[shared:] for row in ids]
        pad_id = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id
        grid = first.get("image_grid_thw")
        positions_by_row: list[np.ndarray] = []
        for index, (row, suffix) in enumerate(zip(ids, suffixes)):
            full_ids = mx.array([row])
            full_mask = mx.ones(full_ids.shape, dtype=mx.int32)
            positions, _ = self.model.language_model.get_rope_index(full_ids, grid, None, full_mask)
            positions_by_row.append(np.asarray(positions)[:, 0, shared:])

        groups = [list(range(len(suffixes)))]
        if group_by_question:
            groups = [list(range(start, end)) for start, end, _ in plan.values()]
        selected_np = np.empty((len(suffixes), len(self.yes_ids) + len(self.no_ids)), dtype=np.float64)
        cache_copy_ms = suffix_ms = head_ms = 0.0
        widths: list[int] = []
        for group in groups:
            batch = len(group)
            width = max(len(suffixes[index]) for index in group)
            widths.append(width)
            suffix_array = np.full((batch, width), pad_id, dtype=np.int64)
            position_array = np.ones((3, batch, width), dtype=np.int64)
            lengths: list[int] = []
            for batch_index, statement_index in enumerate(group):
                suffix = suffixes[statement_index]
                lengths.append(len(suffix))
                suffix_array[batch_index, : len(suffix)] = suffix
                position_array[:, batch_index, : len(suffix)] = positions_by_row[statement_index]

            cache_started = time.perf_counter()
            batch_cache = [type(entry).merge([entry] * batch) for entry in prompt_cache]
            mx.eval([entry.state for entry in batch_cache])
            cache_copy_ms += (time.perf_counter() - cache_started) * 1000

            suffix_started = time.perf_counter()
            suffix_ids = mx.array(suffix_array)
            right_padding = mx.array([width - length for length in lengths])
            attention = mlx_cache.create_causal_mask(width, offset=shared, right_padding=right_padding)
            if compiled:
                hidden = self.compiled_suffix(
                    suffix_ids,
                    attention,
                    mx.array(position_array),
                    tuple(entry.state for entry in batch_cache),
                )
            else:
                hidden = self.model.language_model.model(
                    suffix_ids,
                    inputs_embeds=self.model.language_model.model.embed_tokens(suffix_ids),
                    mask=attention,
                    cache=batch_cache,
                    position_ids=mx.array(position_array),
                )
            last_hidden = hidden[mx.arange(batch), mx.array([length - 1 for length in lengths])]
            mx.eval(last_hidden)
            suffix_ms += (time.perf_counter() - suffix_started) * 1000

            head_started = time.perf_counter()
            selected = last_hidden.astype(mx.float32) @ self.output_rows.astype(mx.float32).T
            mx.eval(selected)
            head_ms += (time.perf_counter() - head_started) * 1000
            selected_np[group] = np.asarray(selected).astype(np.float64)

        z_yes = logsumexp(selected_np[:, : len(self.yes_ids)], axis=1)
        z_no = logsumexp(selected_np[:, len(self.yes_ids) :], axis=1)
        z = z_yes - z_no

        answers: dict[str, dict[str, Any]] = {}
        raw_z: dict[str, list[float]] = {}
        for qid, question in questions.items():
            start, end, keys = plan[qid]
            values = z[start:end].tolist()
            raw_z[qid] = values
            if question["type"] == "noul":
                probability = sigmoid(values[0])
                answers[qid] = {"type": "noul", "noul": probability}
            else:
                probabilities = softmax(values)
                mapping = dict(zip(keys, probabilities))
                answers[qid] = {
                    "type": "choice",
                    "choice": keys[int(np.argmax(probabilities))],
                    "probabilities": mapping,
                }
        wall_ms = (time.perf_counter() - wall_started) * 1000
        return {
            "wall_ms": round(wall_ms, 3),
            "timing_ms": {
                "prepare": round(prepare_ms, 3),
                "prefix": round(prefix_ms, 3),
                "cache_copy": round(cache_copy_ms, 3),
                "suffix": round(suffix_ms, 3),
                "head": round(head_ms, 3),
            },
            "answers": answers,
            "z": raw_z,
            "shared_prefix_tokens": shared,
            "image_tokens": image_tokens,
            "suffix_widths": widths,
            "suffix_groups": len(groups),
            "peak_memory_gb": round(mx.get_peak_memory() / 1e9, 3) if hasattr(mx, "get_peak_memory") else None,
        }

    def full_prompt_reference(self, image: Path, questions: dict[str, dict[str, Any]]) -> dict[str, list[float]]:
        """Slow correctness oracle: independently encode every complete multimodal prompt."""
        blocks, plan = self._statement_plan(questions)
        statement_z: list[float] = []
        for block in blocks:
            text = self._render(block)
            prepared = prepare_inputs(
                self.processor,
                images=str(image) if isinstance(image, (str, Path)) else image,
                prompts=text,
                image_token_index=self.model.config.image_token_index,
                add_special_tokens=should_add_special_tokens(self.model.config.model_type, self.processor),
            )
            input_ids = prepared["input_ids"]
            mask = prepared["attention_mask"]
            feature_kwargs = {
                key: value
                for key, value in prepared.items()
                if key not in ("input_ids", "pixel_values", "attention_mask")
            }
            features = self.model.get_input_embeddings(
                input_ids,
                prepared["pixel_values"],
                mask=mask,
                **feature_kwargs,
            )
            hidden = self.model.language_model.model(
                input_ids,
                inputs_embeds=features.inputs_embeds,
                position_ids=features.position_ids,
                visual_pos_masks=features.visual_pos_masks,
                deepstack_visual_embeds=features.deepstack_visual_embeds,
            )
            selected = hidden[:, -1].astype(mx.float32) @ self.output_rows.astype(mx.float32).T
            mx.eval(selected)
            selected_np = np.asarray(selected).astype(np.float64)
            yes = logsumexp(selected_np[:, : len(self.yes_ids)], axis=1)
            no = logsumexp(selected_np[:, len(self.yes_ids) :], axis=1)
            statement_z.append(float(yes[0] - no[0]))
        return {
            qid: statement_z[start:end]
            for qid, (start, end, _) in plan.items()
        }


def main() -> int:
    args = parse_args()
    root, core = Path.cwd(), Path(args.core).resolve()
    fixtures = {
        name: root / "research/runs/fixtures" / f"{name}-320-q60.jpg"
        for name in ("dog", "receipt", "invoice")
    }
    missing = [str(path) for path in fixtures.values() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing fixtures: {', '.join(missing)}")
    call_log = core / "logs" / "calls" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    scorer = MlxStatementScorer(core, args.model, args.revision)
    shared_validation = scorer.score(fixtures["dog"], QUESTIONS)
    full_reference = scorer.full_prompt_reference(fixtures["dog"], QUESTIONS)
    shared_max_z_delta = max(
        abs(float(a) - float(b))
        for qid in QUESTIONS
        for a, b in zip(shared_validation["z"][qid], full_reference[qid])
    )
    rows: list[dict[str, Any]] = []

    def run_glance(image: Path, warmup: bool, repeat: int) -> dict[str, Any]:
        source = image.read_bytes()
        fresh = jpeg_with_comment(source, f"{args.experiment.lower()}-{time.time_ns()}-{repeat}")
        payload = {
            "model": "vlm",
            "state": {"images": [{"id": "img0", "base64": base64.b64encode(fresh).decode()}]},
            "questions": QUESTIONS,
            "options": {"choice_method": "independent", "calibrated": False},
        }
        started = time.perf_counter()
        response = request_json(f"{args.glance.rstrip('/')}/v1/decide", payload)
        wall_ms = (time.perf_counter() - started) * 1000
        logged = find_call_log(call_log, response["request_id"])
        outputs = logged["output"]
        return {
            "backend": "glance-mps-fp16",
            "image": image.stem.split("-")[0],
            "warmup": warmup,
            "repeat": repeat,
            "wall_ms": round(wall_ms, 3),
            "timing_ms": response["timing_ms"],
            "answers": {qid: outputs[qid]["answer"] for qid in QUESTIONS},
            "z": {qid: outputs[qid]["z"] for qid in QUESTIONS},
        }

    def run_mlx(image: Path, warmup: bool, repeat: int) -> dict[str, Any]:
        return {
            "backend": args.backend,
            "image": image.stem.split("-")[0],
            "warmup": warmup,
            "repeat": repeat,
            **scorer.score(image, QUESTIONS),
        }

    for _, image in fixtures.items():
        for repeat in range(args.warmups + args.repeats):
            warmup = repeat < args.warmups
            runners = (run_glance, run_mlx) if repeat % 2 == 0 else (run_mlx, run_glance)
            for runner in runners:
                row = runner(image, warmup, repeat)
                rows.append(row)
                print(f"{row['backend']} {row['image']} {repeat + 1}/{args.warmups + args.repeats}: {row['wall_ms']:.1f} ms", flush=True)

    measured = [row for row in rows if not row["warmup"]]
    aggregate: dict[str, Any] = {}
    for backend in ("glance-mps-fp16", args.backend):
        selected_rows = [row for row in measured if row["backend"] == backend]
        aggregate[backend] = {
            "wall_ms": summarize([float(row["wall_ms"]) for row in selected_rows]),
            "prefix_ms": summarize([float(row["timing_ms"]["prefix"]) for row in selected_rows]),
        }
        if backend == "glance-mps-fp16":
            aggregate[backend]["score_ms"] = summarize([float(row["timing_ms"]["score"]) for row in selected_rows])
        else:
            for key in ("prepare", "cache_copy", "suffix", "head"):
                aggregate[backend][f"{key}_ms"] = summarize([float(row["timing_ms"][key]) for row in selected_rows])
            aggregate[backend]["peak_memory_gb"] = max(float(row["peak_memory_gb"] or 0) for row in selected_rows)
            aggregate[backend]["shared_prefix_tokens"] = sorted({int(row["shared_prefix_tokens"]) for row in selected_rows})
            aggregate[backend]["image_tokens"] = sorted({int(row["image_tokens"]) for row in selected_rows})

    reference_p50 = float(aggregate["glance-mps-fp16"]["wall_ms"]["p50"])
    mlx_p50 = float(aggregate[args.backend]["wall_ms"]["p50"])
    aggregate[args.backend]["speedup_vs_glance"] = round(reference_p50 / mlx_p50, 4)
    aggregate[args.backend]["latency_reduction_percent"] = round((1 - mlx_p50 / reference_p50) * 100, 1)

    keyed = {(row["image"], row["repeat"], row["backend"]): row for row in measured}
    decisions_equal = True
    max_probability_delta = 0.0
    max_z_delta = 0.0
    question_equal = 0
    question_total = 0
    for image in fixtures:
        for repeat in range(args.warmups, args.warmups + args.repeats):
            reference = keyed[(image, repeat, "glance-mps-fp16")]
            candidate = keyed[(image, repeat, args.backend)]
            for qid in QUESTIONS:
                left, right = reference["answers"][qid], candidate["answers"][qid]
                equal = decision(left) == decision(right)
                decisions_equal = decisions_equal and equal
                question_equal += int(equal)
                question_total += 1
                lv, rv = answer_vector(left), answer_vector(right)
                max_probability_delta = max(
                    max_probability_delta,
                    *(abs(lv.get(label, 0.0) - rv.get(label, 0.0)) for label in set(lv) | set(rv)),
                )
                max_z_delta = max(
                    max_z_delta,
                    *(abs(float(a) - float(b)) for a, b in zip(reference["z"][qid], candidate["z"][qid])),
                )
    guardrail = {
        "decisions_equal": decisions_equal,
        "question_decision_agreement": round(question_equal / question_total, 6),
        "max_probability_delta": round(max_probability_delta, 8),
        "max_z_delta": round(max_z_delta, 8),
        "passed": decisions_equal and max_probability_delta <= 0.10,
    }
    output = {
        "schema_version": 1,
        "experiment": args.experiment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware": "Apple M5, 10-core GPU, 32 GB unified memory",
            "platform": platform.platform(),
            "mlx_model": f"{args.model}@{args.revision}",
            "mlx_load_ms": round(scorer.load_ms, 3),
        },
        "protocol": {"warmups": args.warmups, "repeats_per_image": args.repeats, "fresh_frame": True, "statements": 9},
        "shared_path_validation_max_z_delta": round(shared_max_z_delta, 8),
        "aggregate": aggregate,
        "guardrail": guardrail,
        "backend_candidate": guardrail["passed"] and mlx_p50 <= reference_p50 * 0.95,
        "rows": rows,
    }
    raw_path = root / args.raw
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"aggregate": aggregate, "guardrail": guardrail, "backend_candidate": output["backend_candidate"], "raw": str(raw_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
