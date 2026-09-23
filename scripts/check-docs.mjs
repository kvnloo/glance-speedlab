#!/usr/bin/env node
import { access, readFile, readdir } from 'node:fs/promises';
import { dirname, extname, resolve } from 'node:path';

const root = process.cwd();
const ignoredNames = new Set(['.git', 'dist', 'node_modules']);
const ignoredPaths = new Set([resolve(root, 'research/runs')]);
const markdown = await collect(root);
const failures = [];

for (const file of markdown) {
  const source = await readFile(file, 'utf8');
  for (const match of source.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
    const raw = match[1].trim().replace(/^<|>$/g, '');
    if (!raw || /^(?:https?:|mailto:|#)/.test(raw)) continue;
    const path = raw.split('#', 1)[0];
    try {
      await access(resolve(dirname(file), path));
    } catch {
      failures.push(`${file.slice(root.length + 1)}: missing link target ${raw}`);
    }
  }
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Checked ${markdown.length} Markdown files.`);

async function collect(directory) {
  const output = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (ignoredNames.has(entry.name) || ignoredPaths.has(path)) continue;
    if (entry.isDirectory()) output.push(...await collect(path));
    else if (extname(entry.name) === '.md') output.push(path);
  }
  return output;
}
