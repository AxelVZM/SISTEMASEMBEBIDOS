#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include "ieee_data.h"
namespace ieee_mac {
enum class Status:uint8_t { matched,local,group,invalid,unlisted };
struct Result {Status status=Status::unlisted;const char *organization="",*registry="";uint64_t assignment=0;uint8_t bits=0;};
template<class Entry>inline const Entry *findPrefix(const Entry *entries,size_t count,uint64_t key){
 size_t lo=0,hi=count;while(lo<hi){size_t mid=lo+(hi-lo)/2;if(entries[mid].prefix<key)lo=mid+1;else hi=mid;}
 return lo<count&&entries[lo].prefix==key?entries+lo:nullptr;
}
inline Result lookup(const uint8_t *mac){
 if(!mac)return {Status::invalid};
 uint64_t address=0;for(size_t i=0;i<6;i++)address=(address<<8)|mac[i];
 if(!address)return {Status::invalid};
 if(mac[0]&1)return {Status::group};
 if(mac[0]&2)return {Status::local}; // Never clear U/L to guess a factory OUI.
 if(const auto *e=findPrefix(entries36,sizeof(entries36)/sizeof(*entries36),address>>12))return {Status::matched,organizationAt(e->offset),"MA-S",e->prefix,36};
 if(const auto *e=findPrefix(entries28,sizeof(entries28)/sizeof(*entries28),address>>20))return {Status::matched,organizationAt(e->offset),"MA-M",e->prefix,28};
 if(const auto *e=findPrefix(entries24,sizeof(entries24)/sizeof(*entries24),address>>24))return {Status::matched,organizationAt(e->offset),"MA-L",e->prefix,24};
 return {Status::unlisted};
}
inline void assignmentText(const Result &r,char *out,size_t cap){
 if(!cap)return;
 if(r.status!=Status::matched){out[0]=0;return;}
 snprintf(out,cap,"%0*llX",int(r.bits/4),static_cast<unsigned long long>(r.assignment));
}
}
