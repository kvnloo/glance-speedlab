# Upstream candidates

This file prevents useful general work from getting stranded in the lab while keeping speculative experiments out of stable repositories.

## Release decision for v0.1.0

- **Already global in Glance:** direct logit scoring, shared image-prefix work, and one native request containing every question about a frame. Speedlab measured the existing multi-question path at 2.405× faster than four cold sequential requests; there is no new core patch to claim for that result.
- **Keep in Speedlab for now:** the 8-bit MLX scorer, backend A/B UI, latest-frame scheduler, detailed telemetry, and temporal-reuse control. The MLX result passed the declared fixed-suite gate, but one machine and 84 decisions are not enough evidence to add a second stable runtime to Glance.
- **Do not upstream:** 4-bit scoring, uniform sub-floor token caps, fixed-shape compilation, selected-logit-only output, or untrained decoder truncation. These were either below materiality or failed a decision/probability guardrail.
- **Next promotion gate:** run the 8-bit scorer on a larger labeled suite, sustained load, multiple Apple Silicon generations, OCR/fine-detail slices, and calibrated probability metrics. If it passes, move the scorer—not the Speedlab UI or experiment machinery—behind an explicit experimental backend in `glance`.

The first upstream contribution from this release is documentation: the main Glance site links to the versioned Speedlab report and keeps its claims scoped. Runtime code remains in the lab until the larger gate is met.

| Candidate | Likely home | Promotion evidence | Status |
| --- | --- | --- | --- |
| Reusable persistent camera encoder | `glance-vlm-demos` | Geometry guardrail passed; no p50/p95 speed win, but two allocations/frame avoided | Hygiene candidate, not a speed claim |
| Latest-frame, one-in-flight scheduler | `glance-vlm-demos` | No stale-frame growth and equal/better completed FPS | Lab only; live validation pending |
| Model timing passthrough | `glance-vlm-demos` | Contract agreed; fields stable across model backends | Lab only |
| Faster image/prefix implementation | `glance` | Quality guardrail passes and statistically credible model latency win | Not started |
| Binary image transport | Both | JSON/base64 is a material share of latency at target cadence | Rejected at current sizes (≤0.1 ms p95) |
| Native multi-question batching | `glance-vlm-demos` | 2.405× cold-request speedup; exact decisions within tolerance | Confirmed; preserve as default |
| Temporal reuse gate | `glance-vlm-demos` | Real-camera replication of synthetic 95.1% trigger reduction | Experimental toggle only |
| Aspect-ratio-safe low token caps | `glance` | E012: budget 64 fails on all tall-receipt attempts because processor rounding emits 77 tokens | Bug/UX candidate; define whether caps round up or resize again |
| 2B→4B uncertainty cascade | `glance` or this lab | E011: 2B is 2.994× faster but fixed quality guardrail fails | Research candidate; needs coverage-risk protocol |
| Loaded model profile in demo health | `glance-vlm-demos` | Prevents runs from silently mixing tier/token configurations | Implemented locally by joining `/healthz` and `/v1/models` |
| MLX 8-bit direct backend | `glance` after larger parity/sustained testing; otherwise this lab | E017: 1.381× fresh-frame speedup, 84/84 decisions, max probability drift 0.039 | Implemented as opt-in Speedlab backend |
| MLX selected-row statement scorer | `glance` | E016/E017: same prompts/margins, one multimodal prefix, batched suffixes, selected token rows | Upstream design candidate; preserve diagnostics contract |
| Uniform sub-floor MLX token caps | this lab only | E019: 15.6% faster at 40–45 tokens, but changed tone and drifted 0.411 | Rejected |
| Untrained decoder truncation | this lab only | E020/E021: 6–22% faster, but every 20–27-layer arm failed probability or decision gates | Rejected; trained head required |

Promotion should be a small, isolated commit with benchmark evidence and no Speedlab-specific UI or research machinery.
