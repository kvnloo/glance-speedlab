# Experiment registry

| ID | Date | Hypothesis | Primary metric | Status | Outcome |
| --- | --- | --- | --- | --- | --- |
| E000 | 2026-09-22 | Establish an instrumented live baseline before optimization | p50/p95 loop ms, completed FPS | Ready | Pending live-camera run |
| E001 | 2026-09-22 | H01: 224 px inputs materially beat 320 px | model total/prefix p50; answer agreement | Complete | Rejected: 0.999× speed; quality guardrail failed |
| E002 | 2026-09-22 | H02: lower JPEG quality reduces non-model latency | encoded bytes and encode p50; answer agreement | Complete | Safe at Q40, but no material latency win |
| E003 | 2026-09-22 | H03: one N-question request beats N single requests | wall/model p50 speedup | Complete | Confirmed: 2.405×; guardrail passed |
| E004 | 2026-09-22 | H04: persistent capture resources reduce browser tail latency | capture p50/p95 and allocation count | Complete | No latency win; two allocations/frame avoided |
| E005 | 2026-09-22 | H05: base64/JSON is material below a 150 ms model budget | encode/stringify/parse share of 150 ms | Complete | Rejected: ≤0.1 ms p95 at 320 px |
| E006 | 2026-09-22 | H06: question order affects shared-prefix scoring latency | wall/model p50 delta and answer delta | Complete | Rejected: −0.204%; identical probabilities |
| E007 | 2026-09-22 | H07: temporal reuse increases answer Hz on static video | inferred answer-Hz gain and change recall | Provisional | Synthetic pass: 95.1% fewer triggers at threshold 4 |
| E008 | 2026-09-23 | H08: a 128–256 image-token budget lowers live latency materially | model total/prefix p50; answer agreement | Complete | Rejected: 320 px fixtures already realize only 70–80 tokens; 0.997× at 128 vs 768 |
| E009 | 2026-09-23 | H09: MPS has a better cached-suffix batch size than 16 | model score p50/p95 | Complete | Rejected: 32 is flat; 4/8 are materially slower |
| E010 | 2026-09-23 | H10: one-rotation letter scoring beats independent choice scoring | wall/model p50; choice agreement | Complete | Rejected: 0.974× and probability guardrail failed; four rotations slower |
| E011 | 2026-09-23 | H11: Qwen3-VL-2B improves the live latency/quality frontier | model total p50; answer agreement | Complete | Speed confirmed at 2.994×; quality guardrail failed (83.3% per-question agreement) |
| E012 | 2026-09-23 | H18: sub-128 image budgets cross the processor floor and reduce live latency | model prefix/total p50; answer agreement | Complete | Speed confirmed at 32/48, but guardrails failed; budget 64 failed on tall geometry |
| E013 | 2026-09-23 | H13: an Apple-native MLX 4-bit backend improves fixed-image latency over PyTorch MPS FP16 | fresh-frame/cached end-to-end p50; coarse-label agreement | Complete | Promising: 29.4% lower fresh-frame p50; 81.0% slower than Glance cache hits; protocol parity pending |
| E014 | 2026-09-23 | H22: MLX vision/prompt caching closes the exact-image gap to Glance | cache-hit end-to-end p50; exact generated-label stability | Complete | Mixed: continued chat 2.048× faster at 92.0 ms; standalone vision/APC caches produced zero restored tokens |

## E000 preregistration

- Compare no variants yet; measure the current clean pipeline at 320 px, JPEG 0.60, one choice question.
- Warm up the model before collecting at least 30 camera results and 20 still-image results.
- Report browser loop p50/p95, gateway p50/p95, model prefix/score p50/p95, completed FPS, failures, and exact environment.
- Treat the baseline as invalid if the model is not preloaded, prefix cache configuration is unknown, the camera scene changes materially, or more than one request is in flight.
- No claim of improvement is allowed from E000 alone.

## E001–E007 common environment and controls

