#pragma once
#include "config.h"
#include "announcements.h"
#include "ap_capabilities.h"
#include "wifi_fingerprint.h"
namespace detector {
enum Source:uint8_t {AP=1,CLIENT=2,OTHER=4};
struct Event {uint8_t mac[6]{},channel=0,source=0;int8_t rssi=0;uint32_t time=0;char ssid[33]{};WpsInfo wps;P2pInfo p2p;ApCapabilities capabilities;WifiFingerprint fingerprint;bool probe=false;};
struct Record {Event value;float ema=0;uint32_t frames=0,last=0,probes=0;bool dirty=true,logged=false,wpsConflict=false,typeConflict=false;uint8_t loggedActivity=255;};
inline bool unicast(const uint8_t *m){uint8_t any=0;for(size_t i=0;i<6;i++)any|=m[i];return any&&!(m[0]&1);}
inline bool recent(uint32_t now,uint32_t last){return uint32_t(now-last)<ACTIVE_TTL_MS;}
inline uint8_t activity(uint32_t now,uint32_t last){auto age=uint32_t(now-last);return age<JUST_SEEN_MS?0:age<ACTIVE_TTL_MS?1:2;}
inline bool parseFrame(const uint8_t *p,size_t n,int8_t rssi,uint8_t channel,uint32_t now,Event &e){
 if(!p||n<24||(p[0]&3)||channel<FIRST_CHANNEL||channel>LAST_CHANNEL||!unicast(p+10))return false;
 uint8_t type=(p[0]>>2)&3,sub=p[0]>>4;size_t ies=0;uint8_t source=OTHER;
 if(type==0){
  if(sub==4){ies=24;source=CLIENT;}
  else if(sub==8||sub==5){if(n<36)return false;ies=36;source=AP;}
  else if(sub==0||sub==2){ies=sub==0?28:34;if(n<ies)return false;source=CLIENT;}
  else if(sub==1||sub==3){ies=30;if(n<ies)return false;source=AP;}
  else if(sub==13&&n>=32&&p[24]==4&&p[25]==9&&!memcmp(p+26,"\x50\x6f\x9a\x09",4))ies=32;
  else if(sub==10||sub==12){if(n<26)return false;source=!memcmp(p+10,p+16,6)?AP:CLIENT;}
  else return false;
 }else if(type==2){bool to=p[1]&1,from=p[1]&2;size_t header=24+(to&&from?6:0)+(sub&8?2:0);if(n<header)return false;if(to&&!from)source=CLIENT;else if(from&&!to)source=AP;
 }else return false;
 e={};memcpy(e.mac,p+10,6);e.channel=channel;e.rssi=rssi;e.time=now;e.source=source;
 if((sub==8||sub==5)&&type==0)parseCapabilities(p,n,e.capabilities);
 if(type==0&&sub==4){e.probe=true;if(!probeFingerprint(p+ies,n-ies,e.fingerprint))return false;}
 if(ies){if(!parseAnnouncements(p+ies,n-ies,e.wps,e.p2p))return false;
  if(source==AP)for(size_t at=ies;at<n;){uint8_t id=p[at],len=p[at+1];at+=2;if(id==0){for(size_t i=0;i<len;i++)e.ssid[i]=p[at+i]>=32&&p[at+i]<=126?char(p[at+i]):'?';e.ssid[len]=0;}at+=len;}
 }
 return true;
}
inline int upsertWifi(Record *rows,size_t &count,const Event &e){
 size_t i=0;while(i<count&&memcmp(rows[i].value.mac,e.mac,6))i++;
 if(i==count){if(count<MAX_RECORDS)count++;else{size_t oldest=MAX_RECORDS;uint32_t age=0;for(size_t k=0;k<count;k++){uint32_t a=e.time-rows[k].last;if(a>=ACTIVE_TTL_MS&&(oldest==MAX_RECORDS||a>age)){oldest=k;age=a;}}if(oldest==MAX_RECORDS)return -1;i=oldest;}rows[i]={};memcpy(rows[i].value.mac,e.mac,6);}
 auto &r=rows[i];r.value.channel=e.channel;r.value.rssi=e.rssi;r.value.source|=e.source;r.value.time=e.time;r.ema=r.frames?.75f*r.ema+.25f*e.rssi:e.rssi;r.frames++;r.last=e.time;r.dirty=true;
 if(e.probe){r.probes++;r.value.fingerprint=e.fingerprint;}
 if(e.capabilities.present)r.value.capabilities=e.capabilities;
 if(e.ssid[0])strcpy(r.value.ssid,e.ssid);
 if(e.wps.present&&!e.wps.invalid){
 const char *before[]={r.value.wps.manufacturer,r.value.wps.model,r.value.wps.number},*after[]={e.wps.manufacturer,e.wps.model,e.wps.number};for(size_t k=0;k<3;k++)if(before[k][0]&&after[k][0]&&strcmp(before[k],after[k]))r.wpsConflict=true;
 if(e.wps.hasType){if(r.value.wps.hasType&&memcmp(r.value.wps.deviceType,e.wps.deviceType,8))r.typeConflict=true;memcpy(r.value.wps.deviceType,e.wps.deviceType,8);r.value.wps.hasType=true;}
 if(e.wps.name[0])strcpy(r.value.wps.name,e.wps.name);if(e.wps.manufacturer[0])strcpy(r.value.wps.manufacturer,e.wps.manufacturer);if(e.wps.model[0])strcpy(r.value.wps.model,e.wps.model);if(e.wps.number[0])strcpy(r.value.wps.number,e.wps.number);r.value.wps.present=true;}
 if(e.p2p.present&&!e.p2p.invalid){if(e.p2p.name[0])strcpy(r.value.p2p.name,e.p2p.name);if(e.p2p.hasType){if(r.value.p2p.hasType&&memcmp(r.value.p2p.deviceType,e.p2p.deviceType,8))r.typeConflict=true;memcpy(r.value.p2p.deviceType,e.p2p.deviceType,8);r.value.p2p.hasType=true;}r.value.p2p.present=true;}
 return int(i);
}
struct CountSummary {size_t wifi=0,ble=0,aps=0,clients=0;bool wifiCapacity=false,bleCapacity=false;};
}
