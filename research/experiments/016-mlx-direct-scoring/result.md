# E016 result — native MLX statement scoring

The direct MLX scorer retained the speed advantage after removing E013's generation mismatch. On a fresh four-question request totaling nine statements, 4-bit MLX reduced p50 from 503.4 to 367.3 ms: 1.371×, or 27.0%. Every one of 84 measured question decisions agreed with Glance.

Probability parity failed. Maximum answer-probability drift was 0.361 and maximum raw statement-z drift was 3.089, above the preregistered 0.10 probability limit. The MLX shared-prefix/batched-suffix implementation also differed from nine slow, independent full MLX prompts by up to 0.206 z on the validation image. Per-question suffix groups were slower and did not eliminate quantized shape sensitivity.

## Timing decomposition

| Component | Glance FP16 p50 | MLX 4-bit p50 |
| --- | ---: | ---: |
| Fresh image/prefix | 227.0 ms | 178.3 ms |
| Statement scoring / suffix model | 275.0 ms | 165.7 ms |
| Prefix-KV batch expansion | included | 6.2 ms |
| Selected output rows | full diagnostic included | 0.3 ms |
| End to end | 503.4 ms | 367.3 ms |

Peak MLX memory was 2.726 GB. The path shared 82–92 prefix tokens, including 70–80 image tokens, across all nine statements.

## Decision

The implementation validates H21's speed mechanism but not 4-bit probability parity. Do not connect it to the live UI. Test 8-bit MLX with the same scorer before changing prompts, calibration, or kernels.