- Hardware: Apple M5, 32 GB unified memory; macOS Darwin 26.6.2; MPS float16.
- Glance: commit `3b5205429e153e3c206503409a9e9d5c2f20ee73` (`v0.3.1-34-g3b52054`), Qwen/Qwen3-VL-4B-Instruct revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`, prefix cache enabled.
- Local-only inference. Fixed images are Glance's existing `samples/dog.jpg`, `samples/receipt.jpg`, and `samples/invoice.jpg`; no camera frames are recorded.
- Model experiments use two warmups and at least five measured paired repetitions unless a run fails. Browser microbenchmarks use at least 120 measured iterations and deterministic synthetic frames.
- A speed claim requires a median improvement of at least 5%; a browser component claim also requires a p95 improvement. Quality guardrails are evaluated on paired outputs, not subjective inspection.

## E001 preregistration — resolution

- Compare 224 px and 320 px long-edge JPEGs at quality 60, paired and interleaved.
- Primary metric: model-reported total and prefix p50. Secondary: request bytes and wall p50.
- Guardrail: identical argmax answers on every fixed question/image pair and maximum absolute probability delta ≤0.10.
- Stop after 5 measured paired repetitions per image/variant following two warmups, or any validation failure.

## E002 preregistration — JPEG quality

- Compare JPEG quality 40, 60, and 90 at 320 px, paired and rotated in order.
- Primary metric: encoded bytes and local encode p50; secondary model/wall p50.
- Guardrail: quality 40 must retain all argmax answers relative to quality 90 with maximum absolute probability delta ≤0.10.
- Stop after 5 measured repetitions per image/variant following two warmups.

## E003 preregistration — native batching

- Compare one four-question native request with four sequential one-question requests on the same 320 px image.
- Primary metric: paired wall p50 speedup. Secondary: summed model time and prefix work.
- Guardrail: identical argmax/noul decisions and maximum absolute probability delta ≤0.02.
- Stop after 7 paired repetitions following two warmups.

## E004 preregistration — persistent capture resources

- Compare persistent canvas/context reuse with allocating a canvas/context for every synthetic frame at 320 px, JPEG quality 60.
- Primary metric: capture+JPEG p50 and p95. Guardrail: identical encoded dimensions and decoded geometry.
- Stop after 20 warmups and 200 measured frames per arm; alternate arm order between rounds.

## E005 preregistration — base64/JSON cost

- Measure Blob-to-base64, JSON stringify, and JSON parse for deterministic JPEG payloads near 160/224/320/448 px.
- Primary metric: combined p50/p95 and percentage of a 150 ms model budget. Guardrail: decoded bytes hash-equivalent to source bytes.
- Stop after 20 warmups and 300 measured iterations per size. “Material” means ≥5% of the 150 ms budget at 320 px.

## E006 preregistration — question order

- Compare the same four questions in forward versus reverse order in one native request, alternating which order runs first.
- Primary metric: wall and model p50 delta. Guardrail: identical decisions and maximum absolute probability delta ≤0.02.
- Stop after 10 paired repetitions following two warmups. Treat <5% as operationally negligible.

## E007 preregistration — temporal reuse

- Compare infer-every-frame with thumbnail mean-absolute-difference gating on deterministic static, gradual, and abrupt-change frame sequences.
- Primary metric: inferred answer-Hz multiplier at 30 camera FPS using measured baseline inference time. Guardrail: 100% recall for labeled abrupt changes and ≥95% recall for gradual changes that cross the predeclared visible-change magnitude.
- Sweep thresholds fixed before inspecting outcomes: 1, 2, 4, 8 normalized luma points. Stop after 10 seeded sequences of 300 frames each.

## E008 preregistration — image-token budget

- Compare budgets 128, 192, 256, and 768 on the same 320 px JPEGs and fixed question batch, with prefix sharing enabled.
- Primary metric: paired model total and prefix p50. Secondary: score p50, wall p50, and realized image-token count.
- Guardrail: report exact decision agreement versus 768, maximum absolute probability delta, and results separately for natural-photo and text-heavy images.
- Hardware/model: Apple M5, 32 GB unified memory; Qwen3-VL-4B at the pinned Glance revision recorded with the run.
- Stop after two warmups and at least seven paired, order-rotated repetitions per image/budget, or any validation failure. A speed claim requires at least 5% lower median latency.

## E009 preregistration — cached suffix batch size

- Compare suffix batch sizes 4, 8, 16, and 32 using the same 768-token image input and nine-statement live-camera question batch.
- Primary metric: paired score p50/p95. Secondary: total/wall latency and peak process memory where available.
- Guardrail: identical decisions versus batch 16, maximum absolute probability delta <=0.02, no OOM, and no p95 regression for the selected default.
- Hardware/model: Apple M5, 32 GB unified memory; Qwen3-VL-4B, float16 MPS, prefix sharing enabled.
- Stop after two warmups and at least ten order-rotated repetitions per batch size.

## E010 preregistration — compressed choice scoring

- Compare independent choice statements with letter scoring at one and four cyclic rotations for the three fixed live-camera choice questions.
- Primary metric: paired wall/model p50. Secondary: forward passes and score p50.
- Guardrail: exact choice agreement versus independent on the fixed suite and maximum probability delta <=0.10; report option-order sensitivity explicitly.
- Hardware/model: Apple M5, 32 GB unified memory; Qwen3-VL-4B, 768-token budget, float16 MPS, prefix sharing enabled.
- Stop after two warmups and at least seven paired, order-rotated repetitions per image/method.

## E011 preregistration — 2B fast tier

- Compare pinned Qwen3-VL-2B and Qwen3-VL-4B at a common 384-token budget, then compare each model's fastest E008-safe budget.
- Primary metric: paired model total p50. Secondary: prefix/score latency and memory footprint.
- Guardrail: exact decision agreement and probability drift versus 4B/768 on the fixed suite; do not call the 2B tier acceptable without a labeled real-camera sequence.
- Hardware: Apple M5, 32 GB unified memory; float16 MPS and prefix sharing enabled. Record both pinned model revisions.
- Stop after two warmups and at least seven repetitions per fixed image/configuration, or a model-load/OOM failure.

## E012 preregistration — sub-128 image-token budget

- E008 showed that budgets 128–768 all realize the same 70–80 tokens on 320 px fixtures. Compare 32, 48, 64, 96, and 128 to cross that observed processor floor deliberately.
- Primary metric: paired model prefix and total p50. Secondary: score p50 and realized image-token count.
- Guardrail: exact decision agreement versus 128 and maximum absolute probability delta <=0.10, with natural-photo and text-heavy images reported separately.
- Hardware/model: Apple M5, 32 GB unified memory; pinned Qwen3-VL-2B and 4B may be run as separate, explicitly identified arms; float16 MPS with prefix sharing.
- Stop after two warmups and at least seven order-rotated repetitions per image/budget/model. A speed claim requires at least 5% lower median latency and a lower realized token count.

## E013 preregistration — Apple-native MLX backend

- Compare the active Qwen3-VL-2B PyTorch MPS/FP16 path with a pinned Qwen3-VL-2B MLX 4-bit checkpoint on the same local Apple M5 and the same three Glance sample images. Keep the existing service intact and isolate MLX dependencies in a dedicated virtual environment.
- Primary metric: warm end-to-end p50 for one deterministic visual question after two warmups, with at least five measured repetitions per image. Secondary metrics: first-load time, prompt-processing time, generation throughput, peak resident memory where observable, artifact size, and setup friction.
- Quality guardrail: both backends must identify the same coarse content class (animal photo, receipt, or invoice) for every image. Record exact generated responses because MLX generation is not yet equivalent to Glance's probability-scoring protocol; do not claim drop-in parity from text agreement alone.
- Hardware: Apple M5, 32 GB unified memory. Baseline: pinned Glance commit/model revision already recorded by E011/E012, PyTorch MPS FP16, prefix sharing enabled, 128-token budget. Candidate: record Python, MLX, MLX-VLM, checkpoint ID/revision, and quantization metadata from the run.
- Stop after a successful three-image smoke test plus the measured repetitions, or when installation, checkpoint compatibility, model conversion, memory, or protocol mismatch prevents a valid comparison. A speed claim requires at least 5% lower p50 with the quality guardrail passing; otherwise report the attempt as inconclusive or rejected.

## E014 preregistration — MLX vision and prompt caching

- Compare four modes in the same loaded MLX Qwen3-VL-2B 4-bit process: no reusable cache, `VisionFeatureCache` only, `VisionFeatureCache` plus `PromptCacheState`, and MLX-VLM's automatic prefix cache (APC) in memory-only mode. Compare the winning exact-image arm with E013's Glance exact-image cache-hit result.
- Primary metric: exact-image end-to-end p50 after two warmups, with at least ten measured repetitions. Also measure a paired continued-chat second turn with and without `PromptCacheState`, matching the workload class in Husky's cached-latency comparison. Secondary metrics: reported cached-token count, prompt throughput, peak memory, output stability, and cache contents.
- Guardrail: every measured response must exactly normalize to the same coarse label as the uncached MLX reference. Treat repeated identical requests as an operational cache benchmark, not a fresh-camera claim.
- Hardware/model: Apple M5, 32 GB unified memory; MLX 0.32.2; pinned MLX-VLM commit and Qwen3-VL-2B 4-bit checkpoint from E013. Record any incompatibility between image-feature and prompt/KV reuse.
- Stop after the three arms complete, or on a reproducible cache-correctness failure. A cache win requires at least 5% lower median latency than uncached MLX without changing the generated label.

## E015 preregistration — selected-logit-only statement scoring

- Compare Glance's reference statement readout, which computes a full-vocabulary log-normalizer for the `off_mass` diagnostic, with a selected-logit-only arm that computes the same float32 yes/no logits but leaves statement `off_mass` unavailable. Keep image processing, prefix sharing, model precision, prompt text, suffix batching, and answer construction unchanged.
- Primary metric: paired model scoring p50 for the fixed nine-statement multi-question fixture after two warmups and at least ten measured, order-rotated pairs. Secondary metrics: total latency, one-question latency, and the share of scoring time removed.
- Quality guardrail: the selected arm must preserve every raw statement `z`, every returned decision, and every returned answer probability exactly (maximum absolute delta 0). `off_mass` and warnings derived only from it are excluded by design and must be represented as unavailable, never fabricated as zero.
- Hardware/model: Apple M5 with 10-core GPU and 32 GB unified memory; pinned Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`, float16 MPS, 128-token image budget, prefix sharing, suffix batch 16; Glance base commit `3b5205429e153e3c206503409a9e9d5c2f20ee73` plus the experimental flag.
- Stopping rule: stop after the paired protocol completes or any non-diagnostic output differs. Keep the fast path only if scoring p50 falls by at least 5% without a p95 regression greater than 5%; otherwise revert it. The reference behavior remains the library default regardless of outcome.

