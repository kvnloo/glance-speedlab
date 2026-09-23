# E013 result — Apple-native MLX 4-bit backend

## Interpretation

Promising backend result, not yet a drop-in Glance replacement. On 320 px JPEG fixtures, MLX 4-bit produced the expected coarse class for all three images at 144.1 ms end-to-end p50. The current PyTorch MPS/FP16 Glance path took 204.2 ms p50 when every request had a unique byte hash, so MLX was 1.417× faster, or 29.4% lower latency. Against exact-image Glance prefix-cache hits, however, MLX was 1.81× slower: 144.1 versus 79.6 ms.

The cache distinction is central for the live-camera use case. A unique JPEG COM segment changed Glance's original-byte hash while leaving decoded pixels unchanged; this forced fresh image-prefix work and produced a stable 125 ms prefix p50 plus 77 ms scoring p50. MLX regenerated the visual prefix on every request and reported 108 prompt tokens p50, 861 prompt tokens/s, 208 generated tokens/s, and 2.038 GB peak memory p50.

The registered coarse-label guardrail passed, but protocol parity was not tested. Glance directly scores four statements and returns probabilities; MLX greedily generated a two- or three-token label. The result therefore supports implementing native MLX statement scoring or a compatible local service, followed by probability and multi-question parity testing. It does not justify replacing Glance's current backend yet.

## Setup findings

- The maintained 4-bit checkpoint is 3.3 GB on disk and loaded from the local cache in 512 ms during the measured run.
- The isolated Python environment occupied 1.4 GB because Qwen3-VL's Hugging Face processor currently imports PyTorch and TorchVision even when MLX performs inference.
- Released `mlx-vlm==0.4.1` failed in the Qwen3-VL vision tower because `mx.repeat` received an MLX array rather than an integer repeat count. Pinned upstream commit `b5952d7c97da3cfc5014ff0a81bfe2e59d919cab` contains the compatibility fix and completed the run.
- Raw rows remain in ignored `research/runs/e013-mlx.json`; the privacy-reviewed aggregate is `research/results/e013-mlx.json`.

## Decision

Proceed with an MLX-native Glance scoring prototype in Speedlab. Preserve the current MPS implementation as the reference and retain its exact-image prefix cache. Do not upstream the backend until it reproduces native `noul` and `choice` probabilities, multi-question behavior, and quality guardrails.
