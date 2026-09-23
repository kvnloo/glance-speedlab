# E001 result — Resolution

Rejected. 224 px was effectively identical in speed to 320 px (0.999×), while decision agreement fell to 66.7% and maximum probability drift reached 0.856. The fixed model image-token budget explains why fewer browser pixels did not buy model latency.

Generated from the aggregate artifact `research/results/model-experiments.json`; detailed paired rows remain ignored.

```json
{
  "224": {
    "wall_ms": {
      "n": 15,
      "min": 519.015,
      "p50": 525.209,
      "p90": 537.587,
      "p95": 539.412,
      "max": 539.412,
      "mean": 527.34
    },
    "model_total_ms": {
      "n": 15,
      "min": 519,
      "p50": 525,
      "p90": 537,
      "p95": 539,
      "max": 539,
      "mean": 527.067
    },
    "prefix_ms": {
      "n": 15,
      "min": 196,
      "p50": 201,
      "p90": 209,
      "p95": 209,
      "max": 209,
      "mean": 201.467
    },
    "score_ms": {
      "n": 15,
      "min": 321,
      "p50": 324,
      "p90": 329,
      "p95": 331,
      "max": 331,
      "mean": 324.733
    },
    "input_bytes": {
      "n": 15,
      "min": 3509,
      "p50": 3510,
      "p90": 5688,
      "p95": 5688,
      "max": 5688,
      "mean": 4235.667
    }
  },
  "320": {
    "wall_ms": {
      "n": 15,
      "min": 520.995,
      "p50": 524.864,
      "p90": 530.132,
      "p95": 565.411,
      "max": 565.411,
      "mean": 527.803
    },
    "model_total_ms": {
      "n": 15,
      "min": 521,
      "p50": 524,
      "p90": 530,
      "p95": 565,
      "max": 565,
      "mean": 527.267
    },
    "prefix_ms": {
      "n": 15,
      "min": 198,
      "p50": 201,
      "p90": 203,
      "p95": 226,
      "max": 226,
      "mean": 202.2
    },
    "score_ms": {
      "n": 15,
      "min": 322,
      "p50": 323,
      "p90": 326,
      "p95": 337,
      "max": 337,
      "mean": 324.467
    },
    "input_bytes": {
      "n": 15,
      "min": 6025,
      "p50": 6488,
      "p90": 9770,
      "p95": 9770,
      "max": 9770,
      "mean": 7427.667
    }
  },
  "guardrail": {
    "decision_agreement": 0.6666666666666666,
    "max_probability_delta": 0.856039,
    "passed": false
  },
  "speedup_224_vs_320": 0.9993
}
```
