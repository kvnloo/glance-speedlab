# What Actually Makes a Local Camera VLM Faster?

## A Measurement-First Study of Glance on Apple Silicon

**Yohei Nakajima**  
Draft technical report, September 2026

> Draft status: artifact-complete working manuscript, not peer reviewed. Every quantitative claim should be checked against the linked aggregate artifact before submission. The initial prose was prepared with coding-agent assistance from the committed experiment registry, results, and decision log.

## Abstract

Live-camera applications expose a mismatch between the capabilities of modern vision-language models and the latency users experience. Plausible optimizations exist at every layer—camera capture, image compression, serialization, request scheduling, vision-token count, prompt organization, batch shape, model size, execution backend, caching, and temporal reuse—but optimizing the wrong layer produces clean code without a perceptible speedup. We present Glance Speedlab, a local-first measurement harness for typed vision-language decisions, and report twenty-one preregistered experiments on an Apple M5 laptop using pinned Qwen3-VL-4B and Qwen3-VL-2B checkpoints.

The strongest safe architectural result was native multi-question batching: one four-question request was 2.405× faster than four cold sequential requests while preserving decisions. Moving from the 4B to the 2B checkpoint produced a larger 2.994× median speedup, but the fixed-suite quality guardrail failed: only 83.3% of individual decisions agreed and the maximum probability shift was 0.746. A direct MLX 8-bit scorer closed the earlier backend protocol gap by rendering the same statements, sharing one multimodal prefix, batching suffixes, and reading the same yes/no token variants. It reduced fresh nine-statement p50 from 358.5 to 259.6 ms (1.381×), matched all 84 measured decisions, and limited maximum answer-probability drift to 0.039. The same implementation at 4-bit retained speed but drifted by 0.361. Fixed-shape compilation was flat; uniform vision-token reduction and untrained decoder exits exposed 6–22% speed headroom but failed decision or probability guardrails. A synthetic temporal gate reduced inference triggers by 95.1% while retaining all declared events, but remains unvalidated on labeled real camera sequences.

The central finding is methodological: measure realized model work, not configuration labels or proxy counts. A configured image-token cap had no effect until it fell below the 70–80 tokens actually produced by the controlled 320 px inputs; fewer nominal passes, compilation, and fewer decoder layers did not guarantee an acceptable latency-quality point. The evidence supports a next stage built around the accepted 8-bit MLX backend, larger live-camera validation, trained intermediate decision heads, learned vision-token selection, sustained-load measurement, and model-specific Metal kernels—not further browser transport optimization.

## 1. Introduction

The product requirement behind this work is simple: point a camera at a changing scene, ask one or more typed questions, and receive useful probabilities quickly enough that the interaction feels immediate. The engineering problem is less simple. “Latency” spans capture, resize, JPEG encoding, serialization, local transport, visual preprocessing, image-prefix computation, question scoring, calibration, rendering, and scheduling. A faster component matters only if it occupies a meaningful share of the end-to-end path or enables a different system design.

Glance reads typed decisions from the logits of a frozen open vision-language model rather than decoding free-form prose [1]. It supports yes/no, pick-one, and rating questions and can share an image prefix across multiple questions. This makes it an unusually clean substrate for a latency study: generation length is removed as a major variable, model timing is exposed, and a single image can be paired with one or many structured questions.

This report asks four questions:

1. Where does time go in a local live-camera Glance loop?
2. Which browser, protocol, request-shape, and model changes materially reduce latency?
3. Which apparent speedups survive fixed quality guardrails?
4. What design follows from both the positive and negative results?

The contribution is not a claim of a universal fastest configuration. It is a reproducible artifact, a record of twenty-one controlled experiments, and a set of bounded inferences for the next research phase.

## 2. System

Speedlab uses a pull-based loop:

```text
camera → persistent canvas → JPEG Blob → base64 → local gateway ─┬→ Glance FP16
   ↑                                                             └→ MLX 8-bit
   └──── capture the newest frame only after completion ─────────────┘
```

There is exactly one request in flight. This choice bounds memory and prevents a queue of increasingly stale frames when the camera produces frames faster than the model can answer. A single question and a many-question request share the same native Glance path.

