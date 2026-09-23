const QUESTION_TYPES = new Set(['noul', 'choice']);

export function normalizeDecideInput(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw invalid('Request body must be an object.');
  }

  const imageBase64 = String(value.imageBase64 ?? '');
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(imageBase64) || imageBase64.length < 16) {
    throw invalid('imageBase64 must be plain base64 without a data URL prefix.');
  }

  if (!Array.isArray(value.questions) || value.questions.length < 1 || value.questions.length > 16) {
    throw invalid('questions must contain 1–16 items.');
  }

  const ids = new Set();
  const questions = value.questions.map((raw, index) => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      throw invalid(`questions[${index}] must be an object.`);
    }
    const id = String(raw.id ?? '');
    const type = String(raw.type ?? '');
    const instructions = String(raw.instructions ?? '').trim();
    if (!/^[a-z][a-z0-9_]{0,47}$/.test(id) || ids.has(id)) {
      throw invalid(`questions[${index}].id must be unique snake_case.`);
    }
    ids.add(id);
    if (!QUESTION_TYPES.has(type)) {
      throw invalid(`questions[${index}].type must be noul or choice.`);
    }
    if (!instructions || instructions.length > 1_000 || !instructions.includes('`img0`')) {
      throw invalid(`questions[${index}].instructions must mention \`img0\` and be at most 1000 characters.`);
    }
    if (type === 'choice') {
      if (!Array.isArray(raw.criteria) || raw.criteria.length < 2 || raw.criteria.length > 20) {
        throw invalid(`questions[${index}].criteria must contain 2–20 labels.`);
      }
      const criteria = Object.fromEntries(raw.criteria.map((label, criterionIndex) => {
        const text = String(label).trim();
        if (!text || text.length > 120) {
          throw invalid(`questions[${index}].criteria[${criterionIndex}] is invalid.`);
        }
        return [text, null];
      }));
      return { id, question: { type, instructions, criteria } };
    }
    return { id, question: { type, instructions } };
  });

  return {
    imageBase64,
    questions,
    backend: value.backend === 'mlx-8bit' ? 'mlx-8bit' : 'glance',
    choiceMethod: value.choiceMethod === 'letter' ? 'letter' : 'independent',
    sessionId: sanitizeSessionId(value.sessionId),
    client: sanitizeClientMetrics(value.client),
  };
}

export function toGlanceRequest(input) {
  return {
    model: 'vlm',
    state: {
      images: [{ id: 'img0', base64: input.imageBase64 }],
    },
    questions: Object.fromEntries(input.questions.map(({ id, question }) => [id, question])),
    options: { choice_method: input.choiceMethod, calibrated: false },
  };
}

export function sanitizeSessionId(value) {
  const candidate = String(value ?? 'anonymous');
  return /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(candidate) ? candidate : 'anonymous';
}

export function normalizeMetricInput(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalid('Metric body must be an object.');
  const number = (key, source = value) => {
    const result = Number(source?.[key]);
    return Number.isFinite(result) && result >= 0 ? result : null;
  };
  const timing = value.modelTimingMs && typeof value.modelTimingMs === 'object'
    ? Object.fromEntries(Object.entries(value.modelTimingMs).flatMap(([key, raw]) => {
        const result = Number(raw);
        return /^[a-zA-Z0-9_]{1,48}$/.test(key) && Number.isFinite(result) && result >= 0 ? [[key, result]] : [];
      }))
    : {};
  return {
    sessionId: sanitizeSessionId(value.sessionId),
    record: {
      schemaVersion: 1,
      timestamp: new Date().toISOString(),
      traceId: typeof value.traceId === 'string' ? value.traceId.slice(0, 64) : '',
      sequence: number('sequence'),
      questionCount: number('questionCount'),
      backend: value.backend === 'mlx-8bit' ? 'mlx-8bit' : 'glance',
      choiceMethod: value.choiceMethod === 'letter' ? 'letter' : 'independent',
      temporalReuse: value.temporalReuse === true,
      motionThreshold: number('motionThreshold'),
      maxStaleMs: number('maxStaleMs'),
      loopMs: number('loopMs'),
      requestMs: number('requestMs'),
      capture: sanitizeClientMetrics(value.capture),
      gatewayMs: number('gatewayMs'),
      upstreamMs: number('upstreamMs'),
      modelTimingMs: timing,
    },
  };
}

function sanitizeClientMetrics(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const allowed = ['captureMs', 'encodeMs', 'width', 'height', 'bytes', 'longEdge', 'quality'];
  return Object.fromEntries(allowed.flatMap((key) => {
    const number = Number(value[key]);
    return Number.isFinite(number) && number >= 0 ? [[key, number]] : [];
  }));
}

function invalid(message) {
  const error = new Error(message);
  error.code = 'BAD_INPUT';
  return error;
}
