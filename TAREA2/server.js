const express = require('express');
const http = require('http');
const path = require('path');
const crypto = require('crypto');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*' },
  pingInterval: 10000,
  pingTimeout: 20000,
  transports: ['websocket', 'polling']
});

const STATIC_MAX_AGE = process.env.NODE_ENV === 'production' ? '1h' : 0;
app.use(express.static(path.join(__dirname, 'public'), {
  maxAge: STATIC_MAX_AGE,
  etag: true,
  setHeaders(res,filePath){
    if(/\.(html|js|css)$/i.test(filePath)) res.setHeader('Cache-Control','no-store, max-age=0');
  }
}));

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || '0.0.0.0';
const AUTO_PORT_FALLBACK = process.env.AUTO_PORT_FALLBACK ? process.env.AUTO_PORT_FALLBACK === 'true' : process.env.NODE_ENV !== 'production';
const ROUND_SECONDS = 90;
const ROUNDS_TO_WIN = 2;
const X_INICIAL = [30, 70];
const STORY_ORDER = ['coya', 'cuy', 'gallito', 'jaguar', 'oso', 'gato'];
const STAGE_COUNT = 5;
const RECONNECT_GRACE_MS = 60000;
const SPECIAL_COST = 70;
const GUARD_MAX = 100;
const GUARD_REGEN_PER_TICK = 1.5;
const GUARD_BREAK_MS = 1250;
const ATTACK_MIN_GAP = { golpe:115, patada:130, golpe_fuerte:220, patada_fuerte:250, barrido:190, aereo:160, especial:320 };
const AI_LEVELS = {
  // V7: menos presión constante. La IA deja pequeñas ventanas para reposicionarse/defender.
  facil:    { reactionMin:420, reactionMax:680, move:0.62, block:0.09, dodge:0.05, retreat:0.12, dashCooldown:1450, specialChance:0.025, heavyChance:0.10, attackChance:0.52 },
  medio:    { reactionMin:240, reactionMax:390, move:0.82, block:0.18, dodge:0.10, retreat:0.21, dashCooldown:900,  specialChance:0.06,  heavyChance:0.21, attackChance:0.68 },
  avanzado: { reactionMin:145, reactionMax:240, move:0.98, block:0.29, dodge:0.18, retreat:0.28, dashCooldown:650,  specialChance:0.11,  heavyChance:0.33, attackChance:0.80 }
};

const CHARACTERS = {
  coya:    { name:'Coya', hp:155, speed:1.00, power:1.00, defense:1.00, reach:1.0, body:7.0, special:'Filo solar' },
  cuy:     { name:'Cuy', hp:175, speed:0.88, power:0.95, defense:1.13, reach:0.0, body:8.0, special:'Mochila guardiana' },
  gallito: { name:'Gallito de las Rocas', hp:145, speed:1.18, power:1.05, defense:0.93, reach:1.5, body:6.5, special:'Ráfaga escarlata' },
  jaguar:  { name:'Jaguar', hp:160, speed:1.08, power:1.14, defense:0.97, reach:1.5, body:7.5, special:'Zarpazo del sol' },
  oso:     { name:'Oso de Anteojos', hp:195, speed:0.78, power:1.17, defense:1.18, reach:0.5, body:9.0, special:'Guardia de montaña' },
  gato:    { name:'Gato Andino', hp:140, speed:1.28, power:0.94, defense:0.90, reach:2.5, body:6.0, special:'Garra lunar' }
};

const ATTACKS = {
  golpe:         { dmg:5,  startup:20,  active:70,  recovery:55,  range:11.5, knockback:4.0, height:'high', energy:5,  guardDamage:9 },
  golpe_fuerte:  { dmg:10, startup:95,  active:100, recovery:130, range:13.5, knockback:8.5, height:'high', energy:8,  guardDamage:19, heavy:true },
  patada:        { dmg:9,  startup:30,  active:85,  recovery:70,  range:17.0, knockback:6.3, height:'low',  energy:7,  guardDamage:13 },
  patada_fuerte: { dmg:14, startup:115, active:110, recovery:155, range:20.0, knockback:10.5,height:'low', energy:10, guardDamage:23, heavy:true },
  barrido:       { dmg:8,  startup:70,  active:95,  recovery:120, range:16.0, knockback:7.0, height:'low',  energy:6,  guardDamage:17, knockdown:true },
  aereo:         { dmg:7,  startup:40,  active:85,  recovery:90,  range:14.0, knockback:6.0, height:'high', energy:6,  guardDamage:12 }
};

const SPECIALS = {
  coya:    { dmg:16, startup:120, active:115, recovery:180, range:27, knockback:11, height:'all', effect:'solar',    energy:11, guardDamage:28 },
  cuy:     { dmg:13, startup:150, active:125, recovery:190, range:15, knockback:9,  height:'all', effect:'guardian', energy:10, guardDamage:25 },
  gallito: { dmg:15, startup:90,  active:120, recovery:165, range:21, knockback:10, height:'high',effect:'pluma',    energy:11, guardDamage:26 },
  jaguar:  { dmg:19, startup:110, active:105, recovery:180, range:23, knockback:12, height:'all', effect:'zarpazo',  energy:12, guardDamage:30, lunge:6 },
  oso:     { dmg:20, startup:175, active:130, recovery:220, range:18, knockback:15, height:'all', effect:'montana',  energy:12, guardDamage:34, armor:true },
  gato:    { dmg:16, startup:95,  active:110, recovery:165, range:25, knockback:10, height:'all', effect:'lunar',    energy:11, guardDamage:27, lunge:5, evade:true }
};

