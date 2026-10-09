require('dotenv').config();

const path = require('node:path');
const fs = require('node:fs');
const http = require('node:http');
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { WebSocketServer } = require('ws');

const port = Number(process.env.PORT || 8080);
// Un dispositivo se considera "online" si tiene socket abierto o envió datos hace poco.
const onlineWindowMs = 20 * 1000;
// Ventana para considerar que un recorrido sigue activo (ruta mostrada en el panel).
const activeWindowMs = 3 * 60 * 1000;
const maxLocationsPerDevice = Number(process.env.MAX_LOCATIONS_PER_DEVICE || 50000);
const jwtSecret = process.env.JWT_SECRET || 'development-only-secret';

// ---------------------------------------------------------------------------
// Persistencia: usuarios/dispositivos en JSON, ubicaciones en NDJSON (append-only).
// Escribir el archivo completo en cada punto bloqueaba el event loop y generaba
// picos de latencia; ahora cada muestra es una línea agregada de forma asíncrona.
// ---------------------------------------------------------------------------
const dbFile = path.resolve(process.env.DB_FILE || './data/movimiento.json');
const locationsFile = dbFile.replace(/\.json$/i, '') + '.locations.ndjson';
fs.mkdirSync(path.dirname(dbFile), { recursive: true });

const data = fs.existsSync(dbFile)
  ? JSON.parse(fs.readFileSync(dbFile, 'utf8'))
  : { nextUserId: 1, users: [], devices: [] };
data.users ??= [];
data.devices ??= [];
data.nextUserId ??= 1;

const locationsByDevice = new Map();
const seenSamples = new Set();

function indexLocation(location) {
  let list = locationsByDevice.get(location.deviceId);
  if (!list) locationsByDevice.set(location.deviceId, (list = []));
  const previous = list.at(-1);
  list.push(location);
  // Las muestras reenviadas desde la cola offline pueden llegar desordenadas.
  if (previous && previous.timestamp > location.timestamp) {
    list.sort((a, b) => (a.timestamp < b.timestamp ? -1 : a.timestamp > b.timestamp ? 1 : 0));
  }
  if (list.length > maxLocationsPerDevice) list.splice(0, list.length - maxLocationsPerDevice);
  if (location.sampleId) seenSamples.add(location.sampleId);
}

// Migración desde el formato anterior (ubicaciones dentro del JSON principal).
if (Array.isArray(data.locations) && data.locations.length) {
  const lines = data.locations.map((item) => JSON.stringify({ ...item, deviceId: item.deviceId || item.device_id, device_id: undefined }));
  fs.appendFileSync(locationsFile, lines.join('\n') + '\n');
}
delete data.locations;

if (fs.existsSync(locationsFile)) {
  for (const line of fs.readFileSync(locationsFile, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      const location = JSON.parse(line);
      if (location.deviceId) indexLocation(location);
    } catch { /* línea corrupta: se ignora */ }
  }
}

let metaWriting = false;
let metaPending = false;
function saveMeta() {
  if (metaWriting) { metaPending = true; return; }
  metaWriting = true;
  const tmp = dbFile + '.tmp';
  fs.promises.writeFile(tmp, JSON.stringify(data))
    .then(() => fs.promises.rename(tmp, dbFile))
    .catch((error) => console.error('No se pudo guardar', error))
    .finally(() => {
      metaWriting = false;
      if (metaPending) { metaPending = false; saveMeta(); }
    });
}
saveMeta();

const locationsStream = fs.createWriteStream(locationsFile, { flags: 'a' });
let lastSeenDirty = false;
// last_seen/battery cambian en cada muestra: se guardan como mucho cada 5 s.
setInterval(() => { if (lastSeenDirty) { lastSeenDirty = false; saveMeta(); } }, 5000).unref();

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------
const app = express();
app.set('trust proxy', 1); // Detrás de Nginx: usar X-Forwarded-For para rate limit.
app.use(helmet({ contentSecurityPolicy: false, hsts: false, crossOriginOpenerPolicy: false, originAgentCluster: false }));
app.use(cors({ origin: process.env.CORS_ORIGIN || true }));
app.use(express.json({ limit: '1mb' }));

