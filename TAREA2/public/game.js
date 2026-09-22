const socket = io();

// Cada personaje tiene una imagen distinta para cada pose/accion
const CHARACTERS = {
  coya: personaje("Coya", "coya", "Equilibrada · Filo solar"),
  cuy: personaje("Cuy", "cuy", "Resistente · Mochila guardiana"),
  gallito: personaje("Gallito de las Rocas", "gallito", "Rápido · Puños de acero"),
  jaguar: personaje("Jaguar", "jaguar", "Poderoso · Zarpazo del sol"),
  oso: personaje("Oso de Anteojos", "oso", "Tanque · Guardia de montaña"),
  gato: personaje("Gato Andino", "gato", "Muy veloz · Garra lunar")
};

function personaje(name, id, estilo) {
  const poses = {};
  ["idle", "walk", "punch", "kick", "hurt", "block", "ko"].forEach((pose) => {
    poses[pose] = `img/${id}_${pose}.png`;
  });
  return { name, estilo, poses };
}

// El ataque "especial" reutiliza la pose de patada pero con mas efecto visual
const POSE_POR_ATAQUE = { golpe: "punch", patada: "kick", especial: "kick" };
const STAGES = [
  { nombre: "Machu Picchu", archivo: "/assets/mapas-cusco/machu-picchu.png" },
  { nombre: "Sacsayhuamán", archivo: "/assets/mapas-cusco/sacsayhuaman.png" },
  { nombre: "Qorikancha", archivo: "/assets/mapas-cusco/qorikancha.png" },
  { nombre: "Plaza de Armas", archivo: "/assets/mapas-cusco/plaza-de-armas.png" },
  { nombre: "Ollantaytambo", archivo: "/assets/mapas-cusco/ollantaytambo.png" }
 ];
STAGES.forEach((stage) => {
  const img = new Image();
  img.decoding = "async";
  img.src = stage.archivo;
});

let miId = null;
let salaActual = null;
let miNombre = "";
let miIndex = -1; // 0 = jugador que crea la sala, 1 = el que se une
let modoActual = null; // story | local | online
let musicaSilenciada = localStorage.getItem("maqanakuy-musica") === "off";
let sfxActivos = localStorage.getItem("maqanakuy-sfx") !== "off";
let juegoPausado = false;
let configAbiertaDesdePausa = false;

// ---------- Navegacion entre pantallas + musica ambiental ----------
const musicaFrame = document.getElementById("musica-frame");
function comandoMusica(func) {
  if (!musicaFrame || !musicaFrame.contentWindow) return;
  musicaFrame.contentWindow.postMessage(JSON.stringify({ event: "command", func, args: [] }), "*");
}
function actualizarBotonMusica() {
  const btn = document.getElementById("btn-musica");
  if (!btn) return;
  btn.textContent = musicaSilenciada ? "🔇" : "🔊";
  btn.setAttribute("aria-label", musicaSilenciada ? "Activar música" : "Silenciar música");
}
function sincronizarMusica() {
  const enPelea = document.getElementById("pantalla-batalla").classList.contains("activa");
  if (musicaSilenciada || enPelea) comandoMusica("pauseVideo");
  else comandoMusica("playVideo");
  actualizarBotonMusica();
}
function intentarMusica() { sincronizarMusica(); }
["pointerdown", "keydown", "touchstart"].forEach((evento) => window.addEventListener(evento, intentarMusica, { once: true, passive: true }));
function mostrarPantalla(id) {
  document.querySelectorAll(".pantalla").forEach((p) => p.classList.remove("activa"));
  document.getElementById(id).classList.add("activa");
  const acciones = document.querySelector(".acciones-esquina");
  if (acciones) acciones.style.display = id === "pantalla-inicio" ? "flex" : "none";
  sincronizarMusica();
}
document.getElementById("btn-musica").addEventListener("click", () => {
  musicaSilenciada = !musicaSilenciada; localStorage.setItem("maqanakuy-musica", musicaSilenciada ? "off" : "on"); sincronizarMusica();
});
const modalConfig = document.getElementById("modal-config");
const toggleMusica = document.getElementById("toggle-musica");
const toggleSfx = document.getElementById("toggle-sfx");
toggleMusica.checked = !musicaSilenciada; toggleSfx.checked = sfxActivos; actualizarBotonMusica();
document.getElementById("btn-config").addEventListener("click", () => { modalConfig.classList.add("abierto"); modalConfig.setAttribute("aria-hidden", "false"); });
document.getElementById("btn-cerrar-config").addEventListener("click", () => {
  modalConfig.classList.remove("abierto");
  modalConfig.setAttribute("aria-hidden", "true");
  if (configAbiertaDesdePausa && enBatalla) {
    configAbiertaDesdePausa = false;
    modalPausa.classList.add("abierto");
    modalPausa.setAttribute("aria-hidden", "false");
  }
});
modalConfig.addEventListener("click", (e) => { if (e.target === modalConfig) document.getElementById("btn-cerrar-config").click(); });
toggleMusica.addEventListener("change", () => { musicaSilenciada = !toggleMusica.checked; localStorage.setItem("maqanakuy-musica", musicaSilenciada ? "off" : "on"); sincronizarMusica(); });
toggleSfx.addEventListener("change", () => { sfxActivos = toggleSfx.checked; localStorage.setItem("maqanakuy-sfx", sfxActivos ? "on" : "off"); });

