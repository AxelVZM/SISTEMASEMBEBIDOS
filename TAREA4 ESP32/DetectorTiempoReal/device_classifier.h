#pragma once
#include <initializer_list>
#include "count_core.h"
namespace detector {
enum class DeviceKind:uint8_t {unknown,phone,laptop,computer,tablet,router,ap,network,projector,tv,display,printer,camera,audio,wearable,gaming,storage,media,peripheral,sensor};
struct DeviceClass {DeviceKind kind=DeviceKind::unknown;const char *level="unknown",*evidence="Sin evidencia suficiente";};
inline const char *deviceKey(DeviceKind k){const char*keys[]={"unknown","phone","laptop","computer","tablet","router","ap","network","projector","tv","display","printer","camera","audio","wearable","gaming","storage","media","peripheral","sensor"};return keys[unsigned(k)];}
inline const char *deviceLabel(DeviceKind k){const char*labels[]={"Sin determinar","Telefono / celular","Laptop","Computadora","Tablet","Router","Punto de acceso","Equipo de red","Cañón / proyector","Televisor","Pantalla","Impresora / escaner","Camara","Equipo de audio","Reloj / wearable","Consola","Almacenamiento / NAS","Multimedia","Periferico","Sensor"};return labels[unsigned(k)];}
inline DeviceKind primaryType(const uint8_t *t){
 if(memcmp(t+2,"\x00\x50\xf2\x04",4))return DeviceKind::unknown;
 unsigned c=(unsigned(t[0])<<8)|t[1],s=(unsigned(t[6])<<8)|t[7];
 switch(c){case 1:return (s==5||s==8)?DeviceKind::laptop:s==9?DeviceKind::tablet:DeviceKind::computer;
 case 2:return DeviceKind::peripheral;case 3:return DeviceKind::printer;case 4:return DeviceKind::camera;case 5:return DeviceKind::storage;
 case 6:return s==1?DeviceKind::ap:s==2?DeviceKind::router:DeviceKind::network;
 case 7:return s==1?DeviceKind::tv:s==3?DeviceKind::projector:DeviceKind::display;
 case 8:return DeviceKind::media;case 9:return DeviceKind::gaming;case 10:return DeviceKind::phone;case 11:return DeviceKind::audio;default:return DeviceKind::unknown;}
}
inline DeviceKind mergeType(DeviceKind a,DeviceKind b,bool &conflict){
 if(a==DeviceKind::unknown)return b;if(b==DeviceKind::unknown||a==b)return a;
 for(DeviceKind specific:{DeviceKind::laptop,DeviceKind::tablet})if((a==DeviceKind::computer&&b==specific)||(b==DeviceKind::computer&&a==specific))return specific;
 for(DeviceKind specific:{DeviceKind::tv,DeviceKind::projector})if((a==DeviceKind::display&&b==specific)||(b==DeviceKind::display&&a==specific))return specific;
 for(DeviceKind specific:{DeviceKind::ap,DeviceKind::router})if((a==DeviceKind::network&&b==specific)||(b==DeviceKind::network&&a==specific))return specific;
 conflict=true;return DeviceKind::unknown;
}
inline uint8_t lowerAscii(uint8_t c){return c>='A'&&c<='Z'?c+32:c;}
inline bool wordChar(uint8_t c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c>=128;}
inline bool nameContains(const char*s,const char*pattern){
 size_t n=strlen(s),m=strlen(pattern);for(size_t i=0;i+m<=n;i++){if(i&&wordChar(uint8_t(s[i-1])))continue;size_t k=0;while(k<m&&lowerAscii(s[i+k])==uint8_t(pattern[k]))k++;if(k==m&&(!s[i+m]||!wordChar(uint8_t(s[i+m]))||(s[i+m]>='0'&&s[i+m]<='9')))return true;}return false;
}
inline DeviceKind nameHint(const char*s,bool &conflict){
 struct Rule {const char*word;DeviceKind kind;};
 static const Rule rules[]={
 {"iphone",DeviceKind::phone},{"smartphone",DeviceKind::phone},{"celular",DeviceKind::phone},{"redmi",DeviceKind::phone},{"moto g",DeviceKind::phone},{"galaxy s",DeviceKind::phone},{"galaxy a",DeviceKind::phone},{"galaxy z",DeviceKind::phone},{"pixel 6",DeviceKind::phone},{"pixel 7",DeviceKind::phone},{"pixel 8",DeviceKind::phone},{"pixel 9",DeviceKind::phone},{"pixel 10",DeviceKind::phone},
 {"laptop",DeviceKind::laptop},{"notebook",DeviceKind::laptop},{"macbook",DeviceKind::laptop},{"thinkpad",DeviceKind::laptop},{"ideapad",DeviceKind::laptop},{"vivobook",DeviceKind::laptop},
 {"ipad",DeviceKind::tablet},{"tablet",DeviceKind::tablet},{"galaxy tab",DeviceKind::tablet},
 {"router",DeviceKind::router},{"access point",DeviceKind::ap},
 {"projector",DeviceKind::projector},{"proyector",DeviceKind::projector},{"smart tv",DeviceKind::tv},{"smarttv",DeviceKind::tv},{"bravia",DeviceKind::tv},
 {"printer",DeviceKind::printer},{"impresora",DeviceKind::printer},{"laserjet",DeviceKind::printer},{"deskjet",DeviceKind::printer},{"ecotank",DeviceKind::printer},
 {"camera",DeviceKind::camera},{"camara",DeviceKind::camera},{"webcam",DeviceKind::camera},{"ipcam",DeviceKind::camera},
 {"airpods",DeviceKind::audio},{"earbuds",DeviceKind::audio},{"headphones",DeviceKind::audio},{"speaker",DeviceKind::audio},{"soundbar",DeviceKind::audio},{"auriculares",DeviceKind::audio},
 {"smartwatch",DeviceKind::wearable},{"apple watch",DeviceKind::wearable},{"mi band",DeviceKind::wearable},{"fitbit",DeviceKind::wearable},
 {"playstation",DeviceKind::gaming},{"xbox",DeviceKind::gaming},{"nintendo switch",DeviceKind::gaming},{"nas",DeviceKind::storage},{"diskstation",DeviceKind::storage},{"chromecast",DeviceKind::media}};
 DeviceKind out=DeviceKind::unknown;for(auto&r:rules)if(nameContains(s,r.word))out=mergeType(out,r.kind,conflict);return out;
}
inline DeviceClass classifyWifi(const Record&r){
 if(r.typeConflict||r.wpsConflict)return {DeviceKind::unknown,"conflict","Anuncios de identificacion contradictorios"};
 const auto&v=r.value;bool conflict=false;DeviceKind structured=DeviceKind::unknown;
 if(v.wps.hasType)structured=primaryType(v.wps.deviceType);
 if(v.p2p.hasType)structured=mergeType(structured,primaryType(v.p2p.deviceType),conflict);
 if(conflict)return {DeviceKind::unknown,"conflict","WPS y Wi-Fi Direct discrepan"};
 if(structured!=DeviceKind::unknown)return {structured,"declared",v.wps.hasType&&v.p2p.hasType?"Tipo primario WPS / Wi-Fi Direct":v.wps.hasType?"Tipo primario WPS":"Tipo primario Wi-Fi Direct"};
 DeviceKind hint=DeviceKind::unknown;for(const char*s:{v.wps.model,v.wps.name,v.p2p.name})hint=mergeType(hint,nameHint(s,conflict),conflict);
 if(conflict)return {DeviceKind::unknown,"conflict","Nombres/modelos sugieren tipos diferentes"};
 if(hint!=DeviceKind::unknown)return {hint,"hint","Palabra en nombre/modelo anunciado; puede ser falso"};
 if(v.source&AP)return {DeviceKind::ap,"role","Rol AP observado; no confirma router fisico"};
 return {};
}
}
