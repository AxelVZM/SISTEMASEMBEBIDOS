#pragma once
#include <cstdint>
#include <cstring>
#include <cmath>
namespace detector {
constexpr uint32_t NETWORK_MAGIC=0x71314e43;
constexpr const char *DEFAULT_ENDPOINT="https://6itiwld9ah.execute-api.us-east-2.amazonaws.com/default/RecibirDatosESP32";
struct NetworkSettings {
 uint32_t magic=NETWORK_MAGIC,intervalSeconds=300;
 bool enabled=false;
 char ssid[33]{},password[65]{},endpoint[193]{};
};
inline bool validEndpoint(const char *s){
 if(!s||strncmp(s,"https://",8)||!s[8]||strlen(s)>192)return false;
 const char *slash=strchr(s+8,'/');size_t host=slash?size_t(slash-(s+8)):strlen(s+8);
 if(!host)return false;
 for(const char *p=s;*p;p++)if(uint8_t(*p)<=32||uint8_t(*p)>126||*p=='"'||*p=='\\'||*p=='#')return false;
 for(size_t i=0;i<host;i++)if(s[8+i]=='@')return false;
 return true;
}
inline bool validPassword(const char *s){
 size_t n=strlen(s);if(n==0)return true;
 if(n==64){for(size_t i=0;i<n;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')||(s[i]>='A'&&s[i]<='F')))return false;return true;}
 return n>=8&&n<=63;
}
inline bool validSettings(const NetworkSettings &s){
 if(s.magic!=NETWORK_MAGIC||s.intervalSeconds<60||s.intervalSeconds>3600||!memchr(s.ssid,0,sizeof(s.ssid))||!memchr(s.password,0,sizeof(s.password))||!memchr(s.endpoint,0,sizeof(s.endpoint)))return false;
 return s.ssid[0]&&validPassword(s.password)&&validEndpoint(s.endpoint);
}
inline bool readNetworkSettings(cJSON *j,const NetworkSettings &old,NetworkSettings &out,const char *&error){
 auto *ssid=cJSON_GetObjectItemCaseSensitive(j,"ssid"),*pass=cJSON_GetObjectItemCaseSensitive(j,"password"),*url=cJSON_GetObjectItemCaseSensitive(j,"endpoint"),*enabled=cJSON_GetObjectItemCaseSensitive(j,"enabled"),*interval=cJSON_GetObjectItemCaseSensitive(j,"interval"),*open=cJSON_GetObjectItemCaseSensitive(j,"open");
 error="Configuracion no valida";
 if(!cJSON_IsString(ssid)||!ssid->valuestring[0]||strlen(ssid->valuestring)>32||!cJSON_IsString(url)||!validEndpoint(url->valuestring)||!cJSON_IsBool(enabled)||!cJSON_IsNumber(interval)||interval->valuedouble!=floor(interval->valuedouble)||interval->valuedouble<60||interval->valuedouble>3600||(pass&&!cJSON_IsString(pass))||(open&&!cJSON_IsBool(open)))return false;
 out=NetworkSettings{};strcpy(out.ssid,ssid->valuestring);strcpy(out.endpoint,url->valuestring);out.enabled=cJSON_IsTrue(enabled);out.intervalSeconds=uint32_t(interval->valuedouble);
 if(cJSON_IsTrue(open))out.password[0]=0;
 else if(pass&&pass->valuestring[0]){if(strlen(pass->valuestring)>64)return false;strcpy(out.password,pass->valuestring);}
 else if(!strcmp(old.ssid,out.ssid))strcpy(out.password,old.password);
 else {error="Ingresa la clave de la nueva red o marca red abierta";return false;}
 if(!validSettings(out)){error="Clave WPA: 8-63 bytes o PSK hexadecimal de 64 caracteres";return false;}
 return true;
}
}
