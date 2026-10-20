#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace detector {
struct P2pInfo {char name[65]{};uint8_t deviceType[8]{};bool present=false,invalid=false,hasType=false;};
struct WpsInfo {char manufacturer[41]{},model[61]{},number[41]{},name[65]{};uint8_t deviceType[8]{};bool hasType=false,present=false,invalid=false;};
inline bool copyUtf8(char *out,size_t cap,const uint8_t *p,size_t n){
 while(n&&(p[n-1]==0||p[n-1]==32))n--;
 if(!n||n>=cap)return false;
 for(size_t i=0;i<n;){uint8_t c=p[i];size_t count;uint32_t code;
  if(c<128){if(c<32||c==127)return false;count=1;code=c;}
  else if(c>=0xc2&&c<=0xdf){count=2;code=c&31;}
  else if(c>=0xe0&&c<=0xef){count=3;code=c&15;}
  else if(c>=0xf0&&c<=0xf4){count=4;code=c&7;}
  else return false;
  if(i+count>n)return false;
  for(size_t j=1;j<count;j++){if((p[i+j]&0xc0)!=0x80)return false;code=(code<<6)|(p[i+j]&63);}
  if((count==3&&code<0x800)||(count==4&&code<0x10000)||(code>=0xd800&&code<=0xdfff)||code>0x10ffff)return false;
  i+=count;
 }
 bool meaningful=false;for(size_t i=0;i<n;i++)if(p[i]>32)meaningful=true;if(!meaningful)return false;
 memcpy(out,p,n);out[n]=0;return true;
}
inline void parseWps(const uint8_t *p,size_t n,WpsInfo &out){
 WpsInfo result{};result.present=true;
 for(size_t i=0;i<n;){if(n-i<4){result.invalid=true;break;}uint16_t type=(uint16_t(p[i])<<8)|p[i+1],len=(uint16_t(p[i+2])<<8)|p[i+3];i+=4;if(len>n-i){result.invalid=true;break;}
  if(type==0x1054){if(len!=8||(result.hasType&&memcmp(result.deviceType,p+i,8))){result.invalid=true;break;}memcpy(result.deviceType,p+i,8);result.hasType=true;}
  char *dest=nullptr;size_t cap=0;
  if(type==0x1021){dest=result.manufacturer;cap=sizeof(result.manufacturer);}if(type==0x1023){dest=result.model;cap=sizeof(result.model);}if(type==0x1024){dest=result.number;cap=sizeof(result.number);}if(type==0x1011){dest=result.name;cap=sizeof(result.name);}
  if(dest){char value[81]{};if(!copyUtf8(value,cap,p+i,len)){result.invalid=true;break;}if(dest[0]&&strcmp(dest,value)){result.invalid=true;break;}strcpy(dest,value);}
  i+=len;
 }
 if(result.invalid){result.hasType=false;result.manufacturer[0]=result.model[0]=result.number[0]=result.name[0]=0;}out=result;
}
inline void parseP2p(const uint8_t *p,size_t n,P2pInfo &out){
 P2pInfo result;result.present=true;
 for(size_t i=0;i<n;){if(n-i<3){result.invalid=true;break;}uint8_t type=p[i];uint16_t size=p[i+1]|(uint16_t(p[i+2])<<8);i+=3;if(size>n-i){result.invalid=true;break;}
  if(type==13){if(size<17){result.invalid=true;break;}const uint8_t *v=p+i;size_t prefix=17+size_t(v[16])*8;if(prefix>size){result.invalid=true;break;}WpsInfo fields;parseWps(v+prefix,size-prefix,fields);if(fields.invalid){result.invalid=true;break;}if(result.hasType&&memcmp(result.deviceType,v+8,8)){result.invalid=true;break;}memcpy(result.deviceType,v+8,8);result.hasType=true;if(fields.name[0])strcpy(result.name,fields.name);}
  i+=size;
 }
 if(result.invalid){result.name[0]=0;result.hasType=false;}out=result;
}
inline bool parseAnnouncements(const uint8_t *p,size_t n,WpsInfo &wps,P2pInfo &p2p){
 uint8_t wpsBytes[512],p2pBytes[512];size_t wpsSize=0,p2pSize=0;bool wpsSeen=false,p2pSeen=false,wpsOverflow=false,p2pOverflow=false,ssidSeen=false;
 for(size_t i=0;i<n;){if(n-i<2)return false;uint8_t id=p[i],len=p[i+1];i+=2;if(len>n-i)return false;const uint8_t *v=p+i;
  if(id==0){if(ssidSeen||len>32)return false;ssidSeen=true;}
  if(id==221&&len>=4){
   if(!memcmp(v,"\x50\x6f\x9a\x09",4)){p2pSeen=true;if(p2pSize+len-4>sizeof(p2pBytes))p2pOverflow=true;else{memcpy(p2pBytes+p2pSize,v+4,len-4);p2pSize+=len-4;}}
   if(!memcmp(v,"\x00\x50\xf2\x04",4)){wpsSeen=true;if(wpsSize+len-4>sizeof(wpsBytes))wpsOverflow=true;else{memcpy(wpsBytes+wpsSize,v+4,len-4);wpsSize+=len-4;}}
  }i+=len;
 }
 if(wpsSeen){if(wpsOverflow){wps.present=true;wps.invalid=true;}else parseWps(wpsBytes,wpsSize,wps);}
 if(p2pSeen){if(p2pOverflow){p2p.present=true;p2p.invalid=true;}else parseP2p(p2pBytes,p2pSize,p2p);}
 return true;
}
}
