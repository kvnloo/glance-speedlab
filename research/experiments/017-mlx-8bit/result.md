# E017 result — MLX 8-bit precision frontier

The 8-bit direct scorer passed both gates. Fresh nine-statement p50 fell from 358.5 ms on Glance FP16/MPS to 259.6 ms on MLX 8-bit: 1.381×, or 27.6%. All 84 measured question decisions agreed, and the maximum answer-probability delta was 0.039 against the preregistered 0.10 limit.

This is also faster than the E016 4-bit path on the same machine. The comparison is not a same-run 4-bit/8-bit race, so the magnitude should not be overinterpreted, but the direction is consistent with 8-bit kernels avoiding enough quantization overhead to offset the wider weights.

## Timing decomposition

| Component | Glance FP16 p50 | MLX 8-bit p50 |
| --- | ---: | ---: |
| Fresh image/prefix | 163.0 ms | 120.9 ms |
| Statement scoring / suffix model | 192.0 ms | 118.2 ms |
| Prefix-KV batch expansion | included | 3.3 ms |
| Selected output rows | full diagnostic included | 0.3 ms |
| End to end | 358.5 ms | 259.6 ms |

MLX peak memory was 3.499 GB. The path shared 82–92 prefix tokens, including 70–80 image tokens, across all nine statements. The shared-prefix/batched-suffix result differed from nine slow, independent full MLX prompts by at most 0.145 raw z on the validation image. Maximum drift against Glance was 0.516 raw z, but answer probabilities remained inside the acceptance bound.

## Decision

Promote the pinned 8-bit checkpoint and direct scorer to an opt-in local backend candidate. Keep Glance as the default until the live UI path, cancellation behavior, error recovery, and a larger labeled real-camera suite are validated. Do not spend the next cycle on the selected-token head or cache-copy step: together they are below 4 ms p50. The remaining useful targets are the roughly equal 121 ms prefix and 118 ms suffix transformer phases.

## Integration replication

The first gateway smoke test exposed that Speedlab was adding `state.context.source` to Glance requests. Glance treats state context as prompt content, so this nonessential provenance marker changed the reference probabilities while the MLX scorer correctly reproduced the context-free experiment prompt. Source/backend identity was moved to gateway telemetry and removed from model state.

The complete E017 protocol was then rerun. The replication measured 281.7 ms Glance versus 211.3 ms MLX p50 (1.334×; 25.0%), with all 84 decisions matching and the same 0.0389 maximum probability delta. Absolute latency changed, but the paired direction, magnitude, and semantic result replicated.
