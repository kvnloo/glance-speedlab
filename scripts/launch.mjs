#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { resolve } from 'node:path';
import { loadEnvFile } from 'node:process';

try {
  loadEnvFile(resolve('.env'));
} catch (error) {
  if (error?.code !== 'ENOENT') throw error;
}

const core = resolve(process.env.GLANCE_CORE || '../glance');
const glanceBinary = resolve(core, '.venv/bin/glance');
const mlxPython = resolve(process.env.SPEEDLAB_MLX_PYTHON || 'research/runs/e013-venv/bin/python');
const children = [];
const startMlx = process.argv.includes('--mlx');
const profile = parseProfile(process.argv.slice(2));
const configPath = profile ? await writeProfileConfig(core, profile) : null;

await access(glanceBinary, constants.X_OK);
if (!(await healthy('http://127.0.0.1:8077/healthz'))) {
  console.log(`Starting Glance and loading the local VLM${profile ? ` (${profile.tier}, ${profile.tokens} tokens)` : ''}…`);
  const modelArgs = [...(configPath ? ['--config', configPath] : []), 'serve', '--preload', 'vlm', '--prefix-cache', '--port', '8077'];
  const model = spawn(glanceBinary, modelArgs, {
    cwd: core,
    stdio: 'inherit',
    env: process.env,
  });
  children.push(model);
  await waitForHealth('http://127.0.0.1:8077/healthz', 240_000, model);
} else if (profile && !(await profileMatches(profile))) {
  throw new Error('Glance is already running with a different model profile. Stop that local process, then run this profile command again.');
}

if (startMlx && !(await healthy('http://127.0.0.1:8079/healthz'))) {
  await access(mlxPython, constants.X_OK);
  console.log('Starting the pinned MLX 8-bit direct scorer…');
  const mlx = spawn(mlxPython, ['src/mlx_backend/server.py'], {
    cwd: process.cwd(),
    stdio: 'inherit',
    env: { ...process.env, GLANCE_CORE: core },
  });
  children.push(mlx);
  await waitForHealth('http://127.0.0.1:8079/healthz', 240_000, mlx);
}

console.log('Building the browser app…');
const build = spawnSync(resolve('node_modules/.bin/vite'), ['build'], { cwd: process.cwd(), stdio: 'inherit' });
if (build.status !== 0) process.exit(build.status ?? 1);

if (await healthy('http://127.0.0.1:8787/api/config')) {
  console.log('Speedlab is already running at http://127.0.0.1:8787');
} else {
  const app = spawn(process.execPath, ['src/server/index.mjs', '--static'], { cwd: process.cwd(), stdio: 'inherit', env: process.env });
  children.push(app);
  await waitForHealth('http://127.0.0.1:8787/api/config', 10_000, app);
}

console.log('\nGlance Speedlab is ready: http://127.0.0.1:8787');
if (startMlx) console.log('MLX 8-bit candidate is available in the Backend menu.');
console.log('Press Ctrl-C to stop processes started by this launcher.');

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    for (const child of children) child.kill('SIGTERM');
    process.exit(0);
  });
}
if (children.length) {
  await new Promise((resolvePromise) => {
    for (const child of children) child.once('exit', resolvePromise);
  });
}

async function healthy(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1_500) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForHealth(url, timeoutMs, child) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Process exited before ${url} became ready.`);
    if (await healthy(url)) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 1_000));
  }
  throw new Error(`Timed out waiting for ${url}.`);
}

function parseProfile(argv) {
  const value = (name, fallback) => {
    const index = argv.indexOf(name);
    return index >= 0 ? argv[index + 1] : fallback;
  };
  const requested = argv.some((item) => ['--tier', '--tokens', '--suffix-batch', '--letter-rotations'].includes(item));
  if (!requested) return null;
  const tier = value('--tier', '4b');
  if (!['2b', '4b'].includes(tier)) throw new Error('--tier must be 2b or 4b.');
  const numeric = (name, fallback) => {
    const parsed = Number.parseInt(value(name, String(fallback)), 10);
    if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${name} must be a positive integer.`);
    return parsed;
  };
  return { tier, tokens: numeric('--tokens', 128), suffixBatch: numeric('--suffix-batch', 16), letterRotations: numeric('--letter-rotations', 4) };
}

async function writeProfileConfig(corePath, selected) {
  const source = await readFile(resolve(corePath, 'configs/default.yaml'), 'utf8');
  const configured = source
    .replace('tier_override: null', `tier_override: ${selected.tier === '2b' ? 'apple_8gb' : 'apple_32gb'}`)
    .replace('image_token_budget_override: null', `image_token_budget_override: ${selected.tokens}`)
    .replace(/suffix_batch_size: \d+/, `suffix_batch_size: ${selected.suffixBatch}`)
    .replace(/letter_rotations: \d+/, `letter_rotations: ${selected.letterRotations}`);
  const directory = resolve('research/runs');
  await mkdir(directory, { recursive: true });
  const path = resolve(directory, 'active-glance-config.yaml');
  await writeFile(path, configured, { encoding: 'utf8', mode: 0o600 });
  return path;
}

async function profileMatches(selected) {
  try {
    const [healthResponse, modelsResponse] = await Promise.all([
      fetch('http://127.0.0.1:8077/healthz'),
      fetch('http://127.0.0.1:8077/v1/models'),
    ]);
    const [health, models] = await Promise.all([healthResponse.json(), modelsResponse.json()]);
    const vlm = models.loaded?.find((model) => model.name === 'vlm');
    const expectedTier = selected.tier === '2b' ? 'apple_8gb' : 'apple_32gb';
    return health.selected_tier === expectedTier && vlm?.image_token_budget === selected.tokens;
  } catch {
    return false;
  }
}
