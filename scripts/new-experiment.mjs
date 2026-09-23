#!/usr/bin/env node
import { appendFile, copyFile, mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const slug = process.argv[2]?.trim().toLowerCase();
if (!slug || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
  console.error('Usage: pnpm experiment:new -- short-kebab-case-slug');
  process.exit(2);
}

const root = 'research/experiments';
const entries = await readdir(root, { withFileTypes: true });
const lastId = Math.max(...entries.filter((entry) => entry.isDirectory()).map((entry) => Number.parseInt(entry.name, 10)).filter(Number.isFinite), 0);
const numericId = lastId + 1;
const padded = String(numericId).padStart(3, '0');
const experimentId = `E${padded}`;
const directory = join(root, `${padded}-${slug}`);
await mkdir(directory, { recursive: false });
await copyFile('research/templates/experiment.md', join(directory, 'plan.md'));
const plan = await readFile(join(directory, 'plan.md'), 'utf8');
await writeFile(join(directory, 'plan.md'), plan.replace('E___ — Title', `${experimentId} — ${slug.replaceAll('-', ' ')}`));
await appendFile('research/EXPERIMENTS.md', `\n| ${experimentId} | ${new Date().toISOString().slice(0, 10)} | TODO before implementation | TODO | Planned | Pending |\n`);
console.log(`Created ${directory}/plan.md and registered ${experimentId}.`);
