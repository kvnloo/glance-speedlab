# E004 result — Persistent capture resources

No measurable p50 or p95 latency improvement at 320×180; persistent reuse still avoids two allocations per frame and remains as allocation hygiene, not a speed claim.

Generated from `research/runs/browser-experiments.json`; the detailed raw run remains ignored.

```json
{
  "config": {
    "width": 320,
    "height": 180,
    "jpegQuality": 0.6,
    "warmups": 20,
    "iterations": 200
  },
  "persistent_ms": {
    "n": 200,
    "min": 0.2,
    "p50": 0.3,
    "p90": 0.4,
    "p95": 0.4,
    "max": 6.9,
    "mean": 0.357
  },
  "allocate_each_frame_ms": {
    "n": 200,
    "min": 0.2,
    "p50": 0.3,
    "p90": 0.4,
    "p95": 0.5,
    "max": 1.1,
    "mean": 0.353
  },
  "p50_speedup": 1,
  "p95_speedup": 1.25,
  "allocations_avoided_per_frame": 2,
  "guardrail": {
    "decodedGeometryIdentical": true,
    "passed": true
  }
}
```
