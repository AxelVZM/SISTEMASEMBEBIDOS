const socket = io({ transports: ['websocket', 'polling'], upgrade:true, rememberUpgrade:true, reconnection:true, reconnectionAttempts:Infinity, reconnectionDelay:250, reconnectionDelayMax:1000, timeout:5000 });

const CHARACTERS = {
  coya:    { name:'Coya', estilo:'Equilibrada · Filo solar', icon:'img/coya_idle.png', sheet:'spritesheets/coya.png' },
  cuy:     { name:'Cuy', estilo:'Resistente · Mochila guardiana', icon:'img/cuy_idle.png', sheet:'spritesheets/cuy.png' },
  gallito: { name:'Gallito de las Rocas', estilo:'Rápido · Ráfaga escarlata', icon:'img/gallito_idle.png', sheet:'spritesheets/gallito.png' },
  jaguar:  { name:'Jaguar', estilo:'Poderoso · Zarpazo del sol', icon:'img/jaguar_idle.png', sheet:'spritesheets/jaguar.png' },
  oso:     { name:'Oso de Anteojos', estilo:'Tanque · Guardia de montaña', icon:'img/oso_idle.png', sheet:'spritesheets/oso.png' },
  gato:    { name:'Gato Andino', estilo:'Muy veloz · Garra lunar', icon:'img/gato_idle.png', sheet:'spritesheets/gato.png' }
};
const STAGES = [
  { nombre:'Machu Picchu', archivo:'/assets/mapas-cusco/machu-picchu.png' },
  { nombre:'Sacsayhuamán', archivo:'/assets/mapas-cusco/sacsayhuaman.png' },
  { nombre:'Qorikancha', archivo:'/assets/mapas-cusco/qorikancha.png' },
  { nombre:'Plaza de Armas', archivo:'/assets/mapas-cusco/plaza-de-armas.png' },
  { nombre:'Ollantaytambo', archivo:'/assets/mapas-cusco/ollantaytambo.png' }
];
const SPRITE_STATES = { idle:0, walk:1, run:2, jump:3, crouch:4, block_high:5, block_low:6, punch_light:7, punch_heavy:8, kick_light:9, kick_heavy:10, special:11, hurt_high:12, hurt_low:13, recoil:14, dodge:15, knockdown:16, getup:17, ko:18, victory:19, defeat:20, intro:21 };
const STATE_DUR = { idle:560, walk:280, run:220, jump:330, crouch:300, block_high:280, block_low:280, punch_light:170, punch_heavy:250, kick_light:210, kick_heavy:290, special:360, hurt_high:180, hurt_low:180, recoil:220, dodge:190, knockdown:330, getup:240, ko:720, victory:760, defeat:720, intro:650 };
const SPRITE_SCALE = { coya:{__base:.961}, cuy:{__base:1.094}, gallito:{__base:.959}, jaguar:{__base:.983}, oso:{__base:1.438}, gato:{__base:1.117} };
const COOLDOWNS = { golpe:115, golpe_fuerte:220, patada:130, patada_fuerte:250, barrido:190, aereo:160, especial:320 };
const SPECIAL_COST = 70;
const MENU_TRACK = { id:'khGumqLho7w', nombre:'Tema del menú' };
const STAGE_TRACKS = [
  { id:'b6bRGRKFkXA', nombre:'Tema de Machu Picchu' },
  { id:'9om8qOn4DlQ', nombre:'Tema de Sacsayhuamán' },
  { id:'lwk_8sRlJPY', nombre:'Tema de Qorikancha' },
  { id:'kc03xmkjzxM', nombre:'Tema de Plaza de Armas' },
  { id:'9om8qOn4DlQ', nombre:'Tema de Ollantaytambo' }
];
STAGES.forEach(s=>{const i=new Image();i.src=s.archivo;});
Object.values(CHARACTERS).forEach(c=>{const i=new Image();i.src=c.sheet;});

