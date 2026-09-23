# E015 result — selected-logit-only statement scoring

The optimization was correct but missed its primary keep threshold. On the preregistered nine-statement workload, omitting the full-vocabulary projection reduced score p50 from 179 to 172 ms: 1.041×, or 3.9%. The selected arm's p95 was lower as well, 179 versus 185 ms.

On the secondary four-statement workload, score p50 fell from 91 to 84 ms: 1.083×, or 7.7%. Across both workloads, every raw statement z, decision, and returned probability was exactly identical. Reference statement `off_mass` values were present and selected-only values were correctly unavailable rather than fabricated.

The projection therefore costs approximately 7–8 ms on this model and machine. That is worthwhile for a highly tuned one-question mode, but it is not the dominant cost: suffix transformer execution grows while the avoided vocabulary projection remains nearly fixed. Because the primary improvement was below the preregistered 5% threshold, the experimental Glance implementation was reverted and the reference diagnostic remains intact.

## Reproduction record

- Apple M5, 10-core GPU, 32 GB unified memory.
- Qwen3-VL-2B Instruct, pinned revision, float16 MPS.
- 128 image-token budget; prefix cache hit in both paired arms; suffix batch 16.
- Two warmup pairs and ten measured, order-rotated pairs per image.
- Detailed rows: ignored `research/runs/e015-selected-logit.json`.
- Curated aggregate: [`research/results/e015-selected-logit.json`](../../results/e015-selected-logit.json).

## Decision

Do not prioritize the full-vocabulary normalization. Focus next on the 28-layer suffix computation: MLX direct scoring, fixed-shape compilation, prefix-KV broadcast, and suffix sharing.
