# E014 — MLX vision and prompt caching

## Hypothesis

MLX-VLM's reusable vision-feature and prompt/KV caches will reduce exact-image Qwen3-VL-2B 4-bit latency by at least 5% and may close the 144.1 ms versus 79.6 ms gap measured between uncached MLX and Glance cache hits in E013.

## Motivation

Husky reports cold, cached, and continued-chat latency separately and attributes part of its first-token advantage to retained conversation state. MLX-VLM's pinned source exposes both `VisionFeatureCache` and `PromptCacheState`, but E013 passed neither and therefore regenerated the visual prefix on every call.

## Protocol

- Keep one loaded model and one fixed 320 px quality-60 dog image.
- Run no-cache, vision-cache-only, vision-plus-prompt-cache, and memory-only automatic-prefix-cache arms; instantiate fresh cache objects per arm.
- Use two warmups and at least ten measured identical prompts per arm.
- Record wall latency, prompt/generation throughput, cached-token count, peak memory, normalized label, and cache size.
- Use APC's default 16-token block first. If it records internal matches but cannot restore a media-safe prefix, run one diagnostic 4-token-block arm so a checkpoint can fall between the image tokens and the final text suffix; report both rather than silently replacing the default.
- Separately measure a continued-chat second turn. Populate `PromptCacheState` with a first image question, append a text-only yes/no question to that exact history, and compare the cached second turn with the same full second-turn prompt run cold. Use fresh state per pair and alternate arm order.
- Do not compare this repeated-image result to fresh-camera latency as if the workloads were interchangeable.

## Guardrail and stopping rule

Every measured output must normalize to `animal photo`. Stop after the complete three-arm run or a reproducible cache-correctness failure. Require at least 5% lower p50 than uncached MLX for a positive cache result.
