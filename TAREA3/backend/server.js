require('dotenv').config();

const path = require('node:path');
const http = require('node:http');
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { WebSocketServer } = require('ws');
const db = require('./db');

const port = Number(process.env.PORT || 8080);
// Un dispositivo está "online" si envió algo (punto o latido) hace poco.
const onlineWindowMs = 20 * 1000;
// Hueco máximo entre puntos de un mismo recorrido.
const sessionGapMs = 3 * 60 * 1000;
const jwtSecret = process.env.JWT_SECRET || 'development-only-secret';

// ---------------------------------------------------------------------------
// Estado en memoria (caché). La fuente de verdad es PostgreSQL.
// ---------------------------------------------------------------------------
const devices = new Map();        // deviceId -> fila de devices
const latestByDevice = new Map(); // deviceId -> última ubicación
const stoppedDevices = new Set(); // detuvieron el recorrido (offline inmediato)
const recentSamples = new Set();  // sampleIds recientes (evita difundir duplicados)
const recentOrder = [];
const latencySamples = [];
let discardedSamples = 0;
let dbReady = false;

function rememberSample(sampleId) {
  recentSamples.add(sampleId);
  recentOrder.push(sampleId);
  if (recentOrder.length > 200_000) recentSamples.delete(recentOrder.shift());
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------
const app = express();
app.set('trust proxy', 1); // Detrás de Nginx.
app.use(helmet({ contentSecurityPolicy: false, hsts: false, crossOriginOpenerPolicy: false, originAgentCluster: false }));
app.use(cors({ origin: process.env.CORS_ORIGIN || true }));
app.use(express.json({ limit: '1mb' }));

const authLimiter = rateLimit({ windowMs: 60_000, limit: 20, standardHeaders: true, legacyHeaders: false });
const apiLimiter = rateLimit({
  windowMs: 60_000,
  limit: 1200,
  standardHeaders: true,
  legacyHeaders: false,
  // Envío de puntos y latidos: flujo continuo de varios por segundo.
  skip: (req) => req.method === 'POST' && /\/(locations(\/batch)?|heartbeat)$/.test(req.path),
});
app.use('/api/auth', authLimiter);
app.use('/api', apiLimiter);

// Rutas que necesitan la base de datos responden 503 mientras no esté lista.
app.use('/api', (req, res, next) => {
  if (dbReady || req.path === '/health' || req.path === '/time') return next();
  return res.status(503).json({ error: 'Base de datos no disponible todavía' });
});

const asyncRoute = (handler) => (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);

function tokenFor(user) {
  return jwt.sign({ sub: String(user.id), email: user.email }, jwtSecret, { expiresIn: process.env.JWT_EXPIRES_IN || '8h' });
}

function validCoordinate(value, min, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function finiteOrNull(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// ---------------------------------------------------------------------------
// Tiempo real
// ---------------------------------------------------------------------------
const viewers = new Set();
const deviceSockets = new Map(); // deviceId -> Set<WebSocket> (versiones antiguas de la app)

function broadcast(message) {
  const payload = JSON.stringify(message);
  for (const socket of viewers) {
    // Si un panel no da abasto se descarta en vez de acumular retraso.
    if (socket.readyState === 1 && socket.bufferedAmount < 512 * 1024) socket.send(payload);
  }
}

function isOnline(device) {
  if ((deviceSockets.get(device.device_id)?.size ?? 0) > 0) return true;
  if (stoppedDevices.has(device.device_id)) return false;
  return Date.now() - Date.parse(device.last_seen) < onlineWindowMs;
}

function publicDevice(device) {
  return {
    deviceId: device.device_id, name: device.name, platform: device.platform, appVersion: device.app_version,
    model: device.model, lastSeen: device.last_seen, battery: device.battery, online: isOnline(device),
  };
}

const lastOnlineState = new Map();
function publishDevice(device) {
  const data = publicDevice(device);
  lastOnlineState.set(device.device_id, data.online);
  broadcast({ type: 'device.updated', data });
}

// Avisa al panel cuando un dispositivo deja de enviar (pasa a offline).
setInterval(() => {
  for (const device of devices.values()) {
    const online = isOnline(device);
    if (lastOnlineState.get(device.device_id) !== online) publishDevice(device);
  }
}, 5000).unref();

async function upsertDevice(body) {
  const deviceId = String(body.deviceId || '').trim();
  if (!deviceId || deviceId.length > 150) return { error: 'deviceId inválido' };
  const result = await db.upsertDevice({
    deviceId,
    name: String(body.name || 'Dispositivo sin nombre').trim().slice(0, 120),
    platform: String(body.platform || 'desconocido').slice(0, 40),
    appVersion: String(body.appVersion || '0.0.0').slice(0, 40),
    model: String(body.model || '').slice(0, 120),
    battery: Number.isInteger(body.battery) ? body.battery : null,
  });
  devices.set(deviceId, result.device);
  stoppedDevices.delete(deviceId);
  publishDevice(result.device);
  return result;
}

/**
 * Valida y procesa una ubicación. Se difunde al panel de inmediato; `saved`
 * es una promesa que se resuelve cuando ya está guardada en PostgreSQL.
 */
async function acceptLocation(deviceId, body) {
  if (!deviceId || deviceId.length > 150) return { status: 400, error: 'deviceId obligatorio' };
  if (!validCoordinate(body.latitude, -90, 90) || !validCoordinate(body.longitude, -180, 180)) {
    discardedSamples++;
    return { status: 400, error: 'Coordenadas inválidas' };
  }
  const timestamp = new Date(body.timestamp || Date.now());
  if (Number.isNaN(timestamp.getTime())) {
    discardedSamples++;
    return { status: 400, error: 'timestamp inválido' };
  }
  const sampleId = String(body.sampleId || `${deviceId}-${timestamp.getTime()}-${body.latitude}-${body.longitude}`).slice(0, 200);
  if (recentSamples.has(sampleId)) return { duplicate: true, sampleId, saved: Promise.resolve() };
  rememberSample(sampleId);

  let device = devices.get(deviceId);
  if (!device) {
    // Dispositivo desconocido (p. ej. eliminado desde el panel): se registra solo.
    device = await db.ensureDevice(deviceId);
    devices.set(deviceId, device);
  }

  const receivedMs = Date.now();
  const latencyMs = Math.max(0, receivedMs - timestamp.getTime());
  const live = body.live !== false;
  const location = {
    deviceId, sampleId,
    latitude: body.latitude, longitude: body.longitude,
    accuracy: finiteOrNull(body.accuracy),
    speed: finiteOrNull(body.speed),
    heading: finiteOrNull(body.heading),
    altitude: finiteOrNull(body.altitude),
    battery: Number.isInteger(body.battery) ? body.battery : null,
    timestamp: timestamp.toISOString(),
    receivedAt: new Date(receivedMs).toISOString(),
    latencyMs,
  };

  // 1) Tiempo real: se difunde antes de tocar la base de datos.
  const wasOnline = isOnline(device);
  stoppedDevices.delete(deviceId);
  device.last_seen = location.receivedAt;
  if (location.battery !== null) device.battery = location.battery;
  if (!wasOnline) publishDevice(device);
  const previous = latestByDevice.get(deviceId);
  if (!previous || previous.timestamp <= location.timestamp) latestByDevice.set(deviceId, location);
  broadcast({ type: 'location.updated', data: { ...location, live, serverTime: Date.now() } });

  // Solo las muestras en vivo cuentan para la métrica (no la cola offline).
  if (live && latencyMs < 60_000) {
    latencySamples.push(latencyMs);
    if (latencySamples.length > 5000) latencySamples.shift();
  }

  // 2) Persistencia por lotes.
  db.touchDevice(deviceId, location.receivedAt, location.battery);
  const saved = db.enqueueLocation(location).catch((error) => {
    // No se pudo guardar: se olvida el sampleId para aceptar el reintento.
    recentSamples.delete(sampleId);
    throw error;
  });
  return { location, sampleId, saved };
}

app.get('/api/health', asyncRoute(async (_req, res) => {
  let dbMs = null;
  try { dbMs = await db.ping(); } catch { /* sin conexión */ }
  res.status(dbMs === null ? 503 : 200).json({ ok: dbMs !== null, service: 'movimiento-api', database: dbMs === null ? 'desconectada' : 'postgresql', dbPingMs: dbMs, time: Date.now() });
}));

// Sincronización de reloj del celular (estilo NTP) y medición de RTT.
app.get('/api/time', (_req, res) => res.json({ serverTime: Date.now() }));

app.post('/api/auth/register', asyncRoute(async (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 8) {
    return res.status(400).json({ error: 'Correo inválido o contraseña menor de 8 caracteres' });
  }
  const user = await db.createUser(email, await bcrypt.hash(password, 12));
  if (!user) return res.status(409).json({ error: 'El correo ya está registrado' });
  return res.status(201).json({ token: tokenFor(user), user });
}));

app.post('/api/auth/login', asyncRoute(async (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  const user = await db.findUserByEmail(email);
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: 'Credenciales inválidas' });
  }
  return res.json({ token: tokenFor(user), user: { id: user.id, email: user.email } });
}));

