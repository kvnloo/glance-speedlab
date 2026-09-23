# Related systems and implications

## Husky model-specific inference

[Husky](https://husky.underdog.ai/) is Underdog's model-specific inference engine for its Woof 4B model. The published Apple M5 Max results report up to 730 decode tokens/s and up to 4.5× over MLX on a favorable function-edit workload. The more representative mechanism-level findings are narrower: exact-shape Metal kernels and pipelined submission improve ordinary writing modestly, while the largest gains come from verifying eight proposed tokens per weight read using prompt lookup or a trained draft model.

Husky's useful ideas for Speedlab are:

- report cold prefill, cached/continued latency, and decode throughput separately;
- specialize kernels and packed weight layout when one model is a durable product target;
- keep prefix state resident and preserve message topology so caches actually hit;
- fuse normalization, 4-bit unpacking, and matrix multiplication to reduce dispatch and memory traffic;
- use speculative verification only where multiple decoded tokens matter.

The headline result does not transfer directly. Husky runs one text-oriented Woof checkpoint on an M5 Max with 40 GPU cores; Speedlab uses Qwen3-VL on a base M5 and primarily scores short typed statements rather than generating long replies. Prompt-copy and draft-model speculation therefore have little leverage on Glance's current direct-scoring path. Model-shaped Metal kernels and media-prefix retention are relevant but would be a substantial, model-specific engineering program.

E014 applies Husky's cache measurement discipline locally. MLX reduced a valid continued VLM turn from 188.4 to 92.0 ms p50 when 104 prefix tokens were actually reused, but current MLX-VLM caches restored zero tokens for standalone repeated Qwen3-VL requests.
