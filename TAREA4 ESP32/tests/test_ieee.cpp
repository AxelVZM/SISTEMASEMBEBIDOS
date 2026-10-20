#include "../DetectorTiempoReal/ieee_registry.h"
#include <cassert>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <random>
#include <vector>
using namespace ieee_mac;
void bytes(uint64_t n,uint8_t *mac){for(int i=5;i>=0;i--){mac[i]=uint8_t(n);n>>=8;}}
int main(int argc,char **argv){
 assert(argc==2);std::ifstream source(argv[1]);assert(source.good());std::string line;size_t count=0,lookups=0,blocked=0;uint8_t mac[6];
 while(std::getline(source,line)){
  std::istringstream fields(line);std::string registry,bitsText,prefixText,organization;
  std::getline(fields,registry,'\t');std::getline(fields,bitsText,'\t');std::getline(fields,prefixText,'\t');std::getline(fields,organization);
  unsigned bits=std::stoul(bitsText);uint64_t prefix=std::stoull(prefixText,nullptr,16),start=prefix<<(48-bits),end=start|((1ULL<<(48-bits))-1);count++;
  for(uint64_t address:{start,end}){
   bytes(address,mac);Result r=lookup(mac);
   if(!address){assert(r.status==Status::invalid);blocked++;continue;}
   if(mac[0]&1){assert(r.status==Status::group);blocked++;continue;}
   if(mac[0]&2){assert(r.status==Status::local);blocked++;continue;}
   // More-specific public entries override a parent registry.
   assert(r.status==Status::matched&&r.bits>=bits);if(r.bits==bits){assert(r.assignment==prefix&&organization==r.organization&&registry==r.registry);}
   char printed[10];assignmentText(r,printed,sizeof(printed));assert(std::stoull(printed,nullptr,16)==r.assignment);lookups++;
  }
 }
 assert(count>50000);assert(lookup(nullptr).status==Status::invalid);bytes(0,mac);assert(lookup(mac).status==Status::invalid);
 bytes(0x8EE59B2ACF4EULL,mac);assert(lookup(mac).status==Status::local);
 bytes(0xffffffffffffULL,mac);assert(lookup(mac).status==Status::group);
 // Independent examples from the downloaded official CSVs.
 bytes(0xC85CE2700001ULL,mac);auto medium=lookup(mac);assert(medium.bits==28&&!strcmp(medium.registry,"MA-M")&&!strcmp(medium.organization,"SYNERGY SYSTEMS AND SOLUTIONS"));
 bytes(0x8C1F64AFA001ULL,mac);auto small=lookup(mac);assert(small.bits==36&&!strcmp(small.registry,"MA-S")&&!strcmp(small.organization,"DATA ELECTRONIC DEVICES, INC"));
 // Explicit longest-prefix search boundaries with overlapping synthetic assignments.
 Entry24 synthetic[]={{1,0},{5,0},{9,0}};assert(!findPrefix(synthetic,3,0));assert(findPrefix(synthetic,3,1));assert(findPrefix(synthetic,3,9));assert(!findPrefix(synthetic,3,10));assert(!findPrefix(synthetic,0,1));
 // Public legacy duplicate: preserve all registrants rather than choose one.
 bytes(0x080030123456ULL,mac);auto duplicate=lookup(mac);assert(strstr(duplicate.organization,"CERN")&&strstr(duplicate.organization,"NETWORK RESEARCH"));
 std::mt19937 rng(123);size_t unknown=0;for(size_t i=0;i<10000;i++){for(auto &b:mac)b=uint8_t(rng());auto r=lookup(mac);if(mac[0]&1)assert(r.status==Status::group);else if(mac[0]&2)assert(r.status==Status::local);else if(r.status==Status::unlisted)unknown++;else assert(r.status==Status::matched&&r.organization[0]);}
 assert(unknown);std::cout<<"OK: "<<count<<" prefijos; "<<lookups<<" consultas extremas; "<<blocked<<" direcciones bloqueadas por tipo; 10000 MAC aleatorias; duplicados preservados.\n";
 std::cout<<"Datos constantes (ABI anfitrion): "<<sizeof(organizationData)+sizeof(organizationBlocks)+sizeof(entries24)+sizeof(entries28)+sizeof(entries36)<<" bytes; no reserva de tabla en heap.\n";
}
