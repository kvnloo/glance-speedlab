# E019 result — MLX vision-token frontier

Reducing MLX vision tokens exposes real prefix headroom, but both tested caps failed the fixed-suite quality gate.

| Arm | Realized tokens (dog / receipt / invoice) | Prefix p50 | Wall p50 / p95 | Speedup | Max probability delta | Decision parity |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Default | 70 / 77 / 80 | 176.1 ms | 376.2 / 389.9 ms | — | — | reference |
| Nominal 64 | 54 / 77 / 63 | 169.7 ms | 371.8 / 384.9 ms | 1.012× | 0.445 | failed |
| Nominal 48 | 40 / 45 / 42 | 122.1 ms | 317.4 / 331.5 ms | 1.185× | 0.411 | failed |

Grid rounding matters. The 64-token area limit did not affect the tall receipt at all, while dog and invoice dropped in coarse steps. The 48 arm reduced prefix time 30.7%; suffix time remained essentially flat, supporting the intended mechanism.

Both caps changed the dog `tone` answer from `mixed` to `mostly dark`. The 48 arm also moved the receipt `photo` probability by 0.114 without crossing its decision boundary. The 64 arm moved the invoice tone probability by 0.278 while retaining its label.

## Decision

Keep the default 70–80-token processor behavior in the live MLX backend. The 48-token result is useful as an upper bound on prefix opportunity, not as a deployable mode. A learned or saliency-aware token reducer could revisit the 54 ms prefix saving; uniform pixel-area reduction is exhausted on this suite.
