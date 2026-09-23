# E019 plan — MLX vision-token frontier

## Hypothesis

Constraining Qwen3-VL's MLX image processor below the current 70–80 realized image tokens will cut the roughly 121 ms prefix phase by at least 5% while preserving the fixed-suite decisions and keeping maximum probability drift within 0.10.

## Protocol

- One loaded MLX 8-bit direct scorer; default, nominal 64-token, and nominal 48-token processor caps.
- Convert caps to pixel area using the checkpoint's patch and spatial-merge sizes; report realized tokens after grid rounding.
- Three warmups and ten measured order-rotated repetitions per image/arm.
- Same three 320 px JPEGs and nine statements as E017.

## Metrics and stopping rule

- Primary: prefix and wall p50. Secondary: suffix, p95, realized image tokens, and memory.
- Require exact decisions and maximum answer-probability delta ≤0.10 versus default MLX.
- Advance only at ≥5% wall improvement and no >5% p95 regression. Before a live-default change, measure the selected arm directly against Glance FP16.