const modalPausa = document.getElementById("modal-pausa");
function mostrarPausa() {
  if (!enBatalla || !ultimoEstado || ultimoEstado.finished) return;
  juegoPausado = true;
  teclasPresionadas.clear();
  bloqueando = false;
  socket.emit("pausar", { activo: true });
  document.getElementById("pantalla-batalla").classList.add("pausada");
  modalPausa.classList.add("abierto");
  modalPausa.setAttribute("aria-hidden", "false");
}
function cerrarPausa() {
  if (!enBatalla) return;
  juegoPausado = false;
  socket.emit("pausar", { activo: false });
  document.getElementById("pantalla-batalla").classList.remove("pausada");
  modalPausa.classList.remove("abierto");
  modalPausa.setAttribute("aria-hidden", "true");
}
function alternarPausa() {
  if (!enBatalla) return;
  if (modalConfig.classList.contains("abierto")) {
    modalConfig.classList.remove("abierto");
    modalConfig.setAttribute("aria-hidden", "true");
    if (configAbiertaDesdePausa) {
      configAbiertaDesdePausa = false;
      modalPausa.classList.add("abierto");
      modalPausa.setAttribute("aria-hidden", "false");
    }
    return;
  }
  juegoPausado ? cerrarPausa() : mostrarPausa();
}
function salirDeBatalla() {
  juegoPausado = false;
  document.getElementById("pantalla-batalla").classList.remove("pausada");
  modalPausa.classList.remove("abierto");
  modalPausa.setAttribute("aria-hidden", "true");
  volverMenu();
}
document.getElementById("btn-pausa-batalla").addEventListener("click", mostrarPausa);
document.getElementById("btn-continuar").addEventListener("click", cerrarPausa);
document.getElementById("btn-salir-batalla").addEventListener("click", salirDeBatalla);
document.getElementById("btn-salir-pausa").addEventListener("click", salirDeBatalla);
document.getElementById("btn-config-batalla").addEventListener("click", () => {
  if (!juegoPausado) mostrarPausa();
  modalPausa.classList.remove("abierto");
  modalPausa.setAttribute("aria-hidden", "true");
  configAbiertaDesdePausa = true;
  modalConfig.classList.add("abierto");
  modalConfig.setAttribute("aria-hidden", "false");
});
document.getElementById("btn-config-pausa").addEventListener("click", () => {
  modalPausa.classList.remove("abierto");
  modalPausa.setAttribute("aria-hidden", "true");
  configAbiertaDesdePausa = true;
  modalConfig.classList.add("abierto");
  modalConfig.setAttribute("aria-hidden", "false");
});