const $ = (id)=>document.getElementById(id);
let miPlayerKey=null, salaActual=null, modoActual=null, miIndex=-1, espectador=false, ultimoEstado=null;
let enBatalla=false, juegoPausado=false, configAbiertaDesdePausa=false, peleaAnunciada=false;
let miX=30, saltando=false, localBusyUntil=0, ultimoFrame=performance.now(), ultimoEnvioMov=0;
let movementSeq=0, pingActual=0;
const holdAttackTimers={};
let localNextAttackAt=0;
const motion=new Map();
let pistaActualId=null, pistaActualNombre='';
let musicaSilenciada=localStorage.getItem('maqanakuy-musica')==='off';
let sfxActivos=localStorage.getItem('maqanakuy-sfx')!=='off';
let fxActivos=localStorage.getItem('maqanakuy-fx')!=='off';
let sessionToken=localStorage.getItem('maqanakuy-session') || (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
localStorage.setItem('maqanakuy-session',sessionToken);
const nombreGuardado=localStorage.getItem('maqanakuy-nombre')||'';
$('input-nombre').value=nombreGuardado;
const dificultadGuardada=localStorage.getItem('maqanakuy-dificultad')||'medio';
let mapaMenuSeleccionado=Math.max(0,Math.min(STAGES.length-1,Number(localStorage.getItem('maqanakuy-mapa'))||0));
if($('select-dificultad'))$('select-dificultad').value=dificultadGuardada;
$('select-dificultad')?.addEventListener('change',e=>localStorage.setItem('maqanakuy-dificultad',e.target.value));

function renderMapasMenu(){
  const lista=$('menu-lista-mapas');if(!lista)return;
  lista.innerHTML='';
  STAGES.forEach((stage,i)=>{
    const b=document.createElement('button');b.type='button';b.className='mapa-menu-opcion';b.dataset.index=i;
    b.innerHTML=`<img src="${stage.archivo}" alt="${stage.nombre}"><span>${stage.nombre}</span><i>✓</i>`;
    b.onclick=()=>{mapaMenuSeleccionado=i;localStorage.setItem('maqanakuy-mapa',String(i));renderMapasMenu();sonidos.seleccion();};
    b.classList.toggle('elegido',i===mapaMenuSeleccionado);b.setAttribute('aria-pressed',i===mapaMenuSeleccionado?'true':'false');lista.appendChild(b);
  });
  const nombre=$('mapa-menu-nombre');if(nombre)nombre.textContent=STAGES[mapaMenuSeleccionado]?.nombre||STAGES[0].nombre;
}
renderMapasMenu();

// ---------- Música / configuración ----------
const musicaFrame=$('musica-frame');
function comandoMusica(func,args=[]){if(musicaFrame?.contentWindow)musicaFrame.contentWindow.postMessage(JSON.stringify({event:'command',func,args}), '*');}
function srcMusica(videoId){return `https://www.youtube.com/embed/${videoId}?autoplay=1&loop=1&playlist=${videoId}&controls=0&rel=0&enablejsapi=1&playsinline=1`; }
function pistaDeContexto(){
  if($('pantalla-batalla').classList.contains('activa')){
    const st=ultimoEstado || { mode:modoActual||'local', stageIndex:0, storyIndex:0 };
    const idx=(st.stageIndex||0)%STAGES.length;
    return STAGE_TRACKS[idx] || STAGE_TRACKS[0];
  }
  return MENU_TRACK;
}
function cargarPista(track){
  if(!musicaFrame || !track) return;
  if(pistaActualId===track.id) return;
  pistaActualId=track.id;
  pistaActualNombre=track.nombre||'';
  musicaFrame.src=srcMusica(track.id);
}
function actualizarTextoPista(){
  const el=$('info-musica-actual');
  if(!el) return;
  const track=pistaDeContexto();
  el.textContent=musicaSilenciada ? 'Música: apagada' : `♪ ${track.nombre}`;
}
function actualizarBotonMusica(){const b=$('btn-musica');b.textContent=musicaSilenciada?'🔇':'🔊';b.title=musicaSilenciada?'Activar música':'Silenciar música';}
function sincronizarMusica(){
  const track=pistaDeContexto();
  if(track) cargarPista(track);
  if(musicaSilenciada) comandoMusica('pauseVideo');
  else {comandoMusica('playVideo');comandoMusica('setPlaybackQuality',['small']);}
  actualizarBotonMusica();
  actualizarTextoPista();
}
['pointerdown','keydown','touchstart'].forEach(ev=>window.addEventListener(ev,sincronizarMusica,{once:true,passive:true}));
function mostrarPantalla(id){document.querySelectorAll('.pantalla').forEach(p=>p.classList.remove('activa'));$(id).classList.add('activa');document.querySelector('.acciones-esquina').style.display=id==='pantalla-inicio'?'flex':'none';sincronizarMusica();}
$('btn-musica').onclick=()=>{musicaSilenciada=!musicaSilenciada;localStorage.setItem('maqanakuy-musica',musicaSilenciada?'off':'on');$('toggle-musica').checked=!musicaSilenciada;sincronizarMusica();};
const modalConfig=$('modal-config'), modalPausa=$('modal-pausa');
$('toggle-musica').checked=!musicaSilenciada;$('toggle-sfx').checked=sfxActivos;$('toggle-fx').checked=fxActivos;actualizarBotonMusica();
function abrirConfig(desdePausa=false){configAbiertaDesdePausa=desdePausa;if(desdePausa){modalPausa.classList.remove('abierto');modalPausa.setAttribute('aria-hidden','true');}modalConfig.classList.add('abierto');modalConfig.setAttribute('aria-hidden','false');}
function cerrarConfig(){modalConfig.classList.remove('abierto');modalConfig.setAttribute('aria-hidden','true');if(configAbiertaDesdePausa&&enBatalla){configAbiertaDesdePausa=false;modalPausa.classList.add('abierto');modalPausa.setAttribute('aria-hidden','false');}}
$('btn-config').onclick=()=>abrirConfig(false);$('btn-cerrar-config').onclick=cerrarConfig;modalConfig.onclick=e=>{if(e.target===modalConfig)cerrarConfig();};
$('toggle-musica').onchange=e=>{musicaSilenciada=!e.target.checked;localStorage.setItem('maqanakuy-musica',musicaSilenciada?'off':'on');sincronizarMusica();};
$('toggle-sfx').onchange=e=>{sfxActivos=e.target.checked;localStorage.setItem('maqanakuy-sfx',sfxActivos?'on':'off');};
$('toggle-fx').onchange=e=>{fxActivos=e.target.checked;localStorage.setItem('maqanakuy-fx',fxActivos?'on':'off');};

// ---------- Audio sintetizado ----------
const AudioCtor=window.AudioContext||window.webkitAudioContext; const audioCtx=AudioCtor?new AudioCtor():null;
function tono(a,b,d,tipo='square',vol=.16,delay=0){if(!sfxActivos||!audioCtx)return;const start=audioCtx.currentTime+delay;if(audioCtx.state==='suspended')audioCtx.resume();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type=tipo;o.frequency.setValueAtTime(a,start);o.frequency.exponentialRampToValueAtTime(Math.max(1,b),start+d);g.gain.setValueAtTime(vol,start);g.gain.exponentialRampToValueAtTime(.001,start+d);o.connect(g).connect(audioCtx.destination);o.start(start);o.stop(start+d);}
const sonidos={
  golpe:()=>tono(190,65,.11,'square',.22),patada:()=>tono(270,45,.17,'sawtooth',.22),bloqueo:()=>tono(950,650,.09,'triangle',.15),salto:()=>tono(310,520,.1,'sine',.11),aterrizar:()=>tono(100,60,.08,'triangle',.09),dash:()=>tono(480,170,.1,'sine',.10),fallo:()=>tono(380,180,.12,'sine',.07),ko:()=>tono(130,38,.65,'sawtooth',.28),seleccion:()=>tono(420,700,.1,'square',.12),energia:()=>{tono(500,900,.12,'triangle',.13);tono(700,1100,.14,'triangle',.1,.08)},victoria:()=>[523,659,784,1046].forEach((f,i)=>tono(f,f,.18,'triangle',.15,i*.11)),derrota:()=>tono(300,50,.55,'sawtooth',.18),inicio:()=>{tono(150,90,.22,'sawtooth',.22);tono(700,700,.27,'square',.17,.18)},
  especial:(char)=>{const base={coya:620,cuy:420,gallito:760,jaguar:310,oso:180,gato:850}[char]||500;tono(base,base*.45,.32,'sawtooth',.25);tono(base*1.4,base*.8,.24,'triangle',.14,.08)}
};

// ---------- Spritesheets ----------
function visualState(p){if(!p)return'idle';if(p.hp<=0)return'ko';if(p.state==='attack'){if(p.currentAttack==='especial')return'special';if(p.currentAttack==='patada_fuerte')return'kick_heavy';if(p.currentAttack==='patada'||p.currentAttack==='barrido')return'kick_light';if(p.currentAttack==='golpe_fuerte')return'punch_heavy';return'punch_light';}return SPRITE_STATES[p.state]!==undefined?p.state:'idle';}
function setSprite(el,charId,state,restart=false){const sprite=el.querySelector('.sprite'),c=CHARACTERS[charId];if(!sprite||!c)return;const prev=sprite.dataset.state;if(prev!==state||restart){sprite.dataset.state=state;sprite.dataset.started=String(performance.now());sprite.dataset.lastFrame='';}sprite.style.backgroundImage=`url(\"${c.sheet}\")`;const stableScale=SPRITE_SCALE[charId]?.__base||SPRITE_SCALE[charId]?.idle||1;sprite.style.setProperty('--sprite-scale',String(stableScale));el.dataset.character=charId;}
const SPRITE_NODES=[$('luchador1')?.querySelector('.sprite'),$('luchador2')?.querySelector('.sprite')].filter(Boolean);
function animarSprites(t){if(enBatalla){for(const sprite of SPRITE_NODES){const state=sprite.dataset.state||'idle',row=SPRITE_STATES[state]??0,start=Number(sprite.dataset.started||t),dur=STATE_DUR[state]||500,loop=['idle','walk','run','block_high','block_low','victory'].includes(state);const frame=loop?Math.floor((t-start)/(dur/4))%4:Math.min(3,Math.floor(Math.max(0,t-start)/dur*4));const key=`${row}:${frame}`;if(sprite.dataset.lastFrame!==key){sprite.dataset.lastFrame=key;const x=frame*(100/3),y=row*(100/21);sprite.style.backgroundPosition=`${x}% ${y}%`;}}}requestAnimationFrame(animarSprites);}requestAnimationFrame(animarSprites);

function setMotionTarget(playerId,x,serverTime=0,snap=false){
  if(typeof x!=='number')return;
  const t=performance.now();
  let m=motion.get(playerId);
  if(!m){m={renderX:x,targetX:x,lastTargetX:x,velocity:0,lastAt:t,lastRender:t};motion.set(playerId,m);return;}
  const dt=Math.max(8,t-m.lastAt);
  const rawVelocity=(x-m.targetX)/dt;
  m.velocity=m.velocity*.58+rawVelocity*.42;
  m.lastTargetX=m.targetX;m.targetX=x;m.lastAt=t;
  if(snap||Math.abs(m.renderX-x)>24)m.renderX=x;
}
function syncMotionFromState(st,snap=false){
  if(!st?.players)return;
  st.players.forEach(p=>setMotionTarget(p.id,p.x,st.serverTime||0,snap));
  for(const id of [...motion.keys()])if(!st.players.some(p=>p.id===id))motion.delete(id);
}
function interpolationLoop(t){
  if(enBatalla&&ultimoEstado?.players){
    ultimoEstado.players.forEach((p,idx)=>{
      if(p.id===miPlayerKey&&!espectador)return;
      const m=motion.get(p.id);if(!m)return;
      const el=$(idx===0?'luchador1':'luchador2');if(!el)return;
      const dt=Math.min(40,Math.max(1,t-(m.lastRender||t)));m.lastRender=t;
      const predictionMs=Math.min(55,Math.max(0,pingActual*.22));
      const predicted=Math.max(3,Math.min(97,m.targetX+m.velocity*predictionMs));
      const smoothMs=modoActual==='online'?44:20;
      const alpha=1-Math.exp(-dt/smoothMs);
      m.renderX+= (predicted-m.renderX)*alpha;
      if(Math.abs(predicted-m.renderX)<.025)m.renderX=predicted;
      el.style.left=`${m.renderX}%`;
    });
  }
  requestAnimationFrame(interpolationLoop);
}
requestAnimationFrame(interpolationLoop);
let perfLast=performance.now(),perfFrames=0,perfLow=false,perfGoodWindows=0;
function performanceGuard(t){
  perfFrames++;
  const elapsed=t-perfLast;
  if(elapsed>=1500){
    const fps=perfFrames*1000/elapsed;
    if(fps<43&&!perfLow){perfLow=true;perfGoodWindows=0;document.body.classList.add('performance-low');}
    else if(perfLow&&fps>53){perfGoodWindows++;if(perfGoodWindows>=2){perfLow=false;perfGoodWindows=0;document.body.classList.remove('performance-low');}}
    else if(perfLow)perfGoodWindows=0;
    perfLast=t;perfFrames=0;
  }
  requestAnimationFrame(performanceGuard);
}
requestAnimationFrame(performanceGuard);

// ---------- Pantallas / sala ----------
function nombreActual(){const n=$('input-nombre').value.trim()||'Jugador';localStorage.setItem('maqanakuy-nombre',n);return n;}
function mostrarError(msg=''){['mensaje-error','mensaje-error-online'].forEach(id=>{if($(id))$(id).textContent=msg;});}
function guardarSala(){if(modoActual==='online'&&salaActual&&!espectador)localStorage.setItem('maqanakuy-room',JSON.stringify({code:salaActual,sessionToken}));}
function limpiarSalaGuardada(){localStorage.removeItem('maqanakuy-room');}
function entrarSala(res,mode,isSpectator=false){salaActual=res.code;modoActual=mode;miPlayerKey=res.playerKey||null;sessionToken=res.sessionToken||sessionToken;localStorage.setItem('maqanakuy-session',sessionToken);espectador=isSpectator;guardarSala();mostrarError('');mostrarPantalla('pantalla-sala');}
function iniciarSolo(mode){const difficulty=$('select-dificultad')?.value||'medio';localStorage.setItem('maqanakuy-dificultad',difficulty);localStorage.setItem('maqanakuy-mapa',String(mapaMenuSeleccionado));socket.emit('crear_solo',{name:nombreActual(),mode,sessionToken,difficulty,stageIndex:mapaMenuSeleccionado},res=>{if(!res.ok)return mostrarError(res.error);entrarSala(res,mode,false);});}
$('btn-historia').onclick=()=>iniciarSolo('story');$('btn-local').onclick=()=>iniciarSolo('local');$('btn-multijugador').onclick=()=>{modoActual='online';mostrarPantalla('pantalla-online');};
$('btn-crear').onclick=()=>socket.emit('crear_sala',{name:nombreActual(),sessionToken,stageIndex:mapaMenuSeleccionado},res=>res.ok?entrarSala(res,'online',false):mostrarError(res.error));
$('btn-unirse').onclick=()=>{const code=$('input-codigo').value.trim().toUpperCase();if(!code)return mostrarError('Escribe un código de sala.');socket.emit('unirse_sala',{name:nombreActual(),code,sessionToken},res=>res.ok?entrarSala(res,'online',false):mostrarError(res.error));};
$('btn-espectar').onclick=()=>{const code=$('input-codigo').value.trim().toUpperCase();if(!code)return mostrarError('Escribe el código de la sala que quieres ver.');socket.emit('unirse_espectador',{code},res=>res.ok?entrarSala(res,'online',true):mostrarError(res.error));};
function volverMenu(){if(salaActual)socket.emit('salir_sala');salaActual=null;miPlayerKey=null;miIndex=-1;modoActual=null;espectador=false;ultimoEstado=null;motion.clear();enBatalla=false;peleaAnunciada=false;juegoPausado=false;limpiarSalaGuardada();modalPausa.classList.remove('abierto');modalConfig.classList.remove('abierto');mostrarError('');mostrarPantalla('pantalla-inicio');}
document.querySelectorAll('.btn-volver').forEach(b=>b.onclick=volverMenu);$('btn-menu-final').onclick=volverMenu;

function pintarSelectoresBase(){
  $('lista-personajes').innerHTML='';Object.entries(CHARACTERS).forEach(([id,c])=>{const d=document.createElement('div');d.className='opcion-personaje';d.dataset.id=id;d.innerHTML=`<img class="icono" src="${c.icon}" alt="${c.name}"><span class="nombre">${c.name}</span><small>${c.estilo}</small>`;d.onclick=()=>{if(espectador||ultimoEstado?.started)return;sonidos.seleccion();socket.emit('elegir_personaje',{character:id});};$('lista-personajes').appendChild(d);});
  $('lista-mapas').innerHTML='';STAGES.forEach((s,i)=>{const d=document.createElement('div');d.className='mapa-opcion';d.dataset.index=i;d.innerHTML=`<img src="${s.archivo}" alt="${s.nombre}"><span>${s.nombre}</span>`;d.onclick=()=>{if(espectador||ultimoEstado?.started||ultimoEstado?.hostKey!==miPlayerKey)return;socket.emit('elegir_mapa',{stageIndex:i});sonidos.seleccion();};$('lista-mapas').appendChild(d);});
}pintarSelectoresBase();
function renderLobby(st){
  const online=st.mode==='online',yo=st.players.find(p=>p.id===miPlayerKey),rival=st.players.find(p=>p.id!==miPlayerKey);miIndex=st.players.findIndex(p=>p.id===miPlayerKey);
  $('titulo-sala').textContent=online?`Sala: ${st.code}`:(st.mode==='story'?'MODO HISTORIA':'MODO LOCAL');
  const diffLabel={facil:'Fácil',medio:'Medio',avanzado:'Avanzado'}[st.difficulty]||'Medio';
  $('texto-sala').textContent=espectador?'Modo espectador':online?'Comparte este código con tu rival':`Elige tu luchador · Dificultad ${diffLabel}`;
  $('espectadores-sala').textContent=`👁 ${st.spectators||0}`;
  $('estado-espera').textContent=online&&st.players.length<2?'Esperando rival...':(online&&st.players.some(p=>!p.connected)?'Esperando reconexión del rival...':'');
  const puedeElegir=!espectador && (!online||st.players.length>=1);$('selector-personajes').style.display=puedeElegir?'block':'none';
  $('selector-mapas').style.display=online?'block':'none';$('aviso-host-mapa').textContent=st.hostKey===miPlayerKey?'· tú eliges':'· elegido por el anfitrión';
  document.querySelectorAll('.mapa-opcion').forEach(el=>{el.classList.toggle('elegido',Number(el.dataset.index)===st.stageIndex);el.classList.toggle('bloqueado',st.hostKey!==miPlayerKey||espectador);});
  document.querySelectorAll('.opcion-personaje').forEach(el=>{el.classList.toggle('elegido',yo?.character===el.dataset.id);el.classList.toggle('rival-elegido',!!rival?.character&&rival.character===el.dataset.id);});
}

// ---------- Escenarios ----------
function escenarioDe(st){const idx=(st.stageIndex??0)%STAGES.length;return STAGES[idx]||STAGES[0];}
function aplicarEscenario(st){const s=escenarioDe(st),arena=$('arena');arena.style.backgroundImage=`linear-gradient(180deg,rgba(11,14,24,.08),rgba(12,14,25,.08)),url("${s.archivo}")`;$('nombre-mapa').textContent=s.nombre;arena.dataset.stage=String(st.stageIndex??0);sincronizarMusica();}

// ---------- Pausa ----------
function mostrarPausa(){if(!enBatalla||espectador||ultimoEstado?.finished)return;socket.emit('pausar',{activo:true});}
function cerrarPausa(){if(!enBatalla||espectador)return;socket.emit('pausar',{activo:false});}
function syncPausa(paused){juegoPausado=!!paused;$('pantalla-batalla').classList.toggle('pausada',juegoPausado);if(juegoPausado&&!modalConfig.classList.contains('abierto')){modalPausa.classList.add('abierto');modalPausa.setAttribute('aria-hidden','false');}else if(!juegoPausado){modalPausa.classList.remove('abierto');modalPausa.setAttribute('aria-hidden','true');}}
function alternarPausa(){if(!enBatalla||espectador)return;if(modalConfig.classList.contains('abierto'))return cerrarConfig();juegoPausado?cerrarPausa():mostrarPausa();}
$('btn-pausa-batalla').onclick=mostrarPausa;$('btn-continuar').onclick=cerrarPausa;$('btn-config-batalla').onclick=()=>{if(!juegoPausado)mostrarPausa();abrirConfig(true);};$('btn-config-pausa').onclick=()=>abrirConfig(true);$('btn-salir-batalla').onclick=volverMenu;$('btn-salir-pausa').onclick=volverMenu;

// ---------- Controles / dash / ataques ----------
const teclas=new Set(),lastTap={a:0,d:0},heldSince={a:0,d:0};let bloqueando=false;
function miJugador(){return ultimoEstado?.players.find(p=>p.id===miPlayerKey)||null;}
function puedeControlar(){const p=miJugador();return enBatalla&&!juegoPausado&&!espectador&&ultimoEstado?.roundActive&&p&&p.hp>0&&!['ko','knockdown','getup','hurt_high','hurt_low','recoil','defeat','intro','dodge'].includes(p.state);}
function localAnimationForAttack(attack){const el=$(miIndex===0?'luchador1':'luchador2'),p=miJugador();if(!el||!p)return;const s=attack==='especial'?'special':attack==='patada_fuerte'?'kick_heavy':(attack==='patada'||attack==='barrido'?'kick_light':attack==='golpe_fuerte'?'punch_heavy':'punch_light');setSprite(el,p.character,s,true);localBusyUntil=performance.now()+Math.min(78,STATE_DUR[s]||78);}
function lanzarAtaque(attack,uiType){if(!puedeControlar())return;const p=miJugador();if(attack==='especial'&&p.energy<SPECIAL_COST){mostrarImpacto($(miIndex===0?'luchador1':'luchador2'),'ENERGÍA INSUFICIENTE',true);sonidos.fallo();return;}const t=performance.now();if(t<localNextAttackAt)return;localNextAttackAt=t+(COOLDOWNS[attack]||120);localAnimationForAttack(attack);attack==='especial'?sonidos.especial(p.character):sonidos[uiType||attack]?.();socket.emit('atacar',{attack});}
function detectarAtaque(k,shift=false){if(k==='j')return saltando?'aereo':(shift?'golpe_fuerte':'golpe');if(k==='k')return teclas.has('s')?'barrido':(shift?'patada_fuerte':'patada');if(k==='l')return'especial';return null;}
function dispararAtaquePorTecla(k,shift=false){const atk=detectarAtaque(k,shift);if(atk)lanzarAtaque(atk,k==='j'?'golpe':k==='k'?'patada':'especial');}
function iniciarRepeticionAtaque(k,shift=false){if(holdAttackTimers[k])return;const cada=k==='l'?320:(shift?(k==='j'?220:250):(k==='j'?115:130));holdAttackTimers[k]=setInterval(()=>{if(!enBatalla||juegoPausado||espectador)return;dispararAtaquePorTecla(k,shift);},cada);}
function detenerRepeticionAtaque(k){if(holdAttackTimers[k]){clearInterval(holdAttackTimers[k]);delete holdAttackTimers[k];}}
window.addEventListener('keydown',e=>{
  const k=e.key.toLowerCase();if(k==='escape'){e.preventDefault();alternarPausa();return;}if(!enBatalla||juegoPausado||espectador)return;
  if(['a','d','w','s','u','j','k','l'].includes(k))e.preventDefault();
  if(['a','d'].includes(k)&&!e.repeat){const t=performance.now();if(t-lastTap[k]<170&&puedeControlar()){const dir=k==='a'?-1:1;socket.emit('dash',{direction:dir,seq:++movementSeq});miX=Math.max(3,Math.min(97,miX+dir*9));const el=$(miIndex===0?'luchador1':'luchador2'),p=miJugador();if(el&&p)setSprite(el,p.character,'dodge',true);localBusyUntil=t+100;sonidos.dash();crearParticula(el,'polvo');}lastTap[k]=t;heldSince[k]=t;}
  if(['a','d','s'].includes(k))teclas.add(k);
  if(k==='w'&&!saltando&&puedeControlar()){saltando=true;const el=$(miIndex===0?'luchador1':'luchador2'),p=miJugador();if(el&&p)setSprite(el,p.character,'jump',true);socket.emit('mover',{x:miX,estado:'jump',seq:++movementSeq});sonidos.salto();setTimeout(()=>{saltando=false;sonidos.aterrizar();crearParticula(el,'polvo');if(enBatalla&&!juegoPausado)socket.emit('mover',{x:miX,estado:teclas.has('s')?'crouch':'idle',seq:++movementSeq});},360);}
  if(k==='u'&&!bloqueando&&puedeControlar()){const p=miJugador();if((p?.guard??100)<=0)return;bloqueando=true;const nivel=teclas.has('s')?'low':'high',el=$(miIndex===0?'luchador1':'luchador2');if(el&&p)setSprite(el,p.character,nivel==='low'?'block_low':'block_high',true);socket.emit('bloquear',{activo:true,nivel});}
  if(['j','k','l'].includes(k)){ if(!e.repeat)dispararAtaquePorTecla(k,e.shiftKey); iniciarRepeticionAtaque(k,e.shiftKey); }
});
window.addEventListener('keyup',e=>{const k=e.key.toLowerCase();if(['a','d','s'].includes(k))teclas.delete(k);if(['j','k','l'].includes(k))detenerRepeticionAtaque(k);if(k==='u'&&bloqueando){bloqueando=false;socket.emit('bloquear',{activo:false});const el=$(miIndex===0?'luchador1':'luchador2'),p=miJugador();if(el&&p)setSprite(el,p.character,'idle');}if(k==='s'&&bloqueando)socket.emit('bloquear',{activo:true,nivel:'high'});});
function movementLoop(t){const dt=Math.min(20,t-ultimoFrame);ultimoFrame=t;if(puedeControlar()&&!bloqueando){let moved=false,run=false;if(teclas.has('a')){run=t-heldSince.a>135;miX-=dt*.079*(run?1.52:1);moved=true;}if(teclas.has('d')){run=t-heldSince.d>135;miX+=dt*.079*(run?1.52:1);moved=true;}miX=Math.max(3,Math.min(97,miX));const state=saltando?'jump':teclas.has('s')?'crouch':moved?(run?'run':'walk'):'idle';if(t-ultimoEnvioMov>14){ultimoEnvioMov=t;socket.volatile.emit('mover',{x:miX,estado:state,seq:++movementSeq});}const el=$(miIndex===0?'luchador1':'luchador2'),p=miJugador();if(el){el.style.left=`${miX}%`;if(p&&t>=localBusyUntil&&p.hp>0)setSprite(el,p.character,state);}}
  requestAnimationFrame(movementLoop);}requestAnimationFrame(movementLoop);

// Táctil: respuesta inmediata; mantener puño/patada cambia a ataque fuerte repetido.
for(const b of document.querySelectorAll('.controles-tactiles button')){
  const key=b.dataset.tecla; let holdTimer=null,repeatTimer=null,longMode=false;
  const down=e=>{
    e.preventDefault();b.classList.add('presionado');longMode=false;
    if(key==='j'||key==='k'){
      lanzarAtaque(key==='j'?'golpe':'patada',key==='j'?'golpe':'patada');
      holdTimer=setTimeout(()=>{longMode=true;const strong=key==='j'?'golpe_fuerte':'patada_fuerte';lanzarAtaque(strong,key==='j'?'golpe':'patada');repeatTimer=setInterval(()=>lanzarAtaque(strong,key==='j'?'golpe':'patada'),key==='j'?220:250);},220);
      return;
    }
    window.dispatchEvent(new KeyboardEvent('keydown',{key}));
  };
  const up=e=>{
    e.preventDefault();if(holdTimer){clearTimeout(holdTimer);holdTimer=null;}if(repeatTimer){clearInterval(repeatTimer);repeatTimer=null;}
    if(key!=='j'&&key!=='k')window.dispatchEvent(new KeyboardEvent('keyup',{key}));
    b.classList.remove('presionado');longMode=false;
  };
  b.addEventListener('pointerdown',down);b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);b.addEventListener('pointerleave',e=>{if(b.classList.contains('presionado'))up(e);});
}
function actualizarRecargas(){document.querySelectorAll('.recarga').forEach(el=>{el.style.setProperty('--listo','100%');el.classList.add('lista');});}actualizarRecargas();