// --- Dispositivos -----------------------------------------------------------

// POST: registrar o actualizar un dispositivo.
app.post('/api/devices', asyncRoute(async (req, res) => {
  const result = await upsertDevice(req.body || {});
  if (result.error) return res.status(400).json({ error: result.error });
  return res.status(result.created ? 201 : 200).json({ deviceId: result.device.device_id, created: result.created, serverTime: Date.now() });
}));

// GET: lista de dispositivos.
app.get('/api/devices', (_req, res) => {
  const list = [...devices.values()].sort((a, b) => a.name.localeCompare(b.name)).map(publicDevice);
  res.json({ devices: list });
});

// POST: latido (el celular sigue activo aunque esté quieto y no envíe puntos).
app.post('/api/devices/:deviceId/heartbeat', asyncRoute(async (req, res) => {
  const deviceId = String(req.params.deviceId);
  let device = devices.get(deviceId);
  if (!device) {
    device = await db.ensureDevice(deviceId);
    devices.set(deviceId, device);
  }
  const battery = Number.isInteger(req.body?.battery) ? req.body.battery : null;
  device.last_seen = new Date().toISOString();
  if (battery !== null) device.battery = battery;
  if (req.body?.active === false) stoppedDevices.add(deviceId);
  else stoppedDevices.delete(deviceId);
  db.touchDevice(deviceId, device.last_seen, battery);
  if (lastOnlineState.get(deviceId) !== isOnline(device) || battery !== null) publishDevice(device);
  res.json({ ok: true, serverTime: Date.now() });
}));

