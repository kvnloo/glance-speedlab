# E003 result — Native batching

Confirmed. One cold four-question request was 2.405× faster than four cold single requests (529.8 ms versus 1274.0 ms p50), with 100% decision agreement and only 0.00125 maximum probability drift. This remains the default architecture.

Generated from the aggregate artifact `research/results/model-experiments.json`; detailed paired rows remain ignored.

```json
{
  "batch": {
    "wall_ms": {
      "n": 21,
      "min": 524.892,
      "p50": 529.815,
      "p90": 539.455,
      "p95": 543.123,
      "max": 544.116,
      "mean": 530.577
    },
    "model_total_ms": {
      "n": 21,
      "min": 524,
      "p50": 529,
      "p90": 539,
      "p95": 541,
      "max": 543,
      "mean": 529.667
    },
    "prefix_ms": {
      "n": 21,
      "min": 200,
      "p50": 203,
      "p90": 212,
      "p95": 213,
      "max": 214,
      "mean": 203.714
    },
    "score_ms": {
      "n": 21,
      "min": 323,
      "p50": 325,
      "p90": 327,
      "p95": 330,
      "max": 330,
      "mean": 325.238
    }
  },
  "sequential": {
    "wall_ms": {
      "n": 21,
      "min": 1254.742,
      "p50": 1273.991,
      "p90": 1288.111,
      "p95": 1290.122,
      "max": 1538.379,
      "mean": 1285.48
    },
    "model_total_ms": {
      "n": 21,
      "min": 1253,
      "p50": 1271,
      "p90": 1286,
      "p95": 1288,
      "max": 1535,
      "mean": 1282.333
    },
    "prefix_ms": {
      "n": 21,
      "min": 811,
      "p50": 826,
      "p90": 832,
      "p95": 833,
      "max": 838,
      "mean": 824.667
    },
    "score_ms": {
      "n": 21,
      "min": 437,
      "p50": 441,
      "p90": 447,
      "p95": 452,
      "max": 716,
      "mean": 454.905
    }
  },
  "guardrail": {
    "decision_agreement": 1,
    "max_probability_delta": 0.00125,
    "passed": true
  },
  "speedup_batch_vs_sequential": 2.4046
}
```
