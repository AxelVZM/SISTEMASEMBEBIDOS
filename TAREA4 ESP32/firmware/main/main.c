#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_random.h"
#include "esp_task_wdt.h"
#include "esp_attr.h"
#include "nvs.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_ble_api.h"
#include "esp_gap_bt_api.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "cJSON.h"
#include "wifi_header.h"
#include "wifi_metadata.h"
#include "recovery_policy.h"

#define BLE_READY BIT0
#define BLE_DONE BIT1
#define BT_DONE BIT2
#define BLE_STOPPED BIT3
#define BLE_STARTED BIT4
#define BT_STARTED BIT5
#define BLE_FAILED BIT6
#define OBS_QUEUE 32

typedef struct {int channels[11],n,wifi_ms,dwell_ms,ble_seconds,classic_units,bt_interval_seconds,dedup_ms,min_rssi; bool ble_active; char id[40];} config_t;
typedef struct {
    uint8_t mac[6]; int tech,rssi,channel,role,addr_type,adv_type,company,appearance,cod,tx_power;
    wifi_metadata_t wps;bool name_complete;uint8_t name_source;
    uint64_t ms; char name[249],manufacturer[65],services[16][37],frame[24]; int service_count;
} observation_t;
static QueueHandle_t observations,configs;
static SemaphoreHandle_t output_lock, config_lock;
static EventGroupHandle_t flags;
typedef enum {WIFI_SCAN,BLE_SCAN,BT_CLASSIC_SCAN,PROCESS_EVENTS,IDLE,ERROR_RECOVERY} scan_state_t;
static const char *state_names[]={"WIFI_SCAN","BLE_SCAN","BT_CLASSIC_SCAN","PROCESS_EVENTS","IDLE","ERROR_RECOVERY"};
static scan_state_t state=IDLE;
static scan_state_t previous_state=IDLE;
static unsigned diagnostic_attempt=0;
static char last_failure[300];
static volatile esp_bt_status_t ble_param_result=ESP_BT_STATUS_SUCCESS;
static volatile esp_bt_status_t ble_start_result=ESP_BT_STATUS_SUCCESS;
static volatile esp_bt_status_t ble_stop_result=ESP_BT_STATUS_SUCCESS;
static volatile int ble_failed_operation=0;
static portMUX_TYPE metrics_lock=portMUX_INITIALIZER_UNLOCKED;
typedef struct {
    uint32_t captured,sent,dropped,dedup,rssi_filtered,json_failures,serial_failures,high_water;
    uint32_t channel_events[11],recoveries;uint16_t visited;
    uint64_t wifi_ms,ble_ms,classic_ms,wifi_started,ble_started,classic_started,last_capture;
    bool wifi_initialized,bt_initialized,wifi_active,ble_active,classic_active,ble_active_scan;
    int channel;
} metrics_t;
static metrics_t metrics;
static uint32_t boot_id,boot_count;
static const char *reset_reason="not_available";
RTC_NOINIT_ATTR static uint32_t recovery_magic,recovery_streak;
#define RECOVERY_MAGIC 0xD37EC702
static uint64_t milliseconds(void);
static void set_state(scan_state_t value){portENTER_CRITICAL(&metrics_lock);previous_state=state;state=value;portEXIT_CRITICAL(&metrics_lock);}
static void bump(uint32_t *value){portENTER_CRITICAL(&metrics_lock);(*value)++;portEXIT_CRITICAL(&metrics_lock);}
static void activity(int tech,bool active){
    uint64_t now=milliseconds();portENTER_CRITICAL(&metrics_lock);
    bool *flag=tech==0?&metrics.wifi_active:tech==1?&metrics.ble_active:&metrics.classic_active;
    uint64_t *start=tech==0?&metrics.wifi_started:tech==1?&metrics.ble_started:&metrics.classic_started;
    uint64_t *total=tech==0?&metrics.wifi_ms:tech==1?&metrics.ble_ms:&metrics.classic_ms;
    if(active && !*flag)*start=now;
    if(!active && *flag)*total+=now-*start;
    *flag=active;portEXIT_CRITICAL(&metrics_lock);
}
static config_t cfg={.channels={1,2,3,4,5,6,7,8,9,10,11},.n=11,.wifi_ms=6000,.dwell_ms=250,.ble_seconds=6,.classic_units=4,.dedup_ms=1000,.min_rssi=-100,.ble_active=true};