// --- Ubicaciones (señales GPS) ------------------------------------------------

// POST: un punto GPS. Responde cuando ya está guardado en PostgreSQL.
app.post('/api/devices/:deviceId/locations', asyncRoute(async (req, res) => {
  const result = await acceptLocation(String(req.params.deviceId), req.body || {});
  if (result.error) return res.status(result.status).json({ error: result.error });
  try {
    await result.saved;
  } catch {
    return res.status(503).json({ error: 'No se pudo guardar en la base de datos; reintente' });
  }
  if (result.duplicate) return res.status(200).json({ ok: true, duplicate: true, sampleId: result.sampleId });
  return res.status(201).json({ ok: true, sampleId: result.sampleId, serverTime: Date.now() });
}));

// POST: lote de puntos (cola offline del celular).
app.post('/api/devices/:deviceId/locations/batch', asyncRoute(async (req, res) => {
  const items = Array.isArray(req.body?.locations) ? req.body.locations.slice(0, 500) : [];
  const deviceId = String(req.params.deviceId);
  const results = [];
  for (const item of items) results.push(await acceptLocation(deviceId, { ...item, live: false }));
  const accepted = [];
  const rejected = [];
  await Promise.all(results.map(async (result) => {
    if (result.error) return;
    try {
      await result.saved;
      accepted.push(result.sampleId);
    } catch {
      rejected.push(result.sampleId);
    }
  }));
  return res.status(rejected.length ? 207 : 200).json({ ok: rejected.length === 0, accepted, rejected });
}));

