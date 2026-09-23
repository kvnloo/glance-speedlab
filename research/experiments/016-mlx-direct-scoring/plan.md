# E016 plan — native MLX statement scoring

## Hypothesis

A 4-bit MLX implementation of Glance's existing direct statement scorer will preserve the fixed-suite decisions and probabilities within 0.10 while reducing fresh-frame median latency by at least 5% relative to the active PyTorch MPS/FP16 backend.

Unlike E013, this experiment does not decode a label. It uses one shared multimodal prefix, batched candidate suffixes, and the same yes/no token variants as Glance.

## Protocol

- Apple M5, 10-core GPU, 32 GB unified memory.
- Three controlled 320 px, JPEG-quality-60 fixtures: dog, receipt, and invoice.
- Four fixed questions totaling nine statements; independent choice scoring, no calibration.
- Glance reference: pinned Qwen3-VL-2B FP16 MPS, 128-token image budget, suffix batch 16. Unique JPEG comments force each measured call to be a fresh-frame cache miss without changing decoded pixels.
- MLX candidate: pinned Qwen3-VL-2B 4-bit checkpoint and MLX-VLM environment from E013. Each call runs the vision/prefix once and creates a batched suffix cache from that request-local prefix.
- Two warmups and at least seven measured repetitions per image/backend.

## Metrics and guardrail

- Primary: fresh-frame wall p50.
- Secondary: prefix, suffix model, selected output-head, cache expansion, one-question latency, and peak memory.
- Guardrail: exact decisions and maximum absolute answer-probability delta ≤0.10. Preserve and compare every statement z.
- The candidate intentionally omits full-vocabulary `off_mass`; E015 measured that reference-only diagnostic at roughly 7–8 ms.

## Reproduction

```bash
research/runs/e013-venv/bin/python scripts/run-mlx-direct-experiment.py
```

Raw rows remain ignored under `research/runs/`; curated output will be written only after validation.
