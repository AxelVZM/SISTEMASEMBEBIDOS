#include <cassert>
#include <iostream>
#include "vendor/cJSON.h"
#include "../DetectorTiempoReal/network_config.h"
using namespace detector;
int main(){
 NetworkSettings old{},out{};strcpy(old.ssid,"Casa");strcpy(old.password,"clave-prueba-123");strcpy(old.endpoint,DEFAULT_ENDPOINT);
 const char*error=nullptr;
 auto *j=cJSON_Parse(R"({"ssid":"Casa","password":"","endpoint":"https://ejemplo.com/datos","enabled":true,"interval":300,"open":false})");
 assert(readNetworkSettings(j,old,out,error));assert(!strcmp(out.password,old.password));assert(out.enabled);assert(validSettings(out));cJSON_Delete(j);
 j=cJSON_Parse(R"({"ssid":"Otra","endpoint":"https://ejemplo.com","enabled":false,"interval":60,"open":true})");assert(readNetworkSettings(j,old,out,error));assert(!out.password[0]);cJSON_Delete(j);
 for(const char*s:{R"({"ssid":"Otra","endpoint":"https://ejemplo.com","enabled":true,"interval":300})",R"({"ssid":"Casa","password":"corta","endpoint":"https://ejemplo.com","enabled":true,"interval":300})",R"({"ssid":"Casa","endpoint":"http://ejemplo.com","enabled":true,"interval":300})",R"({"ssid":"Casa","endpoint":"https://ejemplo.com","enabled":true,"interval":59})"}){j=cJSON_Parse(s);assert(!readNetworkSettings(j,old,out,error));cJSON_Delete(j);}
 assert(!validEndpoint("https://user:pass@host/"));assert(!validEndpoint("https://"));assert(!validEndpoint("https://host/\n"));
 std::cout<<"OK: red opcional, validacion, conservar clave, red abierta, URL e intervalos.\n";
}