**Outcome:** rejected by the preregistered primary threshold and reverted. Selected-only scoring preserved every decision, probability, and raw z exactly, but reduced nine-statement score p50 only 3.9% (179→172 ms). The four-statement secondary improved 7.7% (91→84 ms), showing that the full-vocabulary diagnostic costs a roughly fixed 7–8 ms rather than dominating the multi-question path.

## E016 preregistration — native MLX statement scoring

- Implement Glance's independent statement protocol on the pinned 4-bit MLX Qwen3-VL-2B checkpoint: render the same multimodal chat prompts, run one shared image/text prefix, batch the candidate suffixes, and read the same single-token yes/no variants without autoregressive decoding. Compare it with the active PyTorch MPS/FP16 Glance backend on the same three controlled images and four-question/nine-statement request.
- Primary metric: fresh-frame end-to-end p50 after two warmups and at least seven measured repetitions per image/backend. Secondary metrics: image/prefix time, suffix scoring time, output-head time, cache-copy time, peak memory, and one-question latency.
- Quality guardrail: exact per-question decision agreement with Glance and maximum absolute answer-probability delta ≤0.10 across the fixed suite. Record raw statement z values from both systems. The MLX arm does not compute `off_mass`; E015 separately bounds the reference cost of that diagnostic.
- Hardware/model: Apple M5 with 10-core GPU and 32 GB unified memory. Reference: Qwen3-VL-2B revision `89644892e4d85e24eaac8bacfd4f463576704203`, float16 MPS, 128-token image budget, prefix sharing. Candidate: `mlx-community/Qwen3-VL-2B-Instruct-4bit@9c4f5209e57b31f4b9dfba735de3fb983739c9cc`, MLX 0.32.2 and the pinned MLX-VLM commit from E013.
- Stopping rule: stop on a reproducible prompt, mRoPE, KV-cache, or correctness failure, or after the complete paired run. A backend claim requires at least 5% lower fresh-frame p50 and the quality guardrail; otherwise keep the result as an engineering diagnostic only.