const COMBOS = [
  { seq:['golpe','golpe','patada'], name:'Trueno Andino', mult:1.08, energy:8, knockback:1 },
  { seq:['golpe','patada','golpe'], name:'Cóndor Ascendente', mult:1.06, energy:6, knockback:2 },
  { seq:['patada','golpe','patada'], name:'Pachamama', mult:1.07, energy:7, knockback:1 },
  { seq:['aereo','golpe','patada'], name:'Cielo Andino', mult:1.10, energy:10, knockback:2 },
  { seq:['barrido','golpe'], name:'Barrido Inca', mult:1.05, energy:5, knockback:1 },
  { seq:['golpe','golpe_fuerte'], name:'Puño del Apu', mult:1.08, energy:7, knockback:2 },
  { seq:['patada','patada_fuerte'], name:'Quiebre Andino', mult:1.08, energy:7, knockback:2 }
];

const rooms = {};
const clamp = (n,min,max) => Math.max(min, Math.min(max,n));
const uid = (prefix='P') => `${prefix}_${crypto.randomBytes(5).toString('hex')}`;
const now = () => Date.now();

function makeRoomCode() {
  let code;
  do code = Math.random().toString(36).slice(2,6).toUpperCase(); while (rooms[code]);
  return code;
}
function stats() { return { hits:0, misses:0, damage:0, blocks:0, dodges:0, maxCombo:0, specials:0, dashes:0 }; }
function newPlayer(name,index,sessionToken,isBot=false) {
  return {
    key: isBot ? sessionToken : uid('P'), sessionToken, socketId:null, connected:!!isBot,
    name, character:null, isBot, hp:100, maxHp:100, energy:0, guard:GUARD_MAX, maxGuard:GUARD_MAX, x:X_INICIAL[index] ?? 50,
    state:'idle', stateUntil:0, blocking:false, blockLevel:null, invulnerableUntil:0, armorUntil:0,
    rounds:0, matchWins:0, lastMoveAt:now(), lastDash:0, lastAttackAt:0, nextAttackAt:0, lastInputSeq:0, nextDecisionAt:0, attackToken:0, attackPhase:null, currentAttack:null, guardBrokenUntil:0, stunUntil:0,
    combo:0, comboAt:0, comboSeq:[], comboSeqAt:0, stats:stats()
  };
}
function newBot(character,index,code) {
  const p = newPlayer(`IA · ${CHARACTERS[character].name}`, index, `BOT_${code}`, true);
  p.key = `BOT_${code}`; p.character = character; p.connected = true;
  return p;
}
function roomPlayerBySocket(room,socketId) {
  return Object.values(room.players).find(p => p.socketId === socketId) || null;
}
function roomSockets(room) {
  return room.order.map(k => room.players[k]?.socketId).filter(Boolean);
}
function publicState(room) {
  return {
    code:room.code, mode:room.mode, hostKey:room.hostKey, started:room.started, finished:room.finished,
    winner:room.winner || null, round:room.round, timeLeft:room.timeLeft, roundActive:room.roundActive,
    paused:room.paused, stageIndex:room.stageIndex, storyIndex:room.storyIndex || 0, storyTotal:STORY_ORDER.length, difficulty:room.difficulty||'medio',
    spectators:room.spectators.size, rematchVotes:[...room.rematchVotes], serverTime:now(),
    players:room.order.map(key => {
      const p=room.players[key];
      return {
        id:p.key, name:p.name, character:p.character, hp:p.hp, maxHp:p.maxHp, energy:p.energy, guard:p.guard, maxGuard:p.maxGuard,
        x:p.x, state:p.state, estado:p.state, blocking:p.blocking, blockLevel:p.blockLevel,
        rounds:p.rounds, matchWins:p.matchWins, stats:p.stats, connected:p.connected, isBot:p.isBot,
        attackPhase:p.attackPhase, currentAttack:p.currentAttack
      };
    })
  };
}
function emitState(room) { io.to(room.code).emit('estado', publicState(room)); }
function emitMovement(room,p,seq=0,stateOverride=p.state) { io.to(room.code).volatile.emit('movimiento_jugador',{playerId:p.key,x:p.x,state:stateOverride,serverTime:now(),seq}); }
function setState(p,state,duration=0) {
  p.state = state;
  p.stateUntil = duration ? now()+duration : 0;
}
function canAct(p) {
  return p.hp>0 && !['ko','knockdown','getup','hurt_high','hurt_low','recoil','defeat','intro','dodge'].includes(p.state);
}
function canMove(p) {
  return p.hp>0 && !['ko','knockdown','getup','hurt_high','hurt_low','recoil','defeat','intro','dodge'].includes(p.state);
}
function attackDef(p,attack) {
  if (attack==='especial') return { ...SPECIALS[p.character], name:'especial', cost:SPECIAL_COST };
  const d=ATTACKS[attack]; return d ? { ...d, name:attack, cost:0 } : null;
}
function resetRoundPlayer(p,index) {
  const cfg=CHARACTERS[p.character];
  p.maxHp=cfg.hp; p.hp=cfg.hp; p.energy=0; p.guard=GUARD_MAX; p.maxGuard=GUARD_MAX; p.x=X_INICIAL[index] ?? 50;
  p.state='idle'; p.stateUntil=0; p.blocking=false; p.blockLevel=null; p.invulnerableUntil=0; p.armorUntil=0;
  p.lastMoveAt=now(); p.lastDash=0; p.lastAttackAt=0; p.nextAttackAt=0; p.lastInputSeq=0; p.guardBrokenUntil=0; p.stunUntil=0; p.nextDecisionAt=0; p.attackToken++; p.attackPhase=null; p.currentAttack=null; p.combo=0; p.comboAt=0; p.comboSeq=[]; p.comboSeqAt=0;
}
function prepareRound(room) {
  room.order.forEach((key,i)=>{ resetRoundPlayer(room.players[key],i); setState(room.players[key],'intro',900); });
  room.timeLeft=ROUND_SECONDS; room.roundActive=false; room.paused=false; room.rematchVotes.clear();
  const roundNumber=room.round;
  setTimeout(()=>{
    if(rooms[room.code]!==room || room.finished || room.round!==roundNumber) return;
    room.order.forEach(key=>{ const p=room.players[key]; if(p.hp>0)setState(p,'idle'); });
    room.roundActive=true; emitState(room);
  },900);
}
function startMatch(room) {
  room.started=true; room.finished=false; room.winner=null; room.round=1; room.rematchVotes.clear();
  room.order.forEach(key=>{ const p=room.players[key]; p.rounds=0; p.stats=stats(); });
  prepareRound(room); emitState(room);
}
function finishRound(room,winnerKey) {
  if (!room.roundActive || room.finished) return;
  room.roundActive=false;
  room.order.forEach(k=>{ const p=room.players[k]; p.blocking=false; p.blockLevel=null; p.attackToken++; if(p.hp>0)setState(p,'idle'); });
  if (winnerKey) room.players[winnerKey].rounds++;
  io.to(room.code).emit('fin_ronda',{winnerId:winnerKey,round:room.round});
  if (winnerKey && room.players[winnerKey].rounds>=ROUNDS_TO_WIN) {
    room.finished=true; room.winner=winnerKey; room.players[winnerKey].matchWins++;
    room.order.forEach(k=>setState(room.players[k],k===winnerKey?'victory':'defeat'));
    emitState(room); return;
  }
  emitState(room);
  const ended=room.round;
  setTimeout(()=>{
    if (rooms[room.code]!==room || room.finished || room.round!==ended) return;
    room.round++; prepareRound(room); emitState(room);
  },2200);
}
function addEnergy(p,amount) { p.energy=clamp(Math.round(p.energy+amount),0,100); }
function postureEvades(def,rival) {
  if (now()<rival.invulnerableUntil || rival.state==='dodge') return true;
  if (def.height==='high' && rival.state==='crouch') return true;
  if (def.height==='low' && rival.state==='jump') return true;
  return false;
}
function blocksAttack(def,rival) {
  if (!rival.blocking || rival.guard<=0 || now()<rival.guardBrokenUntil) return false;
  if (def.height==='all') return true;
  return rival.blockLevel===def.height;
}
function hitboxesOverlap(attacker,rival,def) {
  const ac=CHARACTERS[attacker.character], rc=CHARACTERS[rival.character];
  const dir = rival.x>=attacker.x ? 1 : -1;
  const bodyA=ac.body/2, bodyR=rc.body/2;
  let start=attacker.x + dir*(bodyA*.55);
  let end=attacker.x + dir*(bodyA + def.range + ac.reach);
  if (start>end) [start,end]=[end,start];
  const hurtStart=rival.x-bodyR, hurtEnd=rival.x+bodyR;
  return Math.max(start,hurtStart) <= Math.min(end,hurtEnd);
}
function comboInfo(p,attack) {
  const t=now();
  if (t-p.comboSeqAt>1300) p.comboSeq=[];
  p.comboSeqAt=t; p.comboSeq.push(attack); if(p.comboSeq.length>4)p.comboSeq.shift();
  for (const c of COMBOS) {
    if (p.comboSeq.length>=c.seq.length && p.comboSeq.slice(-c.seq.length).join(',')===c.seq.join(',')) return c;
  }
  return null;
}
function scheduleWhileUnpaused(room,delay,fn) {
  const started=now();
  function tick(remaining) {
    setTimeout(()=>{
      if (rooms[room.code]!==room) return;
      if (room.paused) return tick(remaining);
      fn();
    },remaining);
  }
  tick(delay);
  return started;
}
function resolveHit(room,attackerKey,attack,token) {
  const attacker=room.players[attackerKey];
  if (!attacker || attacker.attackToken!==token || room.finished || !room.roundActive) return;
  const rivalKey=room.order.find(k=>k!==attackerKey); const rival=room.players[rivalKey];
  if (!rival || rival.hp<=0) return;
  const def=attackDef(attacker,attack); if(!def)return;
  attacker.attackPhase='active';
  if (attack==='especial') {
    if (def.lunge) {
      const dir=rival.x>=attacker.x?1:-1; attacker.x=clamp(attacker.x+dir*def.lunge,3,97);
    }
    if (def.evade) attacker.invulnerableUntil=Math.max(attacker.invulnerableUntil,now()+160);
  }
  io.to(room.code).emit('ataque_activo',{attackerId:attackerKey,attack,effect:def.effect||attack});
  if (!hitboxesOverlap(attacker,rival,def)) {
    attacker.combo=0; attacker.stats.misses++;
    io.to(room.code).emit('ataque_fallido',{attackerId:attackerKey,attack,reason:'distancia'});
    emitState(room); return;
  }
  if (postureEvades(def,rival)) {
    attacker.combo=0; attacker.stats.misses++; rival.stats.dodges++;
    io.to(room.code).emit('ataque_fallido',{attackerId:attackerKey,attack,reason:'esquiva'});
    emitState(room); return;
  }
  const blocked=blocksAttack(def,rival);
  const t=now(); attacker.combo=t-attacker.comboAt<=1350?attacker.combo+1:1; attacker.comboAt=t;
  attacker.stats.maxCombo=Math.max(attacker.stats.maxCombo,attacker.combo);
  let combo=comboInfo(attacker,attack);
  if(blocked){attacker.combo=0;attacker.comboSeq=[];combo=null;}
  const ac=CHARACTERS[attacker.character], rc=CHARACTERS[rival.character];
  // Escalado de combo inverso: los primeros golpes pesan más y el spam pierde daño.
  let mult=Math.max(0.72,1-Math.min(attacker.combo-1,5)*0.06); if(combo)mult*=combo.mult;
  let reduction=blocked?0.82:0;
  if (attack==='especial' && attacker.character==='coya') reduction=blocked?0.76:0;
  if (now()<rival.armorUntil) reduction=Math.max(reduction,0.30);
  let dmg=Math.max(1,Math.round(def.dmg*ac.power*mult/rc.defense*(1-reduction)));
  rival.hp=Math.max(0,rival.hp-dmg);
  attacker.stats.hits++; attacker.stats.damage+=dmg; if(attack==='especial')attacker.stats.specials++;
  let guardBroken=false;
  if(blocked){
    rival.stats.blocks++; addEnergy(rival,4);
    rival.guard=Math.max(0,Math.round((rival.guard-(def.guardDamage||10))*10)/10);
    if(rival.guard<=0){
      guardBroken=true; rival.blocking=false; rival.blockLevel=null; rival.guardBrokenUntil=now()+GUARD_BREAK_MS;
      rival.attackToken++; rival.attackPhase=null; rival.currentAttack=null; setState(rival,'recoil',650);
      io.to(room.code).emit('guardia_rota',{playerId:rival.key});
    }
  }
  addEnergy(attacker,def.energy||5); addEnergy(rival,blocked?1:2);
  if(combo){ addEnergy(attacker,combo.energy); io.to(room.code).emit('combo_especial',{attackerId:attackerKey,name:combo.name}); }
  if(attack==='especial') {
    if(attacker.character==='cuy'){ attacker.hp=Math.min(attacker.maxHp,attacker.hp+9); attacker.armorUntil=now()+2400; }
    if(attacker.character==='oso'){ attacker.armorUntil=now()+1800; }
    if(attacker.character==='gallito'){ addEnergy(attacker,6); }
  }
  let knock=def.knockback+(combo?.knockback||0); const dir=rival.x>=attacker.x?1:-1;
  rival.x=clamp(rival.x+dir*(blocked?Math.max(1.4,knock*.38):knock),3,97);
  if(!blocked && now()>=rival.armorUntil){
    rival.attackToken++; rival.attackPhase=null; rival.currentAttack=null;
    // Cada 4 impactos seguidos se aplica un stun breve y un empuje extra para cortar cadenas infinitas.
    const comboStun=attacker.combo>=4 && now()>=rival.stunUntil;
    if(comboStun){
      rival.stunUntil=now()+620; rival.x=clamp(rival.x+dir*3.5,3,97); setState(rival,'recoil',560);
      io.to(room.code).emit('aturdido',{playerId:rival.key,combo:attacker.combo});
      setTimeout(()=>{if(rival.hp>0&&rival.state==='recoil'&&now()>=rival.stunUntil)setState(rival,'idle');},640);
    } else if(def.knockdown || dmg>=18){
      setState(rival,'knockdown',420);
      setTimeout(()=>{ if(rival.hp>0 && rival.state==='knockdown'){ setState(rival,'getup',270); setTimeout(()=>{if(rival.hp>0&&rival.state==='getup')setState(rival,'idle');},290); } },440);
    } else if(def.heavy || dmg>=13) {
      setState(rival,'recoil',290); setTimeout(()=>{ if(rival.hp>0&&rival.state==='recoil')setState(rival,'idle'); },310);
    } else {
      const hurtState=def.height==='low'?'hurt_low':'hurt_high'; setState(rival,hurtState,185); setTimeout(()=>{ if(rival.hp>0&&rival.state===hurtState)setState(rival,'idle'); },205);
    }
  }
  io.to(room.code).emit('golpe',{attackerId:attackerKey,targetId:rivalKey,attack,dmg,bloqueado:blocked,combo:attacker.combo,effect:def.effect||attack});
  if(attacker.combo>=2)io.to(room.code).emit('combo',{attackerId:attackerKey,count:attacker.combo});
  if(rival.hp<=0){ setState(rival,'ko'); finishRound(room,attackerKey); } else emitState(room);
}
function startAttack(room,attackerKey,attack) {
  if(!room || !room.started || room.finished || !room.roundActive || room.paused)return false;
  const p=room.players[attackerKey]; if(!p || !canAct(p) || p.blocking)return false;
  const def=attackDef(p,attack); if(!def)return false;
  const attackNow=now();
  const minGap=ATTACK_MIN_GAP[attack]||120;
  if(attackNow<(p.nextAttackAt||0))return false;
  p.lastAttackAt=attackNow; p.nextAttackAt=attackNow+minGap;
  if(attack==='especial' && p.energy<SPECIAL_COST){ io.to(p.socketId||'').emit('energia_insuficiente',{needed:SPECIAL_COST,current:p.energy}); return false; }
  if(attack==='aereo' && p.state!=='jump') return false;
  if(attack==='barrido' && p.state!=='crouch') return false;
  if(attack==='especial')p.energy-=SPECIAL_COST;
  if(attack==='especial' && def.armor)p.armorUntil=now()+def.startup+def.active;
  const token=++p.attackToken; p.attackPhase=def.startup?'startup':'active'; p.currentAttack=attack;
  setState(p,'attack',Math.max(100,def.startup+def.active+def.recovery));
  io.to(room.code).emit('ataque_iniciado',{attackerId:attackerKey,attack,startup:def.startup,active:def.active,recovery:def.recovery,effect:def.effect||attack});
  scheduleWhileUnpaused(room,def.startup||0,()=>{
    const cur=room.players[attackerKey]; if(!cur || cur.attackToken!==token)return;
    cur.attackPhase='active'; resolveHit(room,attackerKey,attack,token);
    scheduleWhileUnpaused(room,Math.max(60,def.active),()=>{
      const live=room.players[attackerKey]; if(!live || live.attackToken!==token)return;
      live.attackPhase='recovery';
      scheduleWhileUnpaused(room,Math.max(0,def.recovery),()=>{
        const done=room.players[attackerKey]; if(!done || done.attackToken!==token)return;
        done.attackPhase=null; done.currentAttack=null; if(done.hp>0&&done.state==='attack')setState(done,'idle'); emitState(room);
      });
    });
  });
  return true;
}
function createSoloRoom(socket,name,mode,sessionToken,difficulty='medio',stageIndex=0) {
  const code=makeRoomCode(); const storyIndex=0;
  difficulty=AI_LEVELS[difficulty]?difficulty:'medio';
  stageIndex=Number(stageIndex);if(!Number.isInteger(stageIndex)||stageIndex<0||stageIndex>=STAGE_COUNT)stageIndex=0;
  const room={ code, mode, difficulty, players:{}, order:[], spectators:new Set(), hostKey:null, started:false, finished:false, winner:null,
    round:1,timeLeft:ROUND_SECONDS,roundActive:false,paused:false,stageIndex,storyStartStage:stageIndex,storyIndex,
    rematchVotes:new Set(),createdAt:now() };
  const human=newPlayer(name||'Jugador',0,sessionToken||uid('S')); human.socketId=socket.id; human.connected=true;
  room.players[human.key]=human; room.order.push(human.key); room.hostKey=human.key;
  const botChar=mode==='story'?STORY_ORDER[0]:STORY_ORDER[Math.floor(Math.random()*STORY_ORDER.length)];
  const bot=newBot(botChar,1,code); room.players[bot.key]=bot; room.order.push(bot.key); room.botKey=bot.key;
  rooms[code]=room; socket.join(code); return {room,human};
}
function cleanupDisconnected(room,key) {
  setTimeout(()=>{
    if(rooms[room.code]!==room)return; const p=room.players[key];
    if(!p || p.connected)return;
    if(room.mode!=='online'){ delete rooms[room.code]; return; }
    delete room.players[key]; room.order=room.order.filter(k=>k!==key);
    if(room.order.length===0){ delete rooms[room.code]; return; }
    room.started=false; room.finished=false; room.roundActive=false; room.paused=false; emitState(room);
  },RECONNECT_GRACE_MS);
}
function botTick(room) {
  if(!room.botKey || !room.started || room.finished || !room.roundActive || room.paused)return;
  const bot=room.players[room.botKey], human=room.players[room.order.find(k=>k!==room.botKey)];
  if(!bot||!human||!human.connected)return;
  const cfg=AI_LEVELS[room.difficulty]||AI_LEVELS.medio;
  const t=now();
  if(!canAct(bot))return;
  const dist=Math.abs(bot.x-human.x), dir=human.x>bot.x?1:-1;
  const humanThreat=human.currentAttack||human.state==='attack';

  // Movimiento continuo. La dificultad cambia velocidad de persecución y control de distancia.
  const desired=room.difficulty==='avanzado'?19:room.difficulty==='facil'?23:21;
  if(dist>desired && bot.state!=='dodge' && !bot.blocking){
    const base=dist>34?3.45:2.75;
    const step=base*cfg.move*CHARACTERS[bot.character].speed;
    bot.x=clamp(bot.x+dir*step,3,97);
    setState(bot,dist>30?'run':'walk'); emitMovement(room,bot);
  } else if(dist<6.5 && !humanThreat && t>=bot.nextDecisionAt && Math.random()<cfg.retreat){
    bot.x=clamp(bot.x-dir*(2.8+cfg.move),3,97); setState(bot,'walk'); emitMovement(room,bot);
  }

  if(t<bot.nextDecisionAt)return;
  bot.nextDecisionAt=t+cfg.reactionMin+Math.floor(Math.random()*(cfg.reactionMax-cfg.reactionMin+1));

  // Defensa reactiva.
  if(humanThreat && dist<26){
    const defendRoll=Math.random();
    if(defendRoll<cfg.block){
      bot.blocking=true; bot.blockLevel=human.state==='crouch'?'low':'high';
      setState(bot,bot.blockLevel==='low'?'block_low':'block_high'); emitState(room);
      const hold=room.difficulty==='avanzado'?145:room.difficulty==='facil'?270:205;
      setTimeout(()=>{if(!room.paused&&bot.hp>0){bot.blocking=false;bot.blockLevel=null;if(['block_high','block_low'].includes(bot.state))setState(bot,'idle');emitState(room);}},hold);
      return;
    }
    if(defendRoll<cfg.block+cfg.dodge && t-bot.lastDash>cfg.dashCooldown){
      bot.lastDash=t; bot.stats.dashes++; bot.invulnerableUntil=t+145; setState(bot,'dodge',190);
      bot.x=clamp(bot.x-dir*(6.5+cfg.move),3,97);
      io.to(room.code).emit('dash',{playerId:bot.key,direction:-dir}); emitMovement(room,bot);
      setTimeout(()=>{if(bot.hp>0&&bot.state==='dodge'){setState(bot,'idle');emitMovement(room,bot);}},205);
      return;
    }
  }

  // Si sigue lejos, las dificultades altas usan dash para cerrar distancia.
  if(dist>25){
    if(room.difficulty!=='facil' && Math.random()<(.07+cfg.dodge) && t-bot.lastDash>cfg.dashCooldown){
      bot.lastDash=t; bot.stats.dashes++; bot.invulnerableUntil=t+120; setState(bot,'dodge',175);
      bot.x=clamp(bot.x+dir*(6.7+2*cfg.move)*CHARACTERS[bot.character].speed,3,97);
      io.to(room.code).emit('dash',{playerId:bot.key,direction:dir}); emitMovement(room,bot);
      setTimeout(()=>{if(bot.hp>0&&bot.state==='dodge'){setState(bot,'idle');emitMovement(room,bot);}},190);
    }
    return;
  }

  // Ataque: hay pausas deliberadas para que la pelea respire.
  if(Math.random()>cfg.attackChance){ if(Math.random()<0.38){setState(bot,'idle');emitMovement(room,bot);} return; }
  const roll=Math.random();
  if(bot.energy>=SPECIAL_COST && roll<cfg.specialChance) return void startAttack(room,bot.key,'especial');
  if(roll<cfg.specialChance+cfg.heavyChance*.50) return void startAttack(room,bot.key,'patada_fuerte');
  if(roll<cfg.specialChance+cfg.heavyChance) return void startAttack(room,bot.key,'golpe_fuerte');
  if(room.difficulty==='avanzado' && roll>.88){
    setState(bot,'crouch'); emitMovement(room,bot);
    return void setTimeout(()=>{if(room.roundActive&&!room.paused&&bot.state==='crouch')startAttack(room,bot.key,'barrido');},35);
  }
  if(room.difficulty!=='facil' && roll>.78){
    setState(bot,'jump'); emitMovement(room,bot);
    setTimeout(()=>{if(room.roundActive&&!room.paused&&bot.state==='jump')startAttack(room,bot.key,'aereo');},35);
    return void setTimeout(()=>{if(bot.hp>0&&bot.state==='jump'){setState(bot,'idle');emitMovement(room,bot);}},300);
  }
  if(roll>.48) startAttack(room,bot.key,'patada'); else startAttack(room,bot.key,'golpe');
}

