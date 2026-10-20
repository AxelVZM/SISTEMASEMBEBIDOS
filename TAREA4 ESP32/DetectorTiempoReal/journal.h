#pragma once
Preferences prefs;
const char *LOG_CURRENT="/registro_v7_actual.csv",*LOG_PREVIOUS="/registro_v7_anterior.csv";
String logBuffer="",commandBuffer="",storageReply="";bool commandOverflow=false;
uint32_t flushAt=0,summaryAt=0,journalAt=0,fsRetryAt=0,exportAt=0,exportId=0,exportSequence=0;
uint32_t revisionLog[MAX_RECORDS]{};size_t journalCursor=0;
bool exporting=false,exportStarted=false;File exportFile;size_t exportSize[2]{},exportRead=0;uint8_t exportSegment=0;
String exportPending="";
String csvCell(String s){size_t i=0;while(i<s.length()&&uint8_t(s[i])<=32)i++;if(i<s.length()&&(s[i]=='='||s[i]=='+'||s[i]=='-'||s[i]=='@'))s="'"+s;s.replace("\"","\"\"");return '"'+s+'"';}
String csvRow(const String *s,size_t n){String out;for(size_t i=0;i<n;i++){if(i)out+=';';out+=csvCell(s[i]);}return out+'\n';}
String logHeader(){return "tipo;sesion;uptime_ms;fecha_utc;protocolo;direccion;nombre_anunciado;estado;rssi_dbm;tramas;wifi_60s;reservado_0;evidencia;fabricante_declarado;modelo_declarado;fuente\n";}
String utcNow(){if(!clockValid())return "";time_t epoch=time(nullptr);tm d{};gmtime_r(&epoch,&d);char s[24];strftime(s,sizeof(s),"%Y-%m-%dT%H:%M:%SZ",&d);return s;}
size_t fileSize(const char *path){if(!fsReady)return 0;File f=LittleFS.open(path,"r");if(!f)return 0;size_t n=f.size();f.close();return n;}
size_t journalBytes(){return fileSize(LOG_CURRENT)+fileSize(LOG_PREVIOUS);}
bool flushLog(){
 if(!fsReady||!logBuffer.length())return fsReady;size_t n=fileSize(LOG_CURRENT);
 if(n+logBuffer.length()>LOG_FILE_BYTES&&!exporting){if(LittleFS.exists(LOG_PREVIOUS)&&!LittleFS.remove(LOG_PREVIOUS)){storageError="No se pudo retirar segmento anterior";return false;}if(LittleFS.exists(LOG_CURRENT)&&!LittleFS.rename(LOG_CURRENT,LOG_PREVIOUS)){storageError="No se pudo rotar registro";return false;}n=0;}
 if(n+logBuffer.length()>LOG_FILE_BYTES+65536){storageError="Registro lleno durante descarga";return false;}
 File f=LittleFS.open(LOG_CURRENT,"a");if(!f){storageError="No se pudo abrir registro";return false;}size_t wrote=f.print(logBuffer);f.flush();f.close();if(wrote)logBuffer.remove(0,wrote);if(logBuffer.length()){storageError="Escritura flash incompleta";return false;}storageError="";return true;
}
bool appendLog(const String &s){if(!fsReady||s.length()>LOG_BUFFER_BYTES)return false;if(logBuffer.length()+s.length()>LOG_BUFFER_BYTES&&!flushLog())return false;logBuffer+=s;return true;}
void initializeJournal(){
 prefs.begin("detector3",false);fsReady=LittleFS.begin(false);if(!fsReady&&!prefs.getBool("fsAttempt",false)){prefs.putBool("fsAttempt",true);if(LittleFS.format())fsReady=LittleFS.begin(false);}if(fsReady)prefs.putBool("fsAttempt",true);else storageError="No se monto LittleFS; no se formateara automaticamente";
 logBuffer.reserve(LOG_BUFFER_BYTES);commandBuffer.reserve(1536);
 if(fsReady){String c[16]={"inicio",String(bootId),String(millis()),utcNow(),"","","","automatico"};c[12]=String("reset_reason=")+String(esp_reset_reason());appendLog(csvRow(c,16));flushLog();}
}
uint32_t textHash(const String &s){uint32_t h=2166136261u;for(size_t i=0;i<s.length();i++)h=(h^uint8_t(s[i]))*16777619u;return h?h:1;}
void journalTick(uint32_t now){
 if(!fsReady){if(now-fsRetryAt>=30000){fsRetryAt=now;fsReady=LittleFS.begin(false);if(fsReady)storageError="";}return;}
 if(now-summaryAt>=30000){summaryAt=now;auto c=counts(now);String cells[16]={"resumen",String(bootId),String(now),utcNow(),"","","",c.wifiCapacity?"capacidad_alcanzada":"conteos_separados","","",String(c.wifi),String(0)};cells[12]=String("WiFi omitidas=")+String(tableDrops);appendLog(csvRow(cells,16));}
 if(now-journalAt>=500){journalAt=now;for(size_t k=0;k<4;k++){size_t i=journalCursor++%(MAX_RECORDS);String cells[16];String identity;uint32_t last=0;
 if(i<MAX_RECORDS){if(i>=rowCount)continue;auto &r=rows[i];auto &v=r.value;last=r.last;cells[4]="Wi-Fi";cells[5]=macText(v.mac);cells[6]=v.p2p.name[0]?v.p2p.name:v.wps.name;cells[8]=String(r.ema,1);cells[9]=String(r.frames);cells[12]=manufacturer(v.mac);cells[13]=v.wps.manufacturer;cells[14]=v.wps.model;cells[15]="IEEE titular / WPS-P2P declarado, sin autenticar";auto cls=classifyWifi(r);cells[15]+=String("; tipo=")+deviceLabel(cls.kind)+"; nivel="+cls.level+"; evidencia="+cls.evidence;}
 auto state=activity(now,last);cells[7]=state==0?"recien_observado":state==1?"observado_recientemente":"sin_recepcion_reciente";identity=cells[4]+"|"+cells[5]+"|"+cells[6]+"|"+cells[7]+"|"+cells[12]+"|"+cells[13]+"|"+cells[14]+"|"+cells[15];uint32_t hash=textHash(identity);if(revisionLog[i]==hash)continue;cells[0]="observacion";cells[1]=String(bootId);cells[2]=String(now);cells[3]=utcNow();if(appendLog(csvRow(cells,16)))revisionLog[i]=hash;
 }}
 if(now-flushAt>=10000||logBuffer.length()>=LOG_BUFFER_BYTES-512){flushAt=now;flushLog();}
}
void cancelExport(const char *reason){exportFile.close();exporting=false;exportStarted=false;exportPending="";storageReply=String("{\"kind\":\"export_error\",\"message\":")+quote(reason)+"}";}
void beginExport(uint32_t now){
 if(exporting){storageReply="{\"kind\":\"export_error\",\"message\":\"Ya hay una descarga activa\"}";return;}if(!fsReady||!flushLog()){storageReply="{\"kind\":\"export_error\",\"message\":\"Registro no disponible\"}";return;}
 exporting=true;exportStarted=false;exportId=esp_random();exportSequence=0;exportSegment=0;exportRead=0;exportSize[0]=fileSize(LOG_PREVIOUS);exportSize[1]=fileSize(LOG_CURRENT);exportAt=now;exportPending="";
}
void sendExport(uint32_t now){
 if(storageReply.length()){if(emit(storageReply))storageReply="";return;}if(!exporting)return;
 if(now-exportAt>60000){cancelExport("Descarga detenida por timeout USB");return;}
 if(!exportStarted){String s="{\"kind\":\"export_start\",\"id\":"+String(exportId)+",\"bytes\":"+String(exportSize[0]+exportSize[1])+",\"header\":"+quote(logHeader())+"}";if(emit(s)){exportStarted=true;exportAt=now;}return;}
 if(exportPending.length()){if(emit(exportPending)){exportPending="";exportAt=now;}return;}
 while(exportSegment<2){if(!exportSize[exportSegment]||exportRead>=exportSize[exportSegment]){exportFile.close();exportSegment++;exportRead=0;continue;}if(!exportFile){exportFile=LittleFS.open(exportSegment==0?LOG_PREVIOUS:LOG_CURRENT,"r");if(!exportFile){cancelExport("No se pudo abrir segmento");return;}}break;}
 if(exportSegment>=2){String end="{\"kind\":\"export_end\",\"id\":"+String(exportId)+",\"parts\":"+String(exportSequence)+"}";if(emit(end)){exporting=false;exportFile.close();}return;}
 uint8_t input[288],output[385];size_t need=std::min(size_t(288),exportSize[exportSegment]-exportRead),n=exportFile.read(input,need);if(n!=need){cancelExport("Lectura incompleta");return;}size_t written=0;if(mbedtls_base64_encode(output,sizeof(output),&written,input,n)!=0){cancelExport("Fallo al codificar registro");return;}output[written]=0;exportRead+=n;exportPending="{\"kind\":\"export_chunk\",\"id\":"+String(exportId)+",\"part\":"+String(exportSequence++)+",\"data\":"+quote(reinterpret_cast<char*>(output))+"}";
}
void readCommands(uint32_t now){
 for(size_t i=0;i<128&&Serial.available();i++){char ch=Serial.read();if(ch=='\r')continue;if(ch!='\n'){if(commandBuffer.length()<1536&&!commandOverflow)commandBuffer+=ch;else commandOverflow=true;continue;}if(commandOverflow){commandBuffer="";commandOverflow=false;continue;}
 cJSON *j=cJSON_ParseWithOpts(commandBuffer.c_str(),nullptr,true);commandBuffer="";if(!j)continue;auto *cmd=cJSON_GetObjectItemCaseSensitive(j,"cmd");if(cJSON_IsString(cmd)){
 if(handleNetworkCommand(j,now)){}
 else if(!strcmp(cmd->valuestring,"export_log"))beginExport(now);
 else if(!strcmp(cmd->valuestring,"clock_sync")){auto *epoch=cJSON_GetObjectItemCaseSensitive(j,"epoch");bool ok=cJSON_IsNumber(epoch)&&epoch->valuedouble>=1704067200.0&&epoch->valuedouble<4102444800.0&&epoch->valuedouble==floor(epoch->valuedouble)&&syncClock(uint32_t(epoch->valuedouble));storageReply=String("{\"kind\":\"clock_ack\",\"ok\":")+(ok?"true":"false")+"}";}
 }cJSON_Delete(j);
 }
}
