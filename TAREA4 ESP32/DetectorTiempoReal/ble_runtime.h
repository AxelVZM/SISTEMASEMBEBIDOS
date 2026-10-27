#pragma once
std::atomic<int> bleAsyncError{0};
std::atomic<bool> bleStopPending{false};
void requestBleStop(){if(!bleStopPending.exchange(true)&&esp_ble_gap_stop_scanning()!=ESP_OK)bleStopPending.store(false);}
void bleGap(esp_gap_ble_cb_event_t event,esp_ble_gap_cb_param_t*p){
 if(event==ESP_GAP_BLE_SCAN_PARAM_SET_COMPLETE_EVT){if(p->scan_param_cmpl.status==ESP_BT_STATUS_SUCCESS)bleReady.store(true);else bleAsyncError.store(1);}
 if(event==ESP_GAP_BLE_SCAN_START_COMPLETE_EVT){if(p->scan_start_cmpl.status==ESP_BT_STATUS_SUCCESS)bleScanning.store(true);else bleAsyncError.store(2);bleStartPending.store(false);}
 if(event==ESP_GAP_BLE_SCAN_STOP_COMPLETE_EVT){if(p->scan_stop_cmpl.status==ESP_BT_STATUS_SUCCESS)bleScanning.store(false);else bleAsyncError.store(3);bleStopPending.store(false);}
 if(event!=ESP_GAP_BLE_SCAN_RESULT_EVT)return;
 if(p->scan_rst.search_evt==ESP_GAP_SEARCH_INQ_CMPL_EVT){bleScanning.store(false);bleStopPending.store(false);return;}
 if(p->scan_rst.search_evt!=ESP_GAP_SEARCH_INQ_RES_EVT||!bleAccept.load()||!bleQueue)return;
 BleEvent e;memcpy(e.mac,p->scan_rst.bda,6);e.addressType=p->scan_rst.ble_addr_type;e.rssi=p->scan_rst.rssi;e.time=millis();size_t n=p->scan_rst.adv_data_len;
 if(n<=31&&parseAdvertisement(p->scan_rst.ble_adv,n,e)&&xQueueSend(bleQueue,&e,0)!=pdTRUE)bleDrops.fetch_add(1);
}
bool initializeBleManual(){
 if(bleInitialized)return !bleInitFailed;
 bleInitialized=true;bleInitAt=millis();bleQueue=xQueueCreate(16,sizeof(BleEvent));if(!bleQueue){bleInitFailed=true;return false;}
 esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
 esp_bt_controller_config_t cfg=BT_CONTROLLER_INIT_CONFIG_DEFAULT();esp_err_t err=esp_bt_controller_init(&cfg);
 if(err==ESP_OK)err=esp_bt_controller_enable(ESP_BT_MODE_BLE);
 if(err==ESP_OK)err=esp_bluedroid_init();if(err==ESP_OK)err=esp_bluedroid_enable();if(err==ESP_OK)err=esp_ble_gap_register_callback(bleGap);
 esp_ble_scan_params_t params{};params.scan_type=BLE_SCAN_TYPE_PASSIVE;params.own_addr_type=BLE_ADDR_TYPE_PUBLIC;params.scan_filter_policy=BLE_SCAN_FILTER_ALLOW_ALL;params.scan_interval=0x80;params.scan_window=0x78;params.scan_duplicate=BLE_SCAN_DUPLICATE_DISABLE;
 if(err==ESP_OK)err=esp_ble_gap_set_scan_params(&params);
 if(err!=ESP_OK){bleInitFailed=true;bleError=String("Inicio BLE: ")+esp_err_to_name(err)+". Reinicia la placa para reintentar.";return false;}return true;
}
bool handleModeCommand(cJSON*j,uint32_t now){
 auto*c=cJSON_GetObjectItemCaseSensitive(j,"cmd");if(!cJSON_IsString(c)||strcmp(c->valuestring,"ble_set"))return false;
 auto*v=cJSON_GetObjectItemCaseSensitive(j,"enabled");bool ok=cJSON_IsBool(v)&&!networkBusy()&&!exporting;
 if(ok&&cJSON_IsTrue(v)){
  if(!bleSelected){accepting.store(false);esp_wifi_set_promiscuous(false);ok=initializeBleManual();if(ok){bleSelected=true;bleError="";bleAccept.store(true);}}
 }else if(ok){bleSelected=false;bleAccept.store(false);if(bleScanning.load())requestBleStop();}
 storageReply=String("{\"kind\":\"mode_ack\",\"ok\":")+(ok?"true":"false")+",\"message\":"+quote(ok?(bleSelected?"BLE seleccionado; Wi-Fi pausado":"Volviendo a Wi-Fi"):"No se pudo cambiar: termina red/descarga o revisa BLE")+"}";statusAt=0;return true;
}
void bleTick(uint32_t now){
 int error=bleAsyncError.exchange(0);if(error){bleError=String("Fallo BLE ")+String(error);bleSelected=false;bleAccept.store(false);}
 if(bleSelected&&!bleReady.load()&&now-bleInitAt>8000){bleInitFailed=true;bleError="BLE no confirmo inicio. Reinicia para reintentar.";bleSelected=false;bleAccept.store(false);}
 if(bleSelected&&bleReady.load()&&!bleScanning.load()&&!bleStartPending.load()){
  bleStartPending.store(true);bleWindowAt=now;esp_err_t err=esp_ble_gap_start_scanning(2);
  if(err!=ESP_OK){bleStartPending.store(false);bleError="No se pudo iniciar escaneo BLE";bleSelected=false;bleAccept.store(false);}
 }
 if((bleScanning.load()||bleStartPending.load())&&now-bleWindowAt>5000){bleSelected=false;bleAccept.store(false);bleError="BLE excedio plazo; solicitando parada. Si persiste, reinicia la placa.";requestBleStop();}
 if(!bleSelected&&bleScanning.load())requestBleStop();
 if(!bleSelected&&!networkBusy()&&!bleScanning.load()&&!bleStartPending.load()&&!accepting.load()&&radioReady)resumeWifi();
}
void sendBleRows(){
 for(size_t tries=0;tries<bleCount&&serialBudget>1100;tries++){
 size_t i=bleCursor;bleCursor=(i+1)%bleCount;auto&r=bleRows[i];if(!r.dirty)continue;auto&v=r.value;bool conflict=r.modelConflict||r.companyConflict;
 const char*model=conflict?"":bleModelName(v.model);char id[8];snprintf(id,sizeof(id),"%04X",v.model.id);
 String s="{\"kind\":\"ble\",\"b\":"+String(bootId)+",\"slot\":"+String(i)+",\"mac\":"+quote(macText(v.mac))+",\"addressType\":"+String(v.addressType)+",\"name\":"+quote(v.name)+",\"companyId\":"+(v.hasCompany?String(v.company):String("null"))+",\"company\":"+quote(v.hasCompany?bluetoothCompany(v.company):"No anunciado")+",\"brand\":"+quote(conflict?"":bleModelBrand(v.model))+",\"model\":"+quote(model)+",\"modelId\":"+quote(v.model.format?id:"")+",\"modelSource\":"+quote(v.model.format==1?"Apple proximity pairing / Theengs":v.model.format==2?"MiBeacon FE95 / ESPHome":v.model.format==3?"Ruuvi RAWv2; sin modelo exacto":"Sin decoder compatible")+",\"modelConflict\":"+String(conflict?"true":"false")+",\"encrypted\":"+String(v.model.encrypted?"true":"false")+",\"companyConflict\":"+String(r.companyConflict?"true":"false")+",\"appearance\":"+(v.hasAppearance?String(v.appearance):String("null"))+",\"disAdvertised\":"+String(v.hasDis?"true":"false")+",\"rssi\":"+String(r.ema,1)+",\"frames\":"+String(r.frames)+",\"last\":"+String(r.last)+classJson(classifyBle(r))+"}";
 if(!emit(s)){bleCursor=i;break;}r.dirty=false;
 }
}