setInterval(()=>{
  Object.values(rooms).forEach(room=>{
    if(!room.started||room.finished||!room.roundActive||room.paused)return;
    room.timeLeft=Math.max(0,room.timeLeft-1);
    if(room.timeLeft===0){ const [a,b]=room.order, p1=room.players[a],p2=room.players[b]; const r1=p1.hp/p1.maxHp,r2=p2.hp/p2.maxHp; finishRound(room,r1===r2?null:r1>r2?a:b); }
    else emitState(room);
  });
},1000);
setInterval(()=>Object.values(rooms).forEach(botTick),75);
// Snapshot correctivo de baja frecuencia: evita drift sin saturar la red con estados completos.
setInterval(()=>{Object.values(rooms).forEach(room=>{if(room.started&&!room.finished)emitState(room);});},300);

// Regeneración de guardia. Se pausa mientras el jugador bloquea o está en guard break.
setInterval(()=>{
  Object.values(rooms).forEach(room=>{
    if(!room.started||room.finished||!room.roundActive||room.paused)return;
    room.order.forEach(key=>{
      const p=room.players[key]; if(!p||p.hp<=0)return;
      if(p.guard<=0 && now()>=p.guardBrokenUntil){ p.guard=35; if(p.state==='recoil')setState(p,'idle'); }
      else if(!p.blocking && now()>=p.guardBrokenUntil && p.guard<p.maxGuard){ p.guard=Math.min(p.maxGuard,Math.round((p.guard+GUARD_REGEN_PER_TICK)*10)/10); }
    });
  });
},100);

