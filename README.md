# Glance Speedlab

Glance Speedlab is a local-first research harness for making live-camera vision-language inference faster—and for keeping an honest record of what did and did not work.

It pairs a deliberately small browser application with [Glance](https://github.com/yoheinakajima/glance), a local typed-decision layer over open vision-language models. The application captures the newest camera frame only when the model is ready, sends one native multi-question request, and reports capture, transport, image-prefix, scoring, and full-loop latency separately.

This is a research prototype, not a production monitoring system. The published measurements currently cover one Apple M5 laptop, pinned Qwen3-VL-2B/4B revisions, and a small fixed guardrail suite.

## What we found

| Intervention | Measured outcome | Decision |
| --- | --- | --- |
| Native multi-question request | 2.405× faster than four cold sequential requests | Keep |
| Qwen3-VL-2B instead of 4B | 2.994× faster; only 83.3% per-question decision agreement | Fast tier only |
| 4B at 48 image tokens | 1.092× faster with decision parity; probability drift 0.130 | Promising, guardrail failed |
| MLX 4-bit vs MPS FP16 on new frames | 1.417× faster with all three coarse labels correct | Build Glance-compatible MLX scorer |
| MLX continued-chat prompt cache | 2.048× faster, 188.4→92.0 ms with 104 reused tokens | Useful for stable-image chat, not yet standalone camera calls |
| Selected-logit-only readout | Exact outputs, but only 3.9% faster on nine statements | Reverted; suffix transformer dominates |
| Direct MLX 8-bit statement scorer | 1.381× faster; 84/84 decisions; max probability drift 0.039 | Available as opt-in local backend |
| Direct MLX 4-bit statement scorer | 1.371× faster; max probability drift 0.361 | Reject 4-bit precision |
| Fixed-shape MLX suffix compilation | Exact outputs; only 0.6% p50 improvement | Keep eager execution |
| MLX 48-token vision cap | 1.185× faster; changed tone; max drift 0.411 | Reject uniform token reduction |
| 24-layer untrained exit | 1.125× faster; decisions held; max drift 0.207 | Reject; train a decision head |
| 224 vs 320 px capture | 0.999×; quality guardrail failed | Keep 320 px |
| Base64 and JSON | At most 0.1 ms p95 at 320 px | Ignore for now |
| Suffix batch 4/8/16/32 | 16 and 32 were flat; 4/8 slower | Keep 16 |
| Letter-choice scoring | Fewer passes, but no latency win and worse stability | Keep independent |
| Temporal reuse, synthetic | 95.1% fewer inference triggers at threshold 4 | Experimental pending camera labels |

The main lesson is that model computation dominates. Browser micro-optimizations were useful for cleanliness, but model size, native batching, and avoiding redundant inference moved the system materially. See the [technical paper draft](paper/PAPER.md) and [complete findings](research/FINDINGS.md).

The newest MLX result closes the earlier protocol gap. The candidate renders Glance's exact statement prompts, shares one multimodal prefix, batches the suffixes, and computes the same yes/no token margins without autoregressive text generation. The pinned 8-bit checkpoint passed the fixed guardrail and is available in the UI; it remains opt-in because the evidence still covers only one machine and a small fixture suite.

## Choose a local backend

Speedlab keeps the reference and candidate paths side by side:

| Path | Best for | Hardware | Launch |
| --- | --- | --- | --- |
| Glance + PyTorch MPS | Reproduction and compatibility reference | A Glance-supported machine; measurements here use Apple Silicon | `pnpm launch` |
| 8-bit MLX direct scorer | Lowest accepted fresh-frame latency in this study | Apple Silicon; tested on an M5 with 32 GB, 16 GB or more recommended | `pnpm launch:mlx` |

The MLX path uses Qwen3-VL-2B at 8-bit precision. In E017 it reduced fresh nine-statement median latency by 27.6% (358.5→259.6 ms); an exact replication measured 25.0% (281.7→211.3 ms). It matched all 84 fixed-suite decisions and stayed within 0.039 maximum probability drift, but the suite is small and covers one machine. Treat it as an experimental Apple-specific alternative, not a general replacement for Glance.

The accepted scorer has also been [upstreamed into Glance](https://github.com/yoheinakajima/glance/pull/1) as a pinned,
optional experimental runtime. From a current Glance source checkout, the same native Python, CLI and server APIs work with:

```bash
uv sync --extra mlx
uv run glance ask photo.jpg "Is there a dog?" --backend mlx
uv run glance serve --backend mlx --preload vlm
```

That packaged path additionally supports letter choices, ratings, context and one to four images. Speedlab keeps its smaller
adapter because it is useful for live A/B testing and preserves the exact E017 experiment implementation.

## Quick start

### Requirements

- macOS on Apple Silicon for the measured configuration; other Glance-supported devices may work but are not claimed here
- Node.js 22 or newer
- pnpm 11
- Python 3.11 and `uv` for a source checkout of Glance
- A camera-enabled browser
- Approximately 9 GB for the default 4B weights, less for 2B
- Approximately 2.7 GB more for the optional pinned MLX 8-bit checkpoint

Keep the repositories next to each other, or set `GLANCE_CORE` to the Glance checkout:

```text
workspace/
├── glance/
└── glance-speedlab/
```

Prepare Glance and cache the model before starting its offline local server:

```bash
git clone https://github.com/yoheinakajima/glance.git
cd glance
uv sync
uv run glance doctor --json
uv run glance ask samples/dog.jpg "Is there a dog?"
```

Then, from this repository:

```bash
corepack enable
pnpm install --frozen-lockfile
cp .env.example .env
pnpm launch
```

Open <http://127.0.0.1:8787>. Do not open `src/web/index.html` as a `file://` page; camera permissions and API routing require the local HTTP server.

Everything binds to loopback by default. Camera frames remain in memory and are sent only to the selected local inference backend. Metrics are written only when “Record timing metadata” is enabled, and recorded rows contain configuration and timing metadata—not frames.

### Apple Silicon: launch the 8-bit MLX scorer

Create the ignored, disposable MLX environment once:

```bash
uv venv research/runs/e013-venv --python 3.11
uv pip install --python research/runs/e013-venv/bin/python -r requirements-mlx.txt
```

Then launch the UI, the Glance reference, and the MLX candidate together:

```bash
pnpm launch:mlx
```

Open <http://127.0.0.1:8787> and choose **MLX 8-bit** in the backend control. The first launch downloads the pinned 2B checkpoint (approximately 2.7 GB); subsequent loads use the local model cache. The adapter binds to `127.0.0.1:8079`, accepts only independent scoring, never writes frames, and imports the same scorer used by E016/E017. Switch back to **Glance** in the same UI for an immediate reference comparison.

## Test a model profile

Per-request controls such as question count, choice scoring, capture size, JPEG quality, and temporal reuse are available in the UI. Model-tier changes require a fresh model load:

```bash
pnpm launch:2b
pnpm launch:4b
pnpm launch -- --tier 4b --tokens 48 --suffix-batch 16
```

The UI reports the tier, token cap, and prefix-cache state actually loaded. If another profile already owns port 8077, the launcher stops with an error rather than silently running a different configuration.

The 2B and 48-token profiles are experimental. Neither passed every fixed quality guardrail.

## Benchmark

With the local service running:

```bash
pnpm bench -- --image /absolute/path/to/image.jpg --warmup 3 --iterations 20
```

The command writes machine-readable JSON to stdout and progress to stderr:

```bash
pnpm bench -- --image /absolute/path/to/image.jpg --warmup 3 --iterations 20 \
  > research/runs/local-baseline.json
```

Repeated still images exercise Glance’s exact-image prefix cache. They are not a substitute for fresh-frame camera latency. For comparable research runs, follow [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Research workflow

Every performance change begins with a preregistered experiment:

```bash
pnpm experiment:new -- short-slug
```

Before implementation, record the hypothesis, primary metric, quality guardrail, hardware, model revision, and stopping rule. Detailed rows belong in ignored `research/runs/`; privacy-reviewed aggregates and interpretations belong in version control.

Key research files:

- [Experiment registry](research/EXPERIMENTS.md)
- [Findings](research/FINDINGS.md)
- [Hypotheses](research/HYPOTHESES.md)
- [Decision log](research/DECISIONS.md)
- [Reproducibility guide](docs/REPRODUCIBILITY.md)
- [Models and data](docs/MODELS_AND_DATA.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Paper draft](paper/PAPER.md)
- [Related systems](research/RELATED_WORK.md)

## Repository map

```text
src/web/                 camera capture, scheduler, UI, client telemetry
src/server/              same-origin gateway and opt-in JSONL metric sink
src/mlx_backend/         loopback adapter for the pinned MLX direct scorer
scripts/                 launchers, deterministic benchmarks, summaries
research/experiments/    preregistrations and per-experiment interpretations
research/results/        committed aggregate artifacts
research/runs/           ignored raw local rows; never commit camera frames
paper/                   technical-paper draft and artifact notes
docs/                    architecture, reproduction, and upstream candidates
test/                    protocol and privacy-boundary tests
```

## Development

```bash
pnpm install --frozen-lockfile
pnpm check
```

For split-process development, start Glance separately, then run `pnpm dev` and `pnpm dev:web`. See [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for the full commands.

## Contributing and citation

Experiments, negative results, and reproducibility fixes are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Please report security or privacy issues according to [SECURITY.md](SECURITY.md).

If this repository informs research, use [CITATION.cff](CITATION.cff). Code is available under the [MIT License](LICENSE). Model weights and the Glance dependency retain their own licenses.
