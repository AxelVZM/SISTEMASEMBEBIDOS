#pragma once
#include "lan_core.h"
LanEntry*lanRows=nullptr;size_t lanCount=0,lanWorkCount=0,lanCursor=0;
uint32_t lanScan=0;bool lanLimited=false;std::atomic<bool> lanDone{false};std::atomic<int> lanError{0};
String lanState="idle",lanMessage="Busca servicios anunciados en tu red local";
#include "ssdp_runtime.h"
void lanWorker(void*){
 lanWorkCount=0;lanError.store(0);lanLimited=false;
 if(mdns_init()!=ESP_OK){lanLimited=true;discoverSsdp();lanDone.store(true);vTaskDelete(nullptr);return;}
 char hostname[40];snprintf(hostname,sizeof(hostname),"orbita-%08lx",(unsigned long)bootId);mdns_hostname_set(hostname);
 const char*services[]={"_device-info","_airplay","_googlecast","_ipp","_ipps","_printer","_pdl-datastream","_raop","_smb","_http"};
 for(auto*service:services){mdns_result_t*results=nullptr;
  esp_err_t err=mdns_query_ptr(service,"_tcp",1200,8,&results);
  if(err==ESP_OK)for(auto*p=results;p;p=p->next){
   if(lanWorkCount>=24){lanLimited=true;break;}auto&e=lanRows[lanWorkCount];e={};
   if(p->instance_name)copyUtf8(e.name,sizeof(e.name),(const uint8_t*)p->instance_name,strlen(p->instance_name));
   if(p->hostname)copyUtf8(e.host,sizeof(e.host),(const uint8_t*)p->hostname,strlen(p->hostname));
   strncpy(e.service,service,sizeof(e.service)-1);e.port=p->port;
   for(auto*a=p->addr;a;a=a->next)if(a->addr.type==MDNS_IP_PROTOCOL_V4){String ip=IPAddress(a->addr.u_addr.ip4.addr).toString();strncpy(e.ip,ip.c_str(),sizeof(e.ip)-1);break;}
   for(size_t i=0;i<p->txt_count;i++){const auto&t=p->txt[i];if(t.value)lanTxt(e,t.key,(const uint8_t*)t.value,p->txt_value_len?p->txt_value_len[i]:strlen(t.value));}
   e.last=millis();lanWorkCount++;
  }
  if(results)mdns_query_results_free(results);
 }
 mdns_free();discoverSsdp();lanDone.store(true);vTaskDelete(nullptr);
}
String discoveryStatus(){return String(",\"bleSelected\":")+(bleSelected?"true":"false")+",\"lanScan\":"+String(lanScan)+",\"lanCount\":"+String(lanCount)+",\"lanState\":"+quote(lanState)+",\"lanMessage\":"+quote(lanMessage);}
void sendLanRows(){
 if(lanState!="done")return;
 for(size_t tries=0;tries<lanCount&&serialBudget>1000;tries++){
 size_t i=lanCursor;lanCursor=(i+1)%lanCount;auto&r=lanRows[i];if(!r.dirty)continue;
 String s="{\"kind\":\"lan\",\"b\":"+String(bootId)+",\"slot\":"+String(i)+",\"scan\":"+String(lanScan)+",\"name\":"+quote(r.name)+",\"host\":"+quote(r.host)+",\"ip\":"+quote(r.ip)+",\"service\":"+quote(r.service)+",\"port\":"+String(r.port)+",\"brand\":"+quote(r.identityConflict?"":canonicalBrand(r.brand))+",\"model\":"+quote(r.identityConflict?"":r.model)+",\"evidence\":"+quote(!strcmp(r.service,"SSDP/UPnP")?String(r.evidence):r.evidence[0]?String("mDNS TXT: ")+r.evidence:String("mDNS; sin modelo anunciado"))+",\"last\":"+String(r.last)+String(",\"modelCode\":")+quote(r.modelCode)+",\"resolvedModel\":"+quote(!r.identityConflict&&compatibleModel(r.brand,r.model)?compatibleModel(r.brand,r.model)->name:!r.identityConflict&&compatibleModel(r.brand,r.modelCode)?compatibleModel(r.brand,r.modelCode)->name:"")+classJson(classifyLan(r))+"}";
 if(!emit(s)){lanCursor=i;break;}r.dirty=false;
 }
}

void logLanSnapshot(){
 for(size_t i=0;i<lanCount;i++){const auto&r=lanRows[i];auto cls=classifyLan(r);String cells[16]={"observacion",String(bootId),String(r.last),utcNow(),"LAN",r.ip,r.name,"busqueda_puntual","","","","",r.evidence,r.identityConflict?"":canonicalBrand(r.brand),r.identityConflict?"":r.model,r.service};
 cells[15]+=String("; tipo=")+deviceLabel(cls.kind)+"; nivel="+cls.level+"; evidencia="+cls.evidence+"; codigo="+r.modelCode;
 if(!appendLog(csvRow(cells,16)))break;
 }
 flushLog();
}