**Outcome:** speed supported, parity rejected. The direct 4-bit MLX path reduced fresh nine-statement p50 from 503.4 to 367.3 ms (1.371×; 27.0%) and matched all 84 measured per-question decisions, but maximum probability drift was 0.361 and raw-z drift was 3.089. The shared-prefix arm itself differed from slow, separate MLX full prompts by up to 0.206 z because quantized execution was shape-sensitive. It is not a backend candidate yet.

## E017 preregistration — MLX 8-bit precision frontier

- Run the E016 direct statement scorer unchanged except for replacing the pinned 4-bit MLX checkpoint with `mlx-community/Qwen3-VL-2B-Instruct-8bit@b0338e0e843d8e1befe873d144b81fefdc47efa6`. Compare against the same active Glance FP16 reference and report alongside E016.
- Primary metric: fresh-frame p50 on the same three images and nine statements after two warmups and seven measured repetitions per image. Secondary: prefix/suffix/cache-copy time, peak memory, and speed retained relative to 4-bit MLX.
- Quality guardrail: exact decisions and maximum answer-probability delta ≤0.10 versus Glance. Also record raw-z drift and shared-prefix-versus-full-prompt MLX drift.
- Hardware: Apple M5, 10-core GPU, 32 GB unified memory. Keep prompts, image inputs, batching, selected output rows, and package versions fixed from E016.
- Stopping rule: stop after the complete run or a reproducible checkpoint/compatibility/OOM failure. Keep 8-bit as the backend candidate only if it passes the quality guardrail and remains at least 5% faster than Glance; otherwise test BF16 separately rather than silently widening this experiment.

