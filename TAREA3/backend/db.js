// Acceso a PostgreSQL (AWS RDS).
//
// Diseño para tiempo real: el servidor difunde cada punto al panel en cuanto
// llega y lo encola aquí. La cola se escribe en la base de datos con un único
// INSERT de varias filas: inmediatamente si la base está libre, o agrupando
// los puntos que llegan mientras otra escritura está en curso. Así la
// latencia de la base de datos nunca retrasa la visualización, y el celular
// recibe la confirmación solo cuando el punto ya quedó guardado.

const fs = require('node:fs');
const path = require('node:path');
const { Pool } = require('pg');

function sslConfig() {
  const mode = (process.env.PGSSLMODE || 'require').toLowerCase();
  if (mode === 'disable') return false;
  const ca = process.env.PGSSLROOTCERT || path.join(__dirname, 'certs', 'rds-global-bundle.pem');
  if (fs.existsSync(ca)) return { ca: fs.readFileSync(ca, 'utf8'), rejectUnauthorized: true };
  console.warn('[db] Sin certificado de RDS: SSL activo pero sin verificar el servidor.');
  return { rejectUnauthorized: false };
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || undefined,
  host: process.env.PGHOST,
  port: Number(process.env.PGPORT || 5432),
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  database: process.env.PGDATABASE,
  ssl: sslConfig(),
  max: Number(process.env.PGPOOL_MAX || 10),
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
  application_name: 'movimiento-api',
});
pool.on('error', (error) => console.error('[db] Error en conexión inactiva', error.message));

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS devices (
  device_id    TEXT PRIMARY KEY,
  user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
  name         TEXT NOT NULL,
  platform     TEXT NOT NULL,
  app_version  TEXT NOT NULL DEFAULT '0.0.0',
  model        TEXT NOT NULL DEFAULT '',
  last_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
  battery      SMALLINT,
  consented_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
  id          BIGSERIAL PRIMARY KEY,
  device_id   TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  sample_id   TEXT NOT NULL UNIQUE,
  latitude    DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude   DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  accuracy    REAL,
  speed       REAL,
  heading     REAL,
  altitude    REAL,
  battery     SMALLINT,
  ts          TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  latency_ms  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_locations_device_ts ON locations (device_id, ts);
`;

async function migrate() {
  await pool.query(SCHEMA);
}

async function ping() {
  const started = Date.now();
  await pool.query('SELECT 1');
  return Date.now() - started;
}

// ---------------------------------------------------------------------------
// Escritura por lotes (write-behind)
// ---------------------------------------------------------------------------
const FLUSH_MS = Number(process.env.DB_FLUSH_MS || 200);
const MAX_BATCH = 500;
let queue = [];          // [{ row, resolve, reject }]
let deviceTouches = new Map(); // deviceId -> { lastSeen, battery }
let flushing = null;
let timer = null;
let consecutiveFailures = 0;

function scheduleFlush(immediate = false) {
  if (timer) {
    if (!immediate) return;
    clearTimeout(timer);
  }
  timer = setTimeout(() => { timer = null; flush().catch(() => {}); }, immediate ? 0 : FLUSH_MS);
}

/**
 * Encola una ubicación. La promesa se resuelve cuando está guardada.
 * Escritura adaptativa: si la base de datos está libre se escribe en el
 * siguiente ciclo (latencia mínima); los puntos que llegan mientras hay una
 * escritura en curso se agrupan solos en el siguiente lote.
 */
function enqueueLocation(row) {
  return new Promise((resolve, reject) => {
    queue.push({ row, resolve, reject });
    if (!flushing) scheduleFlush(true);
  });
}

/** Actualiza last_seen/batería en el próximo lote (sin una consulta por punto). */
function touchDevice(deviceId, lastSeen, battery) {
  const previous = deviceTouches.get(deviceId);
  deviceTouches.set(deviceId, { lastSeen, battery: battery ?? previous?.battery ?? null });
  scheduleFlush();
}

async function flush() {
  if (flushing) return flushing;
  flushing = (async () => {
    while (queue.length || deviceTouches.size) {
      const batch = queue.splice(0, MAX_BATCH);
      const touches = deviceTouches;
      deviceTouches = new Map();
      try {
        if (batch.length) await insertLocations(batch.map((item) => item.row));
        if (touches.size) await updateDevicesSeen(touches);
        batch.forEach((item) => item.resolve());
        consecutiveFailures = 0;
      } catch (error) {
        consecutiveFailures++;
        console.error(`[db] Falló el lote (${batch.length} puntos):`, error.message);
        // Se reintenta con espera creciente; los celulares conservan sus
        // puntos en SQLite hasta recibir la confirmación.
        queue = batch.concat(queue);
        for (const [id, value] of touches) if (!deviceTouches.has(id)) deviceTouches.set(id, value);
        if (consecutiveFailures >= 5) {
          for (const item of queue.splice(0)) item.reject(error);
        }
        await new Promise((resolve) => setTimeout(resolve, Math.min(5000, 250 * 2 ** consecutiveFailures)));
      }
    }
  })().finally(() => { flushing = null; });
  return flushing;
}

const LOCATION_COLUMNS = ['device_id', 'sample_id', 'latitude', 'longitude', 'accuracy', 'speed', 'heading', 'altitude', 'battery', 'ts', 'received_at', 'latency_ms'];

async function insertLocations(rows) {
  const values = [];
  const tuples = rows.map((row, i) => {
    const base = i * LOCATION_COLUMNS.length;
    values.push(row.deviceId, row.sampleId, row.latitude, row.longitude, row.accuracy, row.speed,
      row.heading, row.altitude, row.battery, row.timestamp, row.receivedAt, row.latencyMs);
    return `(${LOCATION_COLUMNS.map((_, j) => `$${base + j + 1}`).join(',')})`;
  });
  await pool.query(
    `INSERT INTO locations (${LOCATION_COLUMNS.join(',')}) VALUES ${tuples.join(',')}
     ON CONFLICT (sample_id) DO NOTHING`,
    values,
  );
}

async function updateDevicesSeen(touches) {
  const ids = [];
  const seen = [];
  const batteries = [];
  for (const [id, value] of touches) {
    ids.push(id);
    seen.push(value.lastSeen);
    batteries.push(value.battery);
  }
  await pool.query(
    `UPDATE devices d SET last_seen = GREATEST(d.last_seen, u.last_seen),
            battery = COALESCE(u.battery, d.battery)
       FROM unnest($1::text[], $2::timestamptz[], $3::smallint[]) AS u(device_id, last_seen, battery)
      WHERE d.device_id = u.device_id`,
    [ids, seen, batteries],
  );
}

// ---------------------------------------------------------------------------
// Dispositivos
// ---------------------------------------------------------------------------
function mapDevice(row) {
  return {
    device_id: row.device_id,
    name: row.name,
    platform: row.platform,
    app_version: row.app_version,
    model: row.model,
    last_seen: row.last_seen instanceof Date ? row.last_seen.toISOString() : row.last_seen,
    battery: row.battery,
  };
}

async function upsertDevice(device) {
  const { rows } = await pool.query(
    `INSERT INTO devices (device_id, name, platform, app_version, model, battery, last_seen)
     VALUES ($1, $2, $3, $4, $5, $6, now())
     ON CONFLICT (device_id) DO UPDATE SET
       name = EXCLUDED.name, platform = EXCLUDED.platform, app_version = EXCLUDED.app_version,
       model = CASE WHEN EXCLUDED.model = '' THEN devices.model ELSE EXCLUDED.model END,
       battery = COALESCE(EXCLUDED.battery, devices.battery), last_seen = now()
     RETURNING *, (xmax = 0) AS created`,
    [device.deviceId, device.name, device.platform, device.appVersion, device.model, device.battery],
  );
  return { device: mapDevice(rows[0]), created: rows[0].created };
}

/** Crea un registro mínimo si el dispositivo no existe (no pisa los datos). */
async function ensureDevice(deviceId) {
  const { rows } = await pool.query(
    `INSERT INTO devices (device_id, name, platform) VALUES ($1, 'Dispositivo', 'android')
     ON CONFLICT (device_id) DO UPDATE SET device_id = EXCLUDED.device_id
     RETURNING *`,
    [deviceId],
  );
  return mapDevice(rows[0]);
}

async function listDevices() {
  const { rows } = await pool.query('SELECT * FROM devices ORDER BY name, device_id');
  return rows.map(mapDevice);
}

async function getDevice(deviceId) {
  const { rows } = await pool.query('SELECT * FROM devices WHERE device_id = $1', [deviceId]);
  return rows[0] ? mapDevice(rows[0]) : null;
}

async function deleteDevice(deviceId) {
  await flush();
  const { rowCount } = await pool.query('DELETE FROM devices WHERE device_id = $1', [deviceId]);
  return rowCount > 0;
}

async function deleteLocations(deviceId) {
  await flush();
  const { rowCount } = await pool.query('DELETE FROM locations WHERE device_id = $1', [deviceId]);
  return rowCount;
}

// ---------------------------------------------------------------------------
// Ubicaciones
// ---------------------------------------------------------------------------
function mapLocation(row) {
  return {
    deviceId: row.device_id,
    sampleId: row.sample_id,
    latitude: row.latitude,
    longitude: row.longitude,
    accuracy: row.accuracy,
    speed: row.speed,
    heading: row.heading,
    altitude: row.altitude,
    battery: row.battery,
    timestamp: row.ts.toISOString(),
    receivedAt: row.received_at.toISOString(),
    latencyMs: row.latency_ms,
  };
}

async function latestLocation(deviceId) {
  const { rows } = await pool.query(
    'SELECT * FROM locations WHERE device_id = $1 ORDER BY ts DESC LIMIT 1',
    [deviceId],
  );
  return rows[0] ? mapLocation(rows[0]) : null;
}

async function historyRange(deviceId, from, to, limit = 10000) {
  const { rows } = await pool.query(
    `SELECT * FROM (
       SELECT * FROM locations WHERE device_id = $1 AND ts BETWEEN $2 AND $3
       ORDER BY ts DESC LIMIT $4
     ) t ORDER BY ts`,
    [deviceId, from, to, limit],
  );
  return rows.map(mapLocation);
}

/**
 * Último recorrido: puntos contiguos desde el final sin huecos mayores a
 * gapMs. Se resuelve en la base de datos con una función de ventana.
 */
async function lastSession(deviceId, gapMs, limit = 10000) {
  const { rows } = await pool.query(
    `WITH ordered AS (
       SELECT *, ts - lag(ts) OVER (ORDER BY ts) AS gap
         FROM (SELECT * FROM locations WHERE device_id = $1 ORDER BY ts DESC LIMIT $3::int) recent
     ), start AS (
       SELECT COALESCE(max(ts), '-infinity'::timestamptz) AS ts
         FROM ordered WHERE gap > make_interval(secs => $2::double precision / 1000)
     )
     SELECT o.* FROM ordered o, start s WHERE o.ts >= s.ts ORDER BY o.ts`,
    [deviceId, gapMs, limit],
  );
  return rows.map(mapLocation);
}

async function sampleExists(sampleId) {
  const { rowCount } = await pool.query('SELECT 1 FROM locations WHERE sample_id = $1', [sampleId]);
  return rowCount > 0;
}

// ---------------------------------------------------------------------------
// Usuarios
// ---------------------------------------------------------------------------
async function createUser(email, passwordHash) {
  const { rows } = await pool.query(
    'INSERT INTO users (email, password_hash) VALUES ($1, $2) ON CONFLICT (email) DO NOTHING RETURNING id, email',
    [email, passwordHash],
  );
  return rows[0] || null;
}

async function findUserByEmail(email) {
  const { rows } = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
  return rows[0] || null;
}

async function close() {
  await flush().catch(() => {});
  await pool.end();
}

module.exports = {
  pool, migrate, ping, flush, close,
  enqueueLocation, touchDevice,
  upsertDevice, ensureDevice, listDevices, getDevice, deleteDevice, deleteLocations,
  latestLocation, historyRange, lastSession, sampleExists,
  createUser, findUserByEmail,
  pendingWrites: () => queue.length,
};
