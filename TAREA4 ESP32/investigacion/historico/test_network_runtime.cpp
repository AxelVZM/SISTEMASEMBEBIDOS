#include "peripherals_stub.h"
#include <atomic>
#include <iostream>
#include <fstream>
#include "vendor/cJSON.h"
#include "../DetectorTiempoReal/count_core.h"
#include "../DetectorTiempoReal/ble_core.h"
using namespace detector;
Record rows[MAX_RECORDS]{};BleRecord bleRows[MAX_BLE_RECORDS]{};size_t rowCount=0,bleCount=0;
uint8_t ownMac[6]={0x80,0,0,0,0,1};uint32_t bootId=42,nextBle=0,nowFake=0;
bool blePhase=false,radioReady=true,exporting=false,validTime=true;std::atomic<bool>accepting{true};
String quote(const String&s){auto*j=cJSON_CreateString(s.c_str());auto*p=cJSON_PrintUnformatted(j);String out(p);cJSON_free(p);cJSON_Delete(j);return out;}
String macText(const uint8_t*m){char b[18];snprintf(b,sizeof b,"%02X:%02X:%02X:%02X:%02X:%02X",m[0],m[1],m[2],m[3],m[4],m[5]);return b;}
std::vector<std::string> output;
bool emit(const String&s){output.push_back(s.value);return true;}
uint32_t millis(){return nowFake;}
bool clockValid(){return validTime;}
inline bool ntpStarted=false;void configTime(int,int,const char*,const char*){ntpStarted=true;}
struct{uint32_t free=100000;uint32_t getFreeHeap(){return free;}}ESP;
#define WL_CONNECTED 3
struct{bool connected=false;int begins=0;void begin(const char*,const char*){begins++;}int status(){return connected?3:0;}void disconnect(bool,bool){connected=false;}}WiFi;
int radioRestarts=0;bool startWifi(){radioRestarts++;accepting.store(true);return true;}
int esp_wifi_set_promiscuous(bool){return 0;}
void(*task)(void*)=nullptr;bool taskAllowed=true;
#define pdPASS 1
int xTaskCreate(void(*f)(void*),const char*,int,void*,int,void*){if(!taskAllowed)return 0;task=f;return 1;}
void vTaskDelete(void*){}
#include "../DetectorTiempoReal/network_runtime.h"
void command(const char*s){auto*j=cJSON_Parse(s);assert(j);assert(handleNetworkCommand(j,nowFake));cJSON_Delete(j);}
int main(int argc,char**argv){
 initializeNetwork();assert(!networkConfigured&&!networkSettings.enabled);networkTick(999999);assert(WiFi.begins==0);
 command(R"({"cmd":"network_set","ssid":"Casa","password":"clave-prueba-123","endpoint":"https://ejemplo.com/datos","interval":300,"enabled":false,"open":false})");assert(networkConfigured&&!networkSettings.enabled);sendNetworkStatus(1);assert(output.back().find("clave-prueba-123")==std::string::npos);
 NetworkSettings saved=networkSettings;networkSettings={};initializeNetwork();assert(!strcmp(networkSettings.password,saved.password));
 command(R"({"cmd":"network_test"})");networkTick(nowFake);assert(networkPhase==1&&!accepting.load());WiFi.connected=true;networkTick(nowFake+1);assert(!networkBusy()&&accepting.load()&&httpCalls==0);
 for(size_t i=0;i<50;i++){Event e;e.mac[0]=0x80;e.mac[5]=i+2;e.source=CLIENT;e.channel=6;e.rssi=-40;e.time=1000;strcpy(e.wps.model,"Modelo publicado");e.wps.present=true;upsertWifi(rows,rowCount,e);}
 auto payload=buildCloudPayload(1000);if(argc>1)std::ofstream(argv[1])<<payload.c_str();auto*j=cJSON_Parse(payload.c_str());assert(j);assert(cJSON_GetObjectItem(j,"total_detectado")->valueint==50);assert(cJSON_GetArraySize(cJSON_GetObjectItem(j,"equipos_detectados"))==24);cJSON_Delete(j);
 command(R"({"cmd":"network_set","ssid":"Casa","password":"","endpoint":"https://ejemplo.com/datos","interval":300,"enabled":true,"open":false})");
 nowFake+=2000;networkTick(nowFake);assert(networkPhase==1);validTime=false;WiFi.connected=true;networkTick(++nowFake);assert(networkPhase==2&&ntpStarted);validTime=true;networkTick(++nowFake);assert(networkPhase==3&&task);task(nullptr);networkTick(++nowFake);assert(networkPhase==0&&networkSuccesses==1&&httpCalls==1&&accepting.load());
 // Failed association resumes passive capture without blocking the USB loop.
 networkForceTest=true;networkTick(++nowFake);assert(networkPhase==1);nowFake+=8000;networkTick(nowFake);assert(!networkBusy()&&accepting.load());
 // Forgetting the network affects configuration, not the journal namespace.
 command(R"({"cmd":"network_forget"})");assert(!networkConfigured&&!networkSettings.password[0]);
 std::cout<<"OK: NVS, no clave en telemetria, prueba sin datos, snapshot acotado, maquina de estados, HTTPS y recuperacion.\n";
}
