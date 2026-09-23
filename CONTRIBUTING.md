# Contributing

Glance Speedlab welcomes reproducibility fixes, new backends, measured latency improvements, quality guardrails, and well-documented negative results.

## Before opening a pull request

1. Search existing experiments and hypotheses to avoid duplicating a completed test.
2. For performance work, create or update an entry in `research/EXPERIMENTS.md` before implementation.
3. State one primary hypothesis, the mechanism, primary metric, quality guardrail, environment, and stopping rule.
4. Keep detailed rows in ignored `research/runs/`; commit only privacy-reviewed aggregate artifacts.
5. Run `pnpm check` and `git diff --check`.

Start a new experiment with:

```bash
pnpm experiment:new -- short-slug
```

## Pull-request expectations

- Keep the local gateway thin and preserve native Glance request/response shapes.
- Avoid hosted or paid inference paths. This repository’s experiments are local by default.
- Never commit camera frames, credentials, model weights, personally identifying data, or raw user paths.
- Change one important variable at a time when practical.
- Report null and negative results with the same care as positive results.
- Separate measured evidence from interpretation and future hypotheses.
- Do not claim generality beyond the tested hardware, model revisions, input set, and tasks.

## Code style

The project intentionally has few runtime dependencies. Prefer small modules, explicit data shapes, monotonic timers, and reproducible command-line entry points. Add protocol tests when request fields or telemetry schemas change.

## Issues

Bug reports should include the browser, OS, Node version, Glance commit/version, loaded model profile, reproduction steps, and whether the image was repeated or fresh. Performance proposals should use the experiment issue template.

By participating, contributors agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
