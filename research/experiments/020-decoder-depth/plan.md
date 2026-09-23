# E020 plan — decoder depth frontier

## Hypothesis

The final selected yes/no token margin will stabilize before all 28 language-model layers, allowing a 24- or 20-layer inference exit to reduce both prefix and suffix time by at least 5% without changing fixed-suite decisions or shifting answer probabilities by more than 0.10.

## Protocol

- One loaded MLX 8-bit scorer with the leading 28, 24, or 20 decoder layers active for both prefix and suffix.
- Preserve the vision tower, early deep-stack injection, final norm, selected output rows, prompts, fixtures, and default vision-token behavior.
- Three warmups and ten measured order-rotated repetitions per image/arm.

## Metrics and stopping rule

- Primary: wall p50; secondary prefix/suffix p50/p95 and memory.
- Require exact decisions and maximum answer-probability delta ≤0.10 versus 28 layers.
- Advance only at ≥5% p50 improvement and no >5% p95 regression. A failed untrained exit motivates a trained head, not production truncation.
