# E020 result — decoder depth frontier

Untrained decoder truncation produced proportional speedups but crossed the probability guardrail before a deployable arm emerged.

| Depth | Prefix p50 | Suffix p50 | Wall p50 / p95 | Speedup | Max probability delta | Decisions |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 28 | 175.4 ms | 174.8 ms | 375.7 / 389.3 ms | — | — | reference |
| 24 | 161.2 ms | 149.9 ms | 334.0 / 347.2 ms | 1.125× | 0.207 | all matched |
| 20 | 145.0 ms | 125.0 ms | 294.0 / 305.5 ms | 1.278× | 0.996 | four changed |

The 24-layer arm retained all labels but materially shifted dog tone, receipt content, and receipt photo probabilities. The 20-layer arm changed dog text, receipt content/photo, and invoice photo decisions. The mechanism is confirmed—removing layers reduces both prefix and suffix work—but the pretrained final output head is not calibrated for these intermediate representations.

## Decision

Reject 24 and 20 layers as live modes. Test 26/27 as a separately preregistered boundary refinement. If that boundary cannot clear both 5% speed and 0.10 probability drift, stop raw truncation and require a trained early-exit head or distillation objective.