const authLimiter = rateLimit({ windowMs: 60_000, limit: 20, standardHeaders: true, legacyHeaders: false });
const apiLimiter = rateLimit({
  windowMs: 60_000,
  limit: 1200,
  standardHeaders: true,
  legacyHeaders: false,
  // El envío de ubicaciones es un flujo continuo (hasta varios Hz por dispositivo).
  skip: (req) => req.method === 'POST' && /\/locations(\/batch)?$/.test(req.path),
});
app.use('/api/auth', authLimiter);
app.use('/api', apiLimiter);

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
const deviceSockets = new Map(); // deviceId -> Set<WebSocket>
const latencySamples = [];
let discardedSamples = 0;

function broadcast(message) {
  const payload = JSON.stringify(message);
  for (const socket of viewers) {
    // Si un panel no da abasto (red lenta) se descarta en vez de acumular retraso.
    if (socket.readyState === 1 && socket.bufferedAmount < 512 * 1024) socket.send(payload);
  }
}

function isOnline(device) {
  return (deviceSockets.get(device.device_id)?.size ?? 0) > 0
    || Date.now() - Date.parse(device.last_seen) < onlineWindowMs;
}

function publicDevice(device) {
  return {
    deviceId: device.device_id, name: device.name, platform: device.platform, appVersion: device.app_version,
    model: device.model, lastSeen: device.last_seen, battery: device.battery, online: isOnline(device),
  };
}

function upsertDevice(body) {
  const deviceId = String(body.deviceId || '').trim();
  if (!deviceId || deviceId.length > 150) return { error: 'deviceId inválido' };
  const now = new Date().toISOString();
  const fields = {
    name: String(body.name || 'Dispositivo sin nombre').trim().slice(0, 120),
    platform: String(body.platform || 'desconocido').slice(0, 40),
    app_version: String(body.appVersion || '0.0.0').slice(0, 40),
    model: String(body.model || '').slice(0, 120),
    last_seen: now,
    battery: Number.isInteger(body.battery) ? body.battery : null,
  };
  let device = data.devices.find((item) => item.device_id === deviceId);
  const created = !device;
  if (device) Object.assign(device, fields);
  else data.devices.push((device = { device_id: deviceId, user_id: null, consented_at: now, ...fields }));
  saveMeta();
  broadcast({ type: 'device.updated', data: publicDevice(device) });
  return { device, created };
}

function acceptLocation(deviceId, body) {
  if (!deviceId) return { status: 400, error: 'deviceId obligatorio' };
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
  if (seenSamples.has(sampleId)) return { duplicate: true, sampleId };

  let device = data.devices.find((item) => item.device_id === deviceId);
  // Un dispositivo desconocido (p. ej. tras borrar datos del servidor) se registra solo.
  if (!device) device = upsertDevice({ deviceId, name: 'Dispositivo', platform: 'android' }).device;

  const receivedMs = Date.now();
  const latencyMs = Math.max(0, receivedMs - timestamp.getTime());
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
  indexLocation(location);
  locationsStream.write(JSON.stringify(location) + '\n');

  // Solo las muestras "en vivo" cuentan para la métrica de latencia (no la cola offline).
  if (body.live !== false && latencyMs < 60_000) {
    latencySamples.push(latencyMs);
    if (latencySamples.length > 5000) latencySamples.shift();
  }
  const wasOnline = isOnline(device);
  device.last_seen = location.receivedAt;
  if (location.battery !== null) device.battery = location.battery;
  lastSeenDirty = true;
  if (!wasOnline) broadcast({ type: 'device.updated', data: publicDevice(device) });

  broadcast({ type: 'location.updated', data: { ...location, live: body.live !== false, serverTime: Date.now() } });
  return { location, sampleId };
}

app.get('/api/health', (_req, res) => res.json({ ok: true, service: 'movimiento-api', time: Date.now() }));
app.get('/api/time', (_req, res) => res.json({ serverTime: Date.now() }));

