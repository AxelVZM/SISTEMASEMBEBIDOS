#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace detector {
struct WifiFingerprint {uint8_t bytes[96]{},size=0;bool complete=false;};
inline bool probeFingerprint(const uint8_t*p,size_t n,WifiFingerprint&f){
 f={};bool overflow=false,capability=false;
 for(size_t at=0;at<n;){if(n-at<2)return false;uint8_t id=p[at++],len=p[at++];if(len>n-at)return false;
 // Preserve IE order. Variable/identifying payloads omitted; vendor OUI/type only.
 bool selected=id==1||id==50||id==45||id==127||id==191;
 size_t take=selected?len:id==221?(len<4?len:4):0;
 if(selected&&len)capability=true;
 if(f.size+2+take<=sizeof(f.bytes)&&!overflow){f.bytes[f.size++]=id;f.bytes[f.size++]=uint8_t(take);for(size_t k=0;k<take;k++)f.bytes[f.size++]=p[at+k];}else overflow=true;
 at+=len;
 }f.complete=!overflow&&capability;return true;
}
}
