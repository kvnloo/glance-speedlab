# E018 plan — fixed-shape MLX compilation

## Hypothesis

Explicitly compiling the fixed-shape MLX language-model calls will remove repeated dispatch and graph construction overhead from the validated 8-bit direct scorer, lowering fresh nine-statement p50 by at least 5% without changing its probabilities materially.

## Protocol

- Compare eager and compiled calls in one loaded 8-bit process.
- Keep prompts, fixtures, image preprocessing, shared prefix, suffix padding, cache expansion, and selected-token head fixed.
- Use three warmups and ten measured alternating repetitions per image and arm.
- Record first compile latency and behavior across dog, receipt, and invoice shapes separately.

## Metrics and stopping rule

- Primary: scorer wall p50. Secondary: prefix/suffix p50/p95, compile cost, and peak memory.
- Require exact decisions, maximum probability delta ≤0.001, and raw-z delta ≤0.01.
- Retain only at ≥5% p50 improvement with no >5% p95 regression. Stop on incorrect KV-cache behavior or >60 seconds compilation per shape.
