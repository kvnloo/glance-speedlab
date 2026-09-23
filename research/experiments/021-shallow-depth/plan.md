# E021 plan — shallow decoder refinement

## Hypothesis

Removing only one or two of Qwen3-VL-2B's 28 language layers will preserve the full model's fixed-suite probabilities within 0.10, and the 26-layer arm will still lower p50 by at least 5%.

## Protocol

- Compare leading depths 28, 27, and 26 in one loaded MLX 8-bit process.
- Keep the default processor, prompts, selected output rows, suffix batch, and fixtures fixed from E020.
- Three warmups and ten measured order-rotated repetitions per image/arm.

## Metrics and stopping rule

- Primary: wall p50; secondary prefix/suffix p50/p95 and memory.
- Require exact decisions, maximum probability delta ≤0.10, ≥5% p50 improvement, and no >5% p95 regression.
- If 26 fails quality and 27 fails speed, stop untrained truncation.
