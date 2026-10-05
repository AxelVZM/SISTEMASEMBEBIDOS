const { spawn } = require('child_process');
const { io } = require('socket.io-client');
const assert = require('assert');
const wait = ms => new Promise(r => setTimeout(r, ms));
const PORT = 3100;

async function connectClient() {
  const s = io(`http://127.0.0.1:${PORT}`, { transports: ['websocket'], reconnection: false });
  await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout de conexión')), 3000);
    s.once('connect', () => { clearTimeout(t); resolve(); });
    s.once('connect_error', reject);
  });
  return s;
}

(async () => {
  const child = spawn(process.execPath, ['server.js'], {
    cwd: __dirname,
    env: { ...process.env, PORT: String(PORT), NODE_ENV: 'test', AUTO_PORT_FALLBACK: 'false' },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  child.stderr.on('data', d => process.stderr.write(d));
  await wait(650);
  let a, b, spectator;
  try {
    a = await connectClient(); b = await connectClient(); spectator = await connectClient();
    let state, started = false, farMiss = false, hits = 0, attackAnimated = false;
    a.on('estado', s => { state = s; if (s.started) started = true; });

    const created = await new Promise(r => a.emit('crear_sala', { name: 'Ana', sessionToken: 'test-a' }, r));
    assert(created.ok); const code = created.code; const aKey = created.playerKey;
    const joined = await new Promise(r => b.emit('unirse_sala', { name: 'Beto', code, sessionToken: 'test-b' }, r));
    assert(joined.ok); const bKey = joined.playerKey;
    const watched = await new Promise(r => spectator.emit('unirse_espectador', { code }, r));
    assert(watched.ok);

    a.on('ataque_iniciado', e => { if (e.attackerId === aKey) attackAnimated = true; });
    a.on('ataque_fallido', e => { if (e.attackerId === aKey && e.reason === 'distancia') farMiss = true; });
    a.on('golpe', () => hits++);

    a.emit('elegir_mapa', { stageIndex: 3 });
    a.emit('elegir_personaje', { character: 'coya' });
    b.emit('elegir_personaje', { character: 'jaguar' });
    for (let i = 0; i < 35 && (!started || !state.roundActive); i++) await wait(100);
    assert(started && state.roundActive, 'la pelea debe iniciar tras la animación de entrada');
    assert.equal(state.stageIndex, 3); assert.equal(state.spectators, 1);

    const hpInicial = state.players.find(p => p.id === bKey).hp;
    a.emit('atacar', { attack: 'golpe' }); await wait(500);
    assert(attackAnimated, 'el ataque debe animarse aunque esté lejos');
    assert(farMiss, 'el servidor debe detectar distancia');
    assert.equal(state.players.find(p => p.id === bKey).hp, hpInicial, 'no debe haber daño a distancia');

    for (let i = 0; i < 22; i++) {
      a.emit('mover', { x: 47, estado: 'run' }); b.emit('mover', { x: 53, estado: 'run' }); await wait(65);
    }
    a.emit('atacar', { attack: 'golpe' }); await wait(550);
    assert(hits >= 1, 'debe golpear al estar dentro de la hitbox');
    assert(state.players.find(p => p.id === bKey).hp < hpInicial);

    const before = state.players.find(p => p.id === aKey).x;
    a.emit('dash', { direction: -1 }); await wait(180);
    assert(state.players.find(p => p.id === aKey).x < before, 'dash debe desplazar al jugador');

    console.log('PRUEBA OK: entrada, mapa, espectador, rango, hitbox y dash.');
  } finally {
    a?.close(); b?.close(); spectator?.close(); child.kill('SIGTERM');
  }
})().catch(err => { console.error(err); process.exitCode = 1; });