// ---------- Audio sintetizado (sin archivos externos) ----------
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function sonido({ freqInicial, freqFinal, duracion, tipo = "square", volumen = 0.2 }) {
  if (!sfxActivos) return;
  if (audioCtx.state === "suspended") audioCtx.resume();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = tipo;
  osc.frequency.setValueAtTime(freqInicial, audioCtx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(Math.max(freqFinal, 1), audioCtx.currentTime + duracion);
  gain.gain.setValueAtTime(volumen, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duracion);
  osc.connect(gain).connect(audioCtx.destination);
  osc.start();
  osc.stop(audioCtx.currentTime + duracion);
}

const sonidos = {
  golpe: () => sonido({ freqInicial: 180, freqFinal: 60, duracion: 0.12, tipo: "square", volumen: 0.25 }),
  patada: () => sonido({ freqInicial: 260, freqFinal: 40, duracion: 0.18, tipo: "sawtooth", volumen: 0.25 }),
  especial: () => {
    sonido({ freqInicial: 500, freqFinal: 100, duracion: 0.3, tipo: "sawtooth", volumen: 0.3 });
    setTimeout(() => sonido({ freqInicial: 700, freqFinal: 150, duracion: 0.25, tipo: "square", volumen: 0.2 }), 90);
  },
  bloqueo: () => sonido({ freqInicial: 900, freqFinal: 700, duracion: 0.08, tipo: "triangle", volumen: 0.15 }),
  fallo: () => sonido({ freqInicial: 420, freqFinal: 180, duracion: 0.16, tipo: "sine", volumen: 0.09 }),
  ko: () => {
    sonido({ freqInicial: 120, freqFinal: 35, duracion: 0.7, tipo: "sawtooth", volumen: 0.32 });
    setTimeout(() => sonido({ freqInicial: 70, freqFinal: 40, duracion: 0.45, tipo: "square", volumen: 0.2 }), 120);
  },
  salto: () => sonido({ freqInicial: 300, freqFinal: 500, duracion: 0.1, tipo: "sine", volumen: 0.12 }),
  seleccion: () => sonido({ freqInicial: 400, freqFinal: 700, duracion: 0.1, tipo: "square", volumen: 0.15 }),
  salaLista: () => {
    [392, 523].forEach((f, i) =>
      setTimeout(() => sonido({ freqInicial: f, freqFinal: f, duracion: 0.15, tipo: "triangle", volumen: 0.15 }), i * 110)
    );
  },
  empezarPelea: () => {
    sonido({ freqInicial: 150, freqFinal: 90, duracion: 0.25, tipo: "sawtooth", volumen: 0.28 });
    setTimeout(() => sonido({ freqInicial: 700, freqFinal: 700, duracion: 0.35, tipo: "square", volumen: 0.25 }), 220);
  },
  victoria: () => {
    [523, 659, 784, 1046].forEach((f, i) =>
      setTimeout(() => sonido({ freqInicial: f, freqFinal: f, duracion: 0.2, tipo: "triangle", volumen: 0.2 }), i * 130)
    );
  },
  derrota: () => sonido({ freqInicial: 300, freqFinal: 50, duracion: 0.6, tipo: "sawtooth", volumen: 0.2 })
};

// ---------- Pantalla inicio: modos de juego ----------
function nombreActual() { return document.getElementById("input-nombre").value.trim() || "Jugador"; }
function prepararSalaVisual(titulo, texto) {
  document.getElementById("titulo-sala").innerHTML = titulo;
  document.getElementById("texto-sala").textContent = texto;
}
function iniciarSolo(mode) {
  miNombre = nombreActual(); modoActual = mode;
  socket.emit("crear_solo", { name: miNombre, mode }, (res) => {
    if (!res.ok) return mostrarError(res.error);
    salaActual = res.code; miId = socket.id; miIndex = 0;
    prepararSalaVisual(mode === "story" ? "MODO HISTORIA" : "MODO LOCAL", mode === "story" ? "Elige tu luchador y supera a todos los rivales." : "Elige tu luchador para enfrentar a la máquina.");
    document.getElementById("estado-espera").textContent = "";
    document.getElementById("selector-personajes").style.display = "block";
    mostrarError("");
    mostrarPantalla("pantalla-sala");
  });
}
document.getElementById("btn-historia").addEventListener("click", () => iniciarSolo("story"));
document.getElementById("btn-local").addEventListener("click", () => iniciarSolo("local"));
document.getElementById("btn-multijugador").addEventListener("click", () => { modoActual = "online"; mostrarPantalla("pantalla-online"); });
document.getElementById("btn-crear").addEventListener("click", () => {
  miNombre = nombreActual(); modoActual = "online";
  socket.emit("crear_sala", { name: miNombre }, (res) => {
    if (!res.ok) return mostrarError(res.error); salaActual=res.code; miId=socket.id; miIndex=0;
    document.getElementById("codigo-sala").textContent=salaActual; prepararSalaVisual(`Sala: <span id="codigo-sala">${salaActual}</span>`, "Comparte este código con tu rival"); mostrarError(""); mostrarPantalla("pantalla-sala");
  });
});
document.getElementById("btn-unirse").addEventListener("click", () => {
  miNombre=nombreActual(); modoActual="online"; const codigo=document.getElementById("input-codigo").value.trim().toUpperCase(); if(!codigo)return mostrarError("Escribe un código de sala.");
  socket.emit("unirse_sala", {name:miNombre,code:codigo}, (res)=>{ if(!res.ok)return mostrarError(res.error); salaActual=res.code; miId=socket.id; miIndex=1; prepararSalaVisual(`Sala: <span id="codigo-sala">${salaActual}</span>`, "Sala multijugador"); mostrarError(""); mostrarPantalla("pantalla-sala"); });
});
function volverMenu() {
  if (salaActual) socket.emit("salir_sala"); juegoPausado=false; modalPausa.classList.remove("abierto"); document.getElementById("pantalla-batalla").classList.remove("pausada"); salaActual=null; modoActual=null; enBatalla=false; peleaAnunciada=false; ultimoEstado=null; document.getElementById("selector-personajes").style.display="none"; mostrarError(""); mostrarPantalla("pantalla-inicio");
}
document.querySelectorAll(".btn-volver").forEach(btn=>btn.addEventListener("click", volverMenu));
document.getElementById("btn-menu-final").addEventListener("click", volverMenu);

function mostrarError(msg) {
  const ids = ["mensaje-error", "mensaje-error-online"];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = msg || "";
  });
}

