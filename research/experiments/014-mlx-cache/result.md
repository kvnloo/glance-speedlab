# E014 result — MLX vision and prompt caching

## Interpretation

Mixed result. MLX prompt caching works and is valuable for a correctly shaped continued conversation: a second turn with an explicit, stable first-turn image prefix reused 104 tokens and fell from 188.4 to 92.0 ms p50, a 2.048× speedup and 51.2% latency reduction. Every response remained `yes`. This is the workload most comparable to Husky's continued-chat time-to-first-word comparison.

It does not yet accelerate Speedlab's standalone repeated camera request. `VisionFeatureCache` remained empty because the Qwen3-VL model wrapper does not expose the `encode_image` or `encode_images` hook that MLX-VLM's generic cache checks. `PromptCacheState` cannot reuse an identical complete standalone prompt because it requires a proper appended suffix. Automatic prefix caching found block matches internally but restored zero tokens: block prefixes containing media tokens are deliberately rejected by the current block-cache path. APC bookkeeping therefore regressed p50 by 22–23%.

The continued-chat result is within roughly 15% of E013's 79.6 ms Glance exact-image cache-hit p50, but it is not a paired or protocol-equivalent comparison. Glance scored a standalone four-way choice, while MLX generated `yes` for an appended question.

## Template finding

An implicit `num_images=1` chat template attaches the image to the newest user message. Across turns this moves the image token and destroys the common prefix. Encoding the first user message with an explicit image content item keeps the multimodal prefix stable and enables the 104-token cache hit. Any MLX chat integration must preserve that message topology.

## Decision

- Use `PromptCacheState` for stable-image conversational sessions.
- Do not enable MLX-VLM's APC for standalone live-camera calls in its current form.
- Prototype Qwen3-VL vision-feature caching or a media-safe exact-prefix checkpoint before expecting cached MLX to accelerate the camera loop.
- Raw rows remain ignored in `research/runs/e014-mlx-cache.json`; the curated aggregate is `research/results/e014-mlx-cache.json`.
