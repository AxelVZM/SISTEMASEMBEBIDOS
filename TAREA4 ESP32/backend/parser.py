import json
from .models import Observation, Status, Ack, FirmwareError

MAX_LINE = 4096

def parse_line(raw):
    if len(raw)>MAX_LINE: raise ValueError('Línea serial demasiado larga')
    value = json.loads(raw)
    if not isinstance(value,dict): raise ValueError('Se esperaba objeto JSON')
    # Normalize the v2 type-based dialect while preserving the original event-based API.
    kind=value.pop('type',None)
    if 'protocol_version' in value:
        version=value.pop('protocol_version')
        if 'v' in value and version!=value['v']: raise ValueError('Versiones de protocolo incompatibles')
        value['v']=version
    if kind:
        mapped={'detection':'observation','status':'status','heartbeat':'heartbeat','error':'error','ack':'ack'}.get(kind)
        if mapped is None: raise ValueError('Tipo de mensaje no reconocido')
        if 'event' in value and value['event']!=mapped: raise ValueError('Tipo y evento incompatibles')
        value['event']=mapped
        value.setdefault('v',2)
    for alias,key in [('technology','tech'),('timestamp_ms','uptime_ms')]:
        if alias in value:
            if key in value and value[key]!=value[alias]: raise ValueError('Campos de protocolo contradictorios')
            value[key]=value.pop(alias)
    if value.get('v',1) not in (1,2): raise ValueError('Versión de protocolo no soportada')
    if value.get('event') == 'observation': return Observation.model_validate(value)
    if value.get('event') in ('status','heartbeat','ack','error'):
        model={'status':Status,'heartbeat':Status,'ack':Ack,'error':FirmwareError}[value['event']]
        return model.model_validate(value).model_dump()
    raise ValueError('Evento no reconocido')

class SerialFramer:
    """Reassemble partial UART reads and discard an oversized record until newline."""
    def __init__(self):
        self.buffer=bytearray(); self.discarding=False; self.dropped=0
    def feed(self,chunk):
        lines=[]
        for byte in chunk:
            if byte==10:
                if not self.discarding and self.buffer: lines.append(bytes(self.buffer))
                self.buffer.clear(); self.discarding=False
            elif not self.discarding:
                if len(self.buffer)>=MAX_LINE:
                    self.buffer.clear(); self.discarding=True; self.dropped+=1
                else: self.buffer.append(byte)
        return lines