// ---------- Seleccion de personaje ----------
function pintarSelectorPersonajes() {
  const contenedor = document.getElementById("lista-personajes");
  contenedor.innerHTML = "";
  Object.entries(CHARACTERS).forEach(([id, c]) => {
    const div = document.createElement("div");
    div.className = "opcion-personaje";
    div.dataset.id = id;
    div.innerHTML = `<img class="icono" src="${c.poses.idle}" alt="${c.name}"><span class="nombre">${c.name}</span><small>${c.estilo}</small>`;
    div.addEventListener("click", () => {
      document.querySelectorAll(".opcion-personaje").forEach((o) => o.classList.remove("elegido"));
      div.classList.add("elegido");
      sonidos.seleccion();
      socket.emit("elegir_personaje", { character: id });
    });
    contenedor.appendChild(div);
  });
}
pintarSelectorPersonajes();

const COOLDOWNS = { golpe: 420, patada: 850, especial: 2500 };
const ataquesListosEn = { golpe: 0, patada: 0, especial: 0 };
function lanzarAtaque(ataque) {
  const ahora = performance.now();
  if (!enBatalla || juegoPausado || bloqueando || ahora < ataquesListosEn[ataque]) return;

  ataquesListosEn[ataque] = ahora + COOLDOWNS[ataque];
  enviarMovimiento(saltando ? "jump" : teclasPresionadas.has("s") ? "duck" : "idle");

  // La respuesta visual del jugador es LOCAL e inmediata: no depende de la distancia
  // al rival ni de la latencia con el servidor. El servidor decide por separado si
  // ese ataque realmente alcanza al rival y, solo entonces, aplica daño.
  animarAtaque(socket.id, ataque);
  if (sonidos[ataque]) sonidos[ataque]();

  socket.emit("atacar", { attack: ataque });
}

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    e.preventDefault();
    alternarPausa();
  }
});

// ---------- Controles de combate ----------
const teclasPresionadas = new Set();
let bloqueando = false;
let enBatalla = false;
let miX = 15; // posicion local (0-100), reconciliada con el servidor
let saltando = false;
let ultimoEstadoMovimiento = "idle";

