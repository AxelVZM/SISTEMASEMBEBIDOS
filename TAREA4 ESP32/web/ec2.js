/* Transport for the existing ESP32 panel. Firmware keeps acquisition/classification. */
(()=>{
 const el=id=>document.getElementById(id),source=crypto.randomUUID?.().replaceAll('-','')||('browser'+Date.now());
 let remote=false,remoteOnline=false,key='',sensor='esp32-principal',captureBoot=null,queue=new Map(),sending=false,polling=false,retryAt=0,lastRemote='',generation=0;
 try{key=sessionStorage.getItem('orbita_ec2_token')||'';sensor=sessionStorage.getItem('orbita_ec2_sensor')||sensor;}catch{}
 el('ec2Token').value=key;el('ec2Sensor').value=sensor;
 function message(s){el('ec2State').textContent=s;}
 function configure(){
  const k=el('ec2Token').value.trim(),s=el('ec2Sensor').value.trim();
  if(k.length<32||!/^[-a-zA-Z0-9_]{1,64}$/.test(s)){message('Token: mínimo 32 caracteres. ID: letras, números, guion o guion bajo.');return false;}
  if(k!==key||s!==sensor){queue.clear();captureBoot=null;}key=k;sensor=s;
  try{sessionStorage.setItem('orbita_ec2_token',key);sessionStorage.setItem('orbita_ec2_sensor',sensor);}catch{}
  message('Enlace guardado. Conecta USB para enviar o pulsa Ver sensor remoto.');return true;
 }
 async function api(path,options={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7000);
  try{const r=await fetch(path,{...options,signal:controller.signal,headers:{Authorization:'Bearer '+key,...options.headers}});
   if(!r.ok){let text='HTTP '+r.status;try{text+=' · '+(await r.json()).error;}catch{}throw new Error(text);}return await r.json();
  }finally{clearTimeout(timer);}
 }
 function packet(d){
  if(remote||demo||!connected||!['status','wifi','ble','lan'].includes(d.kind))return;
  if(captureBoot!==d.b){captureBoot=d.b;queue.clear();}
  queue.set(d.kind==='status'?'status':d.kind+':'+d.slot,d);
 }
 async function publish(){
  if(remote||demo||!connected||!key||!el('ec2Publish').checked||sending||!queue.size||Date.now()<retryAt)return;
  sending=true;const batch=[...queue.entries()].sort((a,b)=>(a[0]==='status'?-1:0)-(b[0]==='status'?-1:0));
  try{await api('api/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sensor_id:sensor,source_id:source,packets:batch.map(x=>x[1])})});
   for(const [k,v]of batch)if(queue.get(k)===v)queue.delete(k);
   message('USB → EC2 · datos enviados · sensor '+sensor);
  }catch(e){retryAt=Date.now()+3000;message('No se pudo enviar: '+e.message+'. Se conservan solo las últimas filas pendientes.');}
  finally{sending=false;}
 }
 async function poll(){
  if(!remote||polling)return;polling=true;const g=generation;
  try{const d=await api('api/live?'+new URLSearchParams({sensor}));if(!remote||g!==generation)return;
   if(!d.online){remoteOnline=false;message('Sensor sin datos recientes. Mantén el ESP32 alimentado y su puente USB activo.');render();return;}
   const s=d.packets.find(p=>p.kind==='status');if(!s)throw new Error('No llega estado del sensor');remoteOnline=true;
   const stamp=s.b+':'+s.ms;if(stamp!==lastRemote){acceptLine(JSON.stringify(s));lastRemote=stamp;}
   for(const p of d.packets)if(p.kind!=='status')acceptLine(JSON.stringify(p));
   message('Consulta remota · '+sensor+' · datos recibidos desde EC2');render();
  }catch(e){if(remote&&g===generation){remoteOnline=false;message('Sin enlace remoto: '+e.message);render();}}
  finally{polling=false;}
 }
 async function start(){
  if(connected&&!remote){message('Desconecta primero la vista USB si deseas consultar otro puente.');return;}
  if(!configure())return;if(demo)stopDemo();generation++;remote=true;remoteOnline=false;lastRemote='';queue.clear();clearSession();connected=true;render();
  const g=generation;
  try{const h=await api('api/history?'+new URLSearchParams({sensor,hours:4}));if(remote&&g===generation){history=h.points;chart();}}catch{}
  await poll();
 }
 function stop(){generation++;remote=false;remoteOnline=false;lastRemote='';connected=false;queue.clear();clearSession();message('Consulta remota cerrada. Puedes conectar un ESP32 por USB.');render();}
 function paint(){
  el('ec2Remote').disabled=connected&&!remote;el('ec2Remote').hidden=remote;el('ec2Stop').hidden=!remote;
  for(const id of ['ec2Token','ec2Sensor','ec2Save','ec2Publish'])el(id).disabled=remote;
 }
 window.orbitaEC2={get remote(){return remote;},get online(){return remoteOnline;},packet,render:paint,stop};
 el('ec2Save').onclick=configure;el('ec2Remote').onclick=start;el('ec2Stop').onclick=stop;
 setInterval(publish,500);setInterval(poll,1000);
})();
