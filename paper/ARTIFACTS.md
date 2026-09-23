# Paper claim-to-artifact map

This map is the audit surface for `PAPER.md`. A claim should not become stronger than its linked artifact.

| Claim | Experiment | Aggregate artifact | Interpretation |
| --- | --- | --- | --- |
| 224 px is 0.999× versus 320 and fails quality | E001 | `research/results/model-experiments.json` | `research/experiments/001-resolution/result.md` |
| JPEG quality changes bytes, not local latency materially | E002 | `research/results/model-experiments.json` | `research/experiments/002-jpeg-quality/result.md` |
| Native four-question batch is 2.405× faster | E003 | `research/results/model-experiments.json` | `research/experiments/003-native-batch/result.md` |
| Persistent canvas avoids allocations without a median win | E004 | `research/results/browser-experiments.json` | `research/experiments/004-persistent-capture/result.md` |
| Base64/JSON is at most 0.1 ms p95 at 320 px | E005 | `research/results/browser-experiments.json` | `research/experiments/005-base64-json/result.md` |
| Question order is operationally neutral | E006 | `research/results/model-experiments.json` | `research/experiments/006-question-order/result.md` |
| Synthetic threshold-4 gating reduces triggers 95.1% | E007 | `research/results/browser-experiments.json` | `research/experiments/007-temporal-reuse/result.md` |
| Caps 128–768 realize the same 70–80 tokens at 320 px | E008 | `research/results/next-model-experiments.json` | `research/experiments/008-image-token-budget/result.md` |
| Suffix batch 16 and 32 are flat; 4/8 slower | E009 | `research/results/next-model-experiments.json` | `research/experiments/009-suffix-batch/result.md` |
| Letter scoring does not improve latency and fails quality | E010 | `research/results/next-model-experiments.json` | `research/experiments/010-choice-scoring/result.md` |
| 2B is 2.994× faster but has 83.3% decision agreement | E011 | `research/results/e011-model-tier.json` | `research/experiments/011-2b-fast-tier/result.md` |
| Sub-128 caps are faster but fail the registered guardrails | E012 | `research/results/e012-apple_8gb.json`, `research/results/e012-apple_32gb.json` | `research/experiments/012-sub128-token-budget/result.md` |
| MLX 4-bit lowers fresh-frame latency 29.4%, but is slower than Glance cache hits and lacks protocol parity | E013 | `research/results/e013-mlx.json` | `research/experiments/013-mlx-4bit/result.md` |
| MLX continued-chat caching is 2.048×, while standalone Qwen3-VL cache paths restore zero tokens | E014 | `research/results/e014-mlx-cache.json` | `research/experiments/014-mlx-cache/result.md` |
| Selected-only Glance readout saves 7–8 ms but misses the nine-statement threshold | E015 | `research/results/e015-selected-logit.json` | `research/experiments/015-selected-logit-only/result.md` |
| Direct MLX 4-bit scoring retains speed but fails probability parity | E016 | `research/results/e016-mlx-direct.json` | `research/experiments/016-mlx-direct-scoring/result.md` |
| Direct MLX 8-bit scoring is 1.381× with max probability drift 0.039; exact replication is 1.334× | E017 | `research/results/e017-mlx-8bit.json`, `research/results/e017-mlx-8bit-replication.json` | `research/experiments/017-mlx-8bit/result.md` |
| Fixed-shape suffix compilation is operationally flat | E018 | `research/results/e018-mlx-compile.json` | `research/experiments/018-mlx-compile/result.md` |
| MLX 48-token vision reduction is 1.185× but fails quality | E019 | `research/results/e019-mlx-vision-tokens.json` | `research/experiments/019-mlx-vision-tokens/result.md` |
| Untrained decoder exits expose speed but fail probability/decision gates | E020, E021 | `research/results/e020-mlx-depth.json`, `research/results/e021-mlx-depth.json` | `research/experiments/020-decoder-depth/result.md`, `research/experiments/021-shallow-depth/result.md` |

## Claims intentionally excluded from the main evidence table

- The 121 ms repeated-image and approximately 301 ms rotating-image numbers are operational smoke tests, not preregistered experiments.
- No real-camera accuracy or event-recall claim is made.
- No claim is made that 2B uncertainty predicts when 4B is necessary.
- No Core ML, Neural Engine, power, or sustained-thermal result has been measured. E017 establishes fixed-suite statement-scoring parity within the declared bound, not broad application accuracy.
- No result is claimed for CUDA or hardware other than the recorded Apple M5 system.

## Release audit

Before publishing a paper revision:

1. Re-run every command in `docs/REPRODUCIBILITY.md` from a clean checkout.
2. Verify aggregate hashes or archive the exact release tag.
3. Confirm every table value against the linked JSON.
4. Resolve any mismatch in favor of the artifact and document the correction.
5. Freeze the Glance commit, model revisions, Speedlab tag, OS, Python, Node, PyTorch, Transformers, and browser versions.
