# E002 result — JPEG quality

Quality 40 passed the answer guardrail (100% decisions; maximum probability drift 0.00558) and substantially reduced bytes, but model p50 and local encoding remained operationally unchanged. Keep quality 60 as the default; quality 40 is a bandwidth knob, not a local speed optimization.

Generated from the aggregate artifact `research/results/model-experiments.json`; detailed paired rows remain ignored.

```json
{
  "40": {
    "wall_ms": {
      "n": 15,
      "min": 522.032,
      "p50": 526.713,
      "p90": 529.675,
      "p95": 529.73,
      "max": 529.73,
      "mean": 526.532
    },
    "model_total_ms": {
      "n": 15,
      "min": 522,
      "p50": 526,
      "p90": 529,
      "p95": 529,
      "max": 529,
      "mean": 526.133
    },
    "prefix_ms": {
      "n": 15,
      "min": 199,
      "p50": 201,
      "p90": 203,
      "p95": 207,
      "max": 207,
      "mean": 201.4
    },
    "score_ms": {
      "n": 15,
      "min": 322,
      "p50": 324,
      "p90": 325,
      "p95": 326,
      "max": 326,
      "mean": 323.933
    },
    "input_bytes": {
      "n": 15,
      "min": 4884,
      "p50": 5270,
      "p90": 7494,
      "p95": 7494,
      "max": 7494,
      "mean": 5882.667
    }
  },
  "60": {
    "wall_ms": {
      "n": 15,
      "min": 521.684,
      "p50": 528.108,
      "p90": 531.317,
      "p95": 532.241,
      "max": 532.241,
      "mean": 527.02
    },
    "model_total_ms": {
      "n": 15,
      "min": 521,
      "p50": 528,
      "p90": 530,
      "p95": 531,
      "max": 531,
      "mean": 526.467
    },
    "prefix_ms": {
      "n": 15,
      "min": 199,
      "p50": 201,
      "p90": 203,
      "p95": 203,
      "max": 203,
      "mean": 201.067
    },
    "score_ms": {
      "n": 15,
      "min": 322,
      "p50": 325,
      "p90": 326,
      "p95": 329,
      "max": 329,
      "mean": 324.6
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
  "90": {
    "wall_ms": {
      "n": 15,
      "min": 522.636,
      "p50": 527.342,
      "p90": 529.76,
      "p95": 532.698,
      "max": 532.698,
      "mean": 526.702
    },
    "model_total_ms": {
      "n": 15,
      "min": 522,
      "p50": 527,
      "p90": 529,
      "p95": 529,
      "max": 529,
      "mean": 526
    },
    "prefix_ms": {
      "n": 15,
      "min": 199,
      "p50": 201,
      "p90": 203,
      "p95": 204,
      "max": 204,
      "mean": 201
    },
    "score_ms": {
      "n": 15,
      "min": 321,
      "p50": 325,
      "p90": 326,
      "p95": 326,
      "max": 326,
      "mean": 324.333
    },
    "input_bytes": {
      "n": 15,
      "min": 10724,
      "p50": 11687,
      "p90": 21687,
      "p95": 21687,
      "max": 21687,
      "mean": 14699.333
    }
  },
  "guardrail": {
    "decision_agreement": 1,
    "max_probability_delta": 0.00558,
    "passed": true
  },
  "encoder": {
    "dog-q40": {
      "encode_ms": {
        "n": 50,
        "min": 0.08,
        "p50": 0.083,
        "p90": 0.085,
        "p95": 0.088,
        "max": 0.143,
        "mean": 0.085
      },
      "bytes": 7494
    },
    "dog-q60": {
      "encode_ms": {
        "n": 50,
        "min": 0.088,
        "p50": 0.089,
        "p90": 0.095,
        "p95": 0.1,
        "max": 0.121,
        "mean": 0.091
      },
      "bytes": 9770
    },
    "dog-q90": {
      "encode_ms": {
        "n": 50,
        "min": 0.1,
        "p50": 0.107,
        "p90": 0.123,
        "p95": 0.142,
        "max": 0.207,
        "mean": 0.111
      },
      "bytes": 21687
    },
    "receipt-q40": {
      "encode_ms": {
        "n": 50,
        "min": 0.07,
        "p50": 0.075,
        "p90": 0.081,
        "p95": 0.091,
        "max": 0.11,
        "mean": 0.076
      },
      "bytes": 4884
    },
    "receipt-q60": {
      "encode_ms": {
        "n": 50,
        "min": 0.071,
        "p50": 0.076,
        "p90": 0.077,
        "p95": 0.081,
        "max": 0.091,
        "mean": 0.075
      },
      "bytes": 6025
    },
    "receipt-q90": {
      "encode_ms": {
        "n": 50,
        "min": 0.076,
        "p50": 0.081,
        "p90": 0.094,
        "p95": 0.098,
        "max": 0.135,
        "mean": 0.083
      },
      "bytes": 10724
    },
    "invoice-q40": {
      "encode_ms": {
        "n": 50,
        "min": 0.092,
        "p50": 0.093,
        "p90": 0.098,
        "p95": 0.104,
        "max": 0.109,
        "mean": 0.095
      },
      "bytes": 5270
    },
    "invoice-q60": {
      "encode_ms": {
        "n": 50,
        "min": 0.088,
        "p50": 0.094,
        "p90": 0.1,
        "p95": 0.116,
        "max": 0.138,
        "mean": 0.095
      },
      "bytes": 6488
    },
    "invoice-q90": {
      "encode_ms": {
        "n": 50,
        "min": 0.095,
        "p50": 0.1,
        "p90": 0.114,
        "p95": 0.122,
        "max": 0.136,
        "mean": 0.103
      },
      "bytes": 11687
    }
  }
}
```
