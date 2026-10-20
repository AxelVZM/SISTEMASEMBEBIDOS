#include "../DetectorTiempoReal/count_core.h"
#include "../DetectorTiempoReal/ble_core.h"
#include <cassert>
#include <random>
#include <iostream>
using namespace detector;
int main(){
 uint8_t p[128]{};p[0]=0x40;p[10]=0x90;p[15]=1;Event e;assert(parseFrame(p,24,-60,6,100,e)&&e.source==CLIENT);assert(!parseFrame(p,23,-60,6,100,e));assert(!parseFrame(p,24,-60,12,100,e));p[10]=0x91;assert(!parseFrame(p,24,-60,6,100,e));p[10]=0x90;
 p[0]=0x80;p[36]=0;p[37]=4;memcpy(p+38,"Test",4);assert(parseFrame(p,42,-45,1,150,e)&&e.source==AP&&!strcmp(e.ssid,"Test"));assert(!parseFrame(p,41,-45,1,150,e));p[37]=33;assert(!parseFrame(p,71,-45,1,150,e));
 p[0]=0x08;p[1]=1;assert(parseFrame(p,24,-70,11,200,e)&&e.source==CLIENT);p[1]=2;assert(parseFrame(p,24,-70,11,200,e)&&e.source==AP);p[1]=3;assert(!parseFrame(p,24,-70,11,200,e));assert(parseFrame(p,30,-70,11,200,e)&&e.source==OTHER);
 Record rows[MAX_RECORDS]{};size_t count=0;e={};e.mac[0]=0x90;e.mac[5]=1;e.rssi=-60;e.channel=1;e.time=100;assert(upsertWifi(rows,count,e)==0&&rows[0].ema==-60);e.rssi=-40;e.time=200;assert(upsertWifi(rows,count,e)==0&&rows[0].ema==-55&&count==1);assert(recent(60199,rows[0].last));assert(!recent(60200,rows[0].last));assert(activity(10200,rows[0].last)==1);
 for(size_t i=1;i<MAX_RECORDS;i++){e.mac[5]=i+1;assert(upsertWifi(rows,count,e)>=0);}e.mac[4]=1;assert(upsertWifi(rows,count,e)==-1&&count==MAX_RECORDS);e.time=60200;assert(upsertWifi(rows,count,e)>=0&&count==MAX_RECORDS&&rows[0].frames==1);assert(recent(16,0xfffffff0));
 e.time=60300;strcpy(e.wps.manufacturer,"A");e.wps.present=true;int slot=upsertWifi(rows,count,e);assert(slot>=0);strcpy(e.wps.manufacturer,"B");upsertWifi(rows,count,e);assert(rows[slot].wpsConflict);
 BleEvent b;uint8_t ad[]={3,8,'a','b',5,9,'T','e','s','t',3,8,'x','y',3,255,0x4c,0};assert(parseAdvertisement(ad,sizeof(ad),b)&&!strcmp(b.name,"Test")&&b.hasCompany&&b.company==76);uint8_t bad[]={4,9,'A'};assert(!parseAdvertisement(bad,sizeof(bad),b));uint8_t conflict[]={3,255,1,0,3,255,2,0,3,255,3,0};b={};assert(parseAdvertisement(conflict,sizeof(conflict),b)&&!b.hasCompany&&b.companyConflict);
 BleRecord br[MAX_BLE_RECORDS]{};size_t bc=0;b={};b.mac[0]=0xc3;b.mac[5]=1;b.addressType=1;b.time=10;b.rssi=-50;assert(upsertBle(br,bc,b)==0);b.addressType=0;assert(upsertBle(br,bc,b)==1&&bc==2);for(size_t i=2;i<MAX_BLE_RECORDS;i++){b.mac[5]=i;assert(upsertBle(br,bc,b)>=0);}b.mac[4]=1;assert(upsertBle(br,bc,b)==-1);b.time=60010;assert(upsertBle(br,bc,b)>=0&&bc==32);
 std::mt19937 rng(7);for(int t=0;t<50000;t++){for(auto &v:p)v=uint8_t(rng());size_t n=rng()%129;parseFrame(p,n,-60,1,0,e);b={};parseAdvertisement(p,n,b);}
 std::cout<<"OK: frame bounds, TA/roles, SSID, EMA, TTL/rollover, 96 WiFi/32 BLE capacities, stale replacement, BLE address types/names/conflicts; 50000 malformed/random inputs\n";
}
