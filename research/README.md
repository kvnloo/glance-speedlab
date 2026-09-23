# Research protocol

The aim is not merely a fast demo. It is a credible record of which interventions move latency and throughput, under what conditions, and at what quality cost.

## One experiment

1. Pre-register the claim in `EXPERIMENTS.md` and create a plan with `pnpm experiment:new -- slug`.
2. Record hardware, OS, browser, Glance version/commit, model revision, device/dtype, input size/quality, question set, warmup count, and sample count.
3. Save raw timing output in ignored `research/runs/`; commit only privacy-reviewed aggregate results.
4. Report median, p90, p95, dispersion/sample count, and model-native timing—not just the best run.
5. Run a quality guardrail on a fixed image/question set whenever pixels, model settings, prompts, or scoring change.
6. Write a null/negative result when the hypothesis fails. Explain likely causes without rewriting the hypothesis after seeing data.

## Suggested phases

- A: measurement integrity and stable baseline.
- B: browser capture/encoding and transport.
- C: request shape, batching, prefix reuse, and scheduling.
- D: model/backend changes in a branch of `glance`.
- E: accuracy/latency frontier, repeatability, and paper-grade ablations.

Timing improvements should be reported both in milliseconds and completed inferences per second. A faster component that does not improve the end-to-end loop may still be useful, but it is not an end-to-end speed win.
