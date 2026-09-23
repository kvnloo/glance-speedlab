# E006 result — Question order

Rejected as an optimization. Forward versus reverse order differed by only -0.204% at p50 and produced exactly identical probabilities. Canonical statement sorting in Glance makes caller order irrelevant.

Generated from the aggregate artifact `research/results/model-experiments.json`; detailed paired rows remain ignored.

```json
{
  "forward": {
    "wall_ms": {
      "n": 30,
      "min": 522.871,
      "p50": 527.852,
      "p90": 530.56,
      "p95": 539.799,
      "max": 544.267,
      "mean": 528.366
    },
    "model_total_ms": {
      "n": 30,
      "min": 522,
      "p50": 527,
      "p90": 530,
      "p95": 539,
      "max": 543,
      "mean": 527.467
    },
    "prefix_ms": {
      "n": 30,
      "min": 199,
      "p50": 202,
      "p90": 204,
      "p95": 210,
      "max": 211,
      "mean": 202.467
    },
    "score_ms": {
      "n": 30,
      "min": 322,
      "p50": 324.5,
      "p90": 325,
      "p95": 327,
      "max": 333,
      "mean": 324.333
    }
  },
  "reverse": {
    "wall_ms": {
      "n": 30,
      "min": 522.452,
      "p50": 528.933,
      "p90": 531.736,
      "p95": 551.467,
      "max": 580.06,
      "mean": 530.554
    },
    "model_total_ms": {
      "n": 30,
      "min": 522,
      "p50": 527.5,
      "p90": 531,
      "p95": 551,
      "max": 579,
      "mean": 529.433
    },
    "prefix_ms": {
      "n": 30,
      "min": 199,
      "p50": 202,
      "p90": 204,
      "p95": 207,
      "max": 222,
      "mean": 202.767
    },
    "score_ms": {
      "n": 30,
      "min": 321,
      "p50": 324,
      "p90": 326,
      "p95": 327,
      "max": 328,
      "mean": 324.067
    }
  },
  "guardrail": {
    "decision_agreement": 1,
    "max_probability_delta": 0,
    "passed": true
  },
  "forward_vs_reverse_delta_pct": -0.204
}
```
