#include "../DetectorTiempoReal/device_classifier.h"
#include <cassert>
#include <vector>
#include <iostream>
using namespace detector;
int main(){
 uint8_t ies[]={0,3,'a','b','c',1,2,0x82,0x84,45,2,1,2,221,5,0,0x50,0xf2,4,99};
 WifiFingerprint a,b;assert(probeFingerprint(ies,sizeof ies,a)&&a.complete);ies[2]='z';ies[sizeof ies-1]=33;assert(probeFingerprint(ies,sizeof ies,b)&&b.complete);assert(a.size==b.size&&!memcmp(a.bytes,b.bytes,a.size));
 ies[7]=0x96;assert(probeFingerprint(ies,sizeof ies,b));assert(memcmp(a.bytes,b.bytes,a.size));
 assert(!probeFingerprint(ies,sizeof ies-1,b));assert(!b.complete);
 std::vector<uint8_t> many;for(int i=0;i<60;i++){many.push_back(1);many.push_back(1);many.push_back(0x82);}assert(probeFingerprint(many.data(),many.size(),b)&&!b.complete&&b.size<=96);
 uint8_t frame[64]{};frame[0]=0x40;frame[10]=0x80;frame[15]=1;memcpy(frame+24,ies,sizeof ies);Event e;assert(parseFrame(frame,24+sizeof ies,-45,6,100,e)&&e.probe&&e.fingerprint.complete);
 Record rows[MAX_RECORDS]{};size_t n=0;assert(upsertWifi(rows,n,e)==0);assert(rows[0].probes==1&&rows[0].ema==-45);e.time=200;e.rssi=-65;upsertWifi(rows,n,e);assert(rows[0].probes==2&&rows[0].ema==-50);
 auto saved=rows[0].value.fingerprint;frame[0]=8;frame[1]=1;assert(parseFrame(frame,24,-60,6,300,e)&&!e.probe);upsertWifi(rows,n,e);assert(rows[0].probes==2&&!memcmp(saved.bytes,rows[0].value.fingerprint.bytes,saved.size));
 assert(classifyWifi(rows[0]).kind==DeviceKind::unknown);strcpy(rows[0].value.ssid,"iPhone");assert(classifyWifi(rows[0]).kind==DeviceKind::unknown);strcpy(rows[0].value.wps.name,"MacBook Pro");assert(classifyWifi(rows[0]).kind==DeviceKind::laptop);
 std::cout<<"OK: TLV bounds, truncation rejection, SSID exclusion, capabilities, probes, smoothing, unknown/model hints\n";
}
