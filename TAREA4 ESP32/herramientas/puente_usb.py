"""ESP32 USB -> EC2. Se ejecuta en el PC físico al que está conectado el ESP32."""
import argparse
import getpass
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

class PacketBuffer:
    def __init__(self):
        self.lock=threading.Lock();self.rows={};self.boot=None;self.last_status=0
    def add(self,p):
        if not isinstance(p,dict) or p.get('kind') not in ('status','wifi','ble') or not isinstance(p.get('b'),int):return False
        if p['kind']!='status' and (not isinstance(p.get('slot'),int) or not 0<=p['slot']<(96 if p['kind']=='wifi' else 32)):return False
        with self.lock:
            if self.boot!=p['b']:self.rows.clear();self.boot=p['b']
            key='status' if p['kind']=='status' else p['kind']+':'+str(p['slot'])
            self.rows[key]=p
            if p['kind']=='status':self.last_status=time.monotonic()
        return True
    def snapshot(self):
        with self.lock:
            if time.monotonic()-self.last_status>3:return []
            return sorted(self.rows.items(),key=lambda item:item[0]!='status')
    def ack(self,batch):
        with self.lock:
            for k,v in batch:
                if self.rows.get(k) is v:del self.rows[k]
    def clear(self):
        with self.lock:self.rows.clear();self.last_status=0

def server_origin(url):
    p=urllib.parse.urlsplit(url)
    if not p.hostname or p.username or p.password or p.query or p.fragment or '/..' in p.path or p.path.rstrip('/').endswith('/api'):
        raise ValueError('Usa la URL base (puede incluir /esp32), sin /api, usuario, clave ni parámetros')
    if p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('Usa HTTPS para EC2 o HTTP localhost mediante túnel SSH')
    return url.rstrip('/')

def post_packets(server,token,sensor,source,packets):
    data=json.dumps({'sensor_id':sensor,'source_id':source,'packets':packets},ensure_ascii=False).encode()
    request=urllib.request.Request(server+'/api/ingest',data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=6) as response:
        result=json.load(response)
    if not result.get('ok'):raise RuntimeError('Respuesta del servidor inválida')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',help='COM6 en Windows; si hay un único puerto se selecciona automáticamente')
    parser.add_argument('--server',required=True,help='https://tu-dominio o http://localhost:8000 con túnel SSH')
    parser.add_argument('--sensor',default='esp32-principal')
    args=parser.parse_args()
    try:server=server_origin(args.server)
    except ValueError as e:parser.error(str(e))
    import re
    if not re.fullmatch(r'[-a-zA-Z0-9_]{1,64}',args.sensor):parser.error('ID de sensor inválido')
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:parser.error('Instala pyserial: py -m pip install -r herramientas/requirements.txt')
    if not args.port:
        ports=list(list_ports.comports())
        if len(ports)!=1:parser.error('Indica --port. Puertos disponibles: '+', '.join(p.device for p in ports))
        args.port=ports[0].device
    token=os.environ.get('ORBITA_API_TOKEN') or getpass.getpass('Token del servidor EC2 (no se mostrará): ').strip()
    if len(token)<32:parser.error('Token demasiado corto; usa el generado en EC2')
    buffer=PacketBuffer();stop=threading.Event();source=uuid.uuid4().hex
    def upload():
        last_error=0
        while not stop.wait(.5):
            batch=buffer.snapshot()
            if not batch:continue
            try:
                post_packets(server,token,args.sensor,source,[p for _,p in batch]);buffer.ack(batch)
            except (OSError,ValueError,RuntimeError,urllib.error.URLError) as e:
                if time.monotonic()-last_error>5:
                    code=getattr(e,'code',None)
                    print('Sin subida a EC2'+(' · HTTP '+str(code) if code else '')+'. Reintentando; revisa URL, token y conexión.',flush=True);last_error=time.monotonic()
                stop.wait(2)
    worker=threading.Thread(target=upload,daemon=True);worker.start()
    print('Puente activo:',args.port,'->',server,'· sensor',args.sensor,flush=True)
    print('Cierra el Monitor Serie y cualquier pestaña que use este COM. Ctrl+C para terminar.',flush=True)
    try:
        while not stop.is_set():
            try:
                with serial.Serial(args.port,115200,timeout=.2,write_timeout=1) as port:
                    if hasattr(port,'set_buffer_size'):
                        try:port.set_buffer_size(rx_size=65536,tx_size=4096)
                        except (OSError,AttributeError):pass
                    raw=b'';clock_boot=None;last_report=0
                    while not stop.is_set():
                        chunk=port.read(4096)
                        if not chunk:continue
                        raw+=chunk
                        while b'\n' in raw:
                            line,raw=raw.split(b'\n',1)
                            if len(line)>12000:continue
                            try:p=json.loads(line.decode('utf-8'))
                            except (ValueError,UnicodeError):continue
                            if not buffer.add(p):continue
                            if p['kind']=='status':
                                if clock_boot!=p['b']:
                                    clock_boot=p['b'];epoch=p.get('epoch')
                                    if not p.get('clock') or not isinstance(epoch,(int,float)) or abs(time.time()-epoch)>5:
                                        port.write((json.dumps({'cmd':'clock_sync','epoch':int(time.time())})+'\n').encode())
                                if time.monotonic()-last_report>=10:
                                    print('Recibiendo · Wi-Fi:',p.get('wifi'),'· BLE:',p.get('ble'),flush=True);last_report=time.monotonic()
                        if len(raw)>12000:raw=b''
            except (serial.SerialException,OSError):
                buffer.clear();print('USB no disponible. Reintentando conexión al ESP32...',flush=True);stop.wait(3)
    except KeyboardInterrupt:pass
    finally:stop.set();worker.join(timeout=7);print('Puente detenido. EC2 marcará ausencia de datos recientes.')

if __name__=='__main__':main()
