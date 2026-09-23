# E005 result — Base64 and JSON transport

Rejected. At 320 px, combined base64/stringify/parse measured 0.0 ms p50 and 0.1 ms p95—far below the preregistered 5% materiality threshold for a 150 ms model.

Generated from `research/runs/browser-experiments.json`; the detailed raw run remains ignored.

```json
{
  "config": {
    "warmups": 20,
    "iterations": 300,
    "modelBudgetMs": 150
  },
  "variants": {
    "160": {
      "jpegBytes": 1855,
      "requestBytes": 2618,
      "base64_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.048
      },
      "stringify_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.002
      },
      "parse_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0
      },
      "combined_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.051
      },
      "share_of_150ms_p50_pct": 0,
      "share_of_150ms_p95_pct": 0.067,
      "guardrail": {
        "decodedByteLengthIdentical": true,
        "passed": true
      }
    },
    "224": {
      "jpegBytes": 2343,
      "requestBytes": 3266,
      "base64_ms": {
        "n": 300,
        "min": 0,
        "p50": 0.1,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.2,
        "mean": 0.055
      },
      "stringify_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.002
      },
      "parse_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.001
      },
      "combined_ms": {
        "n": 300,
        "min": 0,
        "p50": 0.1,
        "p90": 0.1,
        "p95": 0.2,
        "max": 0.2,
        "mean": 0.059
      },
      "share_of_150ms_p50_pct": 0.067,
      "share_of_150ms_p95_pct": 0.133,
      "guardrail": {
        "decodedByteLengthIdentical": true,
        "passed": true
      }
    },
    "320": {
      "jpegBytes": 3226,
      "requestBytes": 4446,
      "base64_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.055
      },
      "stringify_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.002
      },
      "parse_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.001
      },
      "combined_ms": {
        "n": 300,
        "min": 0,
        "p50": 0.1,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.059
      },
      "share_of_150ms_p50_pct": 0.067,
      "share_of_150ms_p95_pct": 0.067,
      "guardrail": {
        "decodedByteLengthIdentical": true,
        "passed": true
      }
    },
    "448": {
      "jpegBytes": 4123,
      "requestBytes": 5642,
      "base64_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.051
      },
      "stringify_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.003
      },
      "parse_ms": {
        "n": 300,
        "min": 0,
        "p50": 0,
        "p90": 0,
        "p95": 0,
        "max": 0.1,
        "mean": 0.002
      },
      "combined_ms": {
        "n": 300,
        "min": 0,
        "p50": 0.1,
        "p90": 0.1,
        "p95": 0.1,
        "max": 0.3,
        "mean": 0.055
      },
      "share_of_150ms_p50_pct": 0.067,
      "share_of_150ms_p95_pct": 0.067,
      "guardrail": {
        "decodedByteLengthIdentical": true,
        "passed": true
      }
    }
  },
  "materialAt320": false
}
```
