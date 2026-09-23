#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';

const artifact = JSON.parse(await readFile('research/results/model-experiments.json', 'utf8'));
const reports = {
  E001: {
    directory: '001-resolution', title: 'Resolution',
    interpretation: 'Rejected. 224 px was effectively identical in speed to 320 px (0.999×), while decision agreement fell to 66.7% and maximum probability drift reached 0.856. The fixed model image-token budget explains why fewer browser pixels did not buy model latency.',
  },
  E002: {
    directory: '002-jpeg-quality', title: 'JPEG quality',
    interpretation: 'Quality 40 passed the answer guardrail (100% decisions; maximum probability drift 0.00558) and substantially reduced bytes, but model p50 and local encoding remained operationally unchanged. Keep quality 60 as the default; quality 40 is a bandwidth knob, not a local speed optimization.',
  },
  E003: {
    directory: '003-native-batch', title: 'Native batching',
    interpretation: 'Confirmed. One cold four-question request was 2.405× faster than four cold single requests (529.8 ms versus 1274.0 ms p50), with 100% decision agreement and only 0.00125 maximum probability drift. This remains the default architecture.',
  },
  E006: {
    directory: '006-question-order', title: 'Question order',
    interpretation: 'Rejected as an optimization. Forward versus reverse order differed by only -0.204% at p50 and produced exactly identical probabilities. Canonical statement sorting in Glance makes caller order irrelevant.',
  },
};

for (const [id, report] of Object.entries(reports)) {
  const payload = artifact.summary[id];
  const markdown = `# ${id} result — ${report.title}\n\n${report.interpretation}\n\nGenerated from the aggregate artifact \`research/results/model-experiments.json\`; detailed paired rows remain ignored.\n\n\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\`\n`;
  await writeFile(`research/experiments/${report.directory}/result.md`, markdown);
}

console.log('Wrote curated model experiment results.');