app.post('/api/auth/register', async (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 8) {
    return res.status(400).json({ error: 'Correo inválido o contraseña menor de 8 caracteres' });
  }
  if (data.users.some((user) => user.email === email)) {
    return res.status(409).json({ error: 'El correo ya está registrado' });
  }
  const user = { id: data.nextUserId++, email, password_hash: await bcrypt.hash(password, 12), created_at: new Date().toISOString() };
  data.users.push(user);
  saveMeta();
  return res.status(201).json({ token: tokenFor(user), user: { id: user.id, email: user.email } });
});

app.post('/api/auth/login', async (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  const user = data.users.find((item) => item.email === email);
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: 'Credenciales inválidas' });
  }
  return res.json({ token: tokenFor(user), user: { id: user.id, email: user.email } });
});

app.post('/api/devices', (req, res) => {
  const result = upsertDevice(req.body || {});
  if (result.error) return res.status(400).json({ error: result.error });
  return res.status(result.created ? 201 : 200).json({ deviceId: result.device.device_id, created: result.created });
});

app.post('/api/devices/:deviceId/locations', (req, res) => {
  const result = acceptLocation(String(req.params.deviceId), req.body || {});
  if (result.error) return res.status(result.status).json({ error: result.error });
  if (result.duplicate) return res.status(200).json({ ok: true, duplicate: true, sampleId: result.sampleId });
  return res.status(201).json({ ok: true, sampleId: result.sampleId });
});

app.post('/api/devices/:deviceId/locations/batch', (req, res) => {
  const items = Array.isArray(req.body?.locations) ? req.body.locations.slice(0, 500) : [];
  const accepted = [];
  for (const item of items) {
    const result = acceptLocation(String(req.params.deviceId), { ...item, live: false });
    if (!result.error) accepted.push(result.sampleId);
  }
  return res.json({ ok: true, accepted });
});

app.get('/api/metrics', (_req, res) => {
  const sorted = [...latencySamples].sort((a, b) => a - b);
  const percentile = (ratio) => (sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * ratio))] : null);
  res.json({
    samples: sorted.length,
    averageMs: sorted.length ? sorted.reduce((sum, value) => sum + value, 0) / sorted.length : null,
    p50Ms: percentile(0.5), p95Ms: percentile(0.95), p99Ms: percentile(0.99),
    maxMs: sorted.at(-1) ?? null,
    under1000Percent: sorted.length ? (sorted.filter((value) => value < 1000).length / sorted.length) * 100 : null,
    discardedSamples,
    connectedDevices: [...deviceSockets.values()].filter((set) => set.size > 0).length,
    connectedViewers: viewers.size,
  });
});

app.get('/api/devices', (_req, res) => {
  const devices = [...data.devices].sort((a, b) => a.name.localeCompare(b.name)).map(publicDevice);
  res.json({ devices });
});

