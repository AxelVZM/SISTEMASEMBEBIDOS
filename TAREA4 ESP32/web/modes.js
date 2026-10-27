(()=>{
 const el=id=>document.getElementById(id),bleRows=new Map(),lanRows=new Map();let pending=false,pendingAt=0,session=null,scan=null,notice='',lanFeedback='',commandType='';
 const num=(x,a,b)=>Number.isInteger(x)&&x>=a&&x<=b,txt=(x,n)=>typeof x==='string'&&x.length<=n;
 function reset(){bleRows.clear();lanRows.clear();session=null;scan=null;pending=false;notice='';lanFeedback='';commandType='';}
 function accept(d){
  if(d.kind==='mode_ack'){if(typeof d.ok==='boolean'&&txt(d.message,300)){pending=false;notice=d.message;if(commandType==='lan_scan')lanFeedback=d.message;render();}return true;}
  if(!['ble','lan'].includes(d.kind))return false;
  if(!validClassification(d))return true;
  if(!num(d.b,0,0xffffffff)||d.b!==boot||!num(d.slot,0,d.kind==='ble'?31:23)||!num(d.last,0,0xffffffff))return true;
  if(d.kind==='ble'){
   if(!txt(d.mac,17)||!/^([0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(d.mac)||!num(d.addressType,0,3)||!Number.isFinite(d.rssi)||d.rssi< -127||d.rssi>20||!num(d.frames,1,0xffffffff)||!txt(d.name,64)||!txt(d.company,400))return true;
   for(const [k,n]of [['brand',80],['model',100],['modelId',8],['modelSource',120]])if(!txt(d[k]??'',n))return true;
   if(![undefined,true,false].includes(d.modelConflict)||![undefined,true,false].includes(d.encrypted))return true;
   bleRows.set(d.slot,d);
  }else{
   if(!num(d.scan,0,0xffffffff)||d.scan!==meta?.lanScan||!num(d.port,0,65535))return true;
   for(const[k,n]of [['name',64],['host',64],['ip',45],['service',31],['brand',64],['model',96],['evidence',100]])if(!txt(d[k],n))return true;
   for(const[k,n]of [['modelCode',64],['resolvedModel',100]])if(!txt(d[k]??'',n))return true;
   lanRows.set(d.slot,d);
  }
  window.orbitaEC2?.packet(d);return true;
 }
 async function command(message){if(pending)return;pending=true;commandType=message.cmd;pendingAt=performance.now();notice='Enviando solicitud al ESP32…';if(commandType==='lan_scan')lanFeedback=notice;render();try{await sendCommand(message);}catch(e){pending=false;notice='No se pudo enviar: '+e.message;if(commandType==='lan_scan')lanFeedback=notice;}render();}
 function render(){
  if(!el('modeLabel'))return;
  if(meta&&session!==meta.b){bleRows.clear();lanRows.clear();session=meta.b;scan=null;}
  if(meta&&scan!==meta.lanScan){lanRows.clear();scan=meta.lanScan;}
  if(pending&&performance.now()-pendingAt>10000){pending=false;notice='Sin confirmación. Revisa el estado de la placa antes de reintentar.';if(commandType==='lan_scan')lanFeedback=notice;}
  const live=fresh(),selected=!!meta?.bleSelected,local=connected&&!demo&&!window.orbitaEC2?.remote&&live&&['7.4','7.5','7.5.1'].includes(meta?.firmware),busy=!!meta?.netPaused||pending||!!transfer;
  el('bleActivate').disabled=!local||busy||selected;el('bleDeactivate').disabled=!local||busy||!selected;el('lanDiscover').disabled=!local||busy||selected;
  el('modeLabel').textContent=!live?'Sin telemetría reciente':meta.radio==='BLE'?'BLE seleccionado · Wi-Fi en pausa':meta.radio==='Red'?'Red local / conexión · escucha en pausa':'Wi-Fi activo · Bluetooth sin escanear';
  for(const card of document.querySelectorAll('[data-mode-card]'))card.classList.toggle('selected',live&&card.dataset.modeCard===(meta.radio==='BLE'?'ble':meta.radio==='Red'?'lan':'wifi'));
  const blocked=!connected?'Conecta el ESP32 por USB para activar los controles.':window.orbitaEC2?.remote?'La vista remota es de solo lectura; conecta USB para controlar la placa.':!live?'Sin telemetría reciente; revisa USB.':!local?'Actualiza el firmware de la placa.':'';
  el('bleState').textContent=meta?.bleError?('Error BLE: '+meta.bleError):blocked||notice||(!live?'Conecta USB con firmware 7.4/7.5 para activar.':selected?(meta.bleReady?'Escaneando anuncios BLE. Wi-Fi se reanudará al desactivar.':'Inicializando Bluetooth…'):'BLE desactivado. Abrir este apartado no inicia el escaneo.');
  el('bleObserved').textContent=live?String(meta.ble):'—';el('bleModeBadge').textContent=selected?'Modo seleccionado':'Apagado';
  el('lanState').textContent=blocked||(meta?.lanState==='error'?meta.lanMessage:lanFeedback||meta?.lanMessage)||'Configura tu red de 2,4 GHz y pulsa Buscar servicios.';
  el('lanObserved').textContent=meta?.lanState==='done'?String(meta.lanCount):'—';
  const rows=[...bleRows.values()].sort((a,b)=>b.rssi-a.rssi);
  el('bleRows').innerHTML=rows.length?rows.map(r=>`<tr><td><strong>${esc(r.name||'Sin nombre anunciado')}</strong><br><small>${esc(r.mac)} · ${esc(['Pública','Aleatoria','Identidad pública','Identidad aleatoria'][r.addressType])}</small></td><td>${esc(r.brand||'No determinada')}<br><small>${esc(r.deviceLabel||'Tipo sin determinar')} · ${esc(r.classLevel||'unknown')}</small><br><small>Titular SIG: ${esc(r.company)}</small></td><td><strong>${esc(r.modelConflict?'Sin determinar: conflicto':r.model||'Sin determinar')}</strong><br><small>${r.model?'Modelo anunciado; no autenticado':'Sin ID compatible'}</small></td><td>${esc(r.modelSource||'Sin decoder')}<br><small>ID ${esc(r.modelId||'—')}${r.encrypted?' · datos de medición cifrados':''}</small></td><td>${r.rssi.toFixed(1)} dBm</td><td>${esc(ago(r))}<br><small>${live&&selected&&recent(r)?'Recepción reciente':'Histórico; sin confirmar presencia'}</small></td></tr>`).join(''):'<tr><td colspan="6" class="empty">Activa BLE para recibir anuncios. No todos los aparatos anuncian un modelo.</td></tr>';
  el('lanRows').innerHTML=lanRows.size?[...lanRows.values()].filter(r=>r.scan===meta?.lanScan).map(r=>`<tr><td><strong>${esc(r.name||r.host||'Servicio sin nombre')}</strong><br><small>${esc(r.host)}</small></td><td>${esc(r.ip||'Sin IPv4 anunciada')} : ${r.port}</td><td>${esc(r.service)}<br><strong>${esc(r.deviceLabel||'Tipo sin determinar')}</strong><br><small>${esc(r.classEvidence||'Sin clasificación')}</small></td><td>${esc(r.brand||'No anunciada')}</td><td><strong>${esc(r.resolvedModel||r.model||'No anunciado')}</strong><br><small>${esc(r.modelCode||r.model)}<br>${esc(r.evidence)} · no autenticado</small></td><td>${esc(ago(r))}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">No hay servicios en esta búsqueda. Una red vacía aquí no significa que no tenga dispositivos.</td></tr>';
 }
 el('bleActivate').onclick=()=>command({cmd:'ble_set',enabled:true});el('bleDeactivate').onclick=()=>command({cmd:'ble_set',enabled:false});
 el('lanDiscover').onclick=async()=>{await command({cmd:'lan_scan'});};
 el('lanConfigure').onclick=()=>{setView('explorer');el('networkSettings').open=true;el('networkSettings').scrollIntoView({behavior:'smooth'});el('netSsid').focus();};
 el('bleExport').onclick=()=>downloadCsv([['MAC observada','Tipo direccion','Nombre','Titular SIG','Marca anunciada','Modelo anunciado','ID modelo','Fuente','RSSI','Ultima recepcion ms'],...[...bleRows.values()].map(r=>[r.mac,r.addressType,r.name,r.company,r.brand,r.modelConflict?'':r.model,r.modelId,r.modelSource,r.rssi,r.last])],'observaciones_ble.csv');
 el('lanExport').onclick=()=>downloadCsv([['Busqueda','Nombre','Host','IP','Puerto','Servicio','Marca anunciada','Modelo anunciado','Evidencia','Tipo','Nivel','Evidencia tipo','Codigo','Modelo catalogo'],...[...lanRows.values()].filter(r=>r.scan===meta?.lanScan).map(r=>[r.scan,r.name,r.host,r.ip,r.port,r.service,r.brand,r.model,r.evidence,r.deviceLabel,r.classLevel,r.classEvidence,r.modelCode,r.resolvedModel])],'servicios_lan.csv');
 window.orbitaModes={accept,render,reset,status:()=>{if(pending&&meta?.lanState&&['connecting','scanning'].includes(meta.lanState)){pending=false;notice='';lanFeedback='';}render();}};
})();
