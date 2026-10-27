#include "peripherals_stub.h"
#include <atomic>
#include <cstdio>
#include <iostream>
#include "vendor/cJSON.h"
#include "../DetectorTiempoReal/device_classifier.h"
using namespace detector;
using esp_err_t=int;using esp_gap_ble_cb_event_t=int;
constexpr int ESP_OK=0,ESP_BT_STATUS_SUCCESS=0,ESP_GAP_BLE_SCAN_PARAM_SET_COMPLETE_EVT=1,ESP_GAP_BLE_SCAN_START_COMPLETE_EVT=2,ESP_GAP_BLE_SCAN_STOP_COMPLETE_EVT=3,ESP_GAP_BLE_SCAN_RESULT_EVT=4,ESP_GAP_SEARCH_INQ_CMPL_EVT=5,ESP_GAP_SEARCH_INQ_RES_EVT=6;
constexpr int ESP_BT_MODE_CLASSIC_BT=0,ESP_BT_MODE_BLE=1,BLE_SCAN_TYPE_PASSIVE=0,BLE_ADDR_TYPE_PUBLIC=0,BLE_SCAN_FILTER_ALLOW_ALL=0,BLE_SCAN_DUPLICATE_DISABLE=0,pdTRUE=1;
struct esp_ble_gap_cb_param_t {struct{int status=0;}scan_param_cmpl,scan_start_cmpl,scan_stop_cmpl;struct{int search_evt=0;uint8_t bda[6]{},ble_addr_type=0,ble_adv[31]{};int8_t rssi=0;size_t adv_data_len=0;}scan_rst;};
struct esp_bt_controller_config_t{};
#define BT_CONTROLLER_INIT_CONFIG_DEFAULT() esp_bt_controller_config_t{}
struct esp_ble_scan_params_t{int scan_type,own_addr_type,scan_filter_policy,scan_interval,scan_window,scan_duplicate;};
void(*callback)(int,esp_ble_gap_cb_param_t*)=nullptr;int starts=0,stops=0,inits=0;bool fakeStartFailure=false,busy=false;uint32_t fakeNow=0;
int esp_bt_controller_mem_release(int){return 0;}int esp_bt_controller_init(esp_bt_controller_config_t*){inits++;return 0;}int esp_bt_controller_enable(int){return 0;}int esp_bluedroid_init(){return 0;}int esp_bluedroid_enable(){return 0;}int esp_ble_gap_register_callback(void(*cb)(int,esp_ble_gap_cb_param_t*)){callback=cb;return 0;}
int esp_ble_gap_set_scan_params(esp_ble_scan_params_t*){esp_ble_gap_cb_param_t p;callback(1,&p);return 0;}
int esp_ble_gap_start_scanning(int seconds){assert(seconds==2);starts++;if(fakeStartFailure)return -1;esp_ble_gap_cb_param_t p;callback(2,&p);return 0;}
int esp_ble_gap_stop_scanning(){stops++;return 0;}const char*esp_err_to_name(int){return "test error";}
void* xQueueCreate(int,size_t){return (void*)1;}int xQueueSend(void*,void*,int){return 1;}
uint32_t millis(){return fakeNow;}int esp_wifi_set_promiscuous(bool){return 0;}
bool bleSelected=false,bleInitialized=false,bleInitFailed=false,radioReady=true,exporting=false;
std::atomic<bool>bleReady{false},bleAccept{false},bleScanning{false},bleStartPending{false},accepting{true};std::atomic<uint32_t>bleDrops{0};
void*bleQueue=nullptr;uint32_t bleInitAt=0,bleWindowAt=0,statusAt=0,bootId=1;size_t bleCount=0,bleCursor=0,serialBudget=3600;BleRecord bleRows[MAX_BLE_RECORDS]{};String bleError,storageReply;
bool networkBusy(){return busy;}void resumeWifi(){accepting.store(true);}bool emit(const String&){return true;}String quote(const String&s){return String("\"")+s+"\"";}String macText(const uint8_t*){return "00:00:00:00:00:01";}String classJson(const DeviceClass&){return "";}const char*bluetoothCompany(uint16_t){return "Company";}
#include "../DetectorTiempoReal/ble_runtime.h"
void command(const char*s){auto*j=cJSON_Parse(s);assert(j&&handleModeCommand(j,fakeNow));cJSON_Delete(j);}
int main(){
 bleTick(1000);assert(!bleSelected&&inits==0&&starts==0&&accepting.load());
 command(R"({"cmd":"ble_set","enabled":true})");assert(bleSelected&&inits==1&&!accepting.load());bleTick(1001);assert(starts==1&&bleScanning.load());
 command(R"({"cmd":"ble_set","enabled":true})");bleTick(1002);assert(starts==1&&inits==1);
 command(R"({"cmd":"ble_set","enabled":false})");bleTick(1003);assert(!accepting.load()&&!bleSelected&&stops>0);
 esp_ble_gap_cb_param_t p;callback(3,&p);bleTick(1004);assert(accepting.load()&&!bleScanning.load());
 busy=true;command(R"({"cmd":"ble_set","enabled":true})");assert(!bleSelected&&accepting.load());busy=false;
 command(R"({"cmd":"ble_set","enabled":1})");assert(!bleSelected);
 fakeStartFailure=true;command(R"({"cmd":"ble_set","enabled":true})");bleTick(1005);assert(!bleSelected&&accepting.load());
 std::cout<<"OK: WiFi boot, on-demand BLE initialization, idempotence, asynchronous stop before WiFi, busy/invalid rejection, scan failure recovery\n";
}
