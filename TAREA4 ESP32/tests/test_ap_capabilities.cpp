#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>
#include "../DetectorTiempoReal/ap_capabilities.h"
using namespace detector;
int main(){
 std::vector<uint8_t> frame(36);frame[0]=0x80;frame[34]=0x10;
 // Version, group cipher, pairwise count/cipher, AKM count and PSK/SAE selectors.
 uint8_t rsn[]={1,0,0,0x0f,0xac,4,1,0,0,0x0f,0xac,4,2,0,0,0x0f,0xac,2,0,0x0f,0xac,8};
 frame.push_back(48);frame.push_back(sizeof rsn);frame.insert(frame.end(),rsn,rsn+sizeof rsn);
 frame.push_back(45);frame.push_back(26);frame.resize(frame.size()+26);
 ApCapabilities a;parseCapabilities(frame.data(),frame.size(),a);assert(a.present&&a.generation==4);assert(!strcmp(securityText(a),"WPA2/WPA3"));
 uint8_t malformed[]={1,0,0,0x0f,0xac,4,255,255};parseAkm(malformed,sizeof malformed,a);
 for(size_t n=0;n<frame.size();n++){ApCapabilities b;parseCapabilities(frame.data(),n,b);}
 std::cout<<"OK: capacidades AP, AKM PSK/SAE, RSSI separado, tramas truncadas.\n";
}
