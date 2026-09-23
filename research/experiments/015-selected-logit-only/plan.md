# E015 plan — selected-logit-only statement scoring

## Hypothesis

Glance already computes the float32 logits needed for its yes/no statement score before projecting the same hidden states over the full 151,936-token vocabulary. Omitting that second projection when statement `off_mass` is not requested will lower scoring p50 by at least 5% without changing any decision logit or answer probability.

## Protocol

- Hardware: Apple M5, 10-core GPU, 32 GB unified memory.
- Model: `Qwen/Qwen3-VL-2B-Instruct@89644892e4d85e24eaac8bacfd4f463576704203`, float16 MPS.
- Glance base: `3b5205429e153e3c206503409a9e9d5c2f20ee73` plus the E015 opt-in flag.
- Image configuration: existing 320 px, quality-60 dog, receipt, and invoice fixtures; 128-token budget.
- Scoring configuration: prefix sharing enabled, suffix batch 16, independent statement scoring.
- Compare reference normalization with `compute_statement_off_mass=false` in one loaded process. Prime the exact-image prefix before each order-rotated pair so both measured arms are prefix-cache hits.
- Primary workload: four questions totaling nine candidate statements, ten measured pairs per image after two warmup pairs.
- Secondary workload: one four-way question, ten measured pairs on the dog fixture.

## Metrics and guardrail

- Primary metric: paired model scoring p50; secondary total/wall p50 and p95.
- Every statement `z`, returned decision, and answer probability must be exactly equal. The selected arm must expose statement `off_mass` as unavailable (`null`), never as zero.
- Keep the path only if score p50 improves by at least 5% without a p95 regression greater than 5%.

## Reproduction

```bash
"$GLANCE_CORE/.venv/bin/python" scripts/run-selected-logit-experiment.py
```

Detailed rows are written under ignored `research/runs/`; the privacy-safe aggregate is written to `research/results/e015-selected-logit.json`.
