# Architecture

```text
camera → persistent canvas → JPEG Blob → base64 → thin gateway ─┬→ Glance FP16
   ↑                                                            └→ MLX 8-bit
   └──────── next capture starts only after the prior result ──────────┘
```

The pull loop is deliberate. Capturing at 30 FPS while a model answers at 2–10 FPS creates stale queues, extra memory pressure, and misleading throughput. Speedlab instead samples the newest frame when inference capacity becomes available.

## Model profiles

Tier, image-token cap, suffix batch size, and letter rotations are process-level Glance settings. `scripts/launch.mjs` derives an ignored profile configuration from the pinned Glance defaults and starts a fresh model process. The gateway joins `/healthz` with `/v1/models`, allowing the UI to display the tier and token cap actually loaded. If a requested profile does not match an existing process, the launcher fails instead of silently mixing configurations.

Choice scoring is a per-request variable and travels through the native Glance `options.choice_method` field. Rolling UI windows reset whenever an experimental control changes.

## Inference backends

The gateway preserves one native question-map request and routes it to the selected loopback backend. Glance FP16/MPS is the reference and default. The optional MLX 8-bit service imports the exact E016/E017 direct scorer, accepts independent choice scoring, and returns the same answer and timing envelope. Backend identity is included in every response and opt-in metric row.

The MLX process shares one multimodal image prefix across all statements, expands its KV cache across the suffix batch, and projects only the selected yes/no token rows. It does not autoregressively generate text. Both backend services are single-request processes; the browser still permits only one in-flight request.

## Timing boundaries

| Field | Clock | Meaning |
| --- | --- | --- |
| `captureMs` | browser | canvas draw plus JPEG encoding |
| `encodeMs` | browser | Blob-to-base64 conversion |
| `requestMs` | browser | gateway round trip |
| `gatewayMs` | gateway | request validation, upstream call, response parse |
| `upstreamMs` | gateway | Glance HTTP round trip |
| `model.*` | selected backend | native model timing such as prefix and score |
| `loopMs` | browser | start of capture through parsed result |

Browser and server clocks are not compared directly. Durations are measured within one process using monotonic clocks.

An exact-image prefix-cache hit can legitimately report zero prefix time. Repeated-image benchmarks must be labeled as cached; a changing camera frame normally has a new image hash and pays fresh prefix computation.

## Design constraints

- Native Glance question maps are the internal contract across both backends.
- A one-question request and a many-question request share the same code path.
- No frame persistence, analytics service, database, or hosted inference.
- The gateway may record metadata only after the user opts in.
- Opt-in records use `research/runs/<session>.jsonl`, schema version 1, with one metadata row per completed inference.
- Aborted browser requests do not imply model cancellation: the current Glance server is single-request, synchronous inference.

## Displayed answer age

Answer age is `performance.now() - capturedAt` for the displayed result. The
browser timestamps the frame immediately before drawing the video onto the
capture canvas, before JPEG/base64 encoding and inference. Only an accepted
sample replaces that timestamp; reuse, a pending request, and a failed request
do not make the currently displayed answer younger.

The UI refreshes the age every 250 ms while the camera is active, independently
of inference. Each refresh reads the monotonic clock rather than counting timer
ticks. Browser throttling or a busy main thread can delay the display update;
this is not a hard refresh deadline. Stopping clears the answer, its timestamp,
and the display timer. Resetting the measurement window leaves the age attached
to the answer that is still displayed. Before the first result, age is `—`.

This measures age since **browser frame sampling**, not camera sensor exposure.
It excludes camera/video buffering before sampling, cannot detect an already
stale or frozen video frame, and does not measure answer correctness or scene
change detection latency. A freshly completed result can already be old because
encoding and inference took time. The timestamp stays browser-local; request and
recorded telemetry schemas are unchanged. The existing temporal-reuse refresh
policy is unchanged and is not an observation-age bound.
