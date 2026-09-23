# Decision log

## 2026-09-22 — Separate lab, native protocol

We created a fresh repository instead of restructuring the demo monorepo. Experimental telemetry, negative results, and speculative transport work belong here. Stable, general changes can later be promoted as isolated patches.

The lab sends native Glance request shapes through a thin local gateway. This keeps single- and multi-question behavior unified and preserves model timing fields.

## 2026-09-22 — Pull-based live scheduling

The next frame is captured only after the previous inference completes. This optimizes freshness and bounds memory. Parallel model requests are not useful against the current single-model engine lock and can make camera results stale.

## 2026-09-22 — Round-one optimization decisions

- Keep 320 px and JPEG quality 60 as defaults. Resolution 224 failed the quality guardrail without improving latency; quality 40 reduced bytes but not end-to-end time.
- Keep every enabled question in one native request. E003 measured a 2.405× p50 speedup over cold sequential requests with the answer guardrail intact.
- Keep persistent canvas reuse as allocation hygiene, without claiming a latency improvement.
- Do not pursue binary transport or question ordering at current model speeds; both are below materiality.
- Add threshold-4 temporal reuse as an off-by-default experimental toggle. Synthetic E007 passed, but default enablement waits for a labeled real-camera replication.

## 2026-09-23 — Round-two optimization decisions

- Keep suffix batch size 16 and independent choice scoring. Larger batching was flat; smaller batching and letter scoring regressed latency or quality.
- Do not describe a 128-token configuration as an optimization for 320 px camera frames: those fixtures already realize 70–80 tokens at every tested cap from 128 through 768.
- Treat Qwen3-VL-2B as an experimental fast tier, not a replacement default. Its 2.994× speedup is large enough to justify an uncertainty-gated cascade, but the fixed-suite quality guardrail failed.
- Keep 128 as the safe live token cap. Sub-128 caps are faster, but 32/48 failed probability or decision guardrails and 64 is invalid for some aspect ratios under the current processor rounding.
- Expose choice scoring and temporal-reuse cadence in the live UI, reset rolling windows on every setting change, and record the active choices in local telemetry.

## 2026-09-23 — Apple-native backend decision

- Continue MLX work in Speedlab. The pinned 4-bit Qwen3-VL-2B path reduced fresh-frame p50 from 204.2 to 144.1 ms and retained all three coarse labels.
- Do not replace Glance's backend or expose MLX as equivalent in the live UI yet. E013 used greedy label generation rather than Glance's direct probability scoring, and MLX was slower than Glance on exact-image prefix-cache hits.
- The next gate is native MLX statement scoring with `noul`/`choice` probability parity and one-prefix/many-question behavior. Only a backend that passes that gate becomes an upstream candidate.

## 2026-09-23 — MLX cache and Husky implications

- Use MLX `PromptCacheState` only when an image remains in an explicitly stable first-turn message and later turns append text. E014 measured a 2.048× second-turn speedup with 104 reused tokens.
- Do not treat the current `VisionFeatureCache` or APC toggles as live-camera optimizations for Qwen3-VL. They restored zero tokens in standalone calls and APC added 22–23% latency.
- Prioritize a Qwen-specific media-prefix cache before model-specific Metal kernels. Husky makes specialization credible, but its largest published gains depend on long generation, prompt copying, a trained draft, a different model, and M5 Max hardware.

## 2026-09-23 — Full-vocabulary diagnostic is not the main bottleneck

- E015 proved that `off_mass` normalization is separable from Glance's decision logits: removing it preserved every z, probability, and decision exactly.
- Do not merge the selected-only path under the preregistered rule. It removed 7–8 ms but improved the primary nine-statement score p50 only 3.9%, below the 5% threshold.
- Target the suffix transformer next. Native MLX scoring, fixed shapes, shared suffix structure, and eventually fused quantized kernels have substantially more headroom than another output-head micro-optimization.

## 2026-09-23 — Promote MLX 8-bit as an opt-in candidate

- E016 proved that direct Glance-compatible statement scoring retains MLX's speed advantage, but reject the 4-bit checkpoint because maximum probability drift was 0.361.
- E017's pinned 8-bit checkpoint passes the registered fixed-suite gate: 1.381× fresh-frame speedup, all 84 measured question decisions matched, and maximum probability drift was 0.039.
- Expose MLX 8-bit in Speedlab, not as a silent replacement in Glance. The live service uses the exact benchmark scorer, binds to loopback, keeps frames in memory, and records backend identity per sample.
- Keep provenance out of `state.context`: Glance treats context as prompt content. Backend/source identity belongs in gateway telemetry, otherwise the live Glance prompt no longer matches the validated MLX scorer.
- Keep Glance FP16 as the default until a larger labeled real-camera suite, sustained-load behavior, cancellation, and upstream API design are validated.

## 2026-09-23 — Stop unsafe backend shortcuts

- Keep eager MLX execution. E018's compiled suffix improved p50 only 0.6%; the multimodal prefix cannot be transformed unchanged because Qwen eagerly evaluates deep-stack features.
- Keep the default 70–80 realized vision tokens. A 48-token area cap saved 15.6% but changed tone and drifted by 0.411.
- Do not expose raw decoder-depth toggles. Every tested 20–27-layer exit failed the probability or decision gate; the next version must train an intermediate head or distill full-depth margins.
- Do not prioritize the selected output head or KV batch copy: together they occupy only a few milliseconds on the accepted backend. Prefix/vision and the language stack remain the meaningful targets.
