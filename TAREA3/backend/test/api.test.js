// Pruebas de integración: API + PostgreSQL + difusión al panel (WebSocket).
//
// Necesita un PostgreSQL de pruebas (NUNCA el de producción):
//   PGHOST=127.0.0.1 PGPORT=55432 PGUSER=postgres PGDATABASE=postgres \
//   PGSSLMODE=disable node --test test/
// Sin PGHOST se omiten.

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const WebSocket = require('ws');
const { Pool } = require('pg');

const skip = !process.env.PGHOST && 'define PGHOST (PostgreSQL de pruebas) para ejecutarlas';
const port = 18000 + Math.floor(Math.random() * 1000);
const base = `http://127.0.0.1:${port}/api`;
const deviceId = `prueba-${Date.now()}`;
let server;
let pool;
let viewer;
const broadcasts = [];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function call(method, route, body) {
  const response = await fetch(base + route, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body && JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
}

const t0 = Date.now() - 60_000;
function sample(id, i, extra = {}) {
  return {
    sampleId: `${deviceId}-${id}`,
    // Coordenadas con 13-14 decimales: deben guardarse sin redondeo.
    latitude: -13.523600123456 + i * 0.0000271,
    longitude: -71.957370987654 - i * 0.0000013,
    accuracy: 2.5, speed: 1.3, heading: 10, battery: 80,
    timestamp: new Date(t0 + i * 1000).toISOString(),
    ...extra,
  };
}

before(async () => {
  if (skip) return;
  server = spawn(process.execPath, [path.join(__dirname, '..', 'server.js')], {
    env: { ...process.env, PORT: String(port), JWT_SECRET: 'solo-pruebas' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));
  for (let i = 0; i < 50; i++) {
    try {
      // /health responde antes de migrar; /devices solo cuando la base está lista.
      if ((await call('GET', '/devices')).status === 200) break;
    } catch { /* aún arrancando */ }
    await sleep(200);
  }
  pool = new Pool({ ssl: false });
  viewer = new WebSocket(`ws://127.0.0.1:${port}/ws`);
  viewer.on('message', (raw) => {
    const message = JSON.parse(raw);
    if (message.type === 'location.updated' && message.data.deviceId === deviceId) broadcasts.push(message.data);
  });
  await new Promise((resolve) => viewer.on('open', resolve));
  await call('POST', '/devices', { deviceId, name: 'Prueba', platform: 'android', appVersion: 'test' });
});

after(async () => {
  if (skip) return;
  await call('DELETE', `/devices/${deviceId}`);
  viewer?.close();
  await pool?.end();
  server?.kill();
});

async function rowsInDb() {
  const { rows } = await pool.query(
    'SELECT sample_id, latitude, longitude, segment_start FROM locations WHERE device_id = $1 ORDER BY ts',
    [deviceId],
  );
  return rows;
}

test('G · reintentos y lotes repetidos no duplican puntos', { skip }, async () => {
  const p = sample('g1', 0, { segmentStart: true });
  const first = await call('POST', `/devices/${deviceId}/locations`, p);
  assert.equal(first.status, 201);
  // La red cortó la respuesta y el celular reintenta dos veces.
  const retry1 = await call('POST', `/devices/${deviceId}/locations`, p);
  const retry2 = await call('POST', `/devices/${deviceId}/locations`, p);
  assert.equal(retry1.body.duplicate, true);
  assert.equal(retry2.body.duplicate, true);
  // Y después la cola offline vuelve a mandar el mismo punto en un lote.
  const batch = await call('POST', `/devices/${deviceId}/locations/batch`, { locations: [p, p] });
  assert.equal(batch.status, 200);
  const rows = (await rowsInDb()).filter((r) => r.sample_id === p.sampleId);
  assert.equal(rows.length, 1);
  assert.equal(broadcasts.filter((b) => b.sampleId === p.sampleId).length, 1, 'el panel lo recibe una vez');
});

test('H · lo que envía el celular = lo que guarda PostgreSQL = lo que carga el panel', { skip }, async () => {
  const post = (s) => call('POST', `/devices/${deviceId}/locations`, s);
  const batch = (list) => call('POST', `/devices/${deviceId}/locations/batch`, { locations: list });

  // Ruta tal como la construye RutaGps en el celular:
  await post(sample('h2', 2));
  await post(sample('h3', 3, { replaces: `${deviceId}-h2` }));         // corrección en vivo
  await post(sample('h4', 4));
  // Hueco de señal y cola offline: tramo nuevo + corrección en el mismo lote.
  await batch([
    sample('h5', 20, { segmentStart: true }),
    sample('h6', 21, { segmentStart: true, replaces: `${deviceId}-h5` }),
    sample('h7', 25),
  ]);
  // Una corrección que llega ANTES que el punto que corrige (reintento lento).
  await post(sample('h9', 27, { replaces: `${deviceId}-h8` }));
  await batch([sample('h8', 26)]);

  const expected = ['g1', 'h3', 'h4', 'h6', 'h7', 'h9'].map((id) => `${deviceId}-${id}`);

  // PostgreSQL.
  const rows = await rowsInDb();
  assert.deepEqual(rows.map((r) => r.sample_id), expected);
  assert.deepEqual(rows.filter((r) => r.segment_start).map((r) => r.sample_id), [`${deviceId}-g1`, `${deviceId}-h6`]);
  const h3 = sample('h3', 3);
  const h3Row = rows.find((r) => r.sample_id === h3.sampleId);
  assert.equal(h3Row.latitude, h3.latitude, 'latitud sin redondeo ni inversión');
  assert.equal(h3Row.longitude, h3.longitude, 'longitud sin redondeo ni inversión');

  // API que usa el panel al cargar la ruta.
  const history = await call('GET', `/devices/${deviceId}/history?lastSession=true`);
  assert.deepEqual(history.body.locations.map((l) => l.sampleId), expected);
  assert.deepEqual(history.body.locations.filter((l) => l.segmentStart).map((l) => l.sampleId), [`${deviceId}-g1`, `${deviceId}-h6`]);
  const times = history.body.locations.map((l) => Date.parse(l.timestamp));
  assert.deepEqual(times, [...times].sort((a, b) => a - b), 'orden por hora de captura');

  // Difusión en vivo: el panel recibe qué punto reemplazar.
  await sleep(100);
  const live = broadcasts.find((b) => b.sampleId === `${deviceId}-h3`);
  assert.equal(live.replaces, `${deviceId}-h2`);
  assert.equal(live.correction, true);
});

test('validación: coordenadas fuera de rango se rechazan', { skip }, async () => {
  const bad = await call('POST', `/devices/${deviceId}/locations`, sample('bad', 40, { latitude: 123 }));
  assert.equal(bad.status, 400);
});