app.get('/api/devices/:deviceId/location', (req, res) => {
  if (!data.devices.some((device) => device.device_id === req.params.deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const location = locationsByDevice.get(req.params.deviceId)?.at(-1) || null;
  const activeLocation = location && Date.now() - Date.parse(location.receivedAt || location.timestamp) < activeWindowMs ? location : null;
  res.json({ location: activeLocation, lastKnown: location });
});

app.get('/api/devices/:deviceId/history', (req, res) => {
  if (!data.devices.some((device) => device.device_id === req.params.deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const list = locationsByDevice.get(req.params.deviceId) || [];
  let locations;
  if (req.query.activeOnly === 'true') {
    // Recorrido actual: muestras contiguas desde el final sin huecos mayores a activeWindowMs.
    const last = list.at(-1);
    if (!last || Date.now() - Date.parse(last.receivedAt || last.timestamp) > activeWindowMs) {
      locations = [];
    } else {
      let start = list.length - 1;
      while (start > 0 && Date.parse(list[start].timestamp) - Date.parse(list[start - 1].timestamp) < activeWindowMs) start--;
      locations = list.slice(start);
    }
  } else {
    const from = req.query.from ? new Date(req.query.from) : new Date(Date.now() - 24 * 60 * 60 * 1000);
    const to = req.query.to ? new Date(req.query.to) : new Date();
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return res.status(400).json({ error: 'Rango de fechas inválido' });
    const fromIso = from.toISOString();
    const toIso = to.toISOString();
    locations = list.filter((item) => item.timestamp >= fromIso && item.timestamp <= toIso);
  }
  res.json({ locations: locations.slice(-10000) });
});

app.use(express.static(path.join(__dirname, 'public'), {
  setHeaders: (res, file) => { if (file.endsWith('.html')) res.setHeader('Cache-Control', 'no-cache'); },
}));
app.use('/api', (_req, res) => res.status(404).json({ error: 'Ruta no encontrada' }));

// ---------------------------------------------------------------------------
// WebSocket
// Mensajes del celular: hello, ping, location, locations (lote offline).
// Mensajes del panel: ping. El panel solo recibe difusiones.
// ---------------------------------------------------------------------------
const server = http.createServer(app);
const websocketServer = new WebSocketServer({ server, path: '/ws', perMessageDeflate: false, maxPayload: 1024 * 1024 });

function send(socket, message) {
  if (socket.readyState === 1) socket.send(JSON.stringify(message));
}

function attachDevice(socket, deviceId) {
  viewers.delete(socket);
  socket.deviceId = deviceId;
  let set = deviceSockets.get(deviceId);
  if (!set) deviceSockets.set(deviceId, (set = new Set()));
  set.add(socket);
}

websocketServer.on('connection', (socket) => {
  socket.isAlive = true;
  socket._socket?.setNoDelay(true);
  viewers.add(socket);
  send(socket, { type: 'connected', serverTime: Date.now() });

  socket.on('pong', () => { socket.isAlive = true; });
  socket.on('message', (raw) => {
    socket.isAlive = true;
    let message;
    try {
      message = JSON.parse(raw.toString());
    } catch {
      return send(socket, { type: 'error', error: 'Mensaje WebSocket inválido' });
    }
    switch (message.type) {
      case 'ping':
        // Sincronización de reloj (estilo NTP) y medición de RTT.
        return send(socket, { type: 'pong', t: message.t, serverTime: Date.now() });
      case 'hello': {
        const result = upsertDevice(message.data || {});
        if (result.error) return send(socket, { type: 'error', error: result.error });
        attachDevice(socket, result.device.device_id);
        broadcast({ type: 'device.updated', data: publicDevice(result.device) });
        return send(socket, { type: 'hello.ok', serverTime: Date.now() });
      }
      case 'location': {
        const payload = message.data || {};
        const deviceId = String(payload.deviceId || socket.deviceId || '');
        const result = acceptLocation(deviceId, payload);
        if (result.error) return send(socket, { type: 'location.rejected', data: { sampleId: payload.sampleId, error: result.error } });
        return send(socket, { type: 'location.accepted', data: { sampleId: result.sampleId, duplicate: result.duplicate === true } });
      }
      case 'locations': {
        const items = Array.isArray(message.data) ? message.data.slice(0, 500) : [];
        const accepted = [];
        for (const item of items) {
          const result = acceptLocation(String(item.deviceId || socket.deviceId || ''), { ...item, live: false });
          if (!result.error) accepted.push(result.sampleId);
        }
        return send(socket, { type: 'locations.accepted', data: { sampleIds: accepted } });
      }
      default:
        return undefined;
    }
  });
  socket.on('close', () => {
    viewers.delete(socket);
    if (socket.deviceId) {
      deviceSockets.get(socket.deviceId)?.delete(socket);
      const device = data.devices.find((item) => item.device_id === socket.deviceId);
      if (device) broadcast({ type: 'device.updated', data: publicDevice(device) });
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

function shutdown() {
  locationsStream.end();
  fs.writeFileSync(dbFile, JSON.stringify(data));
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

server.listen(port, () => console.log(`Movimiento API escuchando en http://localhost:${port}`));
