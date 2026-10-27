#include "../DetectorTiempoReal/ssdp_core.h"
#include <cassert>
#include <iostream>
#include <string>
using namespace detector;
int main(){
 assert(!strcmp(canonicalBrand("SAMSUNG ELECTRONICS"),"Samsung"));assert(!strcmp(canonicalBrand("Honor Device Co., Ltd."),"Honor"));assert(!strcmp(canonicalBrand("Huawei"),"Huawei"));assert(!strcmp(canonicalBrand("applefake"),"applefake"));
 assert(compatibleModel("Samsung","SM-S911B"));assert(!compatibleModel("Honor","SM-S911B"));assert(!knownModel("SM-S911Bfake"));assert(!knownModel("iPhone"));
 Record r{};strcpy(r.value.wps.model,"BVL-N49");assert(classifyWifi(r).kind==DeviceKind::phone);r.wpsConflict=true;assert(classifyWifi(r).kind==DeviceKind::unknown);
 uint8_t peer[]={192,168,1,2},local[]={192,168,1,4},mask[]={255,255,255,0};LocalDescription target;
 assert(localDescriptionUrl("http://192.168.1.2:8080/root.xml",peer,local,mask,target));assert(target.port==8080&&!strcmp(target.path,"/root.xml"));
 for(auto*s:{"https://192.168.1.2/x","http://192.168.1.5/x","http://192.168.1.2:65536/x","http://user@192.168.1.2/x","http://192.168.1.2/x\r\nHost: evil","http://192.168.1.2/x#z","http://192.168.1.2:0/x","http://example.com/x"})assert(!localDescriptionUrl(s,peer,local,mask,target));
 char url[100]{};assert(ssdpLocation("HTTP/1.1 200 OK\r\nLocation: http://192.168.1.2/x\r\n\r\n",url,sizeof(url)));
 assert(!ssdpLocation("HTTP/1.1 200 OK\r\nLocation: a\r\nLOCATION: b\r\n\r\n",url,sizeof(url)));
 const char*xml="<?xml version=\"1.0\"?><root xmlns=\"urn:schemas-upnp-org:device-1-0\"><device><deviceType>urn:schemas-upnp-org:device:InternetGatewayDevice:2</deviceType><manufacturer>TP-Link</manufacturer><modelName>Archer &amp; Test</modelName><modelNumber>A1</modelNumber><friendlyName>Router</friendlyName><deviceList><device><manufacturer>Wrong</manufacturer><modelName>Other</modelName></device></deviceList></device></root>\n";
 LanEntry e;assert(upnpDescription(xml,e));assert(!strcmp(e.brand,"TP-Link")&&!strcmp(e.model,"Archer & Test")&&!strcmp(e.modelCode,"A1"));assert(classifyLan(e).kind==DeviceKind::router);
 for(size_t i=0;i<strlen(xml)-1;i++){std::string truncated(xml,i);LanEntry bad;assert(!upnpDescription(truncated.c_str(),bad));}
 for(auto*s:{"<!DOCTYPE root><root></root>","<root><device></root>","<root><device><deviceType>x</deviceType><modelName>&xxe;</modelName></device></root>","<root><device><deviceType>x</deviceType><modelName>a</modelName><modelName>b</modelName></device></root>"}){LanEntry bad;assert(!upnpDescription(s,bad));}
 LanEntry printer;strcpy(printer.service,"_ipps");assert(classifyLan(printer).kind==DeviceKind::printer);lanTxt(printer,"brand",(const uint8_t*)"Samsung",7);lanTxt(printer,"manufacturer",(const uint8_t*)"Apple",5);assert(printer.identityConflict&&classifyLan(printer).kind==DeviceKind::unknown);
 for(uint16_t id:{0x0098,0x015d,0x02df,0x0347,0x0b48,0x03bc,0x0576,0x066f,0x2542,0x1203}){uint8_t v[]={0x95,0xfe,0x40,0x50,uint8_t(id),uint8_t(id>>8),1};auto m=decodeBleModel(0x16,v,sizeof(v));assert(m.format==2&&m.id==id&&bleModelName(m)[0]);}
 uint8_t ruuvi[26]={0x99,0x04,5};auto m=decodeBleModel(0xff,ruuvi,sizeof ruuvi);assert(m.format==3&&!bleModelName(m)[0]&&bleModelBrand(m)[0]);for(size_t n=0;n<26;n++)assert(!decodeBleModel(0xff,ruuvi,n).format);ruuvi[0]=0;assert(!decodeBleModel(0xff,ruuvi,26).format);
 bool conflict=false;assert(nameHint("desktop",conflict)==DeviceKind::computer);assert(nameHint("Redmi Pad",conflict)==DeviceKind::unknown);
 std::cout<<"OK: identity, catalog codes, URL boundaries, SSDP headers, bounded XML, nested devices, truncation, conflicts, LAN types, 10 added MiBeacon IDs\n";
}
