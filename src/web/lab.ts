type Summary = { n: number; min: number; p50: number; p90: number; p95: number; max: number; mean: number };

const runButton = required<HTMLButtonElement>('#run');
const statusNode = required<HTMLElement>('#status');
const resultsNode = required<HTMLElement>('#results');

runButton.addEventListener('click', () => void runAll());
if (new URLSearchParams(location.search).has('autorun')) void runAll();

async function runAll(): Promise<void> {
  runButton.disabled = true;
  try {
    statusNode.textContent = 'E004 · persistent capture resources';
    const e004 = await persistentCanvasExperiment();
    statusNode.textContent = 'E005 · base64 and JSON transport';
    const e005 = await transportExperiment();
    statusNode.textContent = 'E007 · temporal frame reuse';
    const e007 = temporalReuseExperiment();
    const payload = {
      schemaVersion: 1,
      timestamp: new Date().toISOString(),
      environment: {
        userAgent: navigator.userAgent,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: 'deviceMemory' in navigator ? Number((navigator as Navigator & { deviceMemory?: number }).deviceMemory) : null,
      },
      experiments: { E004: e004, E005: e005, E007: e007 },
    };
    resultsNode.textContent = JSON.stringify(payload, null, 2);
    const response = await fetch('/api/research/browser', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Could not save results (${response.status}).`);
    statusNode.textContent = 'complete · saved to research/runs/browser-experiments.json';
  } catch (error) {
    statusNode.textContent = `failed · ${error instanceof Error ? error.message : String(error)}`;
  } finally {
    runButton.disabled = false;
  }
}

async function persistentCanvasExperiment(): Promise<Record<string, unknown>> {
  const width = 320, height = 180, warmups = 20, iterations = 200;
  const persistent = document.createElement('canvas');
  persistent.width = width; persistent.height = height;
  const persistentContext = persistent.getContext('2d', { alpha: false });
  if (!persistentContext) throw new Error('Canvas context unavailable.');

  const arms: Record<string, number[]> = { persistent: [], allocate_each_frame: [] };
  let geometryPassed = true;
  for (let index = 0; index < warmups + iterations; index += 1) {
    const order = index % 2 === 0 ? ['persistent', 'allocate_each_frame'] : ['allocate_each_frame', 'persistent'];
    for (const arm of order) {
      const started = performance.now();
      let canvas: HTMLCanvasElement, context: CanvasRenderingContext2D;
      if (arm === 'persistent') {
        canvas = persistent; context = persistentContext;
      } else {
        canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        const next = canvas.getContext('2d', { alpha: false });
        if (!next) throw new Error('Canvas context unavailable.');
        context = next;
      }
      drawSynthetic(context, width, height, index);
      const blob = await canvasBlob(canvas, 0.6);
      if (index === warmups) {
        const bitmap = await createImageBitmap(blob);
        geometryPassed = geometryPassed && bitmap.width === width && bitmap.height === height;
        bitmap.close();
      }
      if (index >= warmups) arms[arm]?.push(performance.now() - started);
    }
  }
  const persistentStats = summarize(arms.persistent ?? []);
  const allocatedStats = summarize(arms.allocate_each_frame ?? []);
  return {
    config: { width, height, jpegQuality: 0.6, warmups, iterations },
    persistent_ms: persistentStats,
    allocate_each_frame_ms: allocatedStats,
    p50_speedup: round(allocatedStats.p50 / persistentStats.p50),
    p95_speedup: round(allocatedStats.p95 / persistentStats.p95),
    allocations_avoided_per_frame: 2,
    guardrail: { decodedGeometryIdentical: geometryPassed, passed: geometryPassed },
  };
}

async function transportExperiment(): Promise<Record<string, unknown>> {
  const sizes = [160, 224, 320, 448], warmups = 20, iterations = 300;
  const variants: Record<string, unknown> = {};
  for (const edge of sizes) {
    const canvas = document.createElement('canvas');
    canvas.width = edge; canvas.height = Math.round(edge * 9 / 16);
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) throw new Error('Canvas context unavailable.');
    drawSynthetic(context, canvas.width, canvas.height, 17);
    const blob = await canvasBlob(canvas, 0.6);
    const encode: number[] = [], stringify: number[] = [], parse: number[] = [], combined: number[] = [];
    let bytesRoundTrip = true;
    for (let index = 0; index < warmups + iterations; index += 1) {
      const allStarted = performance.now();
      const encodeStarted = performance.now();
      const base64 = await blobToBase64(blob);
      const encodeDone = performance.now();
      const stringifyStarted = performance.now();
      const json = JSON.stringify({ imageBase64: base64, questions: syntheticQuestions });
      const stringifyDone = performance.now();
      const parseStarted = performance.now();
      const parsed = JSON.parse(json) as { imageBase64: string };
      const parseDone = performance.now();
      if (index === warmups) bytesRoundTrip = base64Bytes(parsed.imageBase64) === blob.size;
      if (index >= warmups) {
        encode.push(encodeDone - encodeStarted);
        stringify.push(stringifyDone - stringifyStarted);
        parse.push(parseDone - parseStarted);
        combined.push(parseDone - allStarted);
      }
    }
    const combinedStats = summarize(combined);
    variants[String(edge)] = {
      jpegBytes: blob.size,
      requestBytes: JSON.stringify({ imageBase64: await blobToBase64(blob), questions: syntheticQuestions }).length,
      base64_ms: summarize(encode), stringify_ms: summarize(stringify), parse_ms: summarize(parse), combined_ms: combinedStats,
      share_of_150ms_p50_pct: round(combinedStats.p50 / 150 * 100),
      share_of_150ms_p95_pct: round(combinedStats.p95 / 150 * 100),
      guardrail: { decodedByteLengthIdentical: bytesRoundTrip, passed: bytesRoundTrip },
    };
  }
  const at320 = variants['320'] as { share_of_150ms_p50_pct: number };
  return { config: { warmups, iterations, modelBudgetMs: 150 }, variants, materialAt320: at320.share_of_150ms_p50_pct >= 5 };
}

function temporalReuseExperiment(): Record<string, unknown> {
  const thresholds = [1, 2, 4, 8], seeds = 10, frames = 300, fps = 30, maxStaleFrames = 30;
  const modelMs = Number(new URLSearchParams(location.search).get('modelMs')) || 150;
  const variants: Record<string, unknown> = {};
  for (const threshold of thresholds) {
    let totalTriggers = 0, abruptHit = 0, abruptCount = 0, gradualHit = 0, gradualCount = 0;
    for (let seed = 0; seed < seeds; seed += 1) {
      const sequence = makeSequence(seed, frames);
      let reference = sequence.frames[0] ?? new Uint8Array();
      let lastTrigger = 0;
      const triggerFrames = new Set([0]);
      for (let frame = 1; frame < sequence.frames.length; frame += 1) {
        const current = sequence.frames[frame] ?? new Uint8Array();
        if (meanAbsoluteDifference(current, reference) >= threshold || frame - lastTrigger >= maxStaleFrames) {
          triggerFrames.add(frame); reference = current; lastTrigger = frame;
        }
      }
      totalTriggers += triggerFrames.size;
      for (const event of sequence.events) {
        const hit = [...triggerFrames].some((frame) => frame >= event.start && frame <= event.deadline);
        if (event.kind === 'abrupt') { abruptCount += 1; if (hit) abruptHit += 1; }
        else { gradualCount += 1; if (hit) gradualHit += 1; }
      }
    }
    const durationSeconds = seeds * frames / fps;
    const inferenceHz = totalTriggers / durationSeconds;
    const baselineModelHz = 1_000 / modelMs;
    const abruptRecall = abruptHit / abruptCount;
    const gradualRecall = gradualHit / gradualCount;
    variants[String(threshold)] = {
      triggerCount: totalTriggers,
      inferenceHz: round(inferenceHz),
      computeReductionPct: round((1 - totalTriggers / (seeds * frames)) * 100),
      effectiveAnswerHz: fps,
      answerHzMultiplierVsFreshInference: round(fps / baselineModelHz),
      guardrail: { abruptRecall, gradualRecall, passed: abruptRecall === 1 && gradualRecall >= 0.95 },
    };
  }
  return { config: { thresholds, seeds, frames, cameraFps: fps, maxStaleFrames, modelMs }, variants };
}

function drawSynthetic(context: CanvasRenderingContext2D, width: number, height: number, frame: number): void {
  const gradient = context.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, `hsl(${(frame * 7) % 360} 55% 35%)`);
  gradient.addColorStop(1, '#d8ff91');
  context.fillStyle = gradient; context.fillRect(0, 0, width, height);
  context.fillStyle = 'rgba(8, 10, 12, .78)'; context.fillRect(width * .12, height * .18, width * .76, height * .64);
  context.fillStyle = '#f5f7f1'; context.font = `${Math.max(12, width / 15)}px system-ui`;
  context.fillText(`frame ${frame}`, width * .19, height * .54);
}

function makeSequence(seed: number, length: number): { frames: Uint8Array[]; events: { kind: 'abrupt' | 'gradual'; start: number; deadline: number }[] } {
  const pixels = 64, frames: Uint8Array[] = [], events: { kind: 'abrupt' | 'gradual'; start: number; deadline: number }[] = [];
  let scene = 70 + seed;
  for (let frame = 0; frame < length; frame += 1) {
    if (frame === 90 || frame === 210) { scene += 24; events.push({ kind: 'abrupt', start: frame, deadline: frame + 1 }); }
    if (frame === 30 || frame === 150) events.push({ kind: 'gradual', start: frame, deadline: frame + 12 });
    if ((frame >= 30 && frame <= 42) || (frame >= 150 && frame <= 162)) scene += 1;
    const values = new Uint8Array(pixels);
    for (let pixel = 0; pixel < pixels; pixel += 1) values[pixel] = Math.max(0, Math.min(255, Math.round(scene + seededNoise(seed, frame, pixel))));
    frames.push(values);
  }
  return { frames, events };
}

function seededNoise(seed: number, frame: number, pixel: number): number {
  const value = Math.sin((seed + 1) * 12.9898 + frame * 78.233 + pixel * 37.719) * 43758.5453;
  return ((value - Math.floor(value)) - 0.5) * 1.2;
}

function meanAbsoluteDifference(left: Uint8Array, right: Uint8Array): number {
  let total = 0;
  for (let index = 0; index < left.length; index += 1) total += Math.abs((left[index] ?? 0) - (right[index] ?? 0));
  return total / left.length;
}

function canvasBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('JPEG encode failed.')), 'image/jpeg', quality));
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error('FileReader failed.'));
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.readAsDataURL(blob);
  });
}

function base64Bytes(value: string): number { return atob(value).length; }

function summarize(values: number[]): Summary {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    n: sorted.length, min: round(sorted[0] ?? 0), p50: round(percentile(sorted, .5)), p90: round(percentile(sorted, .9)),
    p95: round(percentile(sorted, .95)), max: round(sorted.at(-1) ?? 0), mean: round(sorted.reduce((sum, value) => sum + value, 0) / Math.max(1, sorted.length)),
  };
}

function percentile(sorted: number[], quantile: number): number {
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * quantile) - 1))] ?? 0;
}

function round(value: number): number { return Math.round(value * 1_000) / 1_000; }

const syntheticQuestions = [{ id: 'content', type: 'choice', instructions: 'What is in `img0`?', criteria: ['animal', 'document', 'other'] }];

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Browser lab element ${selector} is missing.`);
  return element;
}