static uint64_t milliseconds(void){return (uint64_t)(esp_timer_get_time()/1000);}
static bool emit(cJSON *j){
    // Reuse one bounded print buffer. Radio callbacks never serialize JSON.
    static char output_buffer[4096];
    if(!j){bump(&metrics.json_failures);return false;}
    if(xSemaphoreTake(output_lock,pdMS_TO_TICKS(2000))!=pdTRUE){cJSON_Delete(j);bump(&metrics.serial_failures);return false;}
    bool ok=cJSON_PrintPreallocated(j,output_buffer,sizeof(output_buffer),false);
    if(ok){if(puts(output_buffer)==EOF){bump(&metrics.serial_failures);ok=false;}}
    else bump(&metrics.json_failures);
    xSemaphoreGive(output_lock);cJSON_Delete(j);return ok;
}
static void emit_error_text(const char *message){
    cJSON *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"event","error");cJSON_AddStringToObject(j,"type","error");
    cJSON_AddNumberToObject(j,"v",2);cJSON_AddStringToObject(j,"message",message);emit(j);
}
static void error_message(const char *message){
    char text[400];
    if(state==ERROR_RECOVERY && last_failure[0]){
        snprintf(text,sizeof(text),"%.90s | causa: %.290s",message,last_failure);
    }else{
        snprintf(text,sizeof(text),"%.275s | estado=%s intento=%u racha=%lu heap=%lu",message,state_names[state],diagnostic_attempt,(unsigned long)recovery_streak,(unsigned long)esp_get_free_heap_size());
    }
    emit_error_text(text);
}
static const char *gap_status_name(int code){
    switch(code){case ESP_BT_STATUS_SUCCESS:return "SUCCESS";case ESP_BT_STATUS_FAIL:return "FAIL";case ESP_BT_STATUS_NOT_READY:return "NOT_READY";case ESP_BT_STATUS_NOMEM:return "NOMEM";case ESP_BT_STATUS_BUSY:return "BUSY";case ESP_BT_STATUS_UNSUPPORTED:return "UNSUPPORTED";case ESP_BT_STATUS_PARM_INVALID:return "PARM_INVALID";case ESP_BT_STATUS_TIMEOUT:return "TIMEOUT";case ESP_BT_STATUS_MEMORY_FULL:return "MEMORY_FULL";default:return "OTHER_GAP_STATUS";}
}
static void report_failure(const char *module,const char *operation,int code,bool gap_status){
    char code_text[80],diagnostic[300];
    if(gap_status)snprintf(code_text,sizeof(code_text),"gap_status=%d (%s; no esp_err_t)",code,gap_status_name(code));
    else snprintf(code_text,sizeof(code_text),"esp_err=0x%X (%s)",(unsigned)code,esp_err_to_name(code));
    snprintf(diagnostic,sizeof(diagnostic),"mod=%.18s op=%.45s %.79s anterior=%s actual=%s intento=%u heap=%lu",
        module,operation,code_text,state_names[previous_state],state_names[state],diagnostic_attempt,(unsigned long)esp_get_free_heap_size());
    if(!last_failure[0])snprintf(last_failure,sizeof(last_failure),"%s",diagnostic);
    emit_error_text(diagnostic);
}
static bool radio_ok(esp_err_t error,const char *operation){
    if(error==ESP_OK)return true;
    const char *module=strncmp(operation,"wifi",4)==0?"wifi":strncmp(operation,"ble",3)==0?"ble":strncmp(operation,"classic",7)==0?"classic":strncmp(operation,"bt",2)==0 || strncmp(operation,"bluedroid",9)==0?"bluetooth":"system";
    report_failure(module,operation,error,false);return false;
}
static void watched_delay(int ms){
    while(ms>0){esp_task_wdt_reset();int step=ms>250?250:ms;vTaskDelay(pdMS_TO_TICKS(step));ms-=step;}
}
static observation_t fresh(int tech,const uint8_t *mac,int rssi){
    observation_t o={0};o.tech=tech;memcpy(o.mac,mac,6);o.rssi=rssi;o.ms=milliseconds();
    o.company=-1;o.appearance=-1;o.cod=-1;o.tx_power=127;o.addr_type=-1;return o;
}
static void enqueue(observation_t *o){
    portENTER_CRITICAL(&metrics_lock);metrics.captured++;metrics.last_capture=o->ms;
    if(o->tech==0 && o->channel>=1 && o->channel<=11)metrics.channel_events[o->channel-1]++;
    portEXIT_CRITICAL(&metrics_lock);
    if(xQueueSend(observations,o,0)!=pdTRUE)bump(&metrics.dropped);
    unsigned depth=uxQueueMessagesWaiting(observations);
    portENTER_CRITICAL(&metrics_lock);if(depth>metrics.high_water)metrics.high_water=depth;portEXIT_CRITICAL(&metrics_lock);
}

static void wifi_callback(void *buffer,wifi_promiscuous_pkt_type_t type){
    if(type!=WIFI_PKT_MGMT && type!=WIFI_PKT_DATA)return;
    const wifi_promiscuous_pkt_t *p=buffer;wifi_identity_t id;
    if(!wifi_identity(p->payload,p->rx_ctrl.sig_len,&id))return;
    observation_t o=fresh(0,id.mac,p->rx_ctrl.rssi);o.channel=p->rx_ctrl.channel;o.role=id.role;
    snprintf(o.frame,sizeof(o.frame),"%s",id.frame);
    if(type==WIFI_PKT_MGMT && p->rx_ctrl.sig_len>=4)wifi_metadata(p->payload,p->rx_ctrl.sig_len-4,&o.wps);
    enqueue(&o);
}

