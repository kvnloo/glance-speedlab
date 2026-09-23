# E013 — Apple-native MLX 4-bit backend

## Hypothesis

A Qwen3-VL-2B checkpoint running through MLX with 4-bit weights will reduce warm fixed-image end-to-end latency by at least 5% relative to the current PyTorch MPS/FP16 Glance path on the Apple M5.

## Protocol

- Do not replace or stop the active Glance service.
- Install MLX tooling into `research/runs/e013-venv`, which is ignored and disposable.
- Pin and record package versions and the candidate checkpoint revision.
- Use Glance's `dog.jpg`, `receipt.jpg`, and `invoice.jpg`; do not persist user camera frames.
- Ask one deterministic coarse-content question, run two warmups and at least five measured repetitions per image, and retain raw timing rows only under `research/runs/`.
- Compare with the current local Glance service using the nearest native request shape; explicitly identify any protocol mismatch.

## Metrics and guardrail

- Primary: warm end-to-end p50 per image and aggregate.
- Secondary: load time, prompt-processing time, generation throughput, peak RSS when observable, checkpoint size, and reproducibility/setup notes.
- Guardrail: exact coarse class agreement across all three images. Generated-text agreement is exploratory because Glance performs direct probability scoring rather than free generation.

## Environment

- Apple M5, 32 GB unified memory, macOS 26.6.2.
- Baseline: Qwen3-VL-2B, PyTorch MPS FP16, Glance prefix cache, image-token budget 128.
- Candidate: Qwen3-VL-2B MLX 4-bit; exact versions and revisions recorded in the result.

## Stopping rule

Stop after the complete three-image run, or on a reproducible install, conversion, compatibility, memory, or protocol blocker. Require at least 5% lower p50 and a passing guardrail for a positive speed result.

## Reproduction

```bash
uv venv research/runs/e013-venv --python 3.11
uv pip install --python research/runs/e013-venv/bin/python torch torchvision
uv pip install --python research/runs/e013-venv/bin/python \
  'git+https://github.com/Blaizzy/mlx-vlm.git@b5952d7c97da3cfc5014ff0a81bfe2e59d919cab'
research/runs/e013-venv/bin/python scripts/run-mlx-experiment.py
```

The released `mlx-vlm==0.4.1` package was attempted first. It failed in the Qwen3-VL vision tower because an MLX array was passed as `mx.repeat`'s integer repeat count. The pinned upstream commit includes the one-line compatibility fix; keep this distinction in the final result.
