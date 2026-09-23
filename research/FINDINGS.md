# Round-one findings

Seven preregistered experiments separate the useful work from plausible-sounding micro-optimizations.

| Experiment | Result | Decision |
| --- | --- | --- |
| Resolution 224 vs 320 | 0.999×; guardrail failed | Keep 320; attack the model token budget instead |
| JPEG 40 vs 60/90 | Smaller payload, stable answers, no material latency change | Keep 60 default; Q40 is bandwidth-only |
| Four-question native batch | 2.405× faster than four cold requests | Confirmed default architecture |
| Persistent canvas | Same p50/p95; avoids two allocations/frame | Retain as hygiene, make no speed claim |
| Base64 + JSON | 0.0 ms p50 / 0.1 ms p95 at 320 px | Stop optimizing transport for now |
| Question order | −0.204%; exact probability parity | Ignore order; Glance canonicalizes statements |
| Temporal reuse | 95.1% fewer triggers at threshold 4; synthetic recall passed | Experimental toggle, pending real-camera validation |

The dominant measured latency is model work: roughly 201–203 ms prefix plus 323–325 ms score for a cold four-question request on the Apple M5. Browser and transport work remain below materiality.

## Round-two findings

| Experiment | Result | Decision |
| --- | --- | --- |
| 128/192/256/768 token cap | All arms realized 70–80 tokens at 320 px; 128 vs 768 was 0.997× with exact output parity | Reject H08; test below the realized floor |
| Suffix batch 4/8/16/32 | Batch 16 p50 805 ms; 32 was 803 ms, while 8 and 4 rose to 960 and 1,024 ms | Keep 16; 32 is not a material win |
| Letter choice scoring | One rotation used 2 rather than 7 passes but was 0.974× and drifted by 0.318; four rotations was slower and changed decisions | Keep independent |
| Qwen3-VL-2B tier | 267 ms vs 799 ms p50 (2.994×), but 83.3% per-question agreement and max probability drift 0.746 | Strong fast tier, not a drop-in replacement; test uncertainty escalation |
| Sub-128 token caps | 4B/48 was 1.092× with decision parity but delta 0.130; 2B/48 was 1.121× and changed one decision; 64 failed on the tall receipt | No safe fixed default; retain 128 and evaluate 4B/48 on a larger labeled suite |
| MLX 4-bit backend | 144.1 ms vs 204.2 ms fresh-frame p50 (1.417×); all coarse labels correct; 1.81× slower than Glance cache hits | Prototype native Glance scoring in MLX; do not claim protocol parity yet |
| MLX caches | Continued chat reused 104 tokens and improved 188.4→92.0 ms (2.048×); standalone vision/APC restored zero tokens | Use prompt cache for stable-image chat; implement Qwen media-prefix caching for camera calls |
| Selected-logit-only readout | Exact output parity and 7–8 ms saved; nine-statement score p50 improved only 3.9%, while four statements improved 7.7% | Revert under the primary stopping rule; suffix transformer work is the larger target |
| Native MLX 4-bit statement scoring | 27.0% faster and all decisions matched; probability drift 0.361 | Mechanism confirmed, precision rejected |
| Native MLX 8-bit statement scoring | 358.5→259.6 ms p50 (1.381×); 84/84 decisions; max probability drift 0.039 | First viable opt-in backend candidate |
| Fixed-shape `mx.compile` suffix | Exact outputs; 0.6% p50 improvement and slightly worse p95/cache-copy tails | Reject; eager path stays simpler |
| MLX 48-token vision cap | 15.6% faster; tone decision changed; max drift 0.411 | Reject uniform token reduction |
| Untrained decoder exits | 24 layers was 11.1% faster with labels intact but 0.207 drift; 26 layers was 6.1% faster but changed a decision | Stop truncation; train an intermediate head |

The token-cap null result corrects the earlier mechanism assumption: at the live 320 px input size, the image processor is already below a 128-token cap. E012 crossed the floor, but every faster arm failed the preregistered guardrail. The interesting near miss is 4B/48: all fixed decisions held at 9.2% lower median latency, while maximum probability drift was 0.130 against the 0.10 limit.

E013 changed the backend priority from speculative to supported. MLX 4-bit reduced uncached new-frame latency by 29.4% on the three fixed images and kept the expected coarse classes. It did not beat Glance's exact-image prefix-cache path, and its generated-label protocol was not equivalent to Glance's probability scoring. That limitation directly motivated the E016/E017 statement scorer rather than a UI replacement based on free generation.

E014 confirms that “cached MLX” must name the cache and request topology. A stable, explicitly encoded multimodal conversation reused 104 prompt tokens and halved second-turn latency. The same cache objects did nothing for standalone Qwen3-VL calls: the generic vision cache had no model hook, the per-conversation cache had no appended suffix, and APC matched blocks but restored none because the reusable blocks contained media tokens. Husky's cache framing is relevant, while its long-decode speculative gains are not directly transferable to Glance's short direct-scoring workload.

E015 bounds one apparent shortcut. The complete 151,936-token normalization used by `off_mass` costs a repeatable 7–8 ms, and removing it leaves the actual Glance decision math bit-identical. That fixed saving clears 5% for a four-statement request but not for the preregistered nine-statement request, where the 28-layer suffix computation dominates. The implementation was reverted; future work should reduce suffix tokens, layers, memory traffic, or backend cost.

E016 and E017 close the protocol gap left by the initial generated-label MLX test. A direct scorer now renders Glance's statements, shares the complete multimodal prefix, batches suffixes, and projects only the eight selected yes/no token rows. Four-bit execution retained a 27.0% speed advantage but moved probabilities too far. The pinned 8-bit checkpoint was both faster and substantially closer: 27.6% lower fresh-frame p50, exact measured decisions, and 0.039 maximum probability drift. It is exposed as an opt-in local backend, while Glance remains the reference.

E018–E021 narrow the remaining backend work. Explicitly compiling the fixed suffix was operationally flat, and Qwen's eager multimodal preparation prevented compiling the prefix unchanged. Uniformly reducing vision tokens exposed a 54 ms prefix opportunity but changed answers. Removing language layers produced nearly proportional gains, yet even one removed layer caused 0.242 probability drift; no untrained depth passed both speed and quality. The evidence now points toward trained token selection, an intermediate decision head/distillation, or model-specific kernels—not more configuration toggles.

Raw detailed rows are ignored in `research/runs/`. Privacy-reviewed aggregates are committed under `research/results/`; each experiment directory contains its plan and interpretation. The paper’s exact claim-to-artifact map is `paper/ARTIFACTS.md`.
