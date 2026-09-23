# E018 result — fixed-shape MLX compilation

Explicit MLX compilation did not materially accelerate the validated direct scorer. Qwen3-VL's multimodal prefix path calls `mx.eval` while assembling deep-stack vision embeddings, so MLX rejects transforming that path. The narrower fixed-shape cached suffix compiled successfully and preserved every output bit, but reduced full scorer p50 only 0.6%: 391.5 to 389.3 ms.

## Results

| Component | Eager p50 / p95 | Compiled suffix p50 / p95 |
| --- | ---: | ---: |
| Prefix | 182.9 / 207.2 ms | 181.8 / 211.0 ms |
| Suffix model | 183.5 / 199.8 ms | 180.7 / 202.9 ms |
| Prefix-KV batch expansion | 4.9 / 7.4 ms | 6.5 / 14.0 ms |
| End to end | 391.5 / 417.4 ms | 389.3 / 418.3 ms |

The compiled arm was 1.006× faster at p50, below the preregistered 1.05× gate. Its p95 remained within the limit. Exact decisions, probabilities, and raw statement z values matched; peak reported memory fell from 3.499 to 3.291 GB, but memory was secondary and does not justify added execution complexity.

Absolute latency was higher than E017 even though the model and workload were the same, illustrating why the paired, alternating within-run comparison is the claim-bearing result. Thermal and process-history state were not controlled well enough for cross-run absolute comparisons.

## Decision

Keep eager MLX execution. Do not enable compilation in the live service. Future graph work needs either an upstream Qwen path that avoids eager evaluation during transformation or a more invasive compiled vision/prefix implementation; simply decorating the cached suffix is exhausted.
