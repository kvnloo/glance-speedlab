# E007 result — Temporal frame reuse

Supported on deterministic synthetic sequences. Threshold 4 preserved 100% abrupt and gradual event recall while reducing inference triggers 95.1%. It is exposed as an off-by-default experimental live toggle pending a real-camera replication.

Generated from `research/runs/browser-experiments.json`; the detailed raw run remains ignored.

```json
{
  "config": {
    "thresholds": [
      1,
      2,
      4,
      8
    ],
    "seeds": 10,
    "frames": 300,
    "cameraFps": 30,
    "maxStaleFrames": 30,
    "modelMs": 207
  },
  "variants": {
    "1": {
      "triggerCount": 270,
      "inferenceHz": 2.7,
      "computeReductionPct": 91,
      "effectiveAnswerHz": 30,
      "answerHzMultiplierVsFreshInference": 6.21,
      "guardrail": {
        "abruptRecall": 1,
        "gradualRecall": 1,
        "passed": true
      }
    },
    "2": {
      "triggerCount": 192,
      "inferenceHz": 1.92,
      "computeReductionPct": 93.6,
      "effectiveAnswerHz": 30,
      "answerHzMultiplierVsFreshInference": 6.21,
      "guardrail": {
        "abruptRecall": 1,
        "gradualRecall": 1,
        "passed": true
      }
    },
    "4": {
      "triggerCount": 147,
      "inferenceHz": 1.47,
      "computeReductionPct": 95.1,
      "effectiveAnswerHz": 30,
      "answerHzMultiplierVsFreshInference": 6.21,
      "guardrail": {
        "abruptRecall": 1,
        "gradualRecall": 1,
        "passed": true
      }
    },
    "8": {
      "triggerCount": 120,
      "inferenceHz": 1.2,
      "computeReductionPct": 96,
      "effectiveAnswerHz": 30,
      "answerHzMultiplierVsFreshInference": 6.21,
      "guardrail": {
        "abruptRecall": 1,
        "gradualRecall": 1,
        "passed": true
      }
    }
  }
}
```
