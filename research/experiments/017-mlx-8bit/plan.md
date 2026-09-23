# E017 plan — MLX 8-bit precision frontier

## Hypothesis

Changing only the MLX checkpoint from 4-bit to 8-bit will reduce maximum probability drift against Glance from 0.361 to at most 0.10 while preserving at least a 5% fresh-frame speed advantage.

## Protocol

- Reuse the E016 direct scorer, prompts, selected token rows, shared-prefix boundary, suffix batch, fixtures, and paired order.
- Candidate: `mlx-community/Qwen3-VL-2B-Instruct-8bit@b0338e0e843d8e1befe873d144b81fefdc47efa6`.
- Reference: active pinned Qwen3-VL-2B FP16 Glance service.
- Two warmups and seven measured repetitions per image/backend.

## Metrics and stopping rule

- Primary: fresh-frame p50; secondary prefix, suffix, cache expansion, head, memory, and retained speed versus E016.
- Exact decision agreement and maximum answer-probability delta ≤0.10 are required.
- Stop after the complete run, incompatibility, or OOM. Do not fold BF16 into this experiment if 8-bit fails.
