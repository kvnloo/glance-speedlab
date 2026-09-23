#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { basename, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import { createHash } from 'node:crypto';

const args = parseArgs(process.argv.slice(2));
if (!args.image) {
  console.error('Usage: pnpm bench -- --image /absolute/image.jpg [--warmup 3] [--iterations 20] [--url http://127.0.0.1:8787]');
  process.exit(2);
}

const imagePath = resolve(args.image);
const image = await readFile(imagePath);
const gatewayUrl = String(args.url || 'http://127.0.0.1:8787').replace(/\/$/, '');
const warmup = positiveInteger(args.warmup, 3);
const iterations = positiveInteger(args.iterations, 20);
const body = {
  imageBase64: image.toString('base64'),
  questions: [{
    id: 'expression',
    type: 'choice',
    instructions: 'Which visible facial expression best matches the person in `img0` right now?',
    criteria: ['Happy', 'Sad', 'Angry', 'Confused', 'Neutral'],
  }],
};

const health = await fetchJson(`${gatewayUrl}/api/health`);
const rows = [];
for (let index = 0; index < warmup + iterations; index += 1) {
  const startedAt = performance.now();
  const response = await fetch(`${gatewayUrl}/api/decide`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(`Benchmark request ${index + 1} failed: ${JSON.stringify(payload)}`);
  const row = {
    requestMs: round(performance.now() - startedAt),
    gatewayMs: payload.speedlab.gatewayMs,
    upstreamMs: payload.speedlab.upstreamMs,
    modelTimingMs: payload.timing_ms ?? {},
  };
  if (index >= warmup) rows.push(row);
  console.error(`${index < warmup ? 'warmup' : 'sample'} ${index + 1}/${warmup + iterations}: ${row.requestMs} ms`);
}

const fields = ['requestMs', 'gatewayMs', 'upstreamMs'];
const summary = Object.fromEntries(fields.map((field) => [field, summarize(rows.map((row) => row[field]))]));
const modelKeys = [...new Set(rows.flatMap((row) => Object.keys(row.modelTimingMs)))].sort();
summary.modelTimingMs = Object.fromEntries(modelKeys.map((key) => [key, summarize(rows.map((row) => Number(row.modelTimingMs[key])).filter(Number.isFinite))]));

console.log(JSON.stringify({
  schemaVersion: 1,
  experiment: 'E000',
  startedAt: new Date().toISOString(),
  input: {
    name: basename(imagePath),
    bytes: image.length,
    sha256: createHash('sha256').update(image).digest('hex'),
    contentNotStored: true,
  },
  config: { gatewayUrl, warmup, iterations, questionCount: 1 },
  environment: { node: process.version, platform: process.platform, arch: process.arch, health },
  summary,
  rows,
}, null, 2));

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(`Health check failed: ${JSON.stringify(payload)}`);
  return payload;
}

function summarize(values) {
  return {
    count: values.length,
    min: round(Math.min(...values)),
    p50: round(percentile(values, 0.5)),
    p90: round(percentile(values, 0.9)),
    p95: round(percentile(values, 0.95)),
    max: round(Math.max(...values)),
    mean: round(values.reduce((sum, value) => sum + value, 0) / values.length),
  };
}

function percentile(values, quantile) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(quantile * sorted.length) - 1)];
}

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function round(value) {
  return Math.round(value * 100) / 100;
}

function parseArgs(tokens) {
  const result = {};
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === '--') continue;
    if (!token?.startsWith('--')) continue;
    result[token.slice(2)] = tokens[index + 1] ?? true;
    index += 1;
  }
  return result;
}
