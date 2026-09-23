#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9223;
const profile = await mkdtemp(join(tmpdir(), 'glance-speedlab-chrome-'));
const modelMs = Number(process.argv[2]) || 525;
const child = spawn(chrome, [
  '--headless=new', '--disable-gpu', '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`,
  `http://127.0.0.1:8787/lab.html?autorun=1&modelMs=${modelMs}`,
], { stdio: ['ignore', 'ignore', 'ignore'] });

try {
  const target = await waitForTarget(port, 15_000);
  const client = await connect(target.webSocketDebuggerUrl);
  await client.call('Runtime.enable');
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    const evaluation = await client.call('Runtime.evaluate', {
      expression: `({status: document.querySelector('#status')?.textContent, results: document.querySelector('#results')?.textContent})`,
      returnByValue: true,
    });
    const value = evaluation.result?.result?.value;
    if (value?.status?.startsWith('complete')) {
      console.log(value.results);
      process.exitCode = 0;
      break;
    }
    if (value?.status?.startsWith('failed')) throw new Error(value.status);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (Date.now() >= deadline) throw new Error('Browser experiments timed out.');
  client.close();
} finally {
  child.kill('SIGTERM');
  await rm(profile, { recursive: true, force: true });
}

async function waitForTarget(debugPort, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/list`);
      const targets = await response.json();
      const match = targets.find((target) => target.type === 'page' && target.url.includes('/lab.html'));
      if (match) return match;
    } catch {
      // Chrome is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('Chrome DevTools endpoint did not become ready.');
}

async function connect(url) {
  const socket = new WebSocket(url);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  let id = 0;
  const pending = new Map();
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data));
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    if (message.error) waiter.reject(new Error(message.error.message));
    else waiter.resolve(message);
  });
  return {
    call(method, params = {}) {
      id += 1;
      const requestId = id;
      return new Promise((resolve, reject) => {
        pending.set(requestId, { resolve, reject });
        socket.send(JSON.stringify({ id: requestId, method, params }));
      });
    },
    close() { socket.close(); },
  };
}
