#include "../DetectorTiempoReal/device_classifier.h"
#include "../DetectorTiempoReal/lan_core.h"
#include <cassert>
#include <vector>
#include <iostream>
using namespace detector;
std::vector<uint8_t> apple(uint16_t id){std::vector<uint8_t> a(31,0);a[0]=30;a[1]=0xff;a[2]=0x4c;a[4]=7;a[5]=25;a[6]=1;a[7]=id&255;a[8]=id>>8;return a;}
int main(){
 for(uint16_t id:{0x2002,0x200f,0x200e,0x2014,0x2024,0x200a,0x2003,0x2005,0x2006}){auto a=apple(id);BleEvent e;assert(parseAdvertisement(a.data(),a.size(),e));assert(e.model.id==id&&bleModelName(e.model)[0]);for(size_t n=1;n<a.size();n++){BleEvent bad;assert(!parseAdvertisement(a.data(),n,bad));}}
 auto a=apple(0xffff);BleEvent u;assert(parseAdvertisement(a.data(),a.size(),u)&&!bleModelName(u.model)[0]);a[2]=0x75;BleEvent foreign;assert(parseAdvertisement(a.data(),a.size(),foreign)&&!foreign.model.format);
 // MiBeacon UUID + frame control v5, data bit and encryption bit, product ID, counter.
 uint8_t mi[]={8,0x16,0x95,0xfe,0x48,0x50,0x5b,0x05,1};BleEvent e;assert(parseAdvertisement(mi,sizeof mi,e)&&e.model.id==0x055b&&e.model.encrypted);assert(!strcmp(bleModelName(e.model),"LYWSD03MMC"));mi[4]|=0x10;BleEvent truncated;assert(parseAdvertisement(mi,sizeof mi,truncated)&&!truncated.model.format);
 BleRecord rows[MAX_BLE_RECORDS]{};size_t count=0;a=apple(0x2002);e={};e.mac[0]=0x80;assert(parseAdvertisement(a.data(),a.size(),e));upsertBle(rows,count,e);assert(classifyBle(rows[0]).kind==DeviceKind::audio);a=apple(0x200f);BleEvent changed;changed.mac[0]=0x80;parseAdvertisement(a.data(),a.size(),changed);upsertBle(rows,count,changed);assert(rows[0].modelConflict&&classifyBle(rows[0]).kind==DeviceKind::unknown);
 LanEntry lan;lanTxt(lan,"name",(const uint8_t*)"iPhone",6);assert(!lan.model[0]&&!lan.brand[0]);lanTxt(lan,"md",(const uint8_t*)"Model-123",9);assert(!strcmp(lan.model,"Model-123")&&!strcmp(lan.evidence,"md"));lanTxt(lan,"manufacturer",(const uint8_t*)"Vendor",6);assert(!strcmp(lan.brand,"Vendor"));
 std::cout<<"OK: nine Apple IDs, MiBeacon, wrong vendor, truncation, unknown/conflicting models, LAN TXT evidence\n";
}
