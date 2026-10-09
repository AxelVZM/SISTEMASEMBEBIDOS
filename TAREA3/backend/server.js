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
const activeWindowMs = 3 * 60 * 1000;
const jwtSecret = process.env.JWT_SECRET || 'development-only-secret';
const dbFile = path.resolve(process.env.DB_FILE || './data/movimiento.json');
fs.mkdirSync(path.dirname(dbFile), { recursive: true });
const data = fs.existsSync(dbFile)
  ? JSON.parse(fs.readFileSync(dbFile, 'utf8'))
  : { nextUserId: 1, users: [], devices: [], locations: [] };
const saveData = () => fs.writeFileSync(dbFile, JSON.stringify(data, null, 2));
let persistScheduled = false;
function persistSoon() {
  if (persistScheduled) return;
  persistScheduled = true;
  setImmediate(() => {
    persistScheduled = false;
    saveData();
  });
}
const app = express();
app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors({ origin: process.env.CORS_ORIGIN || 'http://localhost:8080' }));
app.use(express.json({ limit: '256kb' }));
app.use(rateLimit({ windowMs: 60_000, limit: 120, standardHeaders: true, legacyHeaders: false }));

function tokenFor(user) {
  return jwt.sign({ sub: String(user.id), email: user.email }, jwtSecret, { expiresIn: process.env.JWT_EXPIRES_IN || '8h' });
}

function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'Autenticación requerida' });
  try {
    req.user = jwt.verify(token, jwtSecret);
    next();
  } catch {
    return res.status(401).json({ error: 'Token inválido o expirado' });
  }
}

function validCoordinate(value, min, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function deviceForUser(deviceId, userId) {
  return data.devices.find((device) => device.device_id === deviceId && String(device.user_id) === String(userId));
}

const sockets = new Set();
const seenSamples = new Set(data.locations.map((location) => location.sampleId).filter(Boolean));
const latencySamples = [];
let discardedSamples = 0;
function broadcast(message) {
  const data = JSON.stringify(message);
  for (const socket of sockets) {
    if (socket.readyState === 1) socket.send(data);
  }

  function recordLatency(location, receivedAt) {
    const acquisition = Date.parse(location.timestamp);
    const latencyMs = Number.isFinite(acquisition) ? Math.max(0, Date.now() - acquisition) : null;
    if (latencyMs !== null) {
      latencySamples.push(latencyMs);
      if (latencySamples.length > 5000) latencySamples.shift();
    }
    return {
      ...location,
      receivedAt,
      broadcastAt: new Date().toISOString(),
      latencyMs,
    };
  }

  function acceptLocation(deviceId, body) {
    if (!data.devices.some((device) => device.device_id === deviceId)) {
      return { status: 404, error: 'Dispositivo no registrado' };
    }
    if (!validCoordinate(body.latitude, -90, 90) || !validCoordinate(body.longitude, -180, 180)) {
      discardedSamples++;
      return { status: 400, error: 'Coordenadas inválidas' };
    }
    const timestamp = new Date(body.timestamp || Date.now());
    if (Number.isNaN(timestamp.getTime())) {
      discardedSamples++;
      return { status: 400, error: 'timestamp inválido' };
    }
    const sampleId = String(body.sampleId || `${deviceId}-${timestamp.getTime()}-${body.latitude}-${body.longitude}`);
    if (seenSamples.has(sampleId)) return { duplicate: true, sampleId };
    seenSamples.add(sampleId);
    const location = {
      deviceId, sampleId, latitude: body.latitude, longitude: body.longitude,
      accuracy: Number.isFinite(body.accuracy) ? body.accuracy : null,
      speed: Number.isFinite(body.speed) ? body.speed : null,
      heading: Number.isFinite(body.heading) ? body.heading : null,
      battery: Number.isInteger(body.battery) ? body.battery : null,
      timestamp: timestamp.toISOString(),
    };
    const receivedAt = new Date().toISOString();
    data.locations.push({ ...location, device_id: deviceId });
    const device = data.devices.find((item) => item.device_id === deviceId);
    Object.assign(device, { last_seen: location.timestamp, battery: location.battery });
    const measured = recordLatency(location, receivedAt);
    persistSoon();
    broadcast({ type: 'location.updated', data: measured });
    return { location: measured };
  }
}

app.get('/api/health', (_req, res) => res.json({ ok: true, service: 'movimiento-api' }));

app.post('/api/auth/register', async (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  const password = String(req.body.password || '');
  if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 8) {
    return res.status(400).json({ error: 'Correo inválido o contraseña menor de 8 caracteres' });
  }
  try {
    const user = { id: data.nextUserId++, email, password_hash: await bcrypt.hash(password, 12), created_at: new Date().toISOString() };
    data.users.push(user);
    saveData();
    return res.status(201).json({ token: tokenFor(user), user });
  } catch {
    return res.status(409).json({ error: 'El correo ya está registrado' });
  }
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
  const body = req.body || {};
  const deviceId = String(body.deviceId || '').trim();
  const name = String(body.name || 'Dispositivo sin nombre').trim().slice(0, 120);
  if (!deviceId || deviceId.length > 150 || !String(body.platform || '').trim()) {
    return res.status(400).json({ error: 'deviceId y platform son obligatorios' });
  }
  const now = new Date().toISOString();
  const existing = data.devices.find((device) => device.device_id === deviceId);
  if (existing) {
    Object.assign(existing, { name, platform: String(body.platform), app_version: String(body.appVersion || '0.0.0'), model: String(body.model || ''), last_seen: now, battery: body.battery ?? null, consented_at: now });
    saveData();
    return res.json({ deviceId, updated: true });
  }
  data.devices.push({ device_id: deviceId, user_id: null, name, platform: String(body.platform), app_version: String(body.appVersion || '0.0.0'), model: String(body.model || ''), last_seen: now, battery: body.battery ?? null, consented_at: now });
  saveData();
  return res.status(201).json({ deviceId, created: true });
});

