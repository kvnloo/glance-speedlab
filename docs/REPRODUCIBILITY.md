# Reproducibility guide

This guide separates three workloads that are easy to confuse: browser-only microbenchmarks, fresh-image model experiments, and operational repeated-image smoke tests.

## 1. Pin the environment

The committed results were collected on:

- Apple M5, 32 GB unified memory
- macOS Darwin 26.6.2
- Node.js 26.5.0 for the latest operational smoke test; the project supports Node 22+
- Python 3.11.15
- PyTorch MPS, float16
- Glance commit `3b5205429e153e3c206503409a9e9d5c2f20ee73`
- Qwen3-VL-4B revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`
- Qwen3-VL-2B revision `89644892e4d85e24eaac8bacfd4f463576704203`

Clone Glance and check out the recorded commit when reproducing the paper tables:

```bash
git clone https://github.com/yoheinakajima/glance.git
cd glance
git checkout 3b5205429e153e3c206503409a9e9d5c2f20ee73
uv sync
uv run glance doctor --json
uv run glance ask samples/dog.jpg "Is there a dog?"
```

Set the checkout location for Speedlab:

```bash
export GLANCE_CORE=/absolute/path/to/glance
corepack enable
pnpm install --frozen-lockfile
pnpm check
```

Do not run the live Glance server concurrently with direct model experiments on memory-constrained hardware. Competing model instances can change latency or cause allocation failures.

## 2. Browser-only experiments

These experiments do not load a VLM. They use deterministic synthetic images to measure capture allocation, base64/JSON overhead, and temporal gating:

```bash
node scripts/run-browser-lab.mjs 525
node scripts/summarize-browser-experiments.mjs
```

The first command starts a temporary local browser lab on port 525. Aggregate results are written to `research/results/browser-experiments.json`; detailed local payloads remain ignored.

## 3. Round-one model experiments

E001, E002, E003, and E006 share one 4B model load:

```bash
"$GLANCE_CORE/.venv/bin/python" scripts/model_experiments.py
node scripts/summarize-model-experiments.mjs
```

The suite uses Glance’s `samples/dog.jpg`, `samples/receipt.jpg`, and `samples/invoice.jpg`. It derives controlled JPEG variants in a temporary directory. Two warmups precede measured repetitions.

## 4. Round-two model experiments

Token caps, suffix batch size, and choice scoring:

```bash
"$GLANCE_CORE/.venv/bin/python" scripts/run-next-model-experiments.py
```

The 2B/4B tier comparison must run both arms:

```bash
"$GLANCE_CORE/.venv/bin/python" scripts/run-model-tier-experiment.py --tier apple_8gb
"$GLANCE_CORE/.venv/bin/python" scripts/run-model-tier-experiment.py --tier apple_32gb
```

The sub-128 token sweep likewise runs both tiers:

```bash
"$GLANCE_CORE/.venv/bin/python" scripts/run-sub128-experiment.py --tier apple_8gb
"$GLANCE_CORE/.venv/bin/python" scripts/run-sub128-experiment.py --tier apple_32gb
```

Each script writes detailed paired rows under `research/runs/` and privacy-reviewed aggregate JSON under `research/results/`.

## 5. Apple-native MLX experiment

Keep the active 2B Glance service running, then create the disposable MLX environment and run E013:

```bash
uv venv research/runs/e013-venv --python 3.11
uv pip install --python research/runs/e013-venv/bin/python torch torchvision
uv pip install --python research/runs/e013-venv/bin/python -r requirements-mlx.txt
research/runs/e013-venv/bin/python scripts/run-mlx-experiment.py
research/runs/e013-venv/bin/python scripts/run-mlx-cache-experiment.py
```

The first script downloads the pinned 3.3 GB MLX checkpoint on its first run. It measures both Glance exact-image cache hits and pixel-identical requests with unique JPEG byte hashes. The second separates standalone vision/APC behavior from a valid continued-chat prompt-cache hit. Raw responses and rows remain ignored; committed aggregates are `research/results/e013-mlx.json` and `research/results/e014-mlx-cache.json`.

## 6. Direct MLX scoring and frontier experiments

Keep the pinned 2B Glance reference running for the direct-backend parity experiments:

```bash
research/runs/e013-venv/bin/python scripts/run-mlx-direct-experiment.py \
  --model mlx-community/Qwen3-VL-2B-Instruct-8bit \
  --revision b0338e0e843d8e1befe873d144b81fefdc47efa6 \
  --backend mlx-8bit-direct --experiment E017 \
  --raw research/runs/e017-mlx-8bit.json
```

E015's selected-logit implementation was intentionally reverted after missing its stopping threshold; its historical script requires the experimental Glance patch described in the plan and is not part of the clean-checkout command block. E016/E017 use the same direct scorer with pinned 4-bit and 8-bit checkpoints. E017 is the claim-bearing accepted backend artifact.

Stop the live MLX adapter before the following one-process frontier runs so a second model instance does not contend for Metal resources:

```bash
research/runs/e013-venv/bin/python scripts/run-mlx-compile-experiment.py
research/runs/e013-venv/bin/python scripts/run-mlx-vision-token-experiment.py
research/runs/e013-venv/bin/python scripts/run-mlx-depth-experiment.py
research/runs/e013-venv/bin/python scripts/run-mlx-depth-experiment.py \
  --depths 28 27 26 --experiment E021 --raw research/runs/e021-mlx-depth.json
```

These commands reproduce E018–E021. Absolute MLX latency varies with thermal and process history; the alternating, within-run ratios are the supported claims.

## 7. Live UI and operational benchmark

Start a known profile:

```bash
pnpm launch:4b
```

Open <http://127.0.0.1:8787>, confirm that the reported tier/token/cache profile is correct, and only then begin a camera run. Enable metric recording if the run should produce local JSONL.

To expose the accepted MLX 8-bit candidate beside the Glance reference:

```bash
pnpm launch:mlx
```

The backend selector resets the rolling measurement window and backend identity is written into every recorded row. The MLX service is loopback-only on port 8079 and processes image bytes in memory.

For an HTTP smoke test:

```bash
pnpm bench -- --image "$GLANCE_CORE/samples/dog.jpg" --warmup 3 --iterations 20
```

Important: after warmup, repeating one image normally produces prefix-cache hits. Report those numbers as cached repeated-image latency. A fresh-frame claim requires changing image hashes and showing nonzero prefix time.

## 8. Reporting rules

- Report p50 and p95, sample count, model prefix, model scoring, and wall time.
- Report realized image-token counts, not only configured caps.
- Compare paired/interleaved arms where practical.
- Keep warmup results separate.
- Treat a result as a speed improvement only at 5% or greater median improvement.
- Run the registered quality guardrail before adopting pixel, prompt, model, token, or scoring changes.
- Do not compare absolute latency across separate thermally or operationally different runs as if they were paired.
- A cached-image measurement is not a fresh-camera measurement.

## 9. Artifact integrity

Committed aggregate files contain no camera frames. Before committing a new artifact:

1. Inspect it for paths, credentials, user names, or image payloads.
2. Confirm model and Glance revisions are present.
3. Confirm raw rows remain under ignored `research/runs/`.
4. Add an interpretation beside the machine-readable aggregate.
5. Run `pnpm check` and `git diff --check`.
