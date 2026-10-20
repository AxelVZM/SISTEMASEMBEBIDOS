#pragma once
#include <cstdint>
#include <cstddef>
namespace detector {
struct ApCapabilities {uint8_t security=0,generation=0;bool present=false;};
enum SecurityBits:uint8_t {PRIVACY=1,WPA=2,RSN=4,PSK=8,ENTERPRISE=16,SAE=32,OWE=64};
inline void parseAkm(const uint8_t*p,size_t n,ApCapabilities &a){
 if(n<8)return;size_t at=6,count=p[at]|(size_t(p[at+1])<<8);at+=2;
 if(count>(n-at)/4)return;at+=count*4;if(n-at<2)return;count=p[at]|(size_t(p[at+1])<<8);at+=2;if(count>(n-at)/4)return;
 for(size_t i=0;i<count;i++,at+=4)if(p[at]==0&&p[at+1]==0x0f&&p[at+2]==0xac){switch(p[at+3]){case 1:case 5:a.security|=ENTERPRISE;break;case 2:case 6:a.security|=PSK;break;case 8:case 9:a.security|=SAE;break;case 18:a.security|=OWE;break;}}
}
inline void parseCapabilities(const uint8_t*p,size_t n,ApCapabilities &a){
 if(n<36)return;a={};a.present=true;if(p[34]&0x10)a.security|=PRIVACY;
 for(size_t at=36;at+2<=n;){uint8_t id=p[at],len=p[at+1];at+=2;if(len>n-at)return;const uint8_t*v=p+at;
 if(id==48&&len>=2){a.security|=RSN;parseAkm(v,len,a);}
 if(id==221&&len>=4&&v[0]==0&&v[1]==0x50&&v[2]==0xf2&&v[3]==1)a.security|=WPA;
 if(id==45&&len>=26)a.generation= a.generation<4?4:a.generation;
 if(id==191&&len>=12)a.generation=a.generation<5?5:a.generation;
 if(id==255&&len>=18&&v[0]==35)a.generation=6;
 at+=len;}
}
inline const char *securityText(const ApCapabilities&a){
 if(!a.present)return "No observado";auto s=a.security;
 if(s&SAE)return s&PSK?"WPA2/WPA3":"WPA3";
 if(s&OWE)return "OWE";if((s&RSN)&&(s&ENTERPRISE))return "WPA2-Enterprise";
 if((s&RSN)&&(s&PSK))return "WPA2";if(s&RSN)return "RSN anunciado";if(s&WPA)return "WPA";
 if(s&PRIVACY)return "Privada; protocolo sin identificar";return "Sin privacidad anunciada";
}
}
