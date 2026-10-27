#pragma once
#include <cstring>
#include "announcements.h"
#include "device_classifier.h"
namespace detector {
struct LanEntry {char name[65]{},host[65]{},ip[46]{},service[32]{},brand[65]{},model[97]{},evidence[80]{},upnpType[96]{},modelCode[65]{};uint16_t port=0;uint32_t last=0;bool dirty=true,identityConflict=false;};
inline bool lanBrandKey(const char*k){return k&&(!strcmp(k,"manufacturer")||!strcmp(k,"brand")||!strcmp(k,"usb_MFG"));}
inline bool lanModelKey(const char*k){return k&&(!strcmp(k,"model")||!strcmp(k,"md")||!strcmp(k,"ty")||!strcmp(k,"usb_MDL"));}
inline void lanTxt(LanEntry&e,const char*k,const uint8_t*v,size_t n){
 if(lanBrandKey(k)){char candidate[65]{};if(copyUtf8(candidate,sizeof(candidate),v,n)){if(e.brand[0]&&strcmp(canonicalBrand(e.brand),canonicalBrand(candidate)))e.identityConflict=true;else copyUtf8(e.brand,sizeof(e.brand),(const uint8_t*)canonicalBrand(candidate),strlen(canonicalBrand(candidate)));}}
 if(lanModelKey(k)&&e.model[0]){char candidate[97]{};if(copyUtf8(candidate,sizeof(candidate),v,n)&&strcmp(e.model,candidate))e.identityConflict=true;}
 if(lanModelKey(k)&&!e.model[0]){if(copyUtf8(e.model,sizeof(e.model),v,n)){strncpy(e.evidence,k,sizeof(e.evidence)-1);}}
}
inline DeviceClass classifyLan(const LanEntry&e){
 if(e.identityConflict)return {DeviceKind::unknown,"conflict","Campos anunciados contradictorios"};
 if(!strcmp(e.service,"_ipp")||!strcmp(e.service,"_ipps")||!strcmp(e.service,"_printer")||!strcmp(e.service,"_pdl-datastream"))return {DeviceKind::printer,"role","Servicio de impresion; puede ser servidor intermediario"};
 if(!strcmp(e.upnpType,"urn:schemas-upnp-org:device:InternetGatewayDevice:1")||!strcmp(e.upnpType,"urn:schemas-upnp-org:device:InternetGatewayDevice:2"))return {DeviceKind::router,"declared","UPnP InternetGatewayDevice anunciado"};
 if(!strncmp(e.upnpType,"urn:schemas-upnp-org:device:MediaRenderer:",39))return {DeviceKind::media,"declared","UPnP MediaRenderer; no confirma televisor"};
 if(compatibleModel(e.brand,e.model)||compatibleModel(e.brand,e.modelCode))return {DeviceKind::phone,"declared","Codigo LAN en catalogo documentado"};
 bool conflict=false;auto k=nameHint(e.model,conflict);k=mergeType(k,nameHint(e.name,conflict),conflict);
 if(conflict)return {DeviceKind::unknown,"conflict","Nombres/modelos sugieren tipos diferentes"};
 if(k!=DeviceKind::unknown)return {k,"hint","Palabra en nombre/modelo LAN; no autenticado"};
 return {};
}
}