// ---------- Estado / HUD ----------
function renderFighter(el,p,isMine,other){if(!p)return;const state=visualState(p);const localLock=isMine&&performance.now()<localBusyUntil&&!['hurt_high','hurt_low','recoil','knockdown','ko','defeat'].includes(p.state);if(!localLock)setSprite(el,p.character,state);el.classList.toggle('espejo',p.x>other.x);el.classList.toggle('energy-ready',p.energy>=SPECIAL_COST);if(!isMine||espectador)setMotionTarget(p.id,p.x,ultimoEstado?.serverTime||0);else if(Math.abs(miX-p.x)>14)miX+=(p.x-miX)*.08;}
function renderBattle(st){aplicarEscenario(st);const[p1,p2]=st.players;if(!p1||!p2)return;miIndex=st.players.findIndex(p=>p.id===miPlayerKey);const hud1=$('hud-jugador1'),hud2=$('hud-jugador2');
  [[hud1,p1],[hud2,p2]].forEach(([h,p])=>{h.querySelector('.nombre-jugador').textContent=p.name+(p.connected?'':' ⟳');h.querySelector('.victorias-jugador').textContent=`★ ${p.matchWins||0}  ${'●'.repeat(p.rounds||0)}`;h.querySelector('.vida-actual').style.width=`${Math.max(0,p.hp/p.maxHp*100)}%`;h.querySelector('.energia-actual').style.width=`${p.energy}%`;const g=h.querySelector('.guardia-actual');if(g)g.style.width=`${Math.max(0,(p.guard??100)/(p.maxGuard||100)*100)}%`;});
  $('ronda-hud').textContent=`RONDA ${st.round||1}`;$('tiempo-hud').textContent=st.timeLeft??90;const mine=miJugador();$('estado-especial').textContent=espectador?'ESPECTADOR':`ENERGÍA ${mine?.energy??0}%`;
  renderFighter($('luchador1'),p1,miPlayerKey===p1.id,p2);renderFighter($('luchador2'),p2,miPlayerKey===p2.id,p1);
  $('btn-pausa-batalla').style.display=espectador?'none':'';$('btn-config-batalla').style.display=espectador?'none':'';syncPausa(st.paused);
}
function renderFinal(st){const mine=st.players.find(p=>p.id===miPlayerKey),rival=st.players.find(p=>p.id!==miPlayerKey);const gane=st.winner===miPlayerKey;
  $('titulo-final').textContent=espectador?'FIN DEL COMBATE':(gane?'GANASTE':'PERDISTE');$('marcador-final').textContent=`${st.players[0]?.rounds||0} — ${st.players[1]?.rounds||0}`;
  $('progreso-historia').textContent='';$('estado-revancha').textContent='';$('btn-revancha').style.display=espectador?'none':'';$('btn-revancha').dataset.accion='revancha';$('btn-revancha').textContent=st.mode==='online'?'Solicitar revancha':'Revancha';
  if(st.mode==='story'&&!espectador){const complete=gane&&st.storyIndex>=st.storyTotal-1;$('progreso-historia').textContent=complete?'¡HISTORIA COMPLETADA!':`Rival ${st.storyIndex+1} de ${st.storyTotal}`;if(gane&&!complete){$('btn-revancha').dataset.accion='siguiente';$('btn-revancha').textContent='Siguiente rival';}}
  if(st.mode==='online'&&!espectador){const voted=st.rematchVotes.includes(miPlayerKey);$('estado-revancha').textContent=st.rematchVotes.length?`Revancha: ${st.rematchVotes.length}/2 aceptada${st.rematchVotes.length>1?'s':''}`:'';if(voted)$('btn-revancha').textContent='Esperando al rival...';}
  const s=mine?.stats||{};$('estadisticas-final').innerHTML=mine?`<div><strong>${s.hits||0}</strong><span>impactos</span></div><div><strong>${s.maxCombo||0}</strong><span>combo máximo</span></div><div><strong>${s.damage||0}</strong><span>daño</span></div><div><strong>${s.blocks||0}</strong><span>bloqueos</span></div><div><strong>${s.dodges||0}</strong><span>esquivas</span></div><div><strong>${s.dashes||0}</strong><span>dash</span></div>`:'';
  if(!espectador)(gane?sonidos.victoria():sonidos.derrota());mostrarPantalla('pantalla-final');
}
socket.on('estado',st=>{const primera=!ultimoEstado||!ultimoEstado.started;ultimoEstado=st;syncMotionFromState(st,primera);modoActual=st.mode;miIndex=st.players.findIndex(p=>p.id===miPlayerKey);if(miIndex>=0&&!enBatalla)miX=st.players[miIndex].x;
  if(!st.started){enBatalla=false;peleaAnunciada=false;syncPausa(false);renderLobby(st);mostrarPantalla('pantalla-sala');return;}
  if(!peleaAnunciada&&!st.finished){peleaAnunciada=true;sonidos.inicio();if(miIndex>=0)miX=st.players[miIndex].x;}
  if(st.finished){enBatalla=false;syncPausa(false);renderFinal(st);return;}
  enBatalla=true;renderBattle(st);mostrarPantalla('pantalla-batalla');
});