window.addEventListener("keydown", (e) => {
  const k = e.key.toLowerCase();
  if (!enBatalla || juegoPausado) return;
  if (e.repeat && ["j", "k", "l", "u", "w"].includes(k)) return;

  if (["a", "d", "w", "s"].includes(k)) {
    teclasPresionadas.add(k);
    e.preventDefault();
  }

  if (k === "w" && !saltando) {
    saltando = true;
    enviarMovimiento("jump");
    setTimeout(() => {
      saltando = false;
      if (!teclasPresionadas.has("s")) enviarMovimiento("idle");
    }, 430);
    sonidos.salto();
  }

  if (k === "u" && !bloqueando) {
    bloqueando = true;
    socket.emit("bloquear", { activo: true });
    sonidos.bloqueo();
  }

  if (k === "j") lanzarAtaque("golpe");
  if (k === "k") lanzarAtaque("patada");
  if (k === "l") lanzarAtaque("especial");
});

window.addEventListener("keyup", (e) => {
  const k = e.key.toLowerCase();
  if (["a", "d", "w", "s"].includes(k)) teclasPresionadas.delete(k);
  if (juegoPausado) return;

  if (k === "u" && bloqueando) {
    bloqueando = false;
    socket.emit("bloquear", { activo: false });
  }

  if (k === "s" && !teclasPresionadas.has("s") && !saltando) {
    enviarMovimiento("idle");
  }
});

// Bucle de movimiento local (izquierda/derecha) sincronizado por red
const VELOCIDAD = 1.15; // movimiento más ágil
let ultimoEnvioMov = 0;

function bucleMovimiento() {
  if (enBatalla && !juegoPausado) {
    let cambio = false;
    if (teclasPresionadas.has("a")) { miX = Math.max(3, miX - VELOCIDAD); cambio = true; }
    if (teclasPresionadas.has("d")) { miX = Math.min(97, miX + VELOCIDAD); cambio = true; }

    const ahora = performance.now();
    if (cambio && ahora - ultimoEnvioMov > 36) {
      ultimoEnvioMov = ahora;
      let estado = "walk";
      if (saltando) estado = "jump";
      else if (teclasPresionadas.has("s")) estado = "duck";
      enviarMovimiento(estado);
    }
    aplicarPosicionLocal();
  }
  requestAnimationFrame(bucleMovimiento);
}
requestAnimationFrame(bucleMovimiento);

function actualizarRecargas() {
  const ahora = performance.now();
  document.querySelectorAll(".recarga").forEach((el) => {
    const ataque = el.dataset.ataque;
    const restante = Math.max(0, ataquesListosEn[ataque] - ahora);
    const progreso = 1 - restante / COOLDOWNS[ataque];
    el.style.setProperty("--listo", `${Math.max(0, progreso) * 100}%`);
    el.classList.toggle("lista", restante <= 0);
  });
  requestAnimationFrame(actualizarRecargas);
}
requestAnimationFrame(actualizarRecargas);

// Los controles táctiles solo se muestran en dispositivos sin teclado preciso.
document.querySelectorAll(".controles-tactiles button").forEach((boton) => {
  const tecla = boton.dataset.tecla;
  const presionar = (e) => {
    e.preventDefault();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: tecla }));
    boton.classList.add("presionado");
  };
  const soltar = (e) => {
    e.preventDefault();
    window.dispatchEvent(new KeyboardEvent("keyup", { key: tecla }));
    boton.classList.remove("presionado");
  };
  boton.addEventListener("pointerdown", presionar);
  boton.addEventListener("pointerup", soltar);
  boton.addEventListener("pointercancel", soltar);
  boton.addEventListener("pointerleave", (e) => {
    if (boton.classList.contains("presionado")) soltar(e);
  });
});

function enviarMovimiento(estado) {
  if (juegoPausado) return;
  ultimoEstadoMovimiento = estado;
  socket.emit("mover", { x: miX, estado });
}

function aplicarPosicionLocal() {
  const elId = miIndex === 0 ? "luchador1" : "luchador2";
  const el = document.getElementById(elId);
  if (el) el.style.left = miX + "%";
}

function hashCadena(valor) {
  return [...String(valor || "AM")].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
}

function obtenerEscenarioActual(estado) {
  if (!estado) return STAGES[0];
  if (estado.mode === "story") {
    const indiceHistoria = Math.max(0, Math.min(Number(estado.storyIndex) || 0, STAGES.length - 1));
    return STAGES[indiceHistoria];
  }
  const idx = hashCadena(salaActual || estado.mode || "local") % STAGES.length;
  return STAGES[idx];
}