static void ad_parse(observation_t *o,const uint8_t *p,size_t len,uint8_t source){
    // Copy only explicit advertising metadata; no raw EIR/AD is stored.
    for(size_t i=0;i<len;){
        unsigned n=p[i]; if(n==0 || i+1+n>len)break;
        unsigned type=p[i+1];const uint8_t *v=p+i+2;unsigned bytes=n-1;
        if((type==8 || type==9) && bytes && (type==9 || !o->name_complete)){
            o->name_complete=(type==9);o->name_source=source;
            unsigned m=bytes<248?bytes:248;
            // Names may be arbitrary bytes. ASCII replacement guarantees valid UTF-8 JSON.
            for(unsigned a=0;a<m;a++){o->name[a]=(v[a]>=32 && v[a]<127)?v[a]:'?';}
            o->name[m]=0;
        }else if(type==0xff && bytes>=2){
            o->company=v[0]|(v[1]<<8);unsigned m=bytes-2;if(m>32)m=32;
            for(unsigned a=0;a<m;a++)snprintf(o->manufacturer+2*a,3,"%02X",v[a+2]);
        }else if(type==0x19 && bytes>=2)o->appearance=v[0]|(v[1]<<8);
        else if(type==0x0a && bytes==1)o->tx_power=(int8_t)v[0];
        else if(type>=2 && type<=7){
            unsigned step=(type<=3)?2:(type<=5?4:16);
            for(unsigned a=0;a+step<=bytes && o->service_count<16;a+=step){
                char *s=o->services[o->service_count++];
                for(unsigned b=0;b<step;b++)snprintf(s+b*2,3,"%02X",v[a+step-1-b]);
            }
        }
        i+=1+n;
    }
}
static void ble_callback(esp_gap_ble_cb_event_t event,esp_ble_gap_cb_param_t *p){
    if(event==ESP_GAP_BLE_SCAN_PARAM_SET_COMPLETE_EVT){
        ble_param_result=p->scan_param_cmpl.status;
        if(p->scan_param_cmpl.status==ESP_BT_STATUS_SUCCESS)xEventGroupSetBits(flags,BLE_READY);
        else {ble_failed_operation=1;xEventGroupSetBits(flags,BLE_FAILED);}
    }else if(event==ESP_GAP_BLE_SCAN_START_COMPLETE_EVT){
        ble_start_result=p->scan_start_cmpl.status;
        if(p->scan_start_cmpl.status==ESP_BT_STATUS_SUCCESS){activity(1,true);xEventGroupSetBits(flags,BLE_STARTED);}
        else {ble_failed_operation=2;xEventGroupSetBits(flags,BLE_FAILED);}
    }else if(event==ESP_GAP_BLE_SCAN_RESULT_EVT){
        if(p->scan_rst.search_evt==ESP_GAP_SEARCH_INQ_RES_EVT){
            observation_t o=fresh(1,p->scan_rst.bda,p->scan_rst.rssi);
            o.addr_type=p->scan_rst.ble_addr_type;o.adv_type=p->scan_rst.ble_evt_type;
            unsigned adv=p->scan_rst.adv_data_len,rsp=p->scan_rst.scan_rsp_len;
            if(adv<=31 && rsp<=31 && adv+rsp<=sizeof(p->scan_rst.ble_adv)){
                ad_parse(&o,p->scan_rst.ble_adv,adv,1);
                if(rsp)ad_parse(&o,p->scan_rst.ble_adv+adv,rsp,2);
            }
            enqueue(&o);
        }else if(p->scan_rst.search_evt==ESP_GAP_SEARCH_INQ_CMPL_EVT){activity(1,false);xEventGroupSetBits(flags,BLE_DONE);}
    }else if(event==ESP_GAP_BLE_SCAN_STOP_COMPLETE_EVT){ble_stop_result=p->scan_stop_cmpl.status;activity(1,false);xEventGroupSetBits(flags,BLE_STOPPED);}
}
static void classic_callback(esp_bt_gap_cb_event_t event,esp_bt_gap_cb_param_t *p){
    if(event==ESP_BT_GAP_DISC_STATE_CHANGED_EVT){
        if(p->disc_st_chg.state==ESP_BT_GAP_DISCOVERY_STARTED){activity(2,true);xEventGroupSetBits(flags,BT_STARTED);}
        if(p->disc_st_chg.state==ESP_BT_GAP_DISCOVERY_STOPPED){activity(2,false);xEventGroupSetBits(flags,BT_DONE);}
    }else if(event==ESP_BT_GAP_DISC_RES_EVT){
        observation_t o=fresh(2,p->disc_res.bda,127);
        for(int i=0;i<p->disc_res.num_prop;i++){
            esp_bt_gap_dev_prop_t *prop=&p->disc_res.prop[i];
            if(prop->type==ESP_BT_GAP_DEV_PROP_RSSI && prop->len>=1)o.rssi=*(int8_t*)prop->val;
            else if(prop->type==ESP_BT_GAP_DEV_PROP_COD && prop->len>=4){uint32_t cod;memcpy(&cod,prop->val,4);o.cod=cod&0xffffff;}
            else if(prop->type==ESP_BT_GAP_DEV_PROP_BDNAME){
                unsigned n=prop->len<248?prop->len:248;const uint8_t *v=prop->val;
                for(unsigned a=0;a<n;a++){o.name[a]=(v[a]>=32&&v[a]<127)?v[a]:'?';}
                o.name[n]=0;o.name_complete=true;o.name_source=3;
            }else if(prop->type==ESP_BT_GAP_DEV_PROP_EIR)ad_parse(&o,prop->val,prop->len,4);
        }enqueue(&o);
    }
}

