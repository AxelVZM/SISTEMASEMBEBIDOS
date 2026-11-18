"""Runtime state and recovery. Serial/storage failures never prevent serving the HTML."""
import json,logging,queue,sqlite3,time
from collections import deque
from pathlib import Path
from .models import Settings
from .store import Store
log=logging.getLogger('detector')
class Runtime:
    def __init__(self,root,data):
        self.root=root;self.data=data;self.started=time.time();self.memory_errors=deque(maxlen=200)
        self.db_error='';self.store=None;self.config_error='';self.settings=Settings()
        try:
            data.mkdir(parents=True,exist_ok=True)
            config=data/'settings.json'
            if config.exists():
                loaded=Settings.model_validate_json(config.read_text(encoding='utf-8'))
                loaded.ble_active=True
                self.settings=loaded
        except (OSError,ValueError) as error:
            self.config_error='Configuración inválida/no disponible; se usan valores predeterminados. '+str(error)[:240]
            self.memory_errors.append(dict(ts=time.time(),message=self.config_error,component='configuration'))
        self.open_database()
        self.connected=False;self.last_event=0;self.last_detection=0;self.last_status=0;self.status={};self.last_error='';self.applied=None
        self.pending=None;self.pending_since=0;self.commands=queue.SimpleQueue();self.invalid=0;self.new_events=[];self.retry_port=False
        self.reconnects=0;self.firmware_restarts=0;self.protocol_errors=0;self.websocket_clients=0;self.websocket_errors=0
        self.serial_error='';self.serial_task_state='starting';self.received_observations=0;self.storage_dropped=0
    def open_database(self):
        try:
            self.data.mkdir(parents=True,exist_ok=True)
            self.store=Store(self.data/'observations.sqlite3',self.root/'data',self.settings);self.db_error=''
        except (sqlite3.Error,OSError,ValueError) as error:
            self.db_error='SQLite no disponible: '+str(error)[:240];self.store=None
            self.memory_errors.append(dict(ts=time.time(),message=self.db_error,component='sqlite'))
    def error(self,message,component='system'):
        self.last_error=str(message);self.memory_errors.append(dict(ts=time.time(),message=str(message)[:400],component=component));log.warning('%s',message)
        if self.store:
            try:self.store.error(message,time.time())
            except sqlite3.Error as error:self.db_error='SQLite: '+str(error)[:200]
    def health(self):
        now=time.time()
        if self.store:
            try:self.store.available()
            except sqlite3.Error as error:self.db_error='SQLite no disponible: '+str(error)[:180]
        responding=self.connected and self.last_status>0 and now-self.last_status<12;scanners={}
        for tech in ('wifi','ble','classic'):
            flag=self.status.get(tech+'_scanning');phase=self.status.get('phase')
            matching=phase in {'wifi':('wifi','WIFI_SCAN'),'ble':('ble','BLE_SCAN'),'classic':('classic','BT_CLASSIC_SCAN')}[tech]
            active=bool(responding and flag is True and matching)
            scanners[tech]=dict(active=active,state='active' if active else 'recovering' if responding and phase=='ERROR_RECOVERY' else 'unknown_legacy' if responding and flag is None else 'waiting_turn' if responding else 'offline')
        active=any(x['active'] for x in scanners.values());database=bool(self.store and not self.db_error)
        return dict(service='esp32-detector',api_version='2.2.0',status='ok' if database else 'degraded',backend=dict(active=True,uptime_seconds=round(now-self.started,1)),
            database=dict(available=database,error=self.db_error or None,schema_version=2 if database else None),
            serial=dict(connected=self.connected,port='USB del navegador' if self.serial_task_state in ('browser_usb','waiting_browser') else self.settings.port,error=self.serial_error or None,worker=self.serial_task_state),
            firmware=dict(responding=responding,version=self.status.get('firmware'),protocol_version=self.status.get('v'),last_status=self.last_status or None,reset_count=self.firmware_restarts),
            scanners=scanners,scanner_active=active,message='ESP32 conectado — escáner activo' if active else 'ESP32 conectado — escaneo no confirmado (firmware v1)' if responding and self.status.get('v',1)==1 else 'ESP32 conectado — esperando turno de escaneo' if responding else 'Puerto serial abierto — firmware sin respuesta' if self.connected else 'ESP32 desconectado — esperando conexión serial',configuration_error=self.config_error or None)
    def diagnostics(self):
        return dict(health=self.health(),firmware=self.status,communication=dict(last_received=self.last_event or None,last_detection=self.last_detection or None,invalid_lines=self.invalid,
            protocol_errors=self.protocol_errors,reconnections=self.reconnects,pending_configuration=self.pending,pending_seconds=round(time.time()-self.pending_since,1) if self.pending else 0,
            websocket_clients=self.websocket_clients,websocket_errors=self.websocket_errors,received_observations=self.received_observations,storage_dropped=self.storage_dropped),
            errors=list(self.memory_errors)[-50:],identification_error=self.store.identifier.last_error if self.store else None)
    def snapshot(self):
        now=time.time();devices=[];stats={}
        if self.store:
            try:devices=self.store.devices(now);stats=self.store.stats(devices,now)
            except (sqlite3.Error,ValueError) as error:
                message='No se pudieron consultar observaciones: '+str(error)[:180]
                if message!=self.db_error:self.error(message,'sqlite')
                self.db_error=message
        health=self.health()
        return dict(ble_active_requested=self.settings.ble_active,profile=self.settings.profile,devices=devices,stats=stats,health=health,diagnostics=self.diagnostics(),scanner=dict(serial_connected=self.connected,firmware_online=health['firmware']['responding'],scanner_active=health['scanner_active'],last_event=self.last_event,status=self.status,last_error=self.last_error,invalid_lines=self.invalid,config_pending=self.pending,applied=self.applied),alerts=self.new_events[-20:])
