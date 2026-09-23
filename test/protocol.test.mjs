import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeDecideInput, normalizeMetricInput, toGlanceRequest } from '../src/server/protocol.mjs';

const imageBase64 = Buffer.from('a small fake image').toString('base64');

test('one question uses the same native batch path', () => {
  const input = normalizeDecideInput({
    imageBase64,
    questions: [{ id: 'expression', type: 'choice', instructions: 'Expression in `img0`?', criteria: ['Happy', 'Neutral'] }],
  });
  const request = toGlanceRequest(input);
  assert.deepEqual(Object.keys(request.questions), ['expression']);
  assert.equal(request.questions.expression.type, 'choice');
  assert.deepEqual(request.questions.expression.criteria, { Happy: null, Neutral: null });
  assert.equal(request.options.choice_method, 'independent');
  assert.deepEqual(request.state, { images: [{ id: 'img0', base64: imageBase64 }] });
});

test('rejects instructions that do not identify the image', () => {
  assert.throws(() => normalizeDecideInput({
    imageBase64,
    questions: [{ id: 'cat', type: 'noul', instructions: 'Is there a cat?' }],
  }), /img0/);
});

test('passes the experimental letter choice method explicitly', () => {
  const input = normalizeDecideInput({
    imageBase64,
    choiceMethod: 'letter',
    questions: [{ id: 'expression', type: 'choice', instructions: 'Expression in `img0`?', criteria: ['Happy', 'Neutral'] }],
  });
  assert.equal(toGlanceRequest(input).options.choice_method, 'letter');
});

test('accepts only the measured MLX backend identifier', () => {
  const base = {
    imageBase64,
    questions: [{ id: 'cat', type: 'noul', instructions: 'Is there a cat in `img0`?' }],
  };
  assert.equal(normalizeDecideInput({ ...base, backend: 'mlx-8bit' }).backend, 'mlx-8bit');
  assert.equal(normalizeDecideInput({ ...base, backend: 'unknown' }).backend, 'glance');
});

test('sanitizes metric fields and session ids', () => {
  const input = normalizeDecideInput({
    imageBase64,
    sessionId: '../../bad',
    client: { captureMs: 3.2, secret: 'nope', width: -1 },
    questions: [{ id: 'cat', type: 'noul', instructions: 'Is there a cat in `img0`?' }],
  });
  assert.equal(input.sessionId, 'anonymous');
  assert.deepEqual(input.client, { captureMs: 3.2 });
});

test('metric records exclude unknown fields', () => {
  const metric = normalizeMetricInput({
    sessionId: 'run-001', traceId: 'abc', sequence: 2, loopMs: 45.2,
    capture: { captureMs: 2.1, imageBase64: 'must-not-survive' },
    modelTimingMs: { prefix: 30, '../bad': 99 }, extra: 'nope',
  });
  assert.equal(metric.sessionId, 'run-001');
  assert.deepEqual(metric.record.capture, { captureMs: 2.1 });
  assert.deepEqual(metric.record.modelTimingMs, { prefix: 30 });
  assert.equal('extra' in metric.record, false);
});
