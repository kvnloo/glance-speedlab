import { createServer } from 'node:http';
import { appendFile, readFile, stat, writeFile } from 'node:fs/promises';
import { extname, join, resolve, sep } from 'node:path';
import { performance } from 'node:perf_hooks';
import { normalizeDecideInput, normalizeMetricInput, toGlanceRequest } from './protocol.mjs';

const host = process.env.SPEEDLAB_HOST?.trim() || '127.0.0.1';
const port = Number.parseInt(process.env.SPEEDLAB_PORT ?? '', 10) || 8787;
const glanceUrl = (process.env.GLANCE_URL?.trim() || 'http://127.0.0.1:8077').replace(/\/$/, '');
const mlxUrl = (process.env.SPEEDLAB_MLX_URL?.trim() || 'http://127.0.0.1:8079').replace(/\/$/, '');
const runsDir = resolve(process.env.SPEEDLAB_RUNS_DIR?.trim() || 'research/runs');
const serveStatic = process.argv.includes('--static');
const distDir = resolve('dist');

const server = createServer(async (request, response) => {
  const startedAt = performance.now();
  const url = new URL(request.url ?? '/', `http://${request.headers.host ?? 'localhost'}`);
  response.setHeader('x-content-type-options', 'nosniff');
  response.setHeader('cache-control', 'no-store');

  try {
    if (request.method === 'GET' && url.pathname === '/api/health') {
      const [glance, models, mlx] = await Promise.all([
        fetchJson(`${glanceUrl}/healthz`, 5_000),
        fetchJson(`${glanceUrl}/v1/models`, 5_000),
        fetchJson(`${mlxUrl}/healthz`, 5_000),
      ]);
      const glanceOnline = glance.ok && models.ok;
      const mlxOnline = mlx.ok;
      return sendJson(response, glanceOnline || mlxOnline ? 200 : 503, {
        online: glanceOnline || mlxOnline,
        glanceOnline,
        mlxOnline,
        glance: glance.payload,
        mlx: mlx.payload,
        models: models.payload?.loaded ?? [],
      });
    }

    if (request.method === 'POST' && url.pathname === '/api/decide') {
      const rawBody = await readBody(request, 5_000_000);
      const input = normalizeDecideInput(JSON.parse(rawBody));
      const glanceBody = JSON.stringify(toGlanceRequest(input));
      const selectedUrl = input.backend === 'mlx-8bit' ? mlxUrl : glanceUrl;
      const upstreamStartedAt = performance.now();
      const upstream = await fetch(`${selectedUrl}/v1/decide`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: glanceBody,
        signal: AbortSignal.timeout(120_000),
      });
      const upstreamMs = performance.now() - upstreamStartedAt;
      const upstreamText = await upstream.text();
      const payload = JSON.parse(upstreamText);
      if (!upstream.ok) {
        return sendJson(response, upstream.status, { error: `${input.backend === 'mlx-8bit' ? 'MLX' : 'Glance'} rejected the request.`, detail: payload });
      }
      const traceId = crypto.randomUUID();
      const result = {
        ...payload,
        speedlab: {
          traceId,
          upstreamMs: round(upstreamMs),
          gatewayMs: round(performance.now() - startedAt),
          requestBytes: Buffer.byteLength(glanceBody),
          responseBytes: Buffer.byteLength(upstreamText),
          backend: input.backend,
          choiceMethod: input.choiceMethod,
        },
      };
      return sendJson(response, 200, result);
    }

    if (request.method === 'GET' && url.pathname === '/api/config') {
      return sendJson(response, 200, { glanceUrl, mlxUrl, recordingDirectory: runsDir });
    }

    if (request.method === 'POST' && url.pathname === '/api/metrics') {
      const rawBody = await readBody(request, 64_000);
      const metric = normalizeMetricInput(JSON.parse(rawBody));
      await appendMetric(metric.sessionId, metric.record);
      response.statusCode = 204;
      return response.end();
    }

    if (request.method === 'POST' && url.pathname === '/api/research/browser') {
      const rawBody = await readBody(request, 256_000);
      const payload = JSON.parse(rawBody);
      if (!payload || payload.schemaVersion !== 1 || !payload.experiments || typeof payload.experiments !== 'object') {
        const error = new Error('Invalid browser research payload.');
        error.code = 'BAD_INPUT';
        throw error;
      }
      await writeFile(join(runsDir, 'browser-experiments.json'), `${JSON.stringify(payload, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 });
      response.statusCode = 204;
      return response.end();
    }

    if (serveStatic && request.method === 'GET') {
      return serveAsset(url.pathname, response);
    }

    sendJson(response, 404, { error: 'Not found.' });
  } catch (error) {
    const status = error?.code === 'BODY_TOO_LARGE' ? 413 : error?.code === 'BAD_INPUT' || error instanceof SyntaxError ? 400 : 502;
    sendJson(response, status, { error: error instanceof Error ? error.message : 'Unexpected gateway error.' });
  }
});

server.listen(port, host, () => {
  console.log(`Glance Speedlab gateway: http://${host}:${port}`);
  console.log(`Glance upstream: ${glanceUrl}`);
});

async function readBody(request, limit) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > limit) {
      const error = new Error(`Request exceeds ${limit} bytes.`);
      error.code = 'BODY_TOO_LARGE';
      throw error;
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8');
}

async function appendMetric(sessionId, value) {
  const path = join(runsDir, `${sessionId}.jsonl`);
  if (!path.startsWith(`${runsDir}${sep}`)) throw new Error('Invalid run path.');
  await appendFile(path, `${JSON.stringify(value)}\n`, { encoding: 'utf8', mode: 0o600 });
}

async function serveAsset(pathname, response) {
  const requested = pathname === '/' ? 'index.html' : pathname.replace(/^\//, '');
  const path = resolve(distDir, requested);
  if (!path.startsWith(`${distDir}${sep}`) && path !== join(distDir, 'index.html')) {
    return sendJson(response, 404, { error: 'Not found.' });
  }
  try {
    const info = await stat(path);
    if (!info.isFile()) throw new Error('Not a file');
    response.statusCode = 200;
    response.setHeader('content-type', mimeType(path));
    response.setHeader('cache-control', path.endsWith('.html') ? 'no-cache' : 'public, max-age=31536000, immutable');
    response.end(await readFile(path));
  } catch {
    const fallback = join(distDir, 'index.html');
    response.statusCode = 200;
    response.setHeader('content-type', 'text/html; charset=utf-8');
    response.end(await readFile(fallback));
  }
}

function sendJson(response, status, value) {
  response.statusCode = status;
  response.setHeader('content-type', 'application/json; charset=utf-8');
  response.end(JSON.stringify(value));
}

async function fetchJson(url, timeoutMs) {
  const startedAt = performance.now();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
    const payload = await response.json();
    return { ok: response.ok, payload, elapsedMs: round(performance.now() - startedAt) };
  } catch {
    return { ok: false, payload: null, elapsedMs: round(performance.now() - startedAt) };
  }
}

function mimeType(path) {
  return ({ '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml' })[extname(path)] ?? 'application/octet-stream';
}

function round(value) {
  return Math.round(value * 100) / 100;
}
