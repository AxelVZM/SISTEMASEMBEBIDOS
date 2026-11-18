from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event: Literal['observation']
    v: Literal[1, 2] = 1
    tech: Literal['wifi', 'ble', 'classic']
    mac: str
    rssi: int | None = Field(default=None, ge=-127, le=20)
    uptime_ms: int = Field(default=0, ge=0)
    name: str = Field(default='', max_length=248)
    name_source: Literal['unknown','advertisement','scan_response','classic_name','classic_eir','wps','ssid'] = 'unknown'
    name_complete: bool = False
    wps_manufacturer: str = Field(default='',max_length=64)
    wps_model_name: str = Field(default='',max_length=32)
    wps_model_number: str = Field(default='',max_length=32)
    wps_device_name: str = Field(default='',max_length=64)
    wps_primary_device_type: str = Field(default='',pattern=r'^(?:[0-9A-Fa-f]{16})?$')
    ssid: str = Field(default='',max_length=32)
    vendor_ies: str = Field(default='',max_length=72,pattern=r'^(?:[0-9A-Fa-f]{6,8}(?:,[0-9A-Fa-f]{6,8})*)?$')
    role: Literal['ap', 'station', 'unknown'] = 'unknown'
    channel: int | None = Field(default=None, ge=1, le=11)
    frame_type: str = Field(default='', max_length=24)
    address_type: Literal['public', 'random', 'unknown'] = 'unknown'
    adv_type: int | None = Field(default=None, ge=0, le=255)
    company_id: int | None = Field(default=None, ge=0, le=65535)
    manufacturer_data: str = Field(default='', max_length=64, pattern=r'^(?:[0-9a-fA-F]{2})*$')
    services: list[str] = Field(default_factory=list, max_length=16)
    appearance: int | None = Field(default=None, ge=0, le=65535)
    cod: int | None = Field(default=None, ge=0, le=0xffffff)
    tx_power: int | None = Field(default=None, ge=-127, le=126)

    @field_validator('mac')
    @classmethod
    def normalize_mac(cls, value):
        value = value.upper()
        if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', value):
            raise ValueError('MAC inválida')
        if value in ('00:00:00:00:00:00', 'FF:FF:FF:FF:FF:FF'):
            raise ValueError('MAC vacía o broadcast')
        return value

    @model_validator(mode='after')
    def unicast_wifi(self):
        if self.tech == 'wifi' and int(self.mac[:2], 16) & 1:
            raise ValueError('Se requiere MAC Wi-Fi unicast')
        return self

class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    port: str = Field(default='COM6', min_length=1, max_length=120)
    baud: Literal[115200] = 115200
    channels: list[int] = Field(default_factory=lambda: list(range(1,12)), min_length=1, max_length=11)
    wifi_ms: int = Field(default=6000, ge=1000, le=60000)
    dwell_ms: int = Field(default=250, ge=50, le=2000)
    ble_seconds: int = Field(default=8, ge=1, le=60)
    classic_units: int = Field(default=5, ge=1, le=48)
    bt_interval_seconds: int = Field(default=0, ge=0, le=300)
    min_rssi: int = Field(default=-100, ge=-127, le=0)
    expiry_seconds: int = Field(default=90, ge=10, le=86400)
    dedup_ms: int = Field(default=1000, ge=100, le=10000)
    retention_days: int = Field(default=7, ge=1, le=365)
    history_limit: int = Field(default=500, ge=10, le=5000)
    rssi_ref: float = Field(default=-59, ge=-100, le=-20)
    loss_n: float = Field(default=2.5, ge=1, le=6)
    alpha: float = Field(default=0.25, ge=0.01, le=1)
    calibrated: bool = False
    ble_active: bool = True
    profile: Literal['custom','rapid','balanced','exhaustive'] = 'custom'

    @field_validator('channels')
    @classmethod
    def valid_channels(cls, values):
        if len(set(values)) != len(values) or any(x < 1 or x > 11 for x in values):
            raise ValueError('Canales únicos entre 1 y 11')
        return values

    def firmware(self):
        return {k: getattr(self,k) for k in ('channels','wifi_ms','dwell_ms','ble_seconds','classic_units','bt_interval_seconds','dedup_ms','min_rssi','ble_active')}

class Status(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event: Literal['status','heartbeat']
    v: Literal[1,2] = 1
    firmware: str = Field(max_length=32)
    boot_id: int = Field(ge=0,le=0xffffffff)
    phase: Literal['boot','wifi','ble','classic','idle','WIFI_SCAN','BLE_SCAN','BT_CLASSIC_SCAN','PROCESS_EVENTS','IDLE','ERROR_RECOVERY']
    uptime_ms: int = Field(ge=0)
    queue_dropped: int = Field(ge=0)
    free_heap: int = Field(ge=0)
    ble_scan_mode: Literal['passive','active'] | None = None
    minimum_free_heap: int | None = Field(default=None, ge=0)
    current_channel: int | None = Field(default=None,ge=1,le=11)
    events_captured: int | None = Field(default=None,ge=0)
    events_sent: int | None = Field(default=None,ge=0)
    queue_depth: int | None = Field(default=None,ge=0,le=32)
    queue_capacity: int | None = Field(default=None,ge=1,le=32)
    queue_high_water: int | None = Field(default=None,ge=0,le=32)
    dedup_suppressed: int | None = Field(default=None,ge=0)
    rssi_filtered: int | None = Field(default=None,ge=0)
    json_failures: int | None = Field(default=None,ge=0)
    serial_failures: int | None = Field(default=None,ge=0)
    wifi_listen_ms: int | None = Field(default=None,ge=0)
    ble_scan_ms: int | None = Field(default=None,ge=0)
    classic_scan_ms: int | None = Field(default=None,ge=0)
    channel_events: list[int] | None = Field(default=None,min_length=11,max_length=11)
    channels_visited: list[int] | None = Field(default=None,max_length=11)
    boot_count: int | None = Field(default=None,ge=1)
    reset_reason: str | None = Field(default=None,max_length=64)
    scanner_recoveries: int | None = Field(default=None,ge=0)
    consecutive_failures: int | None = Field(default=None,ge=0)
    wifi_initialized: bool | None = None
    bluetooth_initialized: bool | None = None
    wifi_scanning: bool | None = None
    ble_scanning: bool | None = None
    classic_scanning: bool | None = None
    last_capture_ms: int | None = Field(default=None,ge=0)
    serial_host_detection: Literal['not_supported'] | None = None

    @field_validator('channel_events','channels_visited')
    @classmethod
    def safe_counters(cls,value,info):
        if value is not None and any(x<0 or (info.field_name=='channels_visited' and (x<1 or x>11)) for x in value):
            raise ValueError('Contador o canal inválido')
        return value

class Ack(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event: Literal['ack']
    v: Literal[1,2] = 1
    id: str = Field(max_length=39)
    state: Literal['applied']

class FirmwareError(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event: Literal['error']
    v: Literal[1,2] = 1
    message: str = Field(max_length=400)

PROFILES = {
    'rapid': dict(wifi_ms=2200,dwell_ms=100,ble_seconds=4,classic_units=3,bt_interval_seconds=0,dedup_ms=500,ble_active=True),
    'balanced': dict(wifi_ms=6000,dwell_ms=250,ble_seconds=8,classic_units=5,bt_interval_seconds=0,dedup_ms=1000,ble_active=True),
    'exhaustive': dict(wifi_ms=16500,dwell_ms=750,ble_seconds=15,classic_units=8,bt_interval_seconds=0,dedup_ms=1000,ble_active=True),
}
