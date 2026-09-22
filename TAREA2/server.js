const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });
app.use(express.static(path.join(__dirname, "public")));

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || "0.0.0.0";
const AUTO_PORT_FALLBACK = process.env.AUTO_PORT_FALLBACK ? process.env.AUTO_PORT_FALLBACK === "true" : process.env.NODE_ENV !== "production";
const ROUND_SECONDS = 75;
const ROUNDS_TO_WIN = 2;
const X_INICIAL = [32, 68];
const BLOQUEO_REDUCCION = 0.75;
const STORY_ORDER = ["coya", "cuy", "gallito", "jaguar", "oso", "gato"];

const CHARACTERS = {
  coya: { name: "Coya", hp: 100, speed: 1, power: 1, defense: 1, reach: 1, special: "Filo solar" },
  cuy: { name: "Cuy", hp: 115, speed: 0.86, power: 0.94, defense: 1.12, reach: 0, special: "Mochila guardiana" },
  gallito: { name: "Gallito de las Rocas", hp: 92, speed: 1.16, power: 1.06, defense: 0.92, reach: 2, special: "Puños de acero" },
  jaguar: { name: "Jaguar", hp: 102, speed: 1.08, power: 1.13, defense: 0.96, reach: 2, special: "Zarpazo del sol" },
  oso: { name: "Oso de Anteojos", hp: 128, speed: 0.76, power: 1.16, defense: 1.18, reach: 1, special: "Guardia de montaña" },
  gato: { name: "Gato Andino", hp: 88, speed: 1.25, power: 0.92, defense: 0.88, reach: 4, special: "Garra lunar" }
};
const ATTACKS = {
  golpe: { dmg: 8, cooldown: 420, range: 17, knockback: 3.5, height: "high" },
  patada: { dmg: 14, cooldown: 850, range: 22, knockback: 6.5, height: "low" },
  especial: { dmg: 24, cooldown: 2500, range: 26, knockback: 10.5, height: "all" }
};

const rooms = {};
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
function makeRoomCode() { let code; do code = Math.random().toString(36).substring(2, 6).toUpperCase(); while (rooms[code]); return code; }
function nuevasEstadisticas() { return { hits: 0, misses: 0, damage: 0, blocks: 0, maxCombo: 0 }; }
function nuevoJugador(name, index) { return { name, character: null, hp:100, maxHp:100, lastAttack:{}, x:X_INICIAL[index]??50, estado:"idle", blocking:false, rounds:0, combo:0, comboAt:0, lastMoveAt:Date.now(), stats:nuevasEstadisticas() }; }
function nuevoBot(character, index=1) { const p = nuevoJugador(`IA · ${CHARACTERS[character].name}`, index); p.character=character; p.maxHp=CHARACTERS[character].hp; p.hp=p.maxHp; p.isBot=true; return p; }
function publicState(room) { return { players: room.order.map(id => { const p=room.players[id]; return { id, name:p.name, character:p.character, hp:p.hp, maxHp:p.maxHp, x:p.x, estado:p.estado, blocking:p.blocking, rounds:p.rounds, stats:p.stats, isBot:!!p.isBot }; }), started:room.started, finished:room.finished, winner:room.winner||null, round:room.round, timeLeft:room.timeLeft, roundActive:room.roundActive, mode:room.mode||"online", storyIndex:room.storyIndex||0, storyTotal:STORY_ORDER.length, paused:!!room.paused } }
function emitirEstado(code, room) { io.to(code).emit("estado", publicState(room)); }
function prepararRonda(room) { room.order.forEach((id,i)=>{ const p=room.players[id], cfg=CHARACTERS[p.character]; p.maxHp=cfg.hp; p.hp=cfg.hp; p.lastAttack={}; p.x=X_INICIAL[i]??50; p.estado="idle"; p.blocking=false; p.combo=0; p.comboAt=0; p.lastMoveAt=Date.now(); }); room.timeLeft=ROUND_SECONDS; room.roundActive=true; room.paused=false; }
function iniciarPartida(room) { room.started=true; room.finished=false; room.winner=null; room.paused=false; room.round=1; room.order.forEach(id=>{ room.players[id].rounds=0; room.players[id].stats=nuevasEstadisticas(); }); prepararRonda(room); }
function finalizarRonda(code, room, winnerId) { if (!room.roundActive || room.finished) return; room.roundActive=false; room.order.forEach(id=>{ room.players[id].blocking=false; room.players[id].estado="idle"; }); if(winnerId) room.players[winnerId].rounds++; io.to(code).emit("fin_ronda", {winnerId,round:room.round}); if(winnerId && room.players[winnerId].rounds>=ROUNDS_TO_WIN){ room.finished=true; room.winner=winnerId; emitirEstado(code,room); return; } emitirEstado(code,room); const r=room.round; setTimeout(()=>{ if(rooms[code]!==room || room.finished || room.round!==r) return; room.round++; prepararRonda(room); emitirEstado(code,room); },2200); }

