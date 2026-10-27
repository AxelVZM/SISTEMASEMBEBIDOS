#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include "announcements.h"
#include "ble_models.h"
namespace detector {
constexpr size_t MAX_BLE_RECORDS=32;
struct BleEvent {BleModel model;bool modelConflict=false;uint8_t mac[6]{},addressType=0;int8_t rssi=0;uint32_t time=0;char name[65]{};uint16_t company=0,appearance=0;bool hasCompany=false,hasAppearance=false,hasDis=false,companyConflict=false;};
struct BleRecord {BleEvent value;float ema=0;uint32_t frames=0,last=0;bool dirty=true,modelConflict=false,companyConflict=false,appearanceConflict=false;};
inline bool parseAdvertisement(const uint8_t *p,size_t n,BleEvent &out){
 if(!p&&n)return false;bool completeName=false,companyConflict=false;
 for(size_t i=0;i<n;){uint8_t len=p[i++];if(!len)break;if(len>n-i||len<1)return false;uint8_t type=p[i];const uint8_t *v=p+i+1;size_t size=len-1;
  if(type==8||type==9){char name[65]{};if(copyUtf8(name,sizeof(name),v,size)&&(type==9||!completeName)){strcpy(out.name,name);if(type==9)completeName=true;}}
  if(type==0xff&&size>=2){uint16_t company=v[0]|(uint16_t(v[1])<<8);if(out.hasCompany&&out.company!=company)companyConflict=true;if(!companyConflict){out.hasCompany=true;out.company=company;}else{out.hasCompany=false;out.companyConflict=true;}}
  if(type==0x19&&size==2){if(out.hasAppearance&&out.appearance!=(v[0]|(uint16_t(v[1])<<8)))return false;out.hasAppearance=true;out.appearance=v[0]|(uint16_t(v[1])<<8);}
  if((type==2||type==3)&&size%2==0)for(size_t k=0;k<size;k+=2)if(v[k]==0x0a&&v[k+1]==0x18)out.hasDis=true;
  auto model=decodeBleModel(type,v,size);if(model.format){if(out.model.format&&!sameModel(out.model,model))out.modelConflict=true;else out.model=model;}
  i+=len;
 }
 return true;
}
inline int upsertBle(BleRecord *rows,size_t &count,const BleEvent &e){
 if(e.addressType>3)return -1;uint8_t any=0,all=255;for(auto c:e.mac){any|=c;all&=c;}if(!any||all==255)return -1;
 size_t i=0;while(i<count&&(memcmp(rows[i].value.mac,e.mac,6)||rows[i].value.addressType!=e.addressType))i++;
 if(i==count){if(count<MAX_BLE_RECORDS)count++;else{size_t target=MAX_BLE_RECORDS;uint32_t oldest=0;for(size_t k=0;k<count;k++){uint32_t age=e.time-rows[k].last;if(age>=60000&&(target==MAX_BLE_RECORDS||age>oldest)){oldest=age;target=k;}}if(target==MAX_BLE_RECORDS)return -1;i=target;}rows[i]={};memcpy(rows[i].value.mac,e.mac,6);rows[i].value.addressType=e.addressType;rows[i].ema=e.rssi;}
 auto &r=rows[i];r.modelConflict|=e.modelConflict;if(e.model.format){if(r.value.model.format&&!sameModel(r.value.model,e.model))r.modelConflict=true;else r.value.model=e.model;}r.companyConflict|=e.companyConflict;{r.ema=r.frames?.75f*r.ema+.25f*e.rssi:e.rssi;r.frames++;r.last=e.time;if(e.name[0])strcpy(r.value.name,e.name);if(e.hasCompany){if(r.value.hasCompany&&r.value.company!=e.company)r.companyConflict=true;r.value.hasCompany=true;r.value.company=e.company;}if(e.hasAppearance){if(r.value.hasAppearance&&r.value.appearance!=e.appearance)r.appearanceConflict=true;r.value.hasAppearance=true;r.value.appearance=e.appearance;}r.value.hasDis|=e.hasDis;}
 r.dirty=true;return int(i);
}
}
