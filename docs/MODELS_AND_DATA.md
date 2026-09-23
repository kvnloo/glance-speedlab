# Models, data, and licenses

This repository does not include model weights, camera frames, or a benchmark dataset.

## Glance

Speedlab depends on [Glance](https://github.com/yoheinakajima/glance) through a local source checkout. Glance has its own license and dependency policy. Pin the commit recorded by an experiment when reproducing results.

## Models

The committed experiments identify exact model IDs and revisions:

| Tier | Model | Revision |
| --- | --- | --- |
| 2B | `Qwen/Qwen3-VL-2B-Instruct` | `89644892e4d85e24eaac8bacfd4f463576704203` |
| 4B | `Qwen/Qwen3-VL-4B-Instruct` | `ebb281ec70b05090aa6165b016eac8ec08e71b17` |
| MLX 2B 4-bit | `mlx-community/Qwen3-VL-2B-Instruct-4bit` | `9c4f5209e57b31f4b9dfba735de3fb983739c9cc` |
| MLX 2B 8-bit | `mlx-community/Qwen3-VL-2B-Instruct-8bit` | `b0338e0e843d8e1befe873d144b81fefdc47efa6` |

Weights are downloaded and cached by the Glance/Hugging Face or MLX toolchain; they are not redistributed here. The live candidate uses the pinned MLX 8-bit row. Review each model card and license before use or redistribution.

## Fixed images

Model guardrails use `samples/dog.jpg`, `samples/receipt.jpg`, and `samples/invoice.jpg` from the pinned Glance checkout. Some scripts derive temporary 320 px JPEG fixtures under ignored `research/runs/`. Consult Glance for the source and licensing of those sample assets.

## Camera data

The live application does not persist frames. Optional telemetry stores only timing and experiment configuration. Contributors must not commit camera frames or personally identifying visual data.

## Aggregate artifacts

Files in `research/results/` contain summarized timings, model revisions, hardware descriptions, and guardrail outcomes. Detailed raw rows remain ignored so they can be regenerated locally without publishing machine-specific paths or accidental sensitive data.
