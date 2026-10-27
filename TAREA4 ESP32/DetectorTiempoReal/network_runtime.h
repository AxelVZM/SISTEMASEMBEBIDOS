#pragma once
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "network_config.h"
#include "device_classifier.h"
#include "cloud_ca.h"
Preferences networkPrefs;
NetworkSettings networkSettings;
bool networkConfigured=false,networkStoreReady=false,networkForceTest=false,networkCancel=false,networkStatusPending=true;
uint8_t networkPhase=0; // 0 capture, 1 associate, 2 clock, 3 HTTPS
uint32_t networkAt=0,networkNext=0,networkStatusAt=0,networkSequence=0,networkSuccesses=0;
int networkLastHttp=0;String networkMessage="Sin configurar; captura autonoma",networkPayload="",networkTarget="";
std::atomic<bool> networkWorkerDone{false};std::atomic<int> networkWorkerCode{0};
bool networkOnlyTest=false,networkAbortIssued=false;
void finishNetwork(uint32_t,const String&);
#include "lan_runtime.h"
bool networkBusy(){return networkPhase!=0;}
String networkPhaseText(){if(networkPhase==4)return "Conectando LAN";if(networkPhase==5)return "Descubriendo LAN";return networkPhase==1?"Conectando Wi-Fi":networkPhase==2?"Sincronizando hora":networkPhase==3?"Enviando HTTPS":"Captura";}
void initializeNetwork(){
 strcpy(networkSettings.endpoint,DEFAULT_ENDPOINT);
 networkStoreReady=networkPrefs.begin("orbita_net71",false);
 if(networkStoreReady&&networkPrefs.getBytesLength("cfg")==sizeof(NetworkSettings)){
  NetworkSettings saved{};if(networkPrefs.getBytes("cfg",&saved,sizeof(saved))==sizeof(saved)&&validSettings(saved)){networkSettings=saved;networkConfigured=true;networkMessage=saved.enabled?"Subida automatica configurada":"Red guardada; subida desactivada";}
 }
 if(!networkStoreReady)networkMessage="No se pudo abrir configuracion NVS";
 networkNext=millis()+30000;
}
bool handleNetworkCommand(cJSON*j,uint32_t now){
 auto*cmd=cJSON_GetObjectItemCaseSensitive(j,"cmd");if(!cJSON_IsString(cmd))return false;
 if(!strcmp(cmd->valuestring,"lan_scan")){
  if(networkBusy()||bleSelected||bleScanning.load()||bleStartPending.load()||exporting||!networkConfigured){storageReply="{\"kind\":\"mode_ack\",\"ok\":false,\"message\":\"Guarda tu red y termina BLE/red/descarga antes de buscar LAN\"}";return true;}
  if(!lanRows){lanRows=new(std::nothrow) LanEntry[24];if(!lanRows){storageReply="{\"kind\":\"mode_ack\",\"ok\":false,\"message\":\"Sin memoria para LAN\"}";return true;}}
  lanCount=0;lanCursor=0;lanScan++;lanDone.store(false);lanState="connecting";lanMessage="Conectando a la red guardada; escucha Wi-Fi pausada";
  accepting.store(false);esp_wifi_set_promiscuous(false);networkPhase=4;networkAt=now;networkCancel=false;networkStatusPending=true;WiFi.begin(networkSettings.ssid,networkSettings.password);return true;
 }
 if(!strcmp(cmd->valuestring,"network_get")){networkStatusPending=true;return true;}
 if(!strcmp(cmd->valuestring,"network_test")){
  if(!networkConfigured)networkMessage="Guarda primero tu red";
  else if(bleSelected)networkMessage="Desactiva BLE para probar tu red";
  else if(networkBusy())networkMessage="Operacion de red en curso";
  else {networkForceTest=true;networkMessage="Prueba de conexion programada";}
  networkStatusPending=true;return true;
 }
 if(!strcmp(cmd->valuestring,"network_forget")){
  bool ok=networkStoreReady&&(networkPrefs.getBytesLength("cfg")==0||networkPrefs.remove("cfg"));
  if(ok){networkSettings=NetworkSettings{};strcpy(networkSettings.endpoint,DEFAULT_ENDPOINT);networkConfigured=false;networkForceTest=false;networkCancel=networkBusy();networkMessage="Red olvidada; captura autonoma";}else networkMessage="No se pudo borrar la configuracion";
  networkStatusPending=true;return true;
 }
 if(strcmp(cmd->valuestring,"network_set"))return false;
 NetworkSettings candidate{};const char*error=nullptr;
 if(!readNetworkSettings(j,networkSettings,candidate,error))networkMessage=error;
 else if(!networkStoreReady||networkPrefs.putBytes("cfg",&candidate,sizeof(candidate))!=sizeof(candidate))networkMessage="No se pudo guardar configuracion en NVS";
 else{networkSettings=candidate;networkConfigured=true;networkCancel=networkBusy();networkNext=now+2000;networkMessage=candidate.enabled?"Guardado; proximo envio automatico":"Guardado; subida desactivada";}
 networkStatusPending=true;return true;
}
void sendNetworkStatus(uint32_t now){
 if(!networkStatusPending&&now-networkStatusAt<2000)return;
 String s="{\"kind\":\"network\",\"configured\":"+String(networkConfigured?"true":"false")+",\"ssid\":"+quote(networkSettings.ssid)+",\"hasPassword\":"+String(networkSettings.password[0]?"true":"false")+",\"enabled\":"+String(networkSettings.enabled?"true":"false")+",\"endpoint\":"+quote(networkSettings.endpoint)+",\"interval\":"+String(networkSettings.intervalSeconds)+",\"busy\":"+String(networkBusy()?"true":"false")+",\"phase\":"+quote(networkPhaseText())+",\"message\":"+quote(networkMessage)+",\"http\":"+String(networkLastHttp)+",\"successes\":"+String(networkSuccesses)+"}";
 if(emit(s)){networkStatusAt=now;networkStatusPending=false;}
}
String cloudClassJson(const DeviceClass&c){return String(",\"deviceType\":")+quote(deviceKey(c.kind))+",\"deviceLabel\":"+quote(deviceLabel(c.kind))+",\"classLevel\":"+quote(c.level)+",\"classEvidence\":"+quote(c.evidence);}
String buildCloudPayload(uint32_t now){
 size_t ids[MAX_RECORDS];for(size_t i=0;i<rowCount;i++)ids[i]=i;
 std::sort(ids,ids+rowCount,[](size_t a,size_t b){return rows[a].ema>rows[b].ema;});
 size_t clients=0,aps=0,sentClients=0,sentAps=0;
 for(size_t i=0;i<rowCount;i++)if(recent(now,rows[i].last)){if(rows[i].value.source&AP)aps++;else if(rows[i].value.source&CLIENT)clients++;}
 String s; s.reserve(18000);
 s="{\"version\":\"7.5\",\"sensor\":"+quote(macText(ownMac))+",\"ciclo_id\":"+quote(String(bootId)+"-"+String(++networkSequence))+",\"duracion_s\":60,\"total_detectado\":"+String(clients)+",\"routers\":"+String(aps)+",\"equipos_detectados\":[";
 for(size_t k=0;k<rowCount&&sentClients<24;k++){auto&r=rows[ids[k]];auto&v=r.value;if(!recent(now,r.last)||(v.source&AP)||!(v.source&CLIENT))continue;
 if(sentClients++)s+=',';
 s+="{\"mac\":"+quote(macText(v.mac))+",\"rssi\":"+String(int(r.ema))+",\"rssi_ultimo\":"+String(v.rssi)+",\"canal\":"+String(v.channel)+",\"paquetes\":"+String(1)+",\"visible_s\":0,\"tipo\":\"Cliente Wi-Fi\",\"fabricante_wps\":"+quote(r.wpsConflict?"":v.wps.manufacturer)+",\"modelo_wps\":"+quote(r.wpsConflict?"":v.wps.model)+",\"nombre_anunciado\":"+quote(v.p2p.name[0]?v.p2p.name:v.wps.name)+cloudClassJson(classifyWifi(r))+"}";
 }
 s+="],\"routers_detectados\":[";
 for(size_t k=0;k<rowCount&&sentAps<16;k++){auto&r=rows[ids[k]];auto&v=r.value;if(!recent(now,r.last)||!(v.source&AP))continue;if(sentAps++)s+=',';
 s+="{\"mac\":"+quote(macText(v.mac))+",\"rssi\":"+String(int(r.ema))+",\"canal\":"+String(v.channel)+",\"beacons\":"+String(1)+",\"ssid\":"+quote(v.ssid)+",\"fabricante_wps\":"+quote(r.wpsConflict?"":v.wps.manufacturer)+",\"modelo_wps\":"+quote(r.wpsConflict?"":v.wps.model)+",\"seguridad\":"+quote(securityText(v.capabilities))+",\"wifi\":"+String(v.capabilities.generation)+cloudClassJson(classifyWifi(r))+"}";
 }
 s+="],\"clientes_enviados\":"+String(sentClients)+",\"routers_enviados\":"+String(sentAps)+",\"estadisticas_acumuladas\":true}";
 if(s.length()>30000)return "";return s;
}
void cloudWorker(void*){
 int code=-1;
 {WiFiClientSecure client;client.setCACert(CLOUD_CA);client.setHandshakeTimeout(5);
 HTTPClient http;http.setConnectTimeout(4000);http.setTimeout(4000);http.setReuse(false);
 if(http.begin(client,networkTarget)){http.addHeader("Content-Type","application/json");code=http.POST(reinterpret_cast<uint8_t*>(const_cast<char*>(networkPayload.c_str())),networkPayload.length());http.end();}}
 networkWorkerCode.store(code);networkWorkerDone.store(true);vTaskDelete(nullptr);
}
void finishNetwork(uint32_t now,const String &message){
 WiFi.disconnect(false,false);networkPhase=0;networkCancel=false;networkAbortIssued=false;networkMessage=message;networkPayload="";networkTarget="";networkStatusPending=true;networkNext=now+networkSettings.intervalSeconds*1000u;
 radioReady=startWifi();
}
void networkTick(uint32_t now){
 if(networkPhase==4){
  if(networkCancel||now-networkAt>=10000){lanState="error";lanMessage="No se pudo conectar o se cancelo la busqueda";finishNetwork(now,lanMessage);return;}
  if(WiFi.status()==WL_CONNECTED){networkPhase=5;lanState="scanning";lanMessage="Consultando mDNS y SSDP/UPnP (hasta 35 segundos)";if(ESP.getFreeHeap()<30000||xTaskCreate(lanWorker,"orbita_lan",8192,nullptr,1,nullptr)!=pdPASS){lanState="error";lanMessage="Sin memoria para busqueda LAN";finishNetwork(now,lanMessage);}}return;
 }
 if(networkPhase==5){if(lanDone.load()){
  if(lanError.load()||networkCancel){lanState="error";lanMessage="Busqueda LAN no completada";lanCount=0;}
  else{lanCount=lanWorkCount;lanState="done";logLanSnapshot();lanMessage=String(lanCount)+" servicios anunciados; no es inventario completo"+(lanLimited?String(". Resultados parciales por limites de recursos"):String(""));}
  finishNetwork(now,lanMessage);
 }return;}

 if(networkPhase==3){
  if(networkWorkerDone.load()){int code=networkWorkerCode.load();networkLastHttp=code;if(code>=200&&code<300)networkSuccesses++;finishNetwork(now,networkCancel?"Operacion cancelada":code>=200&&code<300?"Envio correcto; captura reanudada":String("Fallo HTTPS ")+String(code)+"; captura reanudada");}
  else if((networkCancel||now-networkAt>14000)&&!networkAbortIssued){networkAbortIssued=true;WiFi.disconnect(false,false);networkMessage="Cerrando envio; se espera fin del cliente TLS";networkStatusPending=true;}
  return;
 }
 if(networkBusy()&&networkCancel){finishNetwork(now,"Configuracion aplicada; captura reanudada");return;}
 if(networkPhase==1){
  if(WiFi.status()==WL_CONNECTED){if(networkOnlyTest){finishNetwork(now,"Conexion Wi-Fi comprobada; captura reanudada");return;}if(clockValid())networkPhase=2;else{configTime(0,0,"pool.ntp.org","time.google.com");networkPhase=2;}networkAt=now;networkStatusPending=true;}
  else if(now-networkAt>=8000)finishNetwork(now,"No se pudo conectar; revisa SSID/clave/cobertura 2.4 GHz");
  return;
 }
 if(networkPhase==2){
  if(clockValid()){
   if(ESP.getFreeHeap()<55000){finishNetwork(now,"Sin RAM suficiente para TLS; se conserva registro local");return;}
   networkTarget=networkSettings.endpoint;networkWorkerDone.store(false);networkWorkerCode.store(0);networkPhase=3;networkAt=now;networkStatusPending=true;
   if(xTaskCreate(cloudWorker,"orbita_https",8192,nullptr,1,nullptr)!=pdPASS)finishNetwork(now,"No se pudo crear tarea HTTPS");
  }else if(now-networkAt>=8000)finishNetwork(now,"Sin fecha para validar HTTPS; se conserva registro local");
  return;
 }
 if(bleSelected||bleScanning.load()||bleStartPending.load()||!networkConfigured||(!networkForceTest&&!networkSettings.enabled)||!radioReady||exporting)return;
 if(!networkForceTest&&int32_t(now-networkNext)<0)return;
 networkOnlyTest=networkForceTest;networkForceTest=false;
 if(!networkOnlyTest){networkPayload=buildCloudPayload(now);if(!networkPayload.length()){networkMessage="Carga demasiado grande; se conserva registro local";networkNext=now+networkSettings.intervalSeconds*1000u;networkStatusPending=true;return;}}
 accepting.store(false);esp_wifi_set_promiscuous(false);networkPhase=1;networkAt=now;networkCancel=false;networkAbortIssued=false;networkStatusPending=true;networkMessage=networkOnlyTest?"Probando tu red; escucha temporalmente pausada":"Subiendo snapshot; escucha temporalmente pausada";
 WiFi.begin(networkSettings.ssid,networkSettings.password);
}