app.post('/api/devices/:deviceId/locations', (req, res) => {
  const result = acceptLocation(String(req.params.deviceId), req.body || {});
  if (result.error) return res.status(result.status).json({ error: result.error });
  if (result.duplicate) return res.status(200).json({ ok: true, duplicate: true, sampleId: result.sampleId });
  return res.status(201).json({ ok: true, location: result.location });
});

app.get('/api/metrics', (_req, res) => {
  const sorted = [...latencySamples].sort((a, b) => a - b);
  const percentile = (ratio) => sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * ratio))] : null;
  res.json({
    samples: sorted.length,
    averageMs: sorted.length ? sorted.reduce((sum, value) => sum + value, 0) / sorted.length : null,
    p50Ms: percentile(0.5), p95Ms: percentile(0.95), p99Ms: percentile(0.99),
    maxMs: sorted.at(-1) ?? null,
    under1000Percent: sorted.length ? (sorted.filter((value) => value < 1000).length / sorted.length) * 100 : null,
    discardedSamples,
  });
});

app.get('/api/devices', (_req, res) => {
  const devices = data.devices.sort((a, b) => a.name.localeCompare(b.name)).map((device) => ({
    deviceId: device.device_id, name: device.name, platform: device.platform, appVersion: device.app_version, model: device.model,
    lastSeen: device.last_seen, battery: device.battery, online: Date.now() - Date.parse(device.last_seen) < activeWindowMs,
  }));
  res.json({ devices });
});

app.get('/api/devices/:deviceId/location', (req, res) => {
  if (!data.devices.some((device) => device.device_id === req.params.deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const location = data.locations
    .filter((item) => item.device_id === req.params.deviceId)
    .sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp))[0] || null;
  const activeLocation = location && Date.now() - Date.parse(location.timestamp) < activeWindowMs
    ? location
    : null;
  res.json({ location: activeLocation });
});

app.get('/api/devices/:deviceId/history', (req, res) => {
  if (!data.devices.some((device) => device.device_id === req.params.deviceId)) return res.status(404).json({ error: 'Dispositivo no registrado' });
  const from = req.query.from ? new Date(req.query.from) : new Date(Date.now() - 24 * 60 * 60 * 1000);
  const to = req.query.to ? new Date(req.query.to) : new Date();
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return res.status(400).json({ error: 'Rango de fechas inválido' });
  const activeOnly = req.query.activeOnly === 'true';
  const activeFrom = new Date(Date.now() - activeWindowMs);
  const locations = data.locations
    .filter((item) => item.device_id === req.params.deviceId
      && item.timestamp >= from.toISOString()
      && item.timestamp <= to.toISOString()
      && (!activeOnly || item.timestamp >= activeFrom.toISOString()))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .slice(0, 10000);
  res.json({ locations });
});

const server = http.createServer(app);
const websocketServer = new WebSocketServer({ server, path: '/ws' });
websocketServer.on('connection', (socket, request) => {
  sockets.add(socket);
  socket.send(JSON.stringify({ type: 'connected' }));
  socket.on('message', (raw) => {
    try {
      const message = JSON.parse(raw.toString());
      if (message.type !== 'location' || !message.data) return;
      const deviceId = String(message.data.deviceId || message.data.device_id || '');
      const result = acceptLocation(deviceId, message.data);
      if (result.error) {
        socket.send(JSON.stringify({ type: 'location.rejected', data: { sampleId: message.data.sampleId, error: result.error } }));
      } else {
        socket.send(JSON.stringify({
          type: 'location.accepted',
          data: { sampleId: message.data.sampleId || result.sampleId, duplicate: result.duplicate === true },
        }));
      }
    } catch {
      socket.send(JSON.stringify({ type: 'error', error: 'Mensaje WebSocket inválido' }));
    }
  });
  socket.on('close', () => sockets.delete(socket));
});

app.use(express.static(path.join(__dirname, 'public')));
app.use((_req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));
server.listen(port, () => console.log(`Movimiento API escuchando en http://localhost:${port}`));