function aplicarEscenario(estado) {
  const arena = document.getElementById("arena");
  const nombreMapa = document.getElementById("nombre-mapa");
  if (!arena || !nombreMapa) return;
  const stage = obtenerEscenarioActual(estado);
  arena.style.backgroundImage = `linear-gradient(180deg, rgba(12, 16, 28, 0.1), rgba(12, 18, 34, 0.1)), url("${stage.archivo}")`;
  nombreMapa.textContent = stage.nombre;
}

// ---------- Estado del servidor ----------
let ultimoEstado = null;
const timersPose = {};
let peleaAnunciada = false;

socket.on("estado", (estado) => {
  const yaEstabaEnBatalla = ultimoEstado && ultimoEstado.started && !ultimoEstado.finished;
  ultimoEstado = estado;
  if (typeof estado.paused === "boolean") juegoPausado = estado.paused;

  if (!estado.started) {
    enBatalla = false; modoActual = estado.mode || modoActual;
    if (estado.mode === "online" && estado.players.length < 2) {
      document.getElementById("estado-espera").textContent = "Esperando rival...";
      document.getElementById("selector-personajes").style.display = "none";
    } else {
      document.getElementById("estado-espera").textContent = "";
      if (document.getElementById("selector-personajes").style.display === "none") sonidos.salaLista();
      document.getElementById("selector-personajes").style.display = "block";
    }
    mostrarPantalla("pantalla-sala"); peleaAnunciada = false; return;
  }

  if (!peleaAnunciada) {
    peleaAnunciada = true;
    sonidos.empezarPelea();
    const yo = estado.players.find((p) => p.id === socket.id);
    if (yo) miX = yo.x;
  }

  aplicarEscenario(estado);
  enBatalla = true;
  document.getElementById("pantalla-batalla").classList.toggle("pausada", !!estado.paused);
  if (estado.paused && !modalConfig.classList.contains("abierto")) {
    modalPausa.classList.add("abierto");
    modalPausa.setAttribute("aria-hidden", "false");
  } else if (!estado.paused) {
    modalPausa.classList.remove("abierto");
    modalPausa.setAttribute("aria-hidden", "true");
  }

  if (estado.finished) {
    juegoPausado = false;
    document.getElementById("pantalla-batalla").classList.remove("pausada");
    modalPausa.classList.remove("abierto");
    enBatalla = false;
    const gane = estado.winner === socket.id;
    document.getElementById("titulo-final").textContent = gane ? "GANASTE" : "Perdiste";
    const yo = estado.players.find((p) => p.id === socket.id);
    const rival = estado.players.find((p) => p.id !== socket.id);
    document.getElementById("marcador-final").textContent = `${yo?.rounds || 0} — ${rival?.rounds || 0}`;
    document.getElementById("estadisticas-final").innerHTML = yo ? `
      <div><strong>${yo.stats.hits}</strong><span>impactos</span></div>
      <div><strong>${yo.stats.maxCombo}</strong><span>combo máximo</span></div>
      <div><strong>${yo.stats.damage}</strong><span>daño causado</span></div>
      <div><strong>${yo.stats.blocks}</strong><span>bloqueos</span></div>` : "";
    const progreso = document.getElementById("progreso-historia");
    const btn = document.getElementById("btn-revancha");
    progreso.textContent = ""; btn.dataset.accion = "revancha"; btn.textContent = "Revancha";
    if (estado.mode === "story") {
      const completado = gane && estado.storyIndex >= estado.storyTotal - 1;
      progreso.textContent = completado ? "¡HISTORIA COMPLETADA! Derrotaste a todos los rivales." : `Rival ${estado.storyIndex + 1} de ${estado.storyTotal}`;
      if (gane && !completado) { btn.dataset.accion = "siguiente"; btn.textContent = "Siguiente rival"; }
    }
    gane ? sonidos.victoria() : sonidos.derrota(); mostrarPantalla("pantalla-final"); return;
  }

  pintarBatalla(estado);
  mostrarPantalla("pantalla-batalla");
});

function setPoseLuchador(el, characterId, pose) {
  const c = CHARACTERS[characterId];
  if (!c) return;
  const src = c.poses[pose] || c.poses.idle;
  const img = el.querySelector("img");
  if (img) {
    if (img.dataset.pose !== pose) {
      img.src = src;
      img.dataset.pose = pose;
    }
  } else {
    el.innerHTML = `<img src="${src}" alt="${c.name}">`;
    el.querySelector("img").dataset.pose = pose;
  }
}

