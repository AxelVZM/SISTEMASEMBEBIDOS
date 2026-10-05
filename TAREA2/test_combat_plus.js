const { io } = require('socket.io-client');
const assert = require('assert');
const wait = ms => new Promise(r=>setTimeout(r,ms));

(async()=>{
  const a=io('http://127.0.0.1:3100',{transports:['websocket']});
  const b=io('http://127.0.0.1:3100',{transports:['websocket']});
  const s=io('http://127.0.0.1:3100',{transports:['websocket']});
  let code, aKey, bKey, last, attackStarted=false, hitCount=0, farFail=false;
  a.on('estado',st=>last=st);
  a.on('ataque_iniciado',e=>{if(e.attackerId===aKey)attackStarted=true;});
  a.on('golpe',()=>hitCount++);
  a.on('ataque_fallido',e=>{if(e.attackerId===aKey&&e.reason==='distancia')farFail=true;});
  await new Promise(res=>a.on('connect',res));
  await new Promise(res=>b.on('connect',res));
  const created=await new Promise(r=>a.emit('crear_sala',{name:'Ana',sessionToken:'tok-a'},r));
  assert(created.ok);code=created.code;aKey=created.playerKey;
  const joined=await new Promise(r=>b.emit('unirse_sala',{name:'Beto',code,sessionToken:'tok-b'},r));
  assert(joined.ok);bKey=joined.playerKey;
  const spec=await new Promise(r=>s.emit('unirse_espectador',{code},r)); assert(spec.ok);
  a.emit('elegir_mapa',{stageIndex:3});
  a.emit('elegir_personaje',{character:'coya'}); b.emit('elegir_personaje',{character:'jaguar'});
  for(let i=0;i<20 && !last?.started;i++) await wait(100);
  assert(last?.started,'partida debe iniciar'); assert.equal(last.stageIndex,3,'mapa seleccionado'); assert.equal(last.spectators,1,'espectador');
  const hp0=last.players.find(p=>p.id===bKey).hp;
  a.emit('atacar',{attack:'golpe'}); await wait(500);
  assert(attackStarted,'ataque debe animarse/iniciarse incluso lejos'); assert(farFail,'debe fallar por distancia');
  assert.equal(last.players.find(p=>p.id===bKey).hp,hp0,'lejos no debe haber daño');
  // acercar progresivamente
  for(let i=0;i<18;i++){a.emit('mover',{x:47,estado:'run'});b.emit('mover',{x:53,estado:'run'});await wait(60);}
  await wait(120);
  a.emit('atacar',{attack:'golpe'}); await wait(500);
  assert(hitCount>=1,'cerca debe registrar impacto');
  assert(last.players.find(p=>p.id===bKey).hp<hp0,'cerca debe causar daño');
  // dash
  const xBefore=last.players.find(p=>p.id===aKey).x; a.emit('dash',{direction:-1}); await wait(120); const xAfter=last.players.find(p=>p.id===aKey).x; assert(xAfter<xBefore,'dash debe mover');
  console.log('PRUEBA OK: mapa, espectador, animación a distancia sin daño, hitbox cercano y dash.');
  a.close();b.close();s.close();process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
