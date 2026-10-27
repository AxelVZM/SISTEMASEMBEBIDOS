#pragma once
#include <WiFiUdp.h>
#include "ssdp_core.h"
void discoverSsdp(){
 if(ESP.getFreeHeap()<20000){lanLimited=true;return;}
 WiFiUDP udp;if(!udp.begin(0))return;
 const char query[]="M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 1\r\nST: upnp:rootdevice\r\n\r\n";
 udp.beginPacket(IPAddress(239,255,255,250),1900);udp.write((const uint8_t*)query,sizeof(query)-1);udp.endPacket();
 LocalDescription targets[6]{};size_t count=0;uint32_t started=millis();
 IPAddress own=WiFi.localIP(),mask=WiFi.subnetMask();uint8_t local[4],subnet[4];for(int i=0;i<4;i++){local[i]=own[i];subnet[i]=mask[i];}
 while(millis()-started<2200){int n=udp.parsePacket();if(!n){vTaskDelay(pdMS_TO_TICKS(10));continue;}
  if(n>1023){while(udp.available())udp.read();continue;}
  IPAddress sender=udp.remoteIP();uint8_t peer[4];for(int i=0;i<4;i++)peer[i]=sender[i];
  char packet[1024]{},url[384]{};int got=udp.read((uint8_t*)packet,sizeof(packet)-1);if(got!=n||memchr(packet,0,got))continue;LocalDescription target;
  if(!ssdpLocation(packet,url,sizeof(url))||!localDescriptionUrl(url,peer,local,subnet,target))continue;
  bool duplicate=false;for(size_t i=0;i<count;i++)if(!memcmp(target.ip,targets[i].ip,4)&&target.port==targets[i].port&&!strcmp(target.path,targets[i].path))duplicate=true;
  if(!duplicate){if(count<6)targets[count++]=target;else lanLimited=true;}
 }
 udp.stop();char*xml=new(std::nothrow) char[8193];if(!xml){lanLimited=true;return;}
 for(size_t i=0;i<count&&lanWorkCount<24;i++){
  auto&t=targets[i];IPAddress ip(t.ip[0],t.ip[1],t.ip[2],t.ip[3]);
  WiFiClient client;HTTPClient http;http.useHTTP10(true);http.setConnectTimeout(700);http.setTimeout(900);http.setReuse(false);http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  String url=String("http://")+ip.toString()+":"+String(t.port)+t.path;
  if(!http.begin(client,url))continue;const char*headers[]={"Transfer-Encoding"};http.collectHeaders(headers,1);
  int code=http.GET(),length=http.getSize();
  if(code==200&&length>0&&length<=8192&&http.header("Transfer-Encoding").isEmpty()){
   auto*stream=http.getStreamPtr();size_t used=0;uint32_t at=millis();
   while(used<size_t(length)&&millis()-at<1200){int available=stream->available();if(available>0){int got=stream->read((uint8_t*)xml+used,std::min(size_t(available),size_t(length)-used));if(got>0)used+=got;else break;}else if(!stream->connected())break;else vTaskDelay(pdMS_TO_TICKS(5));}
   if(used==size_t(length)&&!memchr(xml,0,used)){xml[used]=0;LanEntry e;strcpy(e.service,"SSDP/UPnP");strncpy(e.ip,ip.toString().c_str(),sizeof(e.ip)-1);e.port=t.port;
    if(upnpDescription(xml,e)){e.last=millis();lanRows[lanWorkCount++]=e;}
   }
  }
  http.end();
 }
 delete[]xml;if(lanWorkCount==24)lanLimited=true;
}