// GET: última posición conocida.
app.get('/api/devices/:deviceId/location', asyncRoute(async (req, res) => {
  const deviceId = String(req.params.deviceId);
  if (!devices.has(deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const location = latestByDevice.get(deviceId) || await db.latestLocation(deviceId);
  if (location) latestByDevice.set(deviceId, location);
  const active = location && Date.now() - Date.parse(location.receivedAt || location.timestamp) < sessionGapMs ? location : null;
  res.json({ location: active, lastKnown: location });
}));

// GET: historial. ?lastSession=true (último recorrido), ?activeOnly=true
// (recorrido en curso) o ?from=ISO&to=ISO (rango).
app.get('/api/devices/:deviceId/history', asyncRoute(async (req, res) => {
  const deviceId = String(req.params.deviceId);
  if (!devices.has(deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  await db.flush(); // Incluir lo que aún está en la cola de escritura.
  const limit = Math.min(Number(req.query.limit) || 10000, 50000);
  if (req.query.activeOnly === 'true' || req.query.lastSession === 'true') {
    const latest = latestByDevice.get(deviceId) || await db.latestLocation(deviceId);
    if (!latest || (req.query.activeOnly === 'true' && Date.now() - Date.parse(latest.receivedAt) > sessionGapMs)) {
      return res.json({ locations: [] });
    }
    return res.json({ locations: await db.lastSession(deviceId, sessionGapMs, limit) });
  }
  const from = req.query.from ? new Date(req.query.from) : new Date(Date.now() - 24 * 60 * 60 * 1000);
  const to = req.query.to ? new Date(req.query.to) : new Date();
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return res.status(400).json({ error: 'Rango de fechas inválido' });
  res.json({ locations: await db.historyRange(deviceId, from, to, limit) });
}));

// DELETE: borra la ruta de un dispositivo (sin eliminarlo).
app.delete('/api/devices/:deviceId/locations', asyncRoute(async (req, res) => {
  const deviceId = String(req.params.deviceId);
  if (!devices.has(deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const removed = await db.deleteLocations(deviceId);
  latestByDevice.delete(deviceId);
  broadcast({ type: 'route.cleared', data: { deviceId } });
  return res.json({ ok: true, removed });
}));

// DELETE: elimina el dispositivo y su ruta (ON DELETE CASCADE). Si el
// celular sigue enviando datos volverá a aparecer.
app.delete('/api/devices/:deviceId', asyncRoute(async (req, res) => {
  const deviceId = String(req.params.deviceId);
  if (!devices.has(deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  await db.deleteDevice(deviceId);
  devices.delete(deviceId);
  latestByDevice.delete(deviceId);
  lastOnlineState.delete(deviceId);
  broadcast({ type: 'device.removed', data: { deviceId } });
  return res.json({ ok: true });
}));

app.get('/api/metrics', asyncRoute(async (_req, res) => {
  const sorted = [...latencySamples].sort((a, b) => a - b);
  const percentile = (ratio) => (sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * ratio))] : null);
  let dbPingMs = null;
  try { dbPingMs = await db.ping(); } catch { /* sin conexión */ }
  res.json({
    samples: sorted.length,
    averageMs: sorted.length ? sorted.reduce((sum, value) => sum + value, 0) / sorted.length : null,
    p50Ms: percentile(0.5), p95Ms: percentile(0.95), p99Ms: percentile(0.99),
    maxMs: sorted.at(-1) ?? null,
    under1000Percent: sorted.length ? (sorted.filter((value) => value < 1000).length / sorted.length) * 100 : null,
    discardedSamples,
    onlineDevices: [...devices.values()].filter(isOnline).length,
    connectedViewers: viewers.size,
    dbPingMs,
    dbPendingWrites: db.pendingWrites(),
  });
}));

app.use(express.static(path.join(__dirname, 'public'), {
  setHeaders: (res, file) => { if (file.endsWith('.html')) res.setHeader('Cache-Control', 'no-cache'); },
}));
app.use('/api', (_req, res) => res.status(404).json({ error: 'Ruta no encontrada' }));
// eslint-disable-next-line no-unused-vars
app.use((error, _req, res, _next) => {
  console.error('[api]', error.message);
  res.status(500).json({ error: 'Error interno del servidor' });
});

// ---------------------------------------------------------------------------
// WebSocket: el panel recibe las difusiones y mide el RTT con ping. También
// se aceptan los mensajes de versiones anteriores de la app (hello/location).
// ---------------------------------------------------------------------------
const server = http.createServer(app);
const websocketServer = new WebSocketServer({ server, path: '/ws', perMessageDeflate: false, maxPayload: 1024 * 1024 });

function send(socket, message) {
  if (socket.readyState === 1) socket.send(JSON.stringify(message));
}

websocketServer.on('connection', (socket) => {
  socket.isAlive = true;
  socket._socket?.setNoDelay(true);
  viewers.add(socket);
  send(socket, { type: 'connected', serverTime: Date.now() });

  socket.on('pong', () => { socket.isAlive = true; });
  socket.on('message', async (raw) => {
    socket.isAlive = true;
    let message;
    try {
      message = JSON.parse(raw.toString());
    } catch {
      return send(socket, { type: 'error', error: 'Mensaje WebSocket inválido' });
    }
    try {
      switch (message.type) {
        case 'ping':
          return send(socket, { type: 'pong', t: message.t, serverTime: Date.now() });
        case 'hello': {
          if (!dbReady) return send(socket, { type: 'error', error: 'Base de datos no disponible' });
          const result = await upsertDevice(message.data || {});
          if (result.error) return send(socket, { type: 'error', error: result.error });
          viewers.delete(socket);
          socket.deviceId = result.device.device_id;
          if (!deviceSockets.has(socket.deviceId)) deviceSockets.set(socket.deviceId, new Set());
          deviceSockets.get(socket.deviceId).add(socket);
          return send(socket, { type: 'hello.ok', serverTime: Date.now() });
        }
        case 'location': {
          if (!dbReady) return undefined;
          const payload = message.data || {};
          const result = await acceptLocation(String(payload.deviceId || socket.deviceId || ''), payload);
          if (result.error) return send(socket, { type: 'location.rejected', data: { sampleId: payload.sampleId, error: result.error } });
          await result.saved;
          return send(socket, { type: 'location.accepted', data: { sampleId: result.sampleId, duplicate: result.duplicate === true } });
        }
        case 'locations': {
          if (!dbReady) return undefined;
          const items = Array.isArray(message.data) ? message.data.slice(0, 500) : [];
          const accepted = [];
          for (const item of items) {
            const result = await acceptLocation(String(item.deviceId || socket.deviceId || ''), { ...item, live: false });
            if (result.error) continue;
            try { await result.saved; accepted.push(result.sampleId); } catch { /* reintento del celular */ }
          }
          return send(socket, { type: 'locations.accepted', data: { sampleIds: accepted } });
        }
        default:
          return undefined;
      }
    } catch (error) {
      console.error('[ws]', error.message);
      return undefined;
    }
  });
  socket.on('close', () => {
    viewers.delete(socket);
    if (socket.deviceId) {
      deviceSockets.get(socket.deviceId)?.delete(socket);
      const device = devices.get(socket.deviceId);
      if (device) publishDevice(device);
    }
  });
  socket.on('error', () => socket.terminate());
});

// Heartbeat: mantiene vivo el túnel de Nginx y elimina conexiones muertas.
const heartbeat = setInterval(() => {
  for (const socket of websocketServer.clients) {
    if (!socket.isAlive) { socket.terminate(); continue; }
    socket.isAlive = false;
    socket.ping();
  }
}, 15000);
websocketServer.on('close', () => clearInterval(heartbeat));

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------
async function connectDatabase() {
  for (let attempt = 1; ; attempt++) {
    try {
      await db.migrate();
      for (const device of await db.listDevices()) devices.set(device.device_id, device);
      dbReady = true;
      console.log(`[db] PostgreSQL listo (${devices.size} dispositivos)`);
      return;
    } catch (error) {
      console.error(`[db] Sin conexión a PostgreSQL (intento ${attempt}): ${error.message}`);
      await new Promise((resolve) => setTimeout(resolve, Math.min(10_000, 1000 * attempt)));
    }
  }
}

let closing = false;
async function shutdown() {
  if (closing) return;
  closing = true;
  server.close();
  await db.close().catch(() => {});
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

server.listen(port, () => console.log(`Movimiento API escuchando en http://localhost:${port}`));
connectDatabase();