**Outcome:** supported. MLX 8-bit reduced fresh nine-statement p50 from 358.5 to 259.6 ms (1.381×; 27.6%), matched all 84 measured question decisions, and limited maximum answer-probability drift to 0.039. Peak MLX memory was 3.499 GB. The shared-prefix path differed from slow independent full MLX prompts by at most 0.145 raw z, so execution shape remains numerically visible but did not threaten the Glance probability guardrail. An exact-protocol replication after integration measured 281.7→211.3 ms (1.334×; 25.0%) with the same decision and probability result. Promote this pinned checkpoint and scorer as the first opt-in backend candidate.

## E018 preregistration — fixed-shape MLX compilation

- Compare the validated eager MLX 8-bit direct scorer with an `mx.compile` arm in the same loaded process. Compile only fixed-shape language-model work whose cache state can be passed and updated explicitly; keep image preprocessing, prompt text, shared-prefix boundary, suffix padding, selected output rows, and weights unchanged.
- Primary metric: paired nine-statement scorer wall p50 after at least three warmups and ten measured, alternating repetitions per fixed image/arm. Secondary: prefix and suffix p50/p95, compilation cost, recompilation behavior across the three realized shapes, and peak memory.
- Quality guardrail: exact decisions, maximum answer-probability delta ≤0.001, and maximum raw-z delta ≤0.01 against the eager 8-bit arm. A compile arm that cannot represent KV-cache mutation correctly is a failed implementation, not a speed result.
- Hardware/model: Apple M5, 10-core GPU, 32 GB unified memory; `mlx-community/Qwen3-VL-2B-Instruct-8bit@b0338e0e843d8e1befe873d144b81fefdc47efa6`, MLX 0.32.2, pinned MLX-VLM commit from E013.
- Stopping rule: stop after the paired protocol, a reproducible compile/cache correctness failure, or more than 60 seconds of compile overhead per realized shape. Keep compilation only if wall p50 improves at least 5%, p95 does not regress more than 5%, and the quality guardrail passes.

**Outcome:** rejected. Qwen3-VL's multimodal prefix could not be transformed because its input-embedding path performs an eager `mx.eval`; compiling the fixed-shape cached suffix was correct but operationally flat. Across 30 paired measurements, eager versus compiled wall p50 was 391.5 versus 389.3 ms (1.006×; 0.6%), p95 was 417.4 versus 418.3 ms, and all probabilities/raw z values were bit-identical. Compiled cache-copy p50 increased from 4.9 to 6.5 ms. Keep the simpler eager backend.

## E019 preregistration — MLX vision-token frontier