function aplicarEstadoVisual(el, p, esMio) {
  el.classList.toggle("saltando", p.estado === "jump" && p.hp > 0);
  el.classList.toggle("agachado", p.estado === "duck" && p.hp > 0);
  el.classList.toggle("bloqueando", !!p.blocking && p.hp > 0);
  const temporalActivo = Number(el.dataset.poseHasta || 0) > performance.now();
  if (!temporalActivo && p.hp > 0) {
    let pose = "idle";
    if (p.blocking) pose = "block";
    else if (p.estado === "walk" || p.estado === "jump") pose = "walk";
    setPoseLuchador(el, p.character, pose);
  }
  // La posicion de mi propio personaje la controla el bucle local (mas fluida);
  // la del rival se sincroniza directo desde el servidor.
  if (!esMio) el.style.left = p.x + "%";
  else if (Math.abs(miX - p.x) > 5) miX += (p.x - miX) * 0.3;
}

function orientarLuchadores(l1, l2, p1, p2) {
  // Los sprites miran a la derecha de origen; cada luchador sigue al rival.
  l1.classList.toggle("espejo", p1.x > p2.x);
  l2.classList.toggle("espejo", p2.x > p1.x);
}

function pintarBatalla(estado) {
  aplicarEscenario(estado);
  const [p1, p2] = estado.players;
  if (!p1 || !p2) return;

  const hud1 = document.getElementById("hud-jugador1");
  const hud2 = document.getElementById("hud-jugador2");
  hud1.querySelector(".nombre-jugador").textContent = p1.name;
  hud2.querySelector(".nombre-jugador").textContent = p2.name;
  hud1.querySelector(".vida-actual").style.width = `${p1.hp / p1.maxHp * 100}%`;
  hud2.querySelector(".vida-actual").style.width = `${p2.hp / p2.maxHp * 100}%`;
  hud1.querySelector(".nombre-jugador").dataset.rounds = "●".repeat(p1.rounds || 0);
  hud2.querySelector(".nombre-jugador").dataset.rounds = "●".repeat(p2.rounds || 0);
  document.getElementById("ronda-hud").textContent = `RONDA ${estado.round || 1}`;
  document.getElementById("tiempo-hud").textContent = estado.timeLeft ?? 60;

  const l1 = document.getElementById("luchador1");
  const l2 = document.getElementById("luchador2");
  l1.dataset.character = p1.character;
  l2.dataset.character = p2.character;
  orientarLuchadores(l1, l2, p1, p2);

  if (p1.hp <= 0) {
    setPoseLuchador(l1, p1.character, "ko");
    l1.classList.add("ko");
  } else {
    l1.classList.remove("ko");
    const img1 = l1.querySelector("img");
    if (!img1 || img1.dataset.pose === "ko") setPoseLuchador(l1, p1.character, "idle");
  }

  if (p2.hp <= 0) {
    setPoseLuchador(l2, p2.character, "ko");
    l2.classList.add("ko");
  } else {
    l2.classList.remove("ko");
    const img2 = l2.querySelector("img");
    if (!img2 || img2.dataset.pose === "ko") setPoseLuchador(l2, p2.character, "idle");
  }

  aplicarEstadoVisual(l1, p1, miIndex === 0);
  aplicarEstadoVisual(l2, p2, miIndex === 1);
}


function animarAtaque(attackerId, attack) {
  const idsEnOrden = ultimoEstado ? ultimoEstado.players.map((p) => p.id) : [];
  const elementos = [document.getElementById("luchador1"), document.getElementById("luchador2")];
  const poseAtaque = POSE_POR_ATAQUE[attack] || "punch";
  idsEnOrden.forEach((id, i) => {
    if (id !== attackerId) return;
    const el = elementos[i];
    if (!el) return;
    const characterId = el.dataset.character;
    if (!characterId) return;
    clearTimeout(timersPose[el.id + "-atk"]);
    setPoseLuchador(el, characterId, poseAtaque);
    el.dataset.poseHasta = String(performance.now() + 300);
    el.classList.add("atacando", `ataque-${attack}`);
    timersPose[el.id + "-atk"] = setTimeout(() => {
      el.classList.remove("atacando", `ataque-${attack}`);
      if (!el.classList.contains("ko")) setPoseLuchador(el, characterId, "idle");
    }, 280);
  });
}