io.on('connection',socket=>{
  let currentRoom=null, currentPlayerKey=null, spectator=false;
  const bind=(room,p)=>{ currentRoom=room.code; currentPlayerKey=p?.key||null; spectator=!p; socket.join(room.code); };

  socket.on('ping_juego',cb=>{ if(typeof cb==='function')cb({serverTime:now()}); });

  socket.on('crear_solo',({name,mode,sessionToken,difficulty='medio',stageIndex=0}={},cb=()=>{})=>{
    if(!['story','local'].includes(mode))return cb({ok:false,error:'Modo inválido.'});
    const {room,human}=createSoloRoom(socket,name,mode,sessionToken,difficulty,stageIndex); bind(room,human);
    cb({ok:true,code:room.code,mode,playerKey:human.key,sessionToken:human.sessionToken}); emitState(room);
  });

  socket.on('crear_sala',({name,sessionToken,stageIndex=0}={},cb=()=>{})=>{
    const code=makeRoomCode();
    stageIndex=Number(stageIndex);if(!Number.isInteger(stageIndex)||stageIndex<0||stageIndex>=STAGE_COUNT)stageIndex=0;
    const room={code,mode:'online',players:{},order:[],spectators:new Set(),hostKey:null,started:false,finished:false,winner:null,round:1,timeLeft:ROUND_SECONDS,roundActive:false,paused:false,stageIndex,storyIndex:0,rematchVotes:new Set(),createdAt:now()};
    const p=newPlayer(name||'Jugador 1',0,sessionToken||uid('S')); p.socketId=socket.id;p.connected=true;
    room.players[p.key]=p; room.order.push(p.key); room.hostKey=p.key; rooms[code]=room; bind(room,p);
    cb({ok:true,code,playerKey:p.key,sessionToken:p.sessionToken}); emitState(room);
  });

  socket.on('unirse_sala',({name,code,sessionToken}={},cb=()=>{})=>{
    code=String(code||'').toUpperCase(); const room=rooms[code];
    if(!room)return cb({ok:false,error:'Esa sala no existe.'}); if(room.mode!=='online')return cb({ok:false,error:'Esa sala no es multijugador.'});
    if(room.order.length>=2)return cb({ok:false,error:'La sala ya está llena.'});
    const p=newPlayer(name||'Jugador 2',1,sessionToken||uid('S'));p.socketId=socket.id;p.connected=true; room.players[p.key]=p;room.order.push(p.key);bind(room,p);
    cb({ok:true,code,playerKey:p.key,sessionToken:p.sessionToken});emitState(room);
  });

  socket.on('unirse_espectador',({code}={},cb=()=>{})=>{
    code=String(code||'').toUpperCase(); const room=rooms[code]; if(!room)return cb({ok:false,error:'Esa sala no existe.'});
    room.spectators.add(socket.id); bind(room,null); cb({ok:true,code}); emitState(room);
  });

  socket.on('reconectar_sala',({code,sessionToken}={},cb=()=>{})=>{
    code=String(code||'').toUpperCase(); const room=rooms[code]; if(!room)return cb({ok:false});
    const p=Object.values(room.players).find(x=>!x.isBot && x.sessionToken===sessionToken); if(!p)return cb({ok:false});
    p.socketId=socket.id;p.connected=true;p.lastMoveAt=now();bind(room,p);
    if(room.order.every(k=>room.players[k].isBot||room.players[k].connected))room.paused=false;
    cb({ok:true,code,playerKey:p.key,mode:room.mode}); io.to(room.code).emit('rival_reconectado',{playerId:p.key}); emitState(room);
  });

  socket.on('elegir_personaje',({character}={})=>{
    const room=rooms[currentRoom],p=room?.players[currentPlayerKey]; if(!room||!p||!CHARACTERS[character]||room.started)return;
    p.character=character;p.maxHp=CHARACTERS[character].hp;p.hp=p.maxHp; emitState(room);
    if(room.order.length===2&&room.order.every(k=>room.players[k].character))startMatch(room);
  });

  socket.on('elegir_mapa',({stageIndex}={})=>{
    const room=rooms[currentRoom]; if(!room||room.mode!=='online'||room.started||currentPlayerKey!==room.hostKey)return;
    const idx=Number(stageIndex);if(!Number.isInteger(idx)||idx<0||idx>=STAGE_COUNT)return;room.stageIndex=idx;emitState(room);
  });

  socket.on('mover',({x,estado,seq=0}={})=>{
    const room=rooms[currentRoom],p=room?.players[currentPlayerKey]; if(!room||!p||room.paused||!room.roundActive||room.finished||!canMove(p))return;
    seq=Number(seq)||0;if(seq&&seq<=p.lastInputSeq)return;if(seq)p.lastInputSeq=seq;
    const t=now(),elapsed=clamp(t-p.lastMoveAt,0,100),run=estado==='run'; const maxDelta=Math.max(2.2,elapsed*.13*CHARACTERS[p.character].speed*(run?1.35:1));
    if(typeof x==='number')p.x+=clamp(clamp(x,3,97)-p.x,-maxDelta,maxDelta);
    if(['idle','walk','run','jump','crouch'].includes(estado)&&p.state!=='attack')setState(p,estado);p.lastMoveAt=t;emitMovement(room,p,seq,estado);
  });

  socket.on('dash',({direction,seq=0}={})=>{
    const room=rooms[currentRoom],p=room?.players[currentPlayerKey];if(!room||!p||room.paused||!room.roundActive||!canAct(p))return;
    const t=now();if(t-p.lastDash<180)return;const dir=direction<0?-1:1;p.lastDash=t;p.stats.dashes++;p.blocking=false;p.blockLevel=null;p.invulnerableUntil=t+150;setState(p,'dodge',220);
    p.x=clamp(p.x+dir*9.5*CHARACTERS[p.character].speed,3,97);io.to(room.code).emit('dash',{playerId:p.key,direction:dir});emitMovement(room,p,Number(seq)||0);
    setTimeout(()=>{if(p.hp>0&&p.state==='dodge'){setState(p,'idle');emitMovement(room,p,Number(seq)||0);}},235);
  });

  socket.on('bloquear',({activo,nivel}={})=>{
    const room=rooms[currentRoom],p=room?.players[currentPlayerKey];if(!room||!p||room.paused||!room.roundActive||room.finished)return;
    if(activo){if(!canAct(p)||p.guard<=0||now()<p.guardBrokenUntil)return;p.blocking=true;p.blockLevel=nivel==='low'?'low':'high';setState(p,p.blockLevel==='low'?'block_low':'block_high');p.combo=0;}
    else{p.blocking=false;p.blockLevel=null;if(p.hp>0&&['block_high','block_low'].includes(p.state))setState(p,'idle');}
    emitState(room);
  });

  socket.on('atacar',({attack}={})=>{const room=rooms[currentRoom];if(!room||spectator)return;startAttack(room,currentPlayerKey,attack);});

  socket.on('pausar',({activo}={})=>{
    const room=rooms[currentRoom];if(!room||!room.started||room.finished||spectator)return;room.paused=!!activo;
    room.order.forEach(k=>{const p=room.players[k];p.blocking=false;p.blockLevel=null;p.lastMoveAt=now();});emitState(room);
  });

  socket.on('solicitar_revancha',()=>{
    const room=rooms[currentRoom];if(!room||!room.finished||spectator)return;
    if(room.mode!=='online'){startMatch(room);return;}
    room.rematchVotes.add(currentPlayerKey);emitState(room);
    if(room.order.every(k=>room.rematchVotes.has(k))){ room.rematchVotes.clear();startMatch(room); }
  });

  socket.on('siguiente_historia',()=>{
    const room=rooms[currentRoom];if(!room||room.mode!=='story'||!room.finished||room.winner!==currentPlayerKey)return;
    if(room.storyIndex>=STORY_ORDER.length-1)return;room.storyIndex++;room.stageIndex=((room.storyStartStage||0)+room.storyIndex)%STAGE_COUNT;
    const bot=room.players[room.botKey];bot.character=STORY_ORDER[room.storyIndex];bot.name=`IA · ${CHARACTERS[bot.character].name}`;startMatch(room);
  });

  socket.on('salir_sala',()=>{
    const room=rooms[currentRoom];if(!room)return;
    if(spectator){room.spectators.delete(socket.id);socket.leave(room.code);currentRoom=null;spectator=false;emitState(room);return;}
    const p=room.players[currentPlayerKey];if(p){delete room.players[currentPlayerKey];room.order=room.order.filter(k=>k!==currentPlayerKey);}
    socket.leave(room.code);if(room.mode!=='online'||room.order.length===0)delete rooms[room.code];else{room.started=false;room.finished=false;room.roundActive=false;room.paused=false;emitState(room);}currentRoom=null;currentPlayerKey=null;
  });

  socket.on('disconnect',()=>{
    const room=rooms[currentRoom];if(!room)return;
    if(spectator){room.spectators.delete(socket.id);emitState(room);return;}
    const p=room.players[currentPlayerKey];if(!p)return;p.connected=false;p.socketId=null;room.paused=true;
    io.to(room.code).emit('rival_desconectado',{playerId:p.key,graceMs:RECONNECT_GRACE_MS});emitState(room);cleanupDisconnected(room,p.key);
  });
});

app.get('/healthz',(req,res)=>res.status(200).json({ok:true,app:'andes-maqanakuy',version:'menu-mapas-v8'}));
app.get('/personajes',(req,res)=>res.json(CHARACTERS));

function startServer(port){server.listen(port,HOST,()=>{server._listeningPort=port;console.log(`Servidor de Andes Maqanakuy corriendo en http://${HOST}:${port}`);});}
server.on('error',error=>{
  if(error.code==='EADDRINUSE'&&AUTO_PORT_FALLBACK){const next=Number(server._listeningPort||PORT)+1;console.warn(`Puerto ocupado. Probando ${next}...`);server._listeningPort=next;return setTimeout(()=>startServer(next),150);}
  throw error;
});
function shutdown(signal){console.log(`${signal}: cerrando...`);io.close(()=>server.close(()=>process.exit(0)));setTimeout(()=>process.exit(1),5000).unref();}
process.on('SIGTERM',()=>shutdown('SIGTERM'));process.on('SIGINT',()=>shutdown('SIGINT'));
server._listeningPort=PORT;startServer(PORT);