static uint32_t text_hash(const char *text){
    if(!text[0])return 0;
    uint32_t hash=2166136261U;while(*text){hash^=(uint8_t)*text++;hash*=16777619U;}return hash?hash:1;
}
static void writer(void *arg){
    // Bounded cache: identity is scoped to technology; radio callbacks never block on serial.
    static struct {uint8_t mac[6];int tech;uint64_t ms;uint32_t names,wps,classes,company,services;} cache[128];unsigned next=0;
    observation_t o;ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    while(1){
        esp_task_wdt_reset();
        if(xQueueReceive(observations,&o,pdMS_TO_TICKS(500))!=pdTRUE)continue;
        xSemaphoreTake(config_lock,portMAX_DELAY);int min_rssi=cfg.min_rssi,dedup_ms=cfg.dedup_ms;xSemaphoreGive(config_lock);
        if(o.rssi!=127 && o.rssi<min_rssi){bump(&metrics.rssi_filtered);continue;}
        uint32_t names=text_hash(o.name),wps=text_hash(o.wps.manufacturer);
        wps=(wps*16777619U)^text_hash(o.wps.model_name);wps=(wps*16777619U)^text_hash(o.wps.model_number);
        wps=(wps*16777619U)^text_hash(o.wps.device_name);wps=(wps*16777619U)^text_hash(o.wps.ssid);
        wps=(wps*16777619U)^text_hash(o.wps.primary_device_type);wps=(wps*16777619U)^text_hash(o.wps.vendor_ies);
        uint32_t classes=o.appearance>=0?(uint32_t)o.appearance+1:o.cod>=0?(uint32_t)o.cod+1:0;
        uint32_t company=o.company>=0?((uint32_t)o.company+1)^text_hash(o.manufacturer):0,services=0;
        for(int i=0;i<o.service_count;i++)services^=text_hash(o.services[i]);
        int found=-1;
        for(int i=0;i<128;i++)if(cache[i].ms && cache[i].tech==o.tech && memcmp(cache[i].mac,o.mac,6)==0){found=i;break;}
        if(found>=0){
            bool enriched=(names && names!=cache[found].names)||(wps && wps!=cache[found].wps)||(classes && classes!=cache[found].classes)||(company && company!=cache[found].company)||(services && services!=cache[found].services);
            if(!enriched && o.ms-cache[found].ms<(uint64_t)dedup_ms){bump(&metrics.dedup);continue;}
        }
        unsigned slot=found>=0?(unsigned)found:next;
        if(found<0){memset(&cache[slot],0,sizeof(cache[slot]));next=(next+1)%128;}
        memcpy(cache[slot].mac,o.mac,6);cache[slot].tech=o.tech;cache[slot].ms=o.ms;
        if(names)cache[slot].names=names;
        if(wps)cache[slot].wps=wps;
        if(classes)cache[slot].classes=classes;
        if(company)cache[slot].company=company;
        if(services)cache[slot].services=services;
        cJSON *j=cJSON_CreateObject();char mac[18];snprintf(mac,sizeof(mac),"%02X:%02X:%02X:%02X:%02X:%02X",o.mac[0],o.mac[1],o.mac[2],o.mac[3],o.mac[4],o.mac[5]);
        cJSON_AddStringToObject(j,"event","observation");cJSON_AddNumberToObject(j,"v",2);cJSON_AddStringToObject(j,"type","detection");
        cJSON_AddStringToObject(j,"tech",o.tech==0?"wifi":o.tech==1?"ble":"classic");cJSON_AddStringToObject(j,"mac",mac);
        cJSON_AddNumberToObject(j,"uptime_ms",(double)o.ms);
        if(o.rssi!=127)cJSON_AddNumberToObject(j,"rssi",o.rssi);
        if(o.name[0]){
            const char *sources[]={"unknown","advertisement","scan_response","classic_name","classic_eir"};
            cJSON_AddStringToObject(j,"name",o.name);cJSON_AddBoolToObject(j,"name_complete",o.name_complete);
            cJSON_AddStringToObject(j,"name_source",sources[o.name_source<=4?o.name_source:0]);
        }
        if(o.wps.manufacturer[0])cJSON_AddStringToObject(j,"wps_manufacturer",o.wps.manufacturer);
        if(o.wps.model_name[0])cJSON_AddStringToObject(j,"wps_model_name",o.wps.model_name);
        if(o.wps.model_number[0])cJSON_AddStringToObject(j,"wps_model_number",o.wps.model_number);
        if(o.wps.device_name[0])cJSON_AddStringToObject(j,"wps_device_name",o.wps.device_name);
        if(o.wps.ssid[0])cJSON_AddStringToObject(j,"ssid",o.wps.ssid);
        if(o.wps.primary_device_type[0])cJSON_AddStringToObject(j,"wps_primary_device_type",o.wps.primary_device_type);
        if(o.wps.vendor_ies[0])cJSON_AddStringToObject(j,"vendor_ies",o.wps.vendor_ies);
        if(o.tech==0){cJSON_AddNumberToObject(j,"channel",o.channel);cJSON_AddStringToObject(j,"role",o.role==1?"ap":o.role==2?"station":"unknown");cJSON_AddStringToObject(j,"frame_type",o.frame);}
        if(o.tech==1){cJSON_AddStringToObject(j,"address_type",o.addr_type==BLE_ADDR_TYPE_PUBLIC?"public":"random");cJSON_AddNumberToObject(j,"adv_type",o.adv_type);}
        if(o.company>=0){cJSON_AddNumberToObject(j,"company_id",o.company);cJSON_AddStringToObject(j,"manufacturer_data",o.manufacturer);}
        if(o.appearance>=0)cJSON_AddNumberToObject(j,"appearance",o.appearance);
        if(o.cod>=0)cJSON_AddNumberToObject(j,"cod",o.cod);
        if(o.tx_power!=127)cJSON_AddNumberToObject(j,"tx_power",o.tx_power);
        cJSON *j_services=cJSON_AddArrayToObject(j,"services");for(int i=0;i<o.service_count;i++)cJSON_AddItemToArray(j_services,cJSON_CreateString(o.services[i]));
        if(emit(j))bump(&metrics.sent);
    }
}
static int integer(cJSON *j,const char *key,int lo,int hi,int *dest){
    cJSON *v=cJSON_GetObjectItemCaseSensitive(j,key);
    if(!cJSON_IsNumber(v) || v->valuedouble!=v->valueint || v->valueint<lo || v->valueint>hi)return 0;
    *dest=v->valueint;return 1;
}
static void command(cJSON *j){
    cJSON *name=cJSON_GetObjectItemCaseSensitive(j,"command"),*id=cJSON_GetObjectItemCaseSensitive(j,"id");
    if(cJSON_IsString(name) && strcmp(name->valuestring,"recover")==0){
        recovery_streak=0;error_message("Recuperación manual solicitada; reiniciando escáner");vTaskDelay(pdMS_TO_TICKS(100));esp_restart();
    }
    if(!cJSON_IsString(name)||strcmp(name->valuestring,"configure") || !cJSON_IsString(id)||strlen(id->valuestring)>39){error_message("Invalid command");return;}
    config_t next={0};snprintf(next.id,sizeof(next.id),"%s",id->valuestring);
    cJSON *channels=cJSON_GetObjectItemCaseSensitive(j,"channels");bool valid=cJSON_IsArray(channels);
    next.n=cJSON_GetArraySize(channels);if(next.n<1||next.n>11)valid=false;
    for(int a=0;valid&&a<next.n;a++){
        cJSON *v=cJSON_GetArrayItem(channels,a);
        if(!cJSON_IsNumber(v)||v->valuedouble!=v->valueint||v->valueint<1||v->valueint>11){valid=false;break;}
        next.channels[a]=v->valueint;for(int b=0;b<a;b++)if(next.channels[b]==next.channels[a])valid=false;
    }
    valid=valid && integer(j,"wifi_ms",1000,60000,&next.wifi_ms) && integer(j,"dwell_ms",50,2000,&next.dwell_ms)
      && integer(j,"ble_seconds",1,60,&next.ble_seconds) && integer(j,"classic_units",1,48,&next.classic_units)
      && integer(j,"bt_interval_seconds",0,300,&next.bt_interval_seconds) && integer(j,"dedup_ms",100,10000,&next.dedup_ms)
      && integer(j,"min_rssi",-127,0,&next.min_rssi);
    cJSON *active=cJSON_GetObjectItemCaseSensitive(j,"ble_active");
    if(active && !cJSON_IsBool(active))valid=false;
    next.ble_active=cJSON_IsTrue(active);
    if(!valid){error_message("Invalid configuration bounds");return;}
    xQueueOverwrite(configs,&next);
}
static void reader(void *arg){
    char line[1024];size_t n=0;bool discard=false;uint8_t ch;ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    while(1){
        esp_task_wdt_reset();
        if(uart_read_bytes(UART_NUM_0,&ch,1,pdMS_TO_TICKS(100))!=1)continue;
        if(ch=='\n'){
            if(discard)error_message("Comando serial demasiado largo; descartado");
            if(!discard && n){line[n]=0;cJSON *j=cJSON_Parse(line);if(j){command(j);cJSON_Delete(j);}else error_message("Invalid JSON command");}
            n=0;discard=false;
        }else if(ch!='\r'){
            if(n<sizeof(line)-1 && !discard)line[n++]=ch;else discard=true;
        }
    }
}
static void send_status(const char *event){
    metrics_t m;scan_state_t current;
    portENTER_CRITICAL(&metrics_lock);m=metrics;current=state;portEXIT_CRITICAL(&metrics_lock);
    uint64_t now=milliseconds();
    cJSON *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"event",event);cJSON_AddStringToObject(j,"type",event);cJSON_AddNumberToObject(j,"v",2);
    cJSON_AddStringToObject(j,"firmware","2.3.0");cJSON_AddNumberToObject(j,"boot_id",boot_id);cJSON_AddStringToObject(j,"phase",state_names[current]);
    cJSON_AddNumberToObject(j,"uptime_ms",(double)now);cJSON_AddNumberToObject(j,"queue_dropped",m.dropped);
    cJSON_AddNumberToObject(j,"free_heap",esp_get_free_heap_size());cJSON_AddNumberToObject(j,"minimum_free_heap",esp_get_minimum_free_heap_size());
    if(m.channel && m.wifi_active)cJSON_AddNumberToObject(j,"current_channel",m.channel);
    cJSON_AddNumberToObject(j,"events_captured",m.captured);cJSON_AddNumberToObject(j,"events_sent",m.sent);
    cJSON_AddNumberToObject(j,"queue_depth",uxQueueMessagesWaiting(observations));cJSON_AddNumberToObject(j,"queue_capacity",OBS_QUEUE);cJSON_AddNumberToObject(j,"queue_high_water",m.high_water);
    cJSON_AddNumberToObject(j,"dedup_suppressed",m.dedup);cJSON_AddNumberToObject(j,"rssi_filtered",m.rssi_filtered);
    cJSON_AddNumberToObject(j,"json_failures",m.json_failures);cJSON_AddNumberToObject(j,"serial_failures",m.serial_failures);
    cJSON_AddNumberToObject(j,"wifi_listen_ms",(double)(m.wifi_ms+(m.wifi_active?now-m.wifi_started:0)));
    cJSON_AddNumberToObject(j,"ble_scan_ms",(double)(m.ble_ms+(m.ble_active?now-m.ble_started:0)));
    cJSON_AddNumberToObject(j,"classic_scan_ms",(double)(m.classic_ms+(m.classic_active?now-m.classic_started:0)));
    cJSON *channels=cJSON_AddArrayToObject(j,"channels_visited"),*counts=cJSON_AddArrayToObject(j,"channel_events");
    for(int i=0;i<11;i++){if(m.visited&(1<<i))cJSON_AddItemToArray(channels,cJSON_CreateNumber(i+1));cJSON_AddItemToArray(counts,cJSON_CreateNumber(m.channel_events[i]));}
    if(boot_count)cJSON_AddNumberToObject(j,"boot_count",boot_count);
    cJSON_AddStringToObject(j,"reset_reason",reset_reason);cJSON_AddNumberToObject(j,"scanner_recoveries",m.recoveries);cJSON_AddNumberToObject(j,"consecutive_failures",recovery_streak);
    cJSON_AddBoolToObject(j,"wifi_initialized",m.wifi_initialized);cJSON_AddBoolToObject(j,"bluetooth_initialized",m.bt_initialized);
    cJSON_AddBoolToObject(j,"wifi_scanning",m.wifi_active);cJSON_AddBoolToObject(j,"ble_scanning",m.ble_active);cJSON_AddBoolToObject(j,"classic_scanning",m.classic_active);
    if(m.last_capture)cJSON_AddNumberToObject(j,"last_capture_ms",(double)m.last_capture);
    if(m.bt_initialized)cJSON_AddStringToObject(j,"ble_scan_mode",m.ble_active_scan?"active":"passive");
    cJSON_AddStringToObject(j,"serial_host_detection","not_supported");emit(j);
}
static void heartbeat(void *arg){
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    while(1){esp_task_wdt_reset();send_status("heartbeat");watched_delay(3000);}
}
static bool wait_flag(EventBits_t bit,int ms){
    uint64_t end=milliseconds()+ms;
    const char *module=(bit==BT_STARTED || bit==BT_DONE)?"classic":"ble";
    const char *operation=bit==BLE_READY?"scan_params_callback":bit==BLE_STARTED?"scan_start_callback":bit==BLE_DONE?"scan_finished_callback":bit==BLE_STOPPED?"scan_stop_callback":bit==BT_STARTED?"discovery_start_callback":"discovery_stop_callback";
    do{
        esp_task_wdt_reset();
        if(xEventGroupWaitBits(flags,bit,pdTRUE,pdTRUE,pdMS_TO_TICKS(250))&bit){
            if(bit==BLE_STOPPED && ble_stop_result!=ESP_BT_STATUS_SUCCESS)report_failure("ble","scan_stop_callback",ble_stop_result,true);
            return true;
        }
        if(xEventGroupGetBits(flags)&BLE_FAILED){
            report_failure("ble",ble_failed_operation==1?"scan_params_callback":"scan_start_callback",ble_failed_operation==1?ble_param_result:ble_start_result,true);
            return false;
        }
    }while(milliseconds()<end);
    report_failure(module,operation,ESP_ERR_TIMEOUT,false);
    return false;
}
static const char *reason_name(esp_reset_reason_t reason){
    switch(reason){case ESP_RST_POWERON:return "power_on";case ESP_RST_SW:return "software";case ESP_RST_PANIC:return "panic";case ESP_RST_INT_WDT:return "interrupt_watchdog";case ESP_RST_TASK_WDT:return "task_watchdog";case ESP_RST_WDT:return "watchdog";case ESP_RST_BROWNOUT:return "brownout";case ESP_RST_DEEPSLEEP:return "deep_sleep";default:return "other_or_unknown";}
}
static bool configure_ble_scan(bool active){
    esp_ble_scan_params_t scan={.scan_type=active?BLE_SCAN_TYPE_ACTIVE:BLE_SCAN_TYPE_PASSIVE,.own_addr_type=BLE_ADDR_TYPE_PUBLIC,.scan_filter_policy=BLE_SCAN_FILTER_ALLOW_ALL,.scan_interval=0x80,.scan_window=0x40,.scan_duplicate=BLE_SCAN_DUPLICATE_DISABLE};
    xEventGroupClearBits(flags,BLE_READY|BLE_FAILED);
    if(!radio_ok(esp_ble_gap_set_scan_params(&scan),"ble_scan_params") || !wait_flag(BLE_READY,5000))return false;
    portENTER_CRITICAL(&metrics_lock);metrics.ble_active_scan=active;portEXIT_CRITICAL(&metrics_lock);return true;
}
static bool initialize_radios(void){
    if(!metrics.wifi_initialized){
        wifi_init_config_t wi=WIFI_INIT_CONFIG_DEFAULT();
        if(!radio_ok(esp_wifi_init(&wi),"wifi_init"))return false;
        bool ok=radio_ok(esp_wifi_set_storage(WIFI_STORAGE_RAM),"wifi_storage") && radio_ok(esp_wifi_set_mode(WIFI_MODE_NULL),"wifi_mode");
        // ESP-IDF 5.4.2 does not list PE as supported. Use its world-safe
        // profile (channels 1..11), with 802.11d country auto-adoption disabled.
        wifi_promiscuous_filter_t filter={.filter_mask=WIFI_PROMIS_FILTER_MASK_MGMT|WIFI_PROMIS_FILTER_MASK_DATA};
        ok=ok && radio_ok(esp_wifi_set_country_code("01",false),"wifi_country_code_01") && radio_ok(esp_wifi_set_promiscuous_filter(&filter),"wifi_filter") && radio_ok(esp_wifi_set_promiscuous_rx_cb(wifi_callback),"wifi_callback");
        if(!ok){esp_wifi_deinit();return false;}
        portENTER_CRITICAL(&metrics_lock);metrics.wifi_initialized=true;portEXIT_CRITICAL(&metrics_lock);
    }
    if(!metrics.bt_initialized){
        if(esp_bt_controller_get_status()==ESP_BT_CONTROLLER_STATUS_IDLE){esp_bt_controller_config_t bt=BT_CONTROLLER_INIT_CONFIG_DEFAULT();if(!radio_ok(esp_bt_controller_init(&bt),"bt_init"))return false;}
        if(esp_bt_controller_get_status()==ESP_BT_CONTROLLER_STATUS_INITED && !radio_ok(esp_bt_controller_enable(ESP_BT_MODE_BTDM),"bt_enable"))return false;
        if(esp_bluedroid_get_status()==ESP_BLUEDROID_STATUS_UNINITIALIZED && !radio_ok(esp_bluedroid_init(),"bluedroid_init"))return false;
        if(esp_bluedroid_get_status()==ESP_BLUEDROID_STATUS_INITIALIZED && !radio_ok(esp_bluedroid_enable(),"bluedroid_enable"))return false;
        if(!radio_ok(esp_ble_gap_register_callback(ble_callback),"ble_callback") || !radio_ok(esp_bt_gap_register_callback(classic_callback),"classic_callback"))return false;
        if(!configure_ble_scan(cfg.ble_active))return false;
        portENTER_CRITICAL(&metrics_lock);metrics.bt_initialized=true;portEXIT_CRITICAL(&metrics_lock);
    }
    return true;
}
static bool stop_radios(void){
    bool ok=true;
    if(metrics.wifi_active){esp_err_t e=esp_wifi_set_promiscuous(false);esp_err_t stop=esp_wifi_stop();radio_ok(e,"wifi_recovery_promiscuous_stop");radio_ok(stop,"wifi_recovery_stop");ok=(e==ESP_OK && stop==ESP_OK);activity(0,false);}
    if(metrics.ble_active){xEventGroupClearBits(flags,BLE_STOPPED|BLE_FAILED);esp_err_t e=esp_ble_gap_stop_scanning();if(!radio_ok(e,"ble_recovery_stop") || !wait_flag(BLE_STOPPED,3000))ok=false;}
    if(metrics.classic_active){xEventGroupClearBits(flags,BT_DONE|BLE_FAILED);esp_err_t e=esp_bt_gap_cancel_discovery();if(!radio_ok(e,"classic_recovery_cancel") || !wait_flag(BT_DONE,4000))ok=false;}
    return ok;
}
static bool scan_cycle(void){
    set_state(WIFI_SCAN);
    if(!radio_ok(esp_wifi_start(),"wifi_start"))return false;
    if(!radio_ok(esp_wifi_set_promiscuous(true),"wifi_promiscuous")){esp_wifi_stop();return false;}
    activity(0,true);send_status("status");uint64_t end=milliseconds()+cfg.wifi_ms;int index=0;
    while(milliseconds()<end){
        int channel=cfg.channels[index++%cfg.n];
        if(!radio_ok(esp_wifi_set_channel(channel,WIFI_SECOND_CHAN_NONE),"wifi_channel"))return false;
        portENTER_CRITICAL(&metrics_lock);metrics.channel=channel;metrics.visited|=1<<(channel-1);portEXIT_CRITICAL(&metrics_lock);
        uint64_t now=milliseconds();uint64_t remaining=now<end?end-now:0;if(remaining>(uint64_t)cfg.dwell_ms)remaining=cfg.dwell_ms;watched_delay((int)remaining);
    }
    if(!radio_ok(esp_wifi_set_promiscuous(false),"wifi_stop_promiscuous") || !radio_ok(esp_wifi_stop(),"wifi_stop"))return false;
    activity(0,false);
    set_state(BLE_SCAN);
    if(cfg.ble_active!=metrics.ble_active_scan && !configure_ble_scan(cfg.ble_active))return false;
    xEventGroupClearBits(flags,BLE_DONE|BLE_STOPPED|BLE_STARTED|BLE_FAILED);
    if(!radio_ok(esp_ble_gap_start_scanning(cfg.ble_seconds),"ble_start") || !wait_flag(BLE_STARTED,2000)){
        // A request may still complete asynchronously; cancel before any next radio mode.
        xEventGroupClearBits(flags,BLE_STOPPED|BLE_FAILED);esp_ble_gap_stop_scanning();
        if(!wait_flag(BLE_STOPPED,3000)){recovery_streak++;if(detector_recovery_allowed(0,recovery_streak))esp_restart();}
        return false;
    }
    send_status("status");if(!wait_flag(BLE_DONE,(cfg.ble_seconds+3)*1000)){error_message("BLE scan timeout");return false;}
    set_state(BT_CLASSIC_SCAN);xEventGroupClearBits(flags,BT_DONE|BT_STARTED|BLE_FAILED);
    if(!radio_ok(esp_bt_gap_start_discovery(ESP_BT_INQ_MODE_GENERAL_INQUIRY,cfg.classic_units,0),"classic_start") || !wait_flag(BT_STARTED,2000)){
        xEventGroupClearBits(flags,BT_DONE);esp_bt_gap_cancel_discovery();
        if(!wait_flag(BT_DONE,4000)){recovery_streak++;if(detector_recovery_allowed(0,recovery_streak))esp_restart();}
        return false;
    }
    send_status("status");if(!wait_flag(BT_DONE,cfg.classic_units*1280+8000)){error_message("Classic inquiry timeout");return false;}
    set_state(PROCESS_EVENTS);watched_delay(100);
    set_state(IDLE);send_status("status");watched_delay(cfg.bt_interval_seconds*1000+100);return true;
}
void app_main(void){
    output_lock=xSemaphoreCreateMutex();config_lock=xSemaphoreCreateMutex();flags=xEventGroupCreate();observations=xQueueCreate(OBS_QUEUE,sizeof(observation_t));configs=xQueueCreate(1,sizeof(config_t));
    configASSERT(output_lock&&config_lock&&flags&&observations&&configs);setvbuf(stdout,NULL,_IONBF,0);boot_id=esp_random();
    esp_reset_reason_t reason=esp_reset_reason();reset_reason=reason_name(reason);
    if(recovery_magic!=RECOVERY_MAGIC || reason==ESP_RST_POWERON){recovery_magic=RECOVERY_MAGIC;recovery_streak=0;}
    if(reason==ESP_RST_PANIC || reason==ESP_RST_TASK_WDT || reason==ESP_RST_INT_WDT || reason==ESP_RST_WDT)recovery_streak++;
    esp_task_wdt_config_t watchdog={.timeout_ms=10000,.idle_core_mask=(1<<portNUM_PROCESSORS)-1,.trigger_panic=true};
    esp_err_t wdt=esp_task_wdt_reconfigure(&watchdog);if(wdt==ESP_ERR_INVALID_STATE)wdt=esp_task_wdt_init(&watchdog);ESP_ERROR_CHECK(wdt);ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    esp_err_t nvs=nvs_flash_init();
    if(nvs==ESP_ERR_NVS_NO_FREE_PAGES || nvs==ESP_ERR_NVS_NEW_VERSION_FOUND){ESP_ERROR_CHECK(nvs_flash_erase());nvs=nvs_flash_init();}
    if(nvs==ESP_OK){
        nvs_handle_t handle;
        if(nvs_open("detector",NVS_READWRITE,&handle)==ESP_OK){
            uint32_t count=0;esp_err_t read=nvs_get_u32(handle,"boots",&count);
            if((read==ESP_OK || read==ESP_ERR_NVS_NOT_FOUND) && count<UINT32_MAX){
                if(nvs_set_u32(handle,"boots",count+1)==ESP_OK && nvs_commit(handle)==ESP_OK)boot_count=count+1;
            }
            nvs_close(handle);
        }
    }
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0,2048,0,0,NULL,0));
    configASSERT(xTaskCreate(writer,"serial_out",8192,NULL,5,NULL)==pdPASS);
    configASSERT(xTaskCreate(reader,"serial_in",4096,NULL,4,NULL)==pdPASS);
    configASSERT(xTaskCreate(heartbeat,"heartbeat",4096,NULL,2,NULL)==pdPASS);
    bool system_ready=radio_ok(nvs,"nvs_init") && radio_ok(esp_netif_init(),"netif_init") && radio_ok(esp_event_loop_create_default(),"event_loop");
    unsigned attempts=0;
    while(1){
        esp_task_wdt_reset();
        if(!detector_recovery_allowed(attempts,recovery_streak) || !system_ready){
            set_state(ERROR_RECOVERY);error_message("Escáner suspendido tras fallos; diagnóstico serial disponible. Usa recuperación manual.");
            while(1)watched_delay(1000);
        }
        diagnostic_attempt=attempts+1;
        if(!initialize_radios()){
            attempts++;recovery_streak++;bump(&metrics.recoveries);set_state(ERROR_RECOVERY);error_message("Fallo de inicialización de radio; reintento limitado");watched_delay(2000*attempts);continue;
        }
        config_t next;if(xQueueReceive(configs,&next,0)==pdTRUE){
            xSemaphoreTake(config_lock,portMAX_DELAY);cfg=next;xSemaphoreGive(config_lock);
            cJSON *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"event","ack");cJSON_AddNumberToObject(j,"v",2);cJSON_AddStringToObject(j,"id",cfg.id);cJSON_AddStringToObject(j,"state","applied");emit(j);
        }
        if(scan_cycle()){
            attempts=0;last_failure[0]=0;if(milliseconds()>60000)recovery_streak=0;
        }else{
            attempts++;recovery_streak++;bump(&metrics.recoveries);set_state(ERROR_RECOVERY);error_message("Fallo de escaneo; cancelando radio antes de reintentar");
            bool stopped=stop_radios();
            if(!stopped){error_message("No se confirmó cancelación; reinicio controlado o suspensión por límite");if(detector_recovery_allowed(0,recovery_streak))esp_restart();attempts=3;}
            watched_delay(2000*attempts);
        }
    }
}