function ejecutarAtaque(code, room, attackerId, attack, socketFallido=null) {
  if(!room || !room.started || room.finished || !room.roundActive || room.paused) return;
  const attacker=room.players[attackerId], def=ATTACKS[attack]; if(!attacker||!def||attacker.blocking) return;
  const now=Date.now(), last=attacker.lastAttack[attack]||0; if(now-last<def.cooldown) return; attacker.lastAttack[attack]=now;
  const rivalId=room.order.find(id=>id!==attackerId), rival=room.players[rivalId]; if(!rival) return;
  const cfg=CHARACTERS[attacker.character], rivalCfg=CHARACTERS[rival.character], distancia=Math.abs(attacker.x-rival.x);
  // La animación del ataque se emite siempre que el cooldown permite ejecutar la acción.
  io.to(code).emit("ataque_ejecutado", { attackerId, attack });
  // El jugador puede ejecutar y ver la animación del ataque desde cualquier posición,
  // pero el daño solo se aplica si el rival está dentro del alcance real del ataque.
  const alcanceReal = def.range + cfg.reach;
  const fueraDeAlcance = distancia > alcanceReal;
  const esquivado=(def.height==="high"&&rival.estado==="duck")||(def.height==="low"&&rival.estado==="jump");

  // IMPORTANTE: ejecutar un ataque y acertar un ataque son cosas distintas.
  // La animación ya fue enviada arriba. Aquí SOLO se decide si corresponde daño.
  if (fueraDeAlcance) {
    attacker.combo=0;
    attacker.stats.misses++;
    if(socketFallido) socketFallido.emit("ataque_fallido",{attack,distancia,alcance:alcanceReal,reason:"distancia"});
    emitirEstado(code,room);
    return;
  }

  // Si estaba dentro del alcance pero el rival usó la postura correcta, no hay daño
  // y el atacante recibe el aviso visual ESQUIVADO.
  if (esquivado) {
    attacker.combo=0;
    attacker.stats.misses++;
    if(socketFallido) socketFallido.emit("ataque_fallido",{attack,distancia,alcance:alcanceReal,reason:"esquiva"});
    emitirEstado(code,room);
    return;
  }
  attacker.combo=now-attacker.comboAt<=1350?attacker.combo+1:1; attacker.comboAt=now; attacker.stats.maxCombo=Math.max(attacker.stats.maxCombo,attacker.combo);
  const comboBonus=1+Math.min(attacker.combo-1,3)*.08, bloqueado=!!rival.blocking; let reduccion=BLOQUEO_REDUCCION; if(attack==="especial"&&attacker.character==="coya") reduccion=.48;
  const poderEspecial=attack==="especial"&&attacker.character==="jaguar"?1.2:1; const base=def.dmg*cfg.power*poderEspecial*comboBonus/rivalCfg.defense; const dmg=Math.max(1,Math.round(base*(bloqueado?1-reduccion:1))); rival.hp=Math.max(0,rival.hp-dmg);
  if(attack==="especial"&&attacker.character==="cuy"&&!bloqueado) attacker.hp=Math.min(attacker.maxHp,attacker.hp+6);
  attacker.stats.hits++; attacker.stats.damage+=dmg; if(bloqueado) rival.stats.blocks++;
  const dir=rival.x>=attacker.x?1:-1; let knockback=def.knockback; if(attack==="especial"&&attacker.character==="oso") knockback+=5; if(attack==="especial"&&attacker.character==="gato") knockback+=2; rival.x=clamp(rival.x+dir*(bloqueado?Math.max(1,knockback*.35):knockback),3,97);
  io.to(code).emit("golpe",{attackerId,targetId:rivalId,attack,dmg,bloqueado}); if(attacker.combo>=2) io.to(code).emit("combo",{attackerId,count:attacker.combo}); if(rival.hp<=0) finalizarRonda(code,room,attackerId); else emitirEstado(code,room);
}