socket.on("ataque_ejecutado", ({ attackerId, attack }) => {
  // El atacante local ya mostró su animación instantáneamente en lanzarAtaque().
  // Este evento sincroniza la misma animación para el otro jugador (o la IA).
  if (attackerId === socket.id) return;
  animarAtaque(attackerId, attack);
  if (sonidos[attack]) sonidos[attack]();
});

socket.on("golpe", ({ attackerId, targetId, attack, dmg, bloqueado }) => {
  if (bloqueado) setTimeout(() => sonidos.bloqueo(), 60);

  const idsEnOrden = ultimoEstado ? ultimoEstado.players.map((p) => p.id) : [];
  const elementos = [document.getElementById("luchador1"), document.getElementById("luchador2")];
  const poseAtaque = POSE_POR_ATAQUE[attack] || "punch";

  idsEnOrden.forEach((id, i) => {
    const el = elementos[i];
    if (!el) return;
    const characterId = el.dataset.character;
    if (!characterId) return;

    if (id === targetId) {
      clearTimeout(timersPose[el.id + "-hurt"]);
      if (!el.classList.contains("ko") && !bloqueado) {
        setPoseLuchador(el, characterId, "hurt");
        el.dataset.poseHasta = String(performance.now() + 340);
      }
      if (!bloqueado) el.classList.add("golpeado");
      mostrarImpacto(el, bloqueado ? `BLOQUEO · -${dmg}` : `-${dmg}`, bloqueado);
      const arena = document.getElementById("arena");
      if (!bloqueado && arena) {
        arena.classList.remove("sacudida");
        void arena.offsetWidth;
        arena.classList.add("sacudida");
      }
      timersPose[el.id + "-hurt"] = setTimeout(() => {
        el.classList.remove("golpeado");
        if (!el.classList.contains("ko")) setPoseLuchador(el, characterId, "idle");
      }, 320);
    }
  });
});

socket.on("ataque_fallido", ({ reason }) => {
  sonidos.fallo();
  // La animación del ataque ya se mostró. Si está fuera de alcance, simplemente no causa daño.
  if (reason === "esquiva") {
    const el = document.getElementById(miIndex === 0 ? "luchador1" : "luchador2");
    mostrarImpacto(el, "ESQUIVADO", true);
  }
});

socket.on("combo", ({ attackerId, count }) => {
  if (attackerId !== socket.id || count < 2) return;
  const yo = document.getElementById(miIndex === 0 ? "luchador1" : "luchador2");
  mostrarImpacto(yo, `${count} GOLPES`, false);
});

socket.on("fin_ronda", ({ winnerId, round }) => {
  sonidos.ko();
  const anuncio = document.getElementById("anuncio-ronda");
  anuncio.textContent = winnerId === socket.id ? `RONDA ${round} GANADA` : `RONDA ${round} PERDIDA`;
  anuncio.classList.add("visible");
  setTimeout(() => anuncio.classList.remove("visible"), 1900);
});

function mostrarImpacto(luchador, texto, suave = false) {
  const capa = document.getElementById("efectos-combate");
  const arena = document.getElementById("arena");
  if (!capa || !arena || !luchador) return;
  const marca = document.createElement("span");
  marca.className = `impacto${suave ? " suave" : ""}`;
  marca.textContent = texto;
  marca.style.left = luchador.style.left || "50%";
  marca.style.top = "38%";
  capa.appendChild(marca);
  setTimeout(() => marca.remove(), 620);
}

socket.on("rival_desconectado", () => {
  alert("Tu rival se desconectó. Vuelves a la sala.");
  peleaAnunciada = false;
  enBatalla = false;
  if (modoActual === "online") mostrarPantalla("pantalla-sala");
});

// ---------- Revancha ----------
document.getElementById("btn-revancha").addEventListener("click", (e) => {
  peleaAnunciada = false;
  if (e.currentTarget.dataset.accion === "siguiente") socket.emit("siguiente_historia");
  else socket.emit("revancha");
});
