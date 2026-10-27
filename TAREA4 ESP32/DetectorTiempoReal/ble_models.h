#pragma once
#include <cstdint>
#include <cstddef>
namespace detector {
struct BleModel {uint16_t id=0;uint8_t format=0;bool encrypted=false;};
inline bool sameModel(const BleModel&a,const BleModel&b){return a.id==b.id&&a.format==b.format;}
inline const char* bleModelName(const BleModel&m){
 if(m.format==1)switch(m.id){case 0x2002:return "AirPods 1a generacion";case 0x200f:return "AirPods 2a generacion";case 0x200e:return "AirPods Pro 1a generacion";case 0x2014:return "AirPods Pro 2 Lightning";case 0x2024:return "AirPods Pro 2 USB-C";case 0x200a:return "AirPods Max Lightning";case 0x2003:return "Powerbeats3";case 0x2005:return "BeatsX";case 0x2006:return "Beats Solo3";}
 if(m.format==2)switch(m.id){case 0x0098:return "HHCCJCY01";case 0x015d:return "HHCCPOT002";case 0x02df:return "JQJCY01YM";case 0x0347:case 0x0b48:return "CGG1";case 0x03bc:return "GCLS002";case 0x0576:return "CGD1";case 0x066f:return "CGDK2";case 0x2542:return "LYWSD02MMC";case 0x1203:return "XMWSDJ04MMC";case 0x01aa:return "LYWSDCGQ";case 0x045b:return "LYWSD02";case 0x055b:return "LYWSD03MMC";}
 return "";
}
inline const char* bleModelBrand(const BleModel&m){return m.format==3?"Ruuvi (protocolo)":!bleModelName(m)[0]?"":m.format==2?((m.id==0x0347||m.id==0x0b48||m.id==0x0576||m.id==0x066f)?"Qingping/Cleargrass":m.id==0x03bc?"VegTrug":"Xiaomi/Mijia (ecosistema)"):(m.id==0x2003||m.id==0x2005||m.id==0x2006)?"Beats":"Apple";}
inline BleModel decodeBleModel(uint8_t type,const uint8_t*v,size_t n){
 BleModel m;
 // Ruuvi RAWv2: company 0499 + 24-byte payload, format 05.
 // Identifies sensor telemetry, not Tag versus Pro nor the physical sender.
 if(type==0xff&&n==26&&v[0]==0x99&&v[1]==0x04&&v[2]==5){m.format=3;m.id=5;}
 // Apple manufacturer AD: Company ID 004c, proximity-pairing TLV 07/19, version 01.
 if(type==0xff&&n==29&&v[0]==0x4c&&v[1]==0&&v[2]==7&&v[3]==25&&v[4]==1){m.format=1;m.id=v[5]|uint16_t(v[6])<<8;}
 // MiBeacon service AD: UUID FE95, frame control, product ID, frame counter.
 if(type==0x16&&n>=7&&v[0]==0x95&&v[1]==0xfe&&(v[2]&0x40)&&(v[3]>>4)>=2&&(v[3]>>4)<=5){
  size_t minimum=7+((v[2]&0x10)?6:0)+((v[2]&0x20)?1:0);
  if(n>=minimum){m.format=2;m.id=v[4]|uint16_t(v[5])<<8;m.encrypted=v[2]&8;}
 }
 return m;
}
}
