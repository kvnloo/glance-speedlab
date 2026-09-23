# Round-one hypotheses and outcomes

| ID | Hypothesis | Outcome |
| --- | --- | --- |
| H01 | 224 px frames beat 320 px materially | Rejected: model p50 unchanged; decision agreement only 66.7% |
| H02 | Lower JPEG quality reduces non-model latency | Safe bandwidth reduction, but latency effect is negligible |
| H03 | One native request for N questions beats N requests | Confirmed: 2.405× faster with the guardrail passed |
| H04 | Persistent capture resources reduce browser tail latency | No measured p50/p95 win; allocation hygiene only |
| H05 | Base64/JSON becomes material below ~150 ms model latency | Rejected at current payload sizes: ≤0.1 ms p95 |
| H06 | Question order affects shared-prefix scoring latency | Rejected: operational delta −0.204%, probabilities identical |
| H07 | Temporal frame reuse can increase answer Hz | Synthetic support; real-camera validation still required |
| H08 | Lowering the configured image-token budget from 768 to 128–256 reduces the 320 px live path | Rejected: every arm realized the same 70–80 image tokens and had the same latency/output |
| H09 | MPS has a better cached suffix batch size than 16 | Rejected for the nine-statement batch: 32 was flat; 4 and 8 were slower |
| H10 | One-rotation letter-choice scoring beats independent statements | Rejected: fewer forward passes did not reduce total latency and probability drift failed the guardrail |
| H11 | Qwen3-VL-2B offers a better live latency/quality frontier than 4B | Mixed: 2.994× faster, but only 83.3% per-question decision agreement and large probability drift |
| H18 | Budgets below 128 cross the observed token floor and reduce live latency | Speed confirmed; fixed guardrail rejected. 4B/48 was 1.092× with decision parity but probability delta 0.130; 2B/48 changed a decision |
| H13 | MLX or Core ML execution materially beats PyTorch MPS | MLX supported for new frames: 1.417× with coarse-label agreement; full Glance probability parity remains open |
| H22 | MLX vision/prompt caching closes the exact-image gap to Glance | Mixed: continued chat improved 2.048× to 92.0 ms; standalone Qwen3-VL cache paths restored zero tokens |
| H25 | Omitting full-vocabulary `off_mass` normalization materially accelerates direct statement scoring | Rejected on the primary workload: exact outputs and 7–8 ms saved, but nine-statement score p50 improved only 3.9% |
| H21 | Native MLX statement scoring preserves Glance semantics while retaining the backend gain | Supported at 8-bit: 1.381×, exact decisions, max probability drift 0.039; 4-bit failed parity |
| H26 | Eight-bit MLX improves the 4-bit probability frontier without surrendering speed | Confirmed: drift fell 0.361→0.039 and p50 remained 27.6% below Glance |
| H27 | Fixed-shape `mx.compile` materially accelerates the direct scorer | Rejected: suffix outputs were exact, but wall p50 improved only 0.6% |
| H28 | Uniformly lowering MLX vision tokens is a safe prefix optimization | Rejected: 48 nominal tokens was 15.6% faster but changed a decision and drifted 0.411 |
| H29 | The pretrained output head supports a safe untrained decoder exit | Rejected: no depth from 20–27 passed both the speed and quality gates |

## Next hypothesis set

| Priority | ID | Hypothesis | Expected mechanism | Guardrail |
| ---: | --- | --- | --- | --- |
| 1 | H30 | A trained intermediate decision head recovers full-depth statement margins at 20–24 layers | E020 measured 11–22% raw speed headroom, but the pretrained LM head is miscalibrated early | Held-out labels, calibration, open-set failures, and full-depth escalation |
| 2 | H31 | Learned or saliency-aware vision-token selection keeps the 48-token speed gain without uniform-resize errors | E019 isolated a 54 ms prefix saving, but uniform reduction changed tone | Larger labeled suite, OCR/fine-detail slices, token-selection stability |
| 3 | H24 | Model-shaped Metal kernels beat general MLX materially for fixed Qwen3-VL shapes | E018 shows generic compilation is flat; Husky motivates fusion, packed weights, and pipelined submission | Same weights/outputs; separate vision, prefix LM, and suffix LM; development cost |
| 4 | H32 | The accepted MLX 8-bit backend retains its 1.381× gain under a 30-minute live-camera load | Short paired runs do not establish thermals or p99 | Temperature, power, memory, p50/p95/p99, failures, frame age |
| 5 | H33 | MLX 8-bit passes a larger labeled real-camera parity suite against Glance FP16 | E017 passed only three fixtures and four questions | Calibration error, task slices, rare events, exact decision agreement |
| 6 | H12 | Uncertainty-gated fast→reference escalation recovers reference quality at lower mean latency | Fast model/depth/token arms expose large gains with localized failures | Coverage-risk curve, escalation rate, mean and tail latency |
| 7 | H14 | Threshold-4 temporal reuse passes on labeled real-camera sequences | Synthetic gating result transfers to real motion/noise | 100% salient-event recall and ≥95% gradual-change recall |
| 8 | H16 | Reusing vision embeddings for perceptually similar adjacent frames beats response-only reuse | Avoid repeated vision work while still rescoring questions | Drift detection, scene-cut recall, and bounded probability error |
| 9 | H34 | Core ML or ANE placement improves sustained efficiency even if single-run latency is similar | MLX wins on GPU; no ANE path has been measured | Same model semantics, conversion fidelity, sustained watts and latency |

The entries above remain exploratory until moved into `EXPERIMENTS.md` with a fixed protocol.
