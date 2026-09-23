# E021 result — shallow decoder refinement

The 26/27-layer boundary contains no deployable untrained exit.

| Depth | Prefix p50 | Suffix p50 | Wall p50 / p95 | Speedup | Max probability delta | Decisions |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 28 | 178.7 ms | 175.5 ms | 379.7 / 391.8 ms | — | — | reference |
| 27 | 172.5 ms | 168.0 ms | 366.9 / 382.0 ms | 1.035× | 0.242 | all matched |
| 26 | 170.3 ms | 162.4 ms | 356.4 / 374.0 ms | 1.065× | 0.606 | receipt photo changed |

The final layer is disproportionately important to the selected-token probabilities: removing only layer 28 caused more drift than the 24-layer arm in E020 on this suite, even though all 27-layer argmax decisions remained stable. This makes raw layer count an unreliable confidence proxy.

## Decision

Stop untrained decoder truncation. The speed mechanism is real, but neither boundary satisfies both adoption gates. Any return to early exit should train and calibrate a decision head on intermediate representations, or distill full-depth statement margins into a smaller student.
