#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>
#include "../DetectorTiempoReal/device_classifier.h"
using namespace detector;
void type(uint8_t*t,uint16_t c,uint16_t s){uint8_t v[]={uint8_t(c>>8),uint8_t(c),0,0x50,0xf2,4,uint8_t(s>>8),uint8_t(s)};memcpy(t,v,8);}
int main(){
 Record r;r.value.source=CLIENT;r.value.mac[0]=0x8e;
 assert(classifyWifi(r).kind==DeviceKind::unknown);
 strcpy(r.value.ssid,"iPhone MacBook Proyector");assert(classifyWifi(r).kind==DeviceKind::unknown); // Never use SSID to label a client.
 strcpy(r.value.wps.manufacturer,"Apple Inc.");assert(classifyWifi(r).kind==DeviceKind::unknown); // Nor OUI/manufacturer alone.
 strcpy(r.value.wps.name,"MacBook Pro");assert(classifyWifi(r).kind==DeviceKind::laptop&&!strcmp(classifyWifi(r).level,"hint"));
 strcpy(r.value.wps.name,"Canon");assert(classifyWifi(r).kind==DeviceKind::unknown); // Canon brand is not a projector.
 strcpy(r.value.wps.name,"iPhone13");assert(classifyWifi(r).kind==DeviceKind::phone);
 strcpy(r.value.wps.name,"iphone projector");assert(!strcmp(classifyWifi(r).level,"conflict"));r.value.wps.name[0]=0;
 r.value.source=AP;assert(classifyWifi(r).kind==DeviceKind::ap&&!strcmp(classifyWifi(r).level,"role"));
 r.value.wps.hasType=true;type(r.value.wps.deviceType,7,3);assert(classifyWifi(r).kind==DeviceKind::projector);
 type(r.value.wps.deviceType,1,5);assert(classifyWifi(r).kind==DeviceKind::laptop);
 r.value.p2p.hasType=true;type(r.value.p2p.deviceType,7,3);assert(!strcmp(classifyWifi(r).level,"conflict"));
 r={};r.value.wps.hasType=true;type(r.value.wps.deviceType,6,2);assert(classifyWifi(r).kind==DeviceKind::router);
 r.value.wps.deviceType[2]=1;assert(classifyWifi(r).kind==DeviceKind::unknown);
 // Attribute 0x1054, exact length and duplicate checks.
 uint8_t raw[12]={0x10,0x54,0,8};type(raw+4,7,3);WpsInfo w;parseWps(raw,sizeof raw,w);assert(w.hasType&&!w.invalid&&primaryType(w.deviceType)==DeviceKind::projector);
 raw[3]=7;parseWps(raw,sizeof raw,w);assert(w.invalid&&!w.hasType);raw[3]=8;
 std::vector<uint8_t> twice(raw,raw+12);type(raw+4,1,5);twice.insert(twice.end(),raw,raw+12);parseWps(twice.data(),twice.size(),w);assert(w.invalid);
 Record rows[MAX_RECORDS]{};size_t n=0;Event e;e.mac[0]=0x80;e.mac[5]=1;e.wps.present=true;e.wps.hasType=true;type(e.wps.deviceType,1,5);upsertWifi(rows,n,e);assert(classifyWifi(rows[0]).kind==DeviceKind::laptop);type(e.wps.deviceType,7,3);upsertWifi(rows,n,e);assert(rows[0].typeConflict&&!strcmp(classifyWifi(rows[0]).level,"conflict"));
 n=0;Event p;p.mac[0]=0x80;p.mac[5]=2;p.p2p.present=p.p2p.hasType=true;type(p.p2p.deviceType,7,3);upsertWifi(rows,n,p);assert(rows[0].value.p2p.hasType&&classifyWifi(rows[0]).kind==DeviceKind::projector);
 BleEvent b;b.mac[0]=0xc3;uint8_t adv[]={3,0x19,3,0x0a};assert(parseAdvertisement(adv,sizeof adv,b));BleRecord br[MAX_BLE_RECORDS]{};size_t nb=0;upsertBle(br,nb,b);assert(classifyBle(br[0]).kind==DeviceKind::projector);
 b.appearance=0x83;upsertBle(br,nb,b);assert(br[0].appearanceConflict&&!strcmp(classifyBle(br[0]).level,"conflict"));
 assert(appearanceType(0x83)==DeviceKind::laptop);assert(appearanceType(0x40)==DeviceKind::phone);assert(appearanceType(0x87)==DeviceKind::tablet);assert(appearanceType(0xa01)==DeviceKind::tv);assert(appearanceType(0x3c1)==DeviceKind::peripheral);
 std::cout<<"OK: WPS/P2P/BLE, celular/laptop/router/proyector/otros, nombres posibles, conflictos, SSID/OUI no usados, limites TLV.\n";
}
