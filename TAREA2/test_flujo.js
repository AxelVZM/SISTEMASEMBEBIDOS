const { io } = require("socket.io-client");
const assert = require("assert");

const a = io("http://127.0.0.1:3000");
const b = io("http://127.0.0.1:3000");
let code;
let ultimoEstado;
let falloPorDistancia = false;
let impactos = 0;
let iniciado = false;

a.on("connect", () => {
  a.emit("crear_sala", { name: "Ana" }, (res) => {
    assert.equal(res.ok, true);
    code = res.code;
    b.emit("unirse_sala", { name: "Beto", code }, (res2) => {
      assert.equal(res2.ok, true);
      a.emit("elegir_personaje", { character: "cuy" });
      b.emit("elegir_personaje", { character: "jaguar" });
    });
  });
});

a.on("ataque_fallido", () => { falloPorDistancia = true; });
a.on("golpe", () => { impactos += 1; });
a.on("estado", (estado) => {
  ultimoEstado = estado;
  if (!estado.started || iniciado) return;
  iniciado = true;

  // Fallo a distancia y rechazo de teletransporte.
  a.emit("atacar", { attack: "especial" });
  a.emit("mover", { x: 97, estado: "walk" });

  // Acercamiento progresivo válido para ambos jugadores.
  let pasos = 0;
  const acercar = setInterval(() => {
    pasos += 1;
    a.emit("mover", { x: 44, estado: "walk" });
    b.emit("mover", { x: 56, estado: "walk" });
    if (pasos === 7) {
      clearInterval(acercar);
      b.emit("bloquear", { activo: true });
      setTimeout(() => a.emit("atacar", { attack: "golpe" }), 120);
      setTimeout(() => {
        b.emit("bloquear", { activo: false });
        a.emit("atacar", { attack: "patada" });
      }, 720);
    }
  }, 55);

  setTimeout(() => {
    const yo = ultimoEstado.players[0];
    const rival = ultimoEstado.players[1];
    assert.equal(falloPorDistancia, true, "debe detectar ataques fuera de alcance");
    assert.ok(yo.x < 70, "el servidor debe rechazar teletransportes");
    assert.equal(impactos, 2, "debe registrar los dos impactos cercanos");
    assert.ok(rival.hp < rival.maxHp, "el rival debe recibir daño");
    assert.ok(rival.x > 56, "el rival debe retroceder");
    assert.equal(rival.stats.blocks, 1, "debe registrar el bloqueo");
    assert.ok(yo.stats.maxCombo >= 2, "debe registrar el combo");
    console.log("PRUEBA OK: alcance, movimiento validado, bloqueo, combo, daño y retroceso.");
    a.close();
    b.close();
    process.exit(0);
  }, 1900);
});

setTimeout(() => {
  console.error("La prueba excedió el tiempo máximo.");
  process.exit(1);
}, 5000);
