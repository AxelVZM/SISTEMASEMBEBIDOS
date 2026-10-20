/* V7.2 - Conteo autonomo Wi-Fi/BLE; red y nube opcionales configurables por USB.
   ESP32 clasico, core 3.3.2. Captura sin red; subida por ventanas con pausa visible. */
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <cJSON.h>
#include <mbedtls/base64.h>
#include <atomic>
#include <algorithm>
#include <time.h>
#include <sys/time.h>
#include <esp_wifi.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_gap_ble_api.h>
#include <esp_task_wdt.h>
#include <esp_system.h>
#include "count_core.h"
#include "ble_core.h"
#include "oui_data.h"
#include "bluetooth_companies.h"
#include "device_classifier.h"
using namespace detector;
Record rows[MAX_RECORDS]{};BleRecord bleRows[MAX_BLE_RECORDS]{};
size_t rowCount=0,bleCount=0,rowCursor=0,bleCursor=0;
QueueHandle_t rxQueue=nullptr,bleQueue=nullptr;
std::atomic<bool> accepting{false},bleReady{false},bleComplete{false};
std::atomic<uint32_t> rxDrops{0},bleDrops{0};
uint32_t tableDrops=0,bleTableDrops=0,bootId=0,nextBle=0,bleAt=0,hopAt=0,retryAt=0,periodAt=0,statusAt=0,syncAt=0,bleInitAt=0,bleRetryAt=0;
bool radioReady=false,blePhase=false,bleAttempted=false,bleFailed=false,fsReady=false,watchdogReady=false;
uint8_t channel=FIRST_CHANNEL,ownMac[6]{};size_t serialBudget=3600;
String radioError="",bleError="",storageError="";
String quote(const String &s){String out="\"";for(size_t i=0;i<s.length();i++){uint8_t c=s[i];if(c=='"'||c=='\\'){out+='\\';out+=char(c);}else if(c<32){char x[7];snprintf(x,sizeof(x),"\\u%04x",c);out+=x;}else out+=char(c);}return out+'"';}
String classJson(const DeviceClass &c){return String(",\"deviceType\":")+quote(deviceKey(c.kind))+",\"deviceLabel\":"+quote(deviceLabel(c.kind))+",\"classLevel\":"+quote(c.level)+",\"classEvidence\":"+quote(c.evidence);}
String macText(const uint8_t *m){char s[18];snprintf(s,sizeof(s),"%02X:%02X:%02X:%02X:%02X:%02X",m[0],m[1],m[2],m[3],m[4],m[5]);return s;}
bool emit(const String &s){size_t n=s.length()+1;if(n>serialBudget||n>size_t(Serial.availableForWrite()))return false;Serial.write(reinterpret_cast<const uint8_t*>(s.c_str()),s.length());Serial.write('\n');serialBudget-=n;return true;}
CountSummary counts(uint32_t now){CountSummary s;for(size_t i=0;i<rowCount;i++)if(recent(now,rows[i].last)){s.wifi++;if(rows[i].value.source&AP)s.aps++;if(rows[i].value.source&CLIENT)s.clients++;}for(size_t i=0;i<bleCount;i++)if(recent(now,bleRows[i].last))s.ble++;s.wifiCapacity=s.wifi==MAX_RECORDS;s.bleCapacity=s.ble==MAX_BLE_RECORDS;return s;}
bool startWifi();
void resumeWifi();
bool networkBusy();
bool handleNetworkCommand(cJSON*,uint32_t);
#include "hardware.h"
#include "journal.h"
#include "network_runtime.h"
void receiveWifi(void *buffer,wifi_promiscuous_pkt_type_t type){
 if(!accepting.load()||!buffer||(type!=WIFI_PKT_MGMT&&type!=WIFI_PKT_DATA))return;auto *p=static_cast<wifi_promiscuous_pkt_t*>(buffer);if(p->rx_ctrl.rx_state||p->rx_ctrl.sig_len<28||p->rx_ctrl.rssi<MIN_RSSI)return;Event e;if(!parseFrame(p->payload,p->rx_ctrl.sig_len-4,p->rx_ctrl.rssi,p->rx_ctrl.channel,millis(),e)||!memcmp(e.mac,ownMac,6))return;if(xQueueSend(rxQueue,&e,0)!=pdTRUE)rxDrops.fetch_add(1);
}
bool startWifi(){
 accepting.store(false);esp_wifi_set_promiscuous(false);WiFi.persistent(false);WiFi.setAutoReconnect(false);if(!WiFi.mode(WIFI_STA)){radioError="No se pudo activar Wi-Fi";return false;}WiFi.disconnect(false,false);esp_wifi_get_mac(WIFI_IF_STA,ownMac);
 wifi_country_t country{};memcpy(country.cc,"US",3);country.schan=1;country.nchan=11;country.max_tx_power=20;country.policy=WIFI_COUNTRY_POLICY_MANUAL;
 wifi_promiscuous_filter_t filter{};filter.filter_mask=WIFI_PROMIS_FILTER_MASK_MGMT|WIFI_PROMIS_FILTER_MASK_DATA;channel=FIRST_CHANNEL;
 esp_err_t err=esp_wifi_set_country(&country);if(err==ESP_OK)err=esp_wifi_set_promiscuous_filter(&filter);if(err==ESP_OK)err=esp_wifi_set_promiscuous_rx_cb(receiveWifi);if(err==ESP_OK)err=esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE);if(err==ESP_OK)err=esp_wifi_set_promiscuous(true);
 if(err!=ESP_OK){radioError=esp_err_to_name(err);return false;}accepting.store(true);radioError="";hopAt=millis();return true;
}
void gapCallback(esp_gap_ble_cb_event_t event,esp_ble_gap_cb_param_t *p){
 if(event==ESP_GAP_BLE_SCAN_PARAM_SET_COMPLETE_EVT){bleReady.store(p->scan_param_cmpl.status==ESP_BT_STATUS_SUCCESS);bleComplete.store(p->scan_param_cmpl.status!=ESP_BT_STATUS_SUCCESS);return;}
 if(event==ESP_GAP_BLE_SCAN_START_COMPLETE_EVT&&p->scan_start_cmpl.status!=ESP_BT_STATUS_SUCCESS){bleComplete.store(true);return;}
 if(event==ESP_GAP_BLE_SCAN_RESULT_EVT){if(p->scan_rst.search_evt==ESP_GAP_SEARCH_INQ_CMPL_EVT){bleComplete.store(true);return;}if(p->scan_rst.search_evt!=ESP_GAP_SEARCH_INQ_RES_EVT)return;BleEvent e;memcpy(e.mac,p->scan_rst.bda,6);e.addressType=p->scan_rst.ble_addr_type;e.rssi=p->scan_rst.rssi;e.time=millis();size_t n=p->scan_rst.adv_data_len;if(n<=sizeof(p->scan_rst.ble_adv)&&parseAdvertisement(p->scan_rst.ble_adv,n,e)&&xQueueSend(bleQueue,&e,0)!=pdTRUE)bleDrops.fetch_add(1);}
 if(event==ESP_GAP_BLE_SEC_REQ_EVT)esp_ble_gap_security_rsp(p->ble_security.ble_req.bd_addr,false);
}
void initializeBle(){
 bleInitAt=millis();bleRetryAt=bleInitAt;bleReady.store(false);bleComplete.store(false);bleFailed=false;
 if(bleAttempted){auto host=esp_bluedroid_get_status();if(host==ESP_BLUEDROID_STATUS_ENABLED)esp_bluedroid_disable();if(esp_bluedroid_get_status()==ESP_BLUEDROID_STATUS_INITIALIZED)esp_bluedroid_deinit();auto controller=esp_bt_controller_get_status();if(controller==ESP_BT_CONTROLLER_STATUS_ENABLED)esp_bt_controller_disable();if(esp_bt_controller_get_status()==ESP_BT_CONTROLLER_STATUS_INITED)esp_bt_controller_deinit();}
 bleAttempted=true;if(!bleQueue){bleError="Sin cola BLE";bleFailed=true;return;}
 esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);esp_bt_controller_config_t cfg=BT_CONTROLLER_INIT_CONFIG_DEFAULT();esp_err_t err=esp_bt_controller_init(&cfg);if(err==ESP_OK)err=esp_bt_controller_enable(ESP_BT_MODE_BLE);if(err==ESP_OK)err=esp_bluedroid_init();if(err==ESP_OK)err=esp_bluedroid_enable();if(err==ESP_OK)err=esp_ble_gap_register_callback(gapCallback);
 if(err!=ESP_OK){bleError=String("BLE: ")+esp_err_to_name(err);bleFailed=true;return;}
 esp_ble_scan_params_t params{};params.scan_type=BLE_SCAN_TYPE_PASSIVE;params.own_addr_type=BLE_ADDR_TYPE_PUBLIC;params.scan_filter_policy=BLE_SCAN_FILTER_ALLOW_ALL;params.scan_interval=0x80;params.scan_window=0x60;params.scan_duplicate=BLE_SCAN_DUPLICATE_DISABLE;
 if(esp_ble_gap_set_scan_params(&params)!=ESP_OK){bleError="No se pudo configurar BLE";bleFailed=true;}nextBle=millis()+WIFI_OBSERVE_MS;
}
void resumeWifi(){blePhase=false;bleComplete.store(false);nextBle=millis()+WIFI_OBSERVE_MS;if(radioReady){if(esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE)==ESP_OK&&esp_wifi_set_promiscuous(true)==ESP_OK)accepting.store(true);else{radioReady=false;radioError="Fallo al reanudar Wi-Fi";retryAt=millis();}}}
void radioTick(uint32_t now){
 if(networkBusy())return;
 if(!blePhase&&!radioReady&&rxQueue&&now-retryAt>=5000){retryAt=now;radioReady=startWifi();}
 if(blePhase&&(bleComplete.exchange(false)||now-bleAt>7000)){if(now-bleAt>7000)bleError="BLE sin fin de ventana; reintento automatico";esp_ble_gap_stop_scanning();resumeWifi();}
 if(!blePhase&&bleReady.load()&&int32_t(now-nextBle)>=0){accepting.store(false);esp_wifi_set_promiscuous(false);bleComplete.store(false);esp_err_t err=esp_ble_gap_start_scanning(BLE_OBSERVE_SECONDS);if(err==ESP_OK){blePhase=true;bleAt=now;bleError="";}else{bleError="Fallo de escaneo BLE; reintento en 10 s";resumeWifi();}}
 if(!blePhase&&radioReady&&now-hopAt>=HOP_MS){hopAt=now;channel=channel>=LAST_CHANNEL?FIRST_CHANNEL:channel+1;if(esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE)!=ESP_OK){accepting.store(false);radioReady=false;radioError="Fallo de canal; recuperacion automatica";esp_wifi_set_promiscuous(false);retryAt=now;}}
 if(bleAttempted&&!bleReady.load()&&!bleFailed&&now-bleInitAt>10000){bleError="BLE no confirmo inicializacion; Wi-Fi continua";bleFailed=true;}
 if(!blePhase&&bleFailed&&bleQueue&&now-bleRetryAt>=60000)initializeBle();
}
void processEvents(){Event e;for(size_t k=0;k<32&&rxQueue&&xQueueReceive(rxQueue,&e,0)==pdTRUE;k++)if(upsertWifi(rows,rowCount,e)<0)tableDrops++;BleEvent b;for(size_t k=0;k<32&&bleQueue&&xQueueReceive(bleQueue,&b,0)==pdTRUE;k++)if(upsertBle(bleRows,bleCount,b)<0)bleTableDrops++;}
void sendStatus(uint32_t now){
 if(now-statusAt<1000)return;auto c=counts(now);String s="{\"kind\":\"status\",\"firmware\":\"7.2\",\"b\":"+String(bootId)+",\"ms\":"+String(now)+",\"ttl\":60000,\"wifi\":"+String(c.wifi)+",\"ble\":"+String(c.ble)+",\"aps\":"+String(c.aps)+",\"clients\":"+String(c.clients)+",\"wifiKnown\":"+String(rowCount)+",\"bleKnown\":"+String(bleCount)+",\"wifiCapacity\":"+String(c.wifiCapacity?"true":"false")+",\"bleCapacity\":"+String(c.bleCapacity?"true":"false")+",\"wifiOmitted\":"+String(tableDrops)+",\"bleOmitted\":"+String(bleTableDrops)+",\"rxOmitted\":"+String(rxDrops.load())+",\"bleRxOmitted\":"+String(bleDrops.load())+",\"radio\":"+quote(networkBusy()?"Red":blePhase?"BLE":"Wi-Fi")+",\"channel\":"+String(channel)+",\"wifiReady\":"+String(radioReady?"true":"false")+",\"bleReady\":"+String(bleReady.load()?"true":"false")+",\"wifiError\":"+quote(radioError)+",\"bleError\":"+quote(bleError)+",\"storage\":"+String(fsReady?"true":"false")+",\"storageError\":"+quote(storageError)+",\"logBytes\":"+String(journalBytes())+",\"heap\":"+String(ESP.getFreeHeap())+",\"minHeap\":"+String(ESP.getMinFreeHeap())+",\"oled\":"+String(oledReady?"true":"false")+",\"rtc\":"+String(rtcPresent?"true":"false")+",\"clock\":"+String(clockValid()?"true":"false")+",\"epoch\":"+(clockValid()?String(uint32_t(time(nullptr))):String("null"))+",\"watchdog\":"+String(watchdogReady?"true":"false")+",\"resetReason\":"+String(esp_reset_reason())+",\"netPaused\":"+String(networkBusy()?"true":"false")+"}";if(emit(s))statusAt=now;
}
void sendRows(){
 for(size_t tries=0;tries<rowCount&&serialBudget>1000;tries++){size_t i=rowCursor;rowCursor=(i+1)%rowCount;auto &r=rows[i];if(!r.dirty)continue;const auto &v=r.value;String s="{\"kind\":\"wifi\",\"b\":"+String(bootId)+",\"slot\":"+String(i)+",\"mac\":"+quote(macText(v.mac))+",\"local\":"+String(v.mac[0]&2?"true":"false")+",\"role\":"+quote((v.source&AP)&&(v.source&CLIENT)?"AP/cliente":(v.source&AP)?"AP":(v.source&CLIENT)?"Cliente":"Otro emisor")+",\"ssid\":"+quote(v.ssid)+",\"name\":"+quote(v.p2p.name[0]?v.p2p.name:v.wps.name)+",\"nameSource\":"+quote(v.p2p.name[0]?"Wi-Fi Direct":v.wps.name[0]?"WPS":"")+",\"vendor\":"+quote(manufacturer(v.mac))+",\"manufacturer\":"+quote(v.wps.manufacturer)+",\"model\":"+quote(v.wps.model)+",\"wpsConflict\":"+String(r.wpsConflict?"true":"false")+",\"number\":"+quote(v.wps.number)+",\"security\":"+quote(securityText(v.capabilities))+",\"wifiGeneration\":"+String(v.capabilities.generation)+",\"rssi\":"+String(r.ema,1)+",\"channel\":"+String(v.channel)+",\"frames\":"+String(r.frames)+",\"last\":"+String(r.last)+classJson(classifyWifi(r))+"}";if(!emit(s)){rowCursor=i;break;}r.dirty=false;}
}
void sendBleRows(){
 if(!bleCount)return;for(size_t tries=0;tries<bleCount;tries++){size_t i=bleCursor;bleCursor=(i+1)%bleCount;auto &r=bleRows[i];if(!r.dirty)continue;auto &v=r.value;String s="{\"kind\":\"ble\",\"b\":"+String(bootId)+",\"slot\":"+String(i)+",\"mac\":"+quote(macText(v.mac))+",\"addressType\":"+String(v.addressType)+",\"name\":"+quote(v.name)+",\"companyId\":"+(v.hasCompany?String(v.company):String("null"))+",\"company\":"+quote(v.hasCompany?bluetoothCompany(v.company):"No anunciado")+",\"companyConflict\":"+String(r.companyConflict?"true":"false")+",\"appearance\":"+(v.hasAppearance?String(v.appearance):String("null"))+",\"disAdvertised\":"+String(v.hasDis?"true":"false")+",\"rssi\":"+String(r.ema,1)+",\"frames\":"+String(r.frames)+",\"last\":"+String(r.last)+classJson(classifyBle(r))+"}";if(emit(s))r.dirty=false;else bleCursor=i;break;}
}
void setup(){
 Serial.setTxBufferSize(4096);Serial.begin(115200);bootId=esp_random();initializeHardware();initializeJournal();initializeNetwork();rxQueue=xQueueCreate(QUEUE_LENGTH,sizeof(Event));bleQueue=xQueueCreate(16,sizeof(BleEvent));if(rxQueue)radioReady=startWifi();else radioError="Sin memoria para cola Wi-Fi";retryAt=millis();initializeBle();
 esp_task_wdt_config_t cfg{};cfg.timeout_ms=15000;cfg.idle_core_mask=0;cfg.trigger_panic=true;esp_err_t w=esp_task_wdt_init(&cfg);if(w==ESP_ERR_INVALID_STATE)w=esp_task_wdt_reconfigure(&cfg);if(w==ESP_OK)watchdogReady=esp_task_wdt_add(nullptr)==ESP_OK;
}
void loop(){
 uint32_t now=millis();processEvents();networkTick(now);radioTick(now);hardwareTick(now);journalTick(now);readCommands(now);
 if(now-periodAt>=400){periodAt=now;serialBudget=3600;}
 if(now-syncAt>=10000){syncAt=now;for(size_t i=0;i<rowCount;i++)rows[i].dirty=true;for(size_t i=0;i<bleCount;i++)bleRows[i].dirty=true;}
 sendStatus(now);sendNetworkStatus(now);sendExport(now);if((periodAt/400)%2){sendBleRows();sendRows();}else{sendRows();sendBleRows();}
 if(watchdogReady)esp_task_wdt_reset();delay(1);
}