socket.on('movimiento_jugador',({playerId,x,state,serverTime,seq}={})=>{
  if(!ultimoEstado||typeof x!=='number')return;
  const p=ultimoEstado.players.find(v=>v.id===playerId);if(!p)return;
  p.x=x;if(p.state!=='attack'&&['idle','walk','run','jump','crouch'].includes(state))p.state=state;
  setMotionTarget(playerId,x,serverTime||0);
  if(playerId===miPlayerKey&&!espectador&&Math.abs(miX-x)>18)miX+=(x-miX)*.12;
});

// ---------- Eventos de combate ----------
function fighterById(id){if(!ultimoEstado)return null;const idx=ultimoEstado.players.findIndex(p=>p.id===id);return idx===0?$('luchador1'):idx===1?$('luchador2'):null;}
function crearParticula(el,tipo='chispa',extra=''){if(!fxActivos||!el)return;const capa=$('efectos-combate'),p=document.createElement('span');p.className=`particula ${tipo}${extra?' '+extra:''}`;p.style.left=el.style.left||'50%';p.style.top=tipo==='polvo'?'82%':'46%';capa.appendChild(p);setTimeout(()=>p.remove(),700);}
function sacudir(fuerte=false){if(!fxActivos)return;const a=$('arena'),c=fuerte?'sacudida-fuerte':'sacudida';a.classList.remove(c);void a.offsetWidth;a.classList.add(c);setTimeout(()=>a.classList.remove(c),350);}
function mostrarImpacto(el,texto,suave=false,combo=false){if(!el)return;const m=document.createElement('span');m.className=`impacto${suave?' suave':''}${combo?' combo-especial':''}`;m.textContent=texto;m.style.left=el.style.left||'50%';m.style.top='40%';$('efectos-combate').appendChild(m);setTimeout(()=>m.remove(),760);}
socket.on('ataque_iniciado',({attackerId,attack,startup=0,active=100,recovery=0})=>{const p=ultimoEstado?.players.find(x=>x.id===attackerId);if(p){p.state='attack';p.currentAttack=attack;setTimeout(()=>{if(p.currentAttack===attack){p.currentAttack=null;if(p.state==='attack')p.state='idle';}},Math.max(100,startup+active+recovery)+35);}if(attackerId===miPlayerKey)return;const el=fighterById(attackerId);if(!el||!p)return;setSprite(el,p.character,attack==='especial'?'special':attack==='patada_fuerte'?'kick_heavy':(attack==='patada'||attack==='barrido'?'kick_light':attack==='golpe_fuerte'?'punch_heavy':'punch_light'),true);attack==='especial'?sonidos.especial(p.character):sonidos[(attack==='aereo'||attack==='golpe_fuerte')?'golpe':((attack==='patada_fuerte'||attack==='barrido')?'patada':attack)]?.();});
socket.on('ataque_activo',({attackerId,attack,effect})=>{const el=fighterById(attackerId);if(attack==='especial'){el?.classList.add('especial-activo');crearParticula(el,'especial',effect||'');setTimeout(()=>el?.classList.remove('especial-activo'),450);}});
socket.on('golpe',({targetId,attack,dmg,bloqueado,effect})=>{const el=fighterById(targetId);if(!el)return;if(bloqueado){sonidos.bloqueo();crearParticula(el,'bloqueo');mostrarImpacto(el,`BLOQUEO · -${dmg}`,true);}else{el.classList.add('hit-flash');setTimeout(()=>el.classList.remove('hit-flash'),130);crearParticula(el,attack==='especial'?'especial':'chispa',attack==='especial'?(effect||''):'');mostrarImpacto(el,`-${dmg}`);sacudir(attack==='especial'||dmg>=22);} });
socket.on('ataque_fallido',({attackerId,reason})=>{if(attackerId!==miPlayerKey)return;if(reason==='esquiva'){mostrarImpacto(fighterById(attackerId),'ESQUIVADO',true);sonidos.fallo();}});
socket.on('combo',({attackerId,count})=>{if(attackerId===miPlayerKey)$('estado-combo').textContent=`COMBO ×${count}`;setTimeout(()=>{$('estado-combo').textContent='LISTO';},850);});
socket.on('combo_especial',({attackerId,name})=>{const el=fighterById(attackerId);mostrarImpacto(el,name,false,true);sonidos.energia();});
socket.on('dash',({playerId})=>{crearParticula(fighterById(playerId),'polvo');});
socket.on('energia_insuficiente',()=>{mostrarImpacto(fighterById(miPlayerKey),'ENERGÍA INSUFICIENTE',true);sonidos.fallo();});
socket.on('guardia_rota',({playerId})=>{const el=fighterById(playerId);mostrarImpacto(el,'¡GUARDIA ROTA!',false,true);crearParticula(el,'bloqueo');tono(180,55,.28,'sawtooth',.20);if(playerId===miPlayerKey)bloqueando=false;});
socket.on('aturdido',({playerId})=>{const el=fighterById(playerId);mostrarImpacto(el,'ATURDIDO',true);tono(420,120,.18,'triangle',.12);});
socket.on('fin_ronda',({winnerId,round})=>{sonidos.ko();const a=$('anuncio-ronda');a.textContent=espectador?`FIN RONDA ${round}`:(winnerId===miPlayerKey?`RONDA ${round} GANADA`:`RONDA ${round} PERDIDA`);a.classList.add('visible');setTimeout(()=>a.classList.remove('visible'),1900);});
socket.on('rival_desconectado',()=>{if(modoActual==='online'&&!espectador)$('estado-combo').textContent='RIVAL RECONECTANDO…';});
socket.on('rival_reconectado',()=>{$('estado-combo').textContent='RIVAL RECONECTADO';setTimeout(()=>{$('estado-combo').textContent='LISTO';},1400);});

$('btn-revancha').onclick=e=>{peleaAnunciada=false;if(e.currentTarget.dataset.accion==='siguiente')socket.emit('siguiente_historia');else socket.emit('solicitar_revancha');};

// ---------- Ping / reconexión ----------
setInterval(()=>{const t=performance.now();socket.emit('ping_juego',()=>{pingActual=Math.round(performance.now()-t);$('ping-hud').textContent=`${pingActual} ms`;$('ping-sala').textContent=`${pingActual} ms`;});},2000);
socket.on('connect',()=>{const raw=localStorage.getItem('maqanakuy-room');if(!raw)return;try{const saved=JSON.parse(raw);if(!saved.code||!saved.sessionToken)return;socket.emit('reconectar_sala',saved,res=>{if(!res.ok){limpiarSalaGuardada();return;}salaActual=res.code;miPlayerKey=res.playerKey;modoActual=res.mode||'online';sessionToken=saved.sessionToken;espectador=false;});}catch{limpiarSalaGuardada();}});
