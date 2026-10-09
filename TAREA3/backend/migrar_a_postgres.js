// Copia los datos del almacenamiento anterior (archivos JSON/NDJSON en data/)
// a PostgreSQL. Se puede ejecutar varias veces: no duplica nada.
//
//   node migrar_a_postgres.js

require('dotenv').config();

const fs = require('node:fs');
const path = require('node:path');
const db = require('./db');

const dbFile = path.resolve(__dirname, process.env.DB_FILE || './data/movimiento.json');
const locationsFile = dbFile.replace(/\.json$/i, '') + '.locations.ndjson';

function leerUbicaciones(meta) {
  const ubicaciones = [];
  // Formato más antiguo: ubicaciones dentro del JSON principal.
  if (Array.isArray(meta.locations)) ubicaciones.push(...meta.locations);
  if (fs.existsSync(locationsFile)) {
    for (const linea of fs.readFileSync(locationsFile, 'utf8').split('\n')) {
      if (!linea.trim()) continue;
      try { ubicaciones.push(JSON.parse(linea)); } catch { /* línea corrupta */ }
    }
  }
  return ubicaciones
    .map((u) => ({ ...u, deviceId: u.deviceId || u.device_id }))
    .filter((u) => u.deviceId && Number.isFinite(u.latitude) && Number.isFinite(u.longitude) && u.timestamp);
}

async function main() {
  if (!fs.existsSync(dbFile)) {
    console.log(`No hay datos anteriores en ${dbFile}; nada que migrar.`);
    return;
  }
  const meta = JSON.parse(fs.readFileSync(dbFile, 'utf8'));
  await db.migrate();

  let usuarios = 0;
  for (const user of meta.users || []) {
    if (await db.createUser(user.email, user.password_hash)) usuarios++;
  }

  const dispositivos = new Map((meta.devices || []).map((d) => [d.device_id, d]));
  const ubicaciones = leerUbicaciones(meta);
  for (const u of ubicaciones) {
    if (!dispositivos.has(u.deviceId)) dispositivos.set(u.deviceId, { device_id: u.deviceId, name: 'Dispositivo', platform: 'android' });
  }
  for (const d of dispositivos.values()) {
    await db.pool.query(
      `INSERT INTO devices (device_id, name, platform, app_version, model, last_seen, battery)
       VALUES ($1, $2, $3, $4, $5, COALESCE($6::timestamptz, now()), $7)
       ON CONFLICT (device_id) DO NOTHING`,
      [d.device_id, d.name || 'Dispositivo', d.platform || 'android', d.app_version || '0.0.0', d.model || '', d.last_seen || null, Number.isInteger(d.battery) ? d.battery : null],
    );
  }

  let i = 0;
  for (const u of ubicaciones) {
    db.enqueueLocation({
      deviceId: u.deviceId,
      sampleId: String(u.sampleId || `${u.deviceId}-migrado-${i++}`),
      latitude: u.latitude,
      longitude: u.longitude,
      accuracy: Number.isFinite(u.accuracy) ? u.accuracy : null,
      speed: Number.isFinite(u.speed) ? u.speed : null,
      heading: Number.isFinite(u.heading) ? u.heading : null,
      altitude: Number.isFinite(u.altitude) ? u.altitude : null,
      battery: Number.isInteger(u.battery) ? u.battery : null,
      timestamp: u.timestamp,
      receivedAt: u.receivedAt || u.timestamp,
      latencyMs: Number.isFinite(u.latencyMs) ? Math.round(u.latencyMs) : null,
    }).catch(() => {});
  }
  await db.flush();

  const { rows } = await db.pool.query('SELECT (SELECT count(*) FROM devices) AS d, (SELECT count(*) FROM locations) AS l');
  console.log(`Migración completa: ${usuarios} usuarios nuevos, ${dispositivos.size} dispositivos, ${ubicaciones.length} ubicaciones leídas.`);
  console.log(`En PostgreSQL ahora hay ${rows[0].d} dispositivos y ${rows[0].l} ubicaciones.`);
}

main()
  .catch((error) => { console.error('Error en la migración:', error.message); process.exitCode = 1; })
  .finally(() => db.close());