- Compare the validated eager MLX 8-bit direct scorer at its default processor limit with explicit nominal 64- and 48-token pixel caps. Convert a nominal cap to `max_pixels = tokens × patch_size² × merge_size²`; report realized tokens because Qwen's 32-pixel grid rounding can land below the nominal target.
- Primary metric: paired fresh-frame prefix and wall p50 after three warmups and ten measured, order-rotated repetitions per image/arm. Secondary: suffix latency, realized tokens by image, p95, and peak memory.
- Quality guardrail: exact decisions and maximum answer-probability delta ≤0.10 versus the default MLX 8-bit arm on the fixed suite. Also report combined drift versus Glance using E017's recorded outputs or a paired Glance arm before promoting a live default; do not add two independent worst-case deltas and call that measured parity.
- Hardware/model: Apple M5, 10-core GPU, 32 GB unified memory; pinned MLX 8-bit checkpoint and package versions from E017. Keep JPEGs, prompts, suffix batching, and scoring unchanged.
- Stopping rule: stop after the complete sweep or a reproducible invalid image grid. A cap advances only if wall p50 improves at least 5%, p95 does not regress more than 5%, and the quality guardrail passes. The UI backend remains at the default processor limit until combined Glance parity is measured.

**Outcome:** rejected. The nominal 48-token cap realized 40–45 tokens and reduced wall p50 from 376.2 to 317.4 ms (1.185×; 15.6%) by cutting prefix p50 from 176.1 to 122.1 ms, but changed the dog tone decision and reached 0.411 maximum probability drift. The nominal 64-token cap realized 54/77/63 tokens, improved p50 only 1.2%, changed the same dog tone decision, and drifted by 0.445. Keep the default processor limit.

## E020 preregistration — decoder depth frontier

- Compare the full 28-layer MLX 8-bit language model with inference-only 24- and 20-layer exits. Keep the vision tower, deep-stack inputs, final RMS normalization, tied selected-token head, prompts, image tokens, and suffix batch fixed; truncate the same leading decoder stack for both prefix and suffix work.
- Primary metric: paired wall p50 after three warmups and ten measured, order-rotated repetitions per image/arm. Secondary: prefix/suffix p50/p95 and peak memory.
- Quality guardrail: exact decisions and maximum answer-probability delta ≤0.10 versus the full 28-layer arm. This is an untrained early-exit diagnostic; do not interpret a failure as evidence against a trained intermediate head.
- Hardware/model: Apple M5, 10-core GPU, 32 GB unified memory; pinned MLX 8-bit checkpoint and default image processor from E017.
- Stopping rule: stop after the sweep or any invalid cache/layer-shape behavior. A depth advances only at ≥5% lower wall p50, no >5% p95 regression, and a passing guardrail. Do not expose an untrained exit in the UI if it fails.

**Outcome:** rejected, with a near-miss boundary. A 24-layer exit reduced wall p50 from 375.7 to 334.0 ms (1.125×; 11.1%) and preserved every fixed decision, but maximum probability drift was 0.207. A 20-layer exit reached 294.0 ms (1.278×; 21.7%) but changed four decisions and drifted by 0.996. Do not truncate to either depth; refine the 26/27-layer boundary separately.

## E021 preregistration — shallow decoder refinement

- Refine E020 between the full 28-layer reference and failed 24-layer arm by testing 27 and 26 leading decoder layers in the same loaded, order-rotated MLX process. Keep every other variable fixed.
- Primary metric: paired wall p50 after three warmups and ten measured repetitions per image/arm. Secondary: prefix/suffix p50/p95 and memory.
- Quality guardrail: exact decisions and maximum answer-probability delta ≤0.10 versus 28 layers. Record raw-z drift, but probability is the adoption boundary.
- Hardware/model: identical to E020: Apple M5, pinned MLX 8-bit checkpoint, default 70–80 realized image tokens.
- Stopping rule: advance a depth only at ≥5% lower wall p50, no >5% p95 regression, and passing quality. If 26 fails and 27 is below 5%, stop untrained layer truncation and move the idea to trained early-exit heads.

**Outcome:** rejected; stop untrained truncation. The 26-layer arm reduced wall p50 6.1% (379.7→356.4 ms) but changed the receipt-photo decision and drifted by 0.606. The 27-layer arm preserved decisions but improved p50 only 3.4% and drifted by 0.242. Neither passes quality; 27 also misses the speed threshold. Future early exit requires a trained intermediate head or distillation.