The browser reports capture and base64 timings. The gateway reports local round-trip, upstream, and backend identity. Glance or the optional MLX scorer reports image-prefix and scoring timings. Durations are measured with monotonic clocks within each process; clocks are not compared across processes.

Frames remain in memory and are sent only over loopback. Optional run recording writes configuration and timing metadata as JSONL but excludes frame bytes. Raw detailed rows are ignored by version control; privacy-reviewed aggregate artifacts are committed.

## 3. Experimental method

### 3.1 Hardware and software

Unless noted otherwise, experiments used:

- Apple M5 with 32 GB unified memory
- macOS Darwin 26.6.2
- Python 3.11.15
- PyTorch MPS, float16
- Glance commit `3b5205429e153e3c206503409a9e9d5c2f20ee73`
- Prefix sharing enabled
- Qwen3-VL-4B revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`
- Qwen3-VL-2B revision `89644892e4d85e24eaac8bacfd4f463576704203`

Qwen3-VL is a family of dense and mixture-of-experts multimodal models with multiple parameter scales, including the 2B and 4B dense variants used here [2]. PyTorch’s MPS backend maps supported computation to Apple’s Metal Performance Shaders stack [3].

### 3.2 Inputs and questions

The fixed guardrail suite uses Glance’s dog photograph, receipt, and invoice samples. Controlled model experiments derive 320 px long-edge JPEG quality-60 fixtures. The four-question batch contains:

- one four-way content choice,
- two yes/no questions about readable text and natural photography,
- one three-way visual-tone choice.

Under independent scoring this produces nine statement forward passes behind one shared image prefix. The live UI additionally includes facial expression, held object, and finger-count questions. No camera frames are committed.

### 3.3 Preregistration and thresholds

Each experiment declares a hypothesis, primary metric, guardrail, environment, warmups, repetitions, and stopping rule before implementation. A speed claim requires at least a 5% median improvement. Pixel, model, token, prompt, or scoring changes must preserve declared decision and probability bounds before adoption.

Model experiments use paired or order-rotated arms where practical. Browser experiments use deterministic synthetic images. Two model warmups precede measured requests. Exact sample counts are recorded in each experiment plan and aggregate artifact.

### 3.4 Interpretation constraints

Ratios within a paired experiment are more reliable than absolute comparisons between sessions. The model experiments were not performed in a temperature-controlled environment, and some model-tier arms required separate model loads. Absolute baselines varied across runs even when the logical request was similar. We therefore avoid combining independently measured milliseconds into synthetic end-to-end claims.

## 4. Results

### 4.1 Browser and transport work was already negligible

Reducing capture resolution from 320 to 224 px produced a 0.999× speed ratio: no material latency change. It also failed the answer guardrail, with only 66.7% decision agreement on the small fixed suite. Lowering JPEG quality reduced request bytes but did not materially change model or wall latency. Persistent canvas reuse avoided two allocations per frame but did not improve median capture time. Base64 conversion, JSON serialization, and JSON parsing together were at most 0.1 ms p95 for the 320 px payload.

These results bound the opportunity. At measured model latencies of hundreds of milliseconds, optimizing sub-millisecond transport work cannot produce a perceptible end-to-end improvement.

### 4.2 Native question batching was the strongest safe architecture change

One cold four-question request took 529.8 ms p50, compared with 1,274.0 ms for four cold one-question requests. Native batching was therefore 2.405× faster. Decisions matched exactly and maximum probability drift was 0.00125, inside the 0.02 guardrail.

The gain came primarily from avoiding repeated image-prefix work: the sequential arm accumulated approximately 826 ms of prefix time at p50, versus 203 ms for the batch. This supports a simple architectural rule: when several questions refer to the same frame, send one native request.

### 4.3 Configured image-token limits did not equal realized work

We initially expected reducing Glance’s image-token cap from 768 to 128–256 to reduce image-prefix latency. It did not. Every controlled 320 px fixture realized only 70–80 image tokens at all tested caps from 128 through 768. Outputs were identical, and the 128-versus-768 wall-time ratio was 0.997×.

An additional preregistered sweep crossed the observed floor:

| Model | Budget | Realized tokens, p50 | Speedup vs 128 | Decision result | Probability result |
| --- | ---: | ---: | ---: | --- | --- |
| 4B | 48 | 42 | 1.092× | All matched | Max delta 0.130; failed 0.10 limit |
| 4B | 32 | 24 | 1.126× | One changed | Max delta 0.594 |
| 2B | 48 | 42 | 1.121× | One changed | Max delta 0.295 |
| 2B | 32 | 24 | 1.158× | One changed | Max delta 0.183 |

Budget 64 exposed an aspect-ratio edge case. The tall receipt was processed into 77 tokens and rejected for exceeding the configured cap, while other geometries completed at fewer tokens. Budgets 96 and 128 realized the same tokens and were operationally identical.

The 4B/48 result is a near miss rather than a win. It preserved fixed decisions and exceeded the 5% speed threshold, but it failed the preregistered probability guardrail. It belongs on a larger labeled frontier evaluation, not in the default profile.

### 4.4 Larger suffix batches and fewer nominal passes did not guarantee speed

The cached suffix path was tested with batch sizes 4, 8, 16, and 32. Batch 16 and 32 were operationally flat: 805.4 and 802.7 ms wall p50. Batch 8 and 4 regressed to 960.0 and 1,024.3 ms. All answer guardrails passed. The existing batch size 16 remains the default because 32 did not cross the 5% materiality threshold.

Letter scoring was intended to compress a choice question by scoring option letters instead of one yes/no statement per option. One rotation reduced the reported pass count for the two choice questions from seven to two, yet wall p50 increased from 624.2 to 641.2 ms and maximum probability drift reached 0.318. Four rotations increased wall p50 to 802.1 ms, changed a decision, and drifted by 0.720. Nominal pass count was therefore an inadequate proxy for runtime or stability.

### 4.5 Model size produced the largest raw speedup and the clearest quality cost

On identical 320 px fixtures and the nine-statement batch, Qwen3-VL-2B achieved 267.0 ms wall p50 versus 799.4 ms for Qwen3-VL-4B: a 2.994× speedup. Prefix p50 fell from 296 to 121 ms, and scoring p50 fell from 498 to 146 ms.

The quality guardrail failed. The 2B tier agreed with 4B on 10 of 12 individual fixed-suite decisions (83.3%), only one of three complete request vectors, and showed maximum probability drift of 0.746. The result supports a fast tier but rejects unconditional replacement of 4B.

### 4.6 Temporal reuse changed effective compute, not fresh-answer latency

A deterministic synthetic motion gate compared normalized thumbnail luma differences against thresholds 1, 2, 4, and 8. At threshold 4 it reduced inference triggers by 95.1% while retaining every declared abrupt and gradual event in the synthetic sequences. A forced refresh bounded staleness.

This is an effective-throughput result, not a faster model result. Reused answers can update the interface at camera cadence, but a genuinely changed frame still pays model latency. Real-camera validation is required because sensor noise, exposure changes, hands entering the frame, gradual motion, and task relevance are only approximated by the synthetic generator.

### 4.7 Operational smoke tests

With the final live service configured as 2B, 128-token cap, suffix batch 16, and prefix sharing enabled, a repeated still-image HTTP benchmark measured 121 ms request p50 and 124 ms p95 after warmup. Those requests were exact-image prefix-cache hits and reported zero prefix time.

A non-preregistered smoke test rotated three image hashes through a two-entry cache and measured approximately 301 ms wall p50 for one five-way choice question, with 182 ms prefix and 115 ms scoring p50. These numbers validate the deployed path but are not included as paper-grade experimental claims: the sample count was 12 and the images are not a labeled live-camera sequence.

### 4.8 Generated-label MLX established backend opportunity

E013 compared the active Qwen3-VL-2B PyTorch MPS/FP16 service with a pinned MLX 4-bit checkpoint. The input was the same three 320 px quality-60 JPEG fixtures and one coarse four-way classification. Each arm used two warmups and five measured repetitions per image. A unique JPEG comment segment changed Glance's original-byte cache key while preserving decoded pixels, separating exact-image cache hits from fresh-prefix work.

The MLX path measured 144.1 ms end-to-end p50, versus 204.2 ms for new-frame Glance: a 1.417× speedup or 29.4% latency reduction. P95 fell from 208.1 to 150.1 ms. All arms returned the expected coarse class for every fixture. MLX reported 108 prompt tokens p50, 861 prompt tokens/s, 208 generated tokens/s, and 2.038 GB peak memory p50.

Exact-image Glance cache hits remained substantially faster at 79.6 ms p50 because prefix time fell to zero. More importantly, the protocols differed: Glance directly scored four candidate statements and returned probabilities, whereas MLX greedily generated a two- or three-token class label. E013 therefore established backend opportunity rather than drop-in semantic or calibration parity; E016/E017 subsequently addressed that gate.

### 4.9 MLX caching depended on message topology and cache type

E014 tested four standalone MLX cache configurations and a paired continued-chat condition. Neither the generic vision-feature cache nor combined vision/prompt state accelerated an identical standalone Qwen3-VL request. The vision cache remained empty because the model wrapper did not expose the generic encoder hook. Automatic prefix caching found 96–104-token block matches but restored zero tokens because its block path rejects prefixes containing media tokens; its bookkeeping increased p50 by 22–23%.

A correctly shaped continued conversation behaved differently. When the image remained an explicit content item in the first user message, the second turn reused 104 tokens. Median latency fell from 188.4 to 92.0 ms, a 2.048× speedup, and all outputs remained `yes`. With an implicit image count, the template moved the image marker to the newest user message and destroyed the common prefix. Thus “cache enabled” is not a sufficient experimental description: the cache layer, token topology, restored-token count, and fresh-versus-continued workload must be reported.

Husky, a model-specific inference engine for the Woof 4B model, motivates further specialization but does not provide a direct baseline for this workload [5]. Its largest reported gains use prompt-copy or trained-draft verification to emit several decoded tokens per weight read, while Glance directly scores short statements. The transferable ideas are exact-shape kernel fusion, packed weight layout, pipelined submission, and explicit cold/cached reporting; applying them to a fixed VLM would be a separate engineering program.

### 4.10 Direct MLX scoring passed at 8-bit, not 4-bit

E016 replaced generated labels with Glance-compatible direct statement scoring. The implementation rendered the same prompt templates, ran one shared multimodal prefix, expanded its KV cache across nine statement suffixes, and projected only the eight single-token yes/no variants. Four-bit MLX reduced fresh-frame p50 from 503.4 to 367.3 ms (1.371×) and matched all 84 measured decisions, but maximum answer-probability drift was 0.361; it failed the 0.10 bound.

E017 changed only the checkpoint precision. Eight-bit MLX reduced paired p50 from 358.5 to 259.6 ms (1.381×, 27.6%), matched all measured decisions, and limited maximum probability drift to 0.039. Prefix and suffix p50 were 120.9 and 118.2 ms, respectively; KV batch expansion and selected-row projection together consumed below 4 ms p50. Peak reported MLX memory was 3.499 GB. An exact-protocol replication measured 281.7 versus 211.3 ms (1.334×, 25.0%) with the same decision agreement and maximum probability delta. This was the first backend arm to pass both speed and semantic gates, so it became an opt-in live backend while Glance FP16 remained the default reference.

### 4.11 Backend shortcuts exposed headroom but failed adoption gates

E018 compiled the fixed-shape cached suffix with `mx.compile`. Outputs were bit-identical, but wall p50 improved only 0.6% and p95 was flat. The multimodal prefix could not be transformed unchanged because Qwen's deep-stack input path performs an eager evaluation during graph transformation.

E019 constrained the MLX image processor. A nominal 48-token cap realized 40–45 tokens, reduced prefix p50 from 176.1 to 122.1 ms, and improved wall p50 15.6%. It also changed the dog tone answer and shifted probabilities by up to 0.411. A nominal 64 cap saved only 1.2% and also changed tone. The experiment bounds approximately 54 ms of prefix opportunity but rejects uniform pixel-area reduction.

E020/E021 truncated the 28-layer language stack while retaining the final normalization and tied output head. Twenty-four layers was 11.1% faster and preserved decisions but drifted by 0.207. Twenty-six layers was 6.1% faster but changed receipt-photo; 27 layers retained decisions but saved only 3.4% and drifted by 0.242. No 20–27-layer arm passed both gates. The mechanism motivates a trained intermediate head or distillation, not raw truncation.

## 5. What can be inferred

### 5.1 Optimize the dominant model blocks first

At current speeds, browser capture and serialization are orders of magnitude smaller than model work. They should remain measurable and clean, but they are not the priority. The next large gains must reduce image-prefix computation, reduce scoring computation, use a faster model/backend, or avoid inference.

### 5.2 Measure realized work, not requested settings

The 128–768 token sweep initially appeared to reject token reduction. In reality, none of those limits constrained the 320 px fixtures. Only the sub-128 sweep changed realized tokens. Any token-budget study should log the processed token count and input geometry, not merely the configured cap.

The budget-64 geometry failure also shows that “cap” semantics need definition. A robust system must either round caps to processor-valid grids, accept bounded overshoot, or resize again until the emitted grid is valid.

The MLX frontier repeated the lesson. A nominal 64-token pixel area produced 54 tokens for the dog, 77 for the receipt, and 63 for the invoice. Reporting the label “64” without the realized grids would hide both the weak speed result and its geometry dependence.

### 5.3 Proxy counts are insufficient

Fewer forward passes did not make one-rotation letter scoring faster. Batch size 32 did not beat 16 materially. Image bytes did not predict model latency. Optimization decisions should use synchronized wall/model measurements, not pass counts, payload size, or configuration values alone.

### 5.4 The likely architecture is conditional computation

The 2B tier is almost 3× faster than 4B but imperfect. The accepted MLX 8-bit backend is 1.381× faster than the same 2B semantics on the fixed suite, while token and depth shortcuts have localized failures. These results suggest a cascade rather than one global setting:

```text
nearly unchanged frame → reuse recent answer
changed frame           → 2B fast tier
routine local scoring   → MLX 8-bit direct backend
uncertain/disagreement  → full-depth/reference tier
fine detail or text     → full token budget
```

This architecture is still a hypothesis. A useful cascade requires calibrated uncertainty, a labeled live sequence, a coverage-risk curve, escalation-rate reporting, and end-to-end tail latency. Raw top probability may not identify all 2B disagreements.

### 5.5 “Feels immediate” has multiple definitions

Cached response latency, fresh-frame latency, completed inference rate, displayed answer rate, and frame age are distinct metrics. Temporal reuse can improve displayed answer rate without changing fresh inference. Parallel capture can increase throughput while making answers older. A camera system should report both latency and staleness.

## 6. Negative results and why they matter

Most attempted interventions did not become defaults. Recording those results narrows the search space:

- Lower browser resolution did not reduce realized model work and harmed answers.
- JPEG quality was a bandwidth lever, not a local latency lever.
- Persistent canvas reuse improved allocation behavior, not median speed.
- Base64/JSON was below materiality.
- Question order was neutral because Glance canonicalizes statements.
- Suffix batch 32 did not materially beat 16.
- Letter scoring did not convert fewer passes into lower wall time.
- Token caps above realized usage were inert.
- Token caps below the floor traded quality for only 9–16% speed.
- Four-bit direct MLX preserved labels but failed probability parity.
- Explicit suffix compilation was operationally flat.
- Uniform MLX vision-token reduction exposed speed but changed answers.
- Every untrained 20–27-layer exit failed a probability or decision gate.

These are not failures of the research program. They prevent engineering effort and product claims from accumulating around plausible but unmeasured stories.

## 7. Limitations

The study has substantial limits:

1. **One primary machine.** Results come from one Apple M5 laptop with 32 GB unified memory. They do not establish CUDA, Intel, older Apple Silicon, or mobile behavior.
2. **Small quality suite.** Three fixed images and four questions can catch gross regressions but cannot establish application accuracy.
3. **Synthetic temporal validation.** E007 does not substitute for labeled camera video.
4. **Separate model loads.** The 2B and 4B arms could not be fully interleaved. Thermal state, allocator state, and background activity may confound absolute differences, although the approximately 3× gap is large.
5. **Cross-run baseline variation.** Similar logical requests produced different absolute baselines across experiment sessions. Only within-experiment ratios should be treated as controlled.
6. **No power or memory study.** Latency was measured; energy, sustained thermals, and peak unified memory were not.
7. **Backend generalization.** E017 closes fixed-suite protocol parity within a 0.10 probability bound, but three images and four questions do not establish application accuracy. The continued-chat cache result is not equivalent to a standalone camera decision. Core ML, Neural Engine execution, and newer native MPS paths remain untested.
8. **No user-perception study.** “Immediate” is used as a design target, not a measured psychophysical threshold.
9. **Model-specific prompts and processors.** Conclusions about letter scoring, grid rounding, and confidence may not transfer to another VLM family.

## 8. Next experiments

The evidence prioritizes:

1. **Larger MLX parity suite.** Compare the accepted 8-bit backend with Glance on labeled live-camera, OCR, fine-detail, and rare-event slices; report calibration and task errors, not only fixed prompts.
2. **Trained intermediate decision heads.** Distill full-depth statement margins into 20–24-layer representations and measure coverage, calibration, open-set failure, and escalation to full depth.
3. **Learned vision-token selection.** Recover the 54 ms E019 prefix opportunity with saliency-aware or task-conditioned tokens rather than uniform resizing.
4. **Model-shaped Metal kernels.** Profile vision, prefix language, and suffix language separately, then test fused 8-bit kernels, packed weights, and pipelined submission while holding outputs fixed.
5. **Sustained-load profiling.** Run both accepted backends for 30 minutes and report temperature, power, memory, p50/p95/p99, failures, and frame age.
6. **Real-camera temporal validation and cascades.** Label salient events, gradual changes, scene cuts, exposure changes, and irrelevant motion; measure uncertainty-gated escalation end to end.
7. **Core ML/Neural Engine.** Test conversion fidelity and sustained efficiency as a separate backend, without assuming ANE placement implies lower latency.

## 9. Reproducibility and artifact

The artifact includes the complete experiment registry, plans, aggregate JSON, scripts, UI, protocol tests, and reproduction commands. Detailed raw rows are intentionally excluded from version control to reduce privacy and path-leakage risk; they are regenerated locally by the scripts.

The primary entry points are:

- `research/EXPERIMENTS.md` — preregistrations and status
- `research/FINDINGS.md` — concise result synthesis
- `research/results/` — machine-readable aggregate artifacts
- `research/experiments/` — per-experiment plans and interpretations
- `docs/REPRODUCIBILITY.md` — exact commands and reporting rules
- `paper/ARTIFACTS.md` — claim-to-artifact map

## 10. Conclusion

The fastest credible path was not a collection of front-end micro-optimizations. Native multi-question batching removed redundant prefix work safely. A smaller model produced a much larger speedup but crossed a quality boundary. The direct MLX 8-bit scorer then delivered a measured 1.381× gain while passing the declared fixed-suite semantic bound. More aggressive token and depth reductions exposed further compute headroom but crossed decision or probability boundaries. Temporal reuse offered the largest effective compute reduction, but only by changing when inference is required.

The resulting strategy is conditional and measurement-driven: batch questions that share a frame, use the validated full-depth MLX 8-bit path where its evidence applies, escalate uncertain cases, reuse answers only under validated temporal rules, and reserve more invasive work for trained heads, learned token selection, and measured kernels. Just as importantly, retain the negative results. In a latency system, knowing which attractive ideas are below materiality—or fast but semantically unsafe—is part of the contribution.

## References

1. Nakajima, Y. *Glance: Ask an open vision-language model typed questions about an image and get probabilities back, on your own machine.* Source repository, 2026. <https://github.com/yoheinakajima/glance>
2. Bai, S., et al. *Qwen3-VL Technical Report.* arXiv:2511.21631, 2025. <https://arxiv.org/abs/2511.21631>
3. PyTorch Contributors. *MPS backend.* PyTorch documentation. <https://docs.pytorch.org/docs/main/notes/mps.html>
4. Hannun, A., Digani, J., Katharopoulos, A., and Collobert, R. *MLX: Efficient and flexible machine learning on Apple silicon.* 2023. <https://opensource.apple.com/projects/mlx/>
5. Wen, S. *Husky: a model-specific inference engine up to 4.5× faster than Apple's MLX.* Underdog, 2026. <https://husky.underdog.ai/>
