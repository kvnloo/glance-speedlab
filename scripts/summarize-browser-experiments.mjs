#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const raw = JSON.parse(await readFile('research/runs/browser-experiments.json', 'utf8'));
const result = {
  environment: raw.environment,
  timestamp: raw.timestamp,
  experiments: raw.experiments,
};
await mkdir('research/results', { recursive: true });
await writeFile('research/results/browser-experiments.json', `${JSON.stringify(result, null, 2)}\n`);

const reports = {
  E004: {
    directory: '004-persistent-capture',
    title: 'Persistent capture resources',
    interpretation: 'No measurable p50 or p95 latency improvement at 320×180; persistent reuse still avoids two allocations per frame and remains as allocation hygiene, not a speed claim.',
  },
  E005: {
    directory: '005-base64-json',
    title: 'Base64 and JSON transport',
    interpretation: 'Rejected. At 320 px, combined base64/stringify/parse measured 0.0 ms p50 and 0.1 ms p95—far below the preregistered 5% materiality threshold for a 150 ms model.',
  },
  E007: {
    directory: '007-temporal-reuse',
    title: 'Temporal frame reuse',
    interpretation: 'Supported on deterministic synthetic sequences. Threshold 4 preserved 100% abrupt and gradual event recall while reducing inference triggers 95.1%. It is exposed as an off-by-default experimental live toggle pending a real-camera replication.',
  },
};

for (const [id, report] of Object.entries(reports)) {
  const payload = raw.experiments[id];
  const markdown = `# ${id} result — ${report.title}\n\n${report.interpretation}\n\nGenerated from \`research/runs/browser-experiments.json\`; the detailed raw run remains ignored.\n\n\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\`\n`;
  await writeFile(`research/experiments/${report.directory}/result.md`, markdown);
}

console.log('Wrote curated browser experiment results.');