function crearSalaSolo(socket, name, mode) {
  const code=makeRoomCode(), storyIndex=0; let botChar;
  if(mode==="story") botChar=STORY_ORDER[storyIndex]; else botChar=STORY_ORDER[Math.floor(Math.random()*STORY_ORDER.length)];
  rooms[code]={ players:{}, order:[], started:false, finished:false, roundActive:false, round:1, timeLeft:ROUND_SECONDS, winner:null, mode, storyIndex, paused:false };
  rooms[code].players[socket.id]=nuevoJugador(name||"Jugador",0); rooms[code].order.push(socket.id);
  const botId=`BOT_${code}`; rooms[code].players[botId]=nuevoBot(botChar,1); rooms[code].order.push(botId); rooms[code].botId=botId;
  socket.join(code); return code;
}

setInterval(()=>{ Object.entries(rooms).forEach(([code,room])=>{ if(!room.started||room.finished||!room.roundActive||room.paused)return; room.timeLeft=Math.max(0,room.timeLeft-1); if(room.timeLeft===0){ const [a,b]=room.order,p1=room.players[a],p2=room.players[b],r1=p1.hp/p1.maxHp,r2=p2.hp/p2.maxHp; finalizarRonda(code,room,r1===r2?null:r1>r2?a:b); } else emitirEstado(code,room); }); },1000);

setInterval(()=>{ Object.entries(rooms).forEach(([code,room])=>{ if(!room.botId||!room.started||room.finished||!room.roundActive||room.paused)return; const bot=room.players[room.botId], humanId=room.order.find(id=>id!==room.botId), human=room.players[humanId]; if(!bot||!human)return; const dist=Math.abs(bot.x-human.x), dir=human.x>bot.x?1:-1; bot.blocking=false;
    if(dist>19){ bot.x=clamp(bot.x+dir*(2.65*CHARACTERS[bot.character].speed),3,97); bot.estado="walk"; }
    else { bot.estado="idle"; const roll=Math.random(); if(roll<.18){ bot.blocking=true; setTimeout(()=>{ if(room.players[room.botId]) room.players[room.botId].blocking=false; },350); } else { const attack=roll>.80?"especial":roll>.46?"patada":"golpe"; ejecutarAtaque(code,room,room.botId,attack); } }
    emitirEstado(code,room);
  }); },360);

