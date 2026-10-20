#include "peripherals_stub.h"
#include <cmath>
#include <ctime>
#include <iostream>
#include "vendor/cJSON.h"
#include "../DetectorTiempoReal/count_core.h"
#include "../DetectorTiempoReal/ble_core.h"
#include "../DetectorTiempoReal/bluetooth_companies.h"
#include "../DetectorTiempoReal/device_classifier.h"
using namespace detector;
struct FakeSerial {std::string input;size_t pos=0;size_t available(){return input.size()-pos;}char read(){return input[pos++];}}Serial;
uint32_t testNow=0;uint32_t millis(){return testNow;}uint32_t esp_random(){return 42;}int esp_reset_reason(){return 1;}
Record rows[MAX_RECORDS]{};BleRecord bleRows[MAX_BLE_RECORDS]{};size_t rowCount=0,bleCount=0;uint32_t bootId=123,tableDrops=0,bleTableDrops=0;bool fsReady=false;String storageError="";
bool clockValid(){return false;}bool syncClock(uint32_t n){return n>=1704067200u&&n<4102444800u;}
CountSummary counts(uint32_t now){CountSummary c;for(size_t i=0;i<rowCount;i++)c.wifi+=recent(now,rows[i].last);for(size_t i=0;i<bleCount;i++)c.ble+=recent(now,bleRows[i].last);return c;}
String quote(const String &s){cJSON *j=cJSON_CreateString(s.c_str());char *p=cJSON_PrintUnformatted(j);String out(p);cJSON_free(p);cJSON_Delete(j);return out;}
String macText(const uint8_t *m){char s[18];snprintf(s,sizeof(s),"%02X:%02X:%02X:%02X:%02X:%02X",m[0],m[1],m[2],m[3],m[4],m[5]);return s;}
String manufacturer(const uint8_t *){return "IEEE titular";}
std::vector<std::string> packets;bool emitAllowed=true;bool emit(const String &s){if(!emitAllowed)return false;assert(s.length()<3600);packets.push_back(s.value);return true;}
int mbedtls_base64_encode(unsigned char *out,size_t cap,size_t *written,const unsigned char *data,size_t n){const char *alpha="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";size_t need=4*((n+2)/3);if(cap<need+1)return -1;size_t j=0;for(size_t i=0;i<n;i+=3){uint32_t v=uint32_t(data[i])<<16;if(i+1<n)v|=uint32_t(data[i+1])<<8;if(i+2<n)v|=data[i+2];out[j++]=alpha[(v>>18)&63];out[j++]=alpha[(v>>12)&63];out[j++]=i+1<n?alpha[(v>>6)&63]:'=';out[j++]=i+2<n?alpha[v&63]:'=';}out[j]=0;*written=j;return 0;}
bool handleNetworkCommand(cJSON*,uint32_t){return false;}
#include "../DetectorTiempoReal/journal.h"
std::string decode(const char *s){std::string out,alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";uint32_t buffer=0;int bits=0;for(;*s&&*s!='=';s++){auto v=alphabet.find(*s);assert(v!=std::string::npos);buffer=(buffer<<6)|v;bits+=6;if(bits>=8){bits-=8;out+=char((buffer>>bits)&255);}}return out;}
int main(){
 initializeJournal();assert(fsReady&&LittleFS.formats==1);
 String header=logHeader();assert(std::count(header.value.begin(),header.value.end(),';')==15);assert(csvCell("=1+1").value=="\"'=1+1\"");
 Event e;e.mac[0]=0x90;e.mac[5]=1;e.time=100;e.rssi=-50;e.channel=6;strcpy(e.wps.name,"Equipo á");e.wps.present=true;assert(upsertWifi(rows,rowCount,e)==0);BleEvent b;b.mac[0]=0xc3;b.mac[5]=1;b.addressType=1;b.time=100;b.rssi=-60;strcpy(b.name,"BLE prueba");assert(upsertBle(bleRows,bleCount,b)==0);
 for(int i=0;i<40;i++){testNow+=500;journalTick(testNow);}assert(flushLog());assert(LittleFS.files[LOG_CURRENT]->find("Equipo á")!=std::string::npos);assert(LittleFS.files[LOG_CURRENT]->find("BLE prueba")!=std::string::npos);testNow=31000;journalTick(testNow);assert(flushLog());assert(LittleFS.files[LOG_CURRENT]->find("resumen")!=std::string::npos);
 for(int i=0;i<50;i++){assert(appendLog(String(std::string(4000,'a'))+'\n'));assert(flushLog());}assert(LittleFS.exists(LOG_PREVIOUS));
 // Use small UTF-8 segments to verify bounded snapshot export, not rotation volume.
 *LittleFS.files[LOG_PREVIOUS]="anterior;á\n";*LittleFS.files[LOG_CURRENT]="actual;é\n";const std::string expected=*LittleFS.files[LOG_PREVIOUS]+*LittleFS.files[LOG_CURRENT];beginExport(testNow);emitAllowed=false;sendExport(testNow);assert(exporting&&!exportStarted);emitAllowed=true;for(int i=0;i<30&&exporting;i++){testNow+=100;sendExport(testNow);}assert(!exporting);std::string bytes;bool ended=false;unsigned part=0;for(auto &packet:packets){auto *j=cJSON_ParseWithOpts(packet.c_str(),nullptr,true);assert(j);auto *kind=cJSON_GetObjectItem(j,"kind");assert(cJSON_IsString(kind));if(!strcmp(kind->valuestring,"export_chunk")){assert(cJSON_GetObjectItem(j,"part")->valueint==int(part++));bytes+=decode(cJSON_GetObjectItem(j,"data")->valuestring);}if(!strcmp(kind->valuestring,"export_end"))ended=true;cJSON_Delete(j);}assert(ended&&bytes==expected);
 Serial.input="{\"cmd\":\"clock_sync\",\"epoch\":1770000000}\n";readCommands(testNow);assert(storageReply.value.find("true")!=std::string::npos);Serial.input=std::string(1700,'x')+'\n';Serial.pos=0;while(Serial.available())readCommands(testNow);assert(!commandOverflow&&commandBuffer.length()==0);
 LittleFS.mounted=false;initializeJournal();assert(!fsReady&&LittleFS.formats==1);testNow+=31000;journalTick(testNow);assert(!fsReady&&LittleFS.formats==1);
 std::cout<<"OK: first-use/no destructive remount, 16-column CSV, states/summary, rotation, UTF8 snapshot export/backpressure, bounded USB commands, clock request.\n";
}