io.on("connection", socket=>{
  let currentRoom=null;
  socket.on("crear_solo",({name,mode},cb)=>{ if(!["story","local"].includes(mode)) return cb({ok:false,error:"Modo inválido."}); currentRoom=crearSalaSolo(socket,name,mode); cb({ok:true,code:currentRoom,mode}); emitirEstado(currentRoom,rooms[currentRoom]); });
  socket.on("crear_sala",({name},cb)=>{ const code=makeRoomCode(); rooms[code]={players:{},order:[],started:false,finished:false,roundActive:false,round:1,timeLeft:ROUND_SECONDS,winner:null,mode:"online",paused:false}; rooms[code].players[socket.id]=nuevoJugador(name||"Jugador 1",0); rooms[code].order.push(socket.id); currentRoom=code; socket.join(code); cb({ok:true,code}); emitirEstado(code,rooms[code]); });
  socket.on("unirse_sala",({name,code},cb)=>{ const room=rooms[code]; if(!room)return cb({ok:false,error:"Esa sala no existe."}); if(room.mode!=="online")return cb({ok:false,error:"Esa sala no es multijugador."}); if(room.order.length>=2)return cb({ok:false,error:"La sala ya está llena."}); room.players[socket.id]=nuevoJugador(name||"Jugador 2",1); room.order.push(socket.id); currentRoom=code; socket.join(code); cb({ok:true,code}); emitirEstado(code,room); });
  socket.on("elegir_personaje",({character})=>{ const room=rooms[currentRoom]; if(!room||!room.players[socket.id]||!CHARACTERS[character])return; const p=room.players[socket.id]; p.character=character; p.maxHp=CHARACTERS[character].hp; p.hp=p.maxHp; const all=room.order.length===2&&room.order.every(id=>room.players[id].character); if(all&&!room.started) iniciarPartida(room); emitirEstado(currentRoom,room); });
  socket.on("mover",({x,estado})=>{ const room=rooms[currentRoom]; if(!room||!room.started||room.finished||!room.roundActive||room.paused)return; const p=room.players[socket.id]; if(!p)return; const now=Date.now(),elapsed=clamp(now-p.lastMoveAt,0,120),maxDelta=Math.max(1.55,elapsed*.085*CHARACTERS[p.character].speed); if(typeof x==="number")p.x+=clamp(clamp(x,3,97)-p.x,-maxDelta,maxDelta); if(["idle","walk","jump","duck"].includes(estado))p.estado=estado; p.lastMoveAt=now; emitirEstado(currentRoom,room); });
  socket.on("bloquear",({activo})=>{ const room=rooms[currentRoom]; if(!room||!room.started||room.finished||!room.roundActive||room.paused)return; const p=room.players[socket.id]; if(!p)return; p.blocking=!!activo; if(p.blocking)p.combo=0; emitirEstado(currentRoom,room); });
  socket.on("pausar",({activo})=>{ const room=rooms[currentRoom]; if(!room||!room.started||room.finished)return; room.paused=!!activo; room.order.forEach(id=>{ if(room.players[id]){ room.players[id].blocking=false; room.players[id].estado="idle"; room.players[id].lastMoveAt=Date.now(); } }); emitirEstado(currentRoom,room); });
  socket.on("atacar",({attack})=>ejecutarAtaque(currentRoom,rooms[currentRoom],socket.id,attack,socket));
  socket.on("revancha",()=>{ const room=rooms[currentRoom]; if(!room||room.order.length!==2||!room.order.every(id=>room.players[id].character))return; iniciarPartida(room); emitirEstado(currentRoom,room); });
  socket.on("siguiente_historia",()=>{ const room=rooms[currentRoom]; if(!room||room.mode!=="story"||!room.finished||room.winner!==socket.id)return; if(room.storyIndex>=STORY_ORDER.length-1)return; room.storyIndex++; const bot=room.players[room.botId]; bot.character=STORY_ORDER[room.storyIndex]; bot.name=`IA · ${CHARACTERS[bot.character].name}`; bot.maxHp=CHARACTERS[bot.character].hp; bot.hp=bot.maxHp; iniciarPartida(room); emitirEstado(currentRoom,room); });
  socket.on("salir_sala",()=>{ if(!currentRoom||!rooms[currentRoom])return; const room=rooms[currentRoom]; delete room.players[socket.id]; room.order=room.order.filter(id=>id!==socket.id); if(room.mode!=="online"||room.order.length===0)delete rooms[currentRoom]; else {room.started=false;room.finished=false;room.roundActive=false;room.paused=false;io.to(currentRoom).emit("rival_desconectado");emitirEstado(currentRoom,room);} socket.leave(currentRoom); currentRoom=null; });
  socket.on("disconnect",()=>{ if(!currentRoom||!rooms[currentRoom])return; const room=rooms[currentRoom]; delete room.players[socket.id]; room.order=room.order.filter(id=>id!==socket.id); if(room.mode!=="online"||room.order.length===0)delete rooms[currentRoom]; else {room.started=false;room.finished=false;room.roundActive=false;room.paused=false;io.to(currentRoom).emit("rival_desconectado");emitirEstado(currentRoom,room);} });
});

app.get("/healthz", (req, res) => res.status(200).json({ ok: true, app: "andes-maqanakuy", version: "aws-rango-v2" }));
app.get("/personajes",(req,res)=>res.json(CHARACTERS));

function iniciarServidor(puerto) {
  server.listen(puerto, HOST, () => {
    server._listeningPort = puerto;
    console.log(`Servidor de Andes Maqanakuy corriendo en http://${HOST}:${puerto}`);
  });
}

server.on("error", (error) => {
  if (error.code === "EADDRINUSE" && AUTO_PORT_FALLBACK) {
    const actual = Number(server._listeningPort || PORT);
    const siguiente = actual + 1;
    console.warn(`El puerto ${actual} está en uso. Probando con ${siguiente}...`);
    server._listeningPort = siguiente;
    setTimeout(() => iniciarServidor(siguiente), 150);
    return;
  }
  if (error.code === "EADDRINUSE") {
    console.error(`El puerto ${server._listeningPort || PORT} está ocupado. En producción define un PORT libre.`);
  }
  throw error;
});

function apagar(signal) {
  console.log(`${signal}: cerrando Andes Maqanakuy...`);
  io.close(() => {
    server.close(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 5000).unref();
}
process.on("SIGTERM", () => apagar("SIGTERM"));
process.on("SIGINT", () => apagar("SIGINT"));

server._listeningPort = PORT;
iniciarServidor(PORT);
