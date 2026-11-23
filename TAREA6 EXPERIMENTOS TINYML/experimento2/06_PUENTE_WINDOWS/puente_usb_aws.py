"""Puente ESP32-CAM -> AWS: autodetecta COM, reconecta, evita DTR/RTS, envia CAL/TINYML.
No requiere que el navegador abra el puerto. Cerrar Monitor Serie Arduino.
"""
import argparse, math, time, sys, os
from urllib.parse import urlparse
import serial
from serial.tools import list_ports
import requests

def val(v):
    try:
        f=float(v)
        return f if math.isfinite(f) else None
    except (ValueError,TypeError): return None

def parse_line(line):
    f=[x.strip() for x in line.strip().split(',')]
    if not f:return None
    if f[0]=='CAL' and len(f)==10:
        t,h=val(f[1]),val(f[2]); cl,ref,led=f[3:6]; p=list(map(val,f[6:9]));lat=val(f[9]);mode='TINYML' if cl==led and cl!='SIN_MODELO' else 'CALIBRACION_O_FALLBACK'
    elif f[0]=='TINYML' and len(f)==8:
        t,h=val(f[1]),val(f[2]);cl=led=f[3];p=list(map(val,f[4:7]));lat=val(f[7]);mode='TINYML'
    elif f[0]=='DHT22' and len(f)==3:
        t,h=val(f[1]),val(f[2]);cl='SIN_MODELO';led='DESCONOCIDO';p=[None]*3;lat=0;mode='DIAGNOSTICO'
    else:return None
    if t is None or h is None or not -40<=t<=80 or not 0<=h<=100:return None
    if cl not in ('FRIO','TEMPLADO','CALIENTE','SIN_MODELO'):return None
    if led not in ('FRIO','TEMPLADO','CALIENTE','DESCONOCIDO'):return None
    return dict(temperatura=t,humedad=h,clase_red=cl,clase_led=led,p_frio=p[0],p_templado=p[1],p_caliente=p[2],latencia_us=lat or 0,modo=mode)

def candidates(selected):
    found=list(list_ports.comports())
    if selected!='auto':
        return [x for x in found if x.device.lower()==selected.lower()]
    def priority(x):
        d=((x.description or '')+' '+(x.manufacturer or '')).lower()
        return (0 if x.vid in (0x1a86,0x10c4) or any(k in d for k in ('ch340','ch341','cp210','usb-serial')) else 1,x.device)
    return sorted(found,key=priority)

def open_serial(device):
    s=serial.Serial(port=None,baudrate=115200,timeout=.8,write_timeout=1,rtscts=False,dsrdtr=False)
    s.port=device;s.dtr=False;s.rts=False;s.open();s.dtr=False;s.rts=False
    return s

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',default='auto')
    ap.add_argument('--url',default='https://18.191.113.248/ESP32/experimento2/api/ingest')
    ap.add_argument('--insecure',action='store_true',help='SOLO si la IP usa certificado autofirmado; desactiva validacion TLS')
    ap.add_argument('--token',default=os.environ.get('TINYML_INGEST_TOKEN',''))
    args=ap.parse_args()
    print('PUENTE ESP32 -> AWS | COM automatico | 115200 | Ctrl+C para salir',flush=True)
    session=requests.Session()
    last_port=None
    while True:
        ports=candidates(args.port)
        if not ports:
            print('Esperando dispositivo USB serial ...',flush=True);time.sleep(3);continue
        selected=ports[0].device
        try:
            sp=open_serial(selected)
        except (serial.SerialException,OSError) as e:
            print('Puerto ocupado/no disponible:',selected,str(e)[:140],flush=True);time.sleep(3);continue
        print('CONECTADO:',selected,'(DTR/RTS desactivados)',flush=True)
        silent=time.monotonic();last_status=0
        try:
            while True:
                raw=sp.readline()
                if not raw:
                    if time.monotonic()-silent>12 and time.monotonic()-last_status>12:
                        print('Puerto abierto, sin bytes. Revisar firmware/arranque; reconectando...',flush=True)
                        break
                    continue
                silent=time.monotonic()
                txt=raw.decode('utf-8','replace').strip()
                if txt and (txt.startswith(('BOOT','READY','ERROR'))):print('[ESP32]',txt,flush=True)
                rec=parse_line(txt)
                if rec is None:continue
                print(f'LECTURA {selected}: {rec["temperatura"]:.1f} C / {rec["humedad"]:.1f}% / {rec["clase_red"]}',flush=True)
                hdr={'Content-Type':'application/json'}
                if args.token:hdr['X-API-Key']=args.token
                try:
                    result=session.post(args.url,json=rec,headers=hdr,timeout=7,verify=not args.insecure)
                    if result.ok: print('AWS OK',result.status_code,flush=True)
                    else: print('AWS ERROR',result.status_code,result.text[:180],flush=True)
                except requests.RequestException as e: print('ERROR HTTPS:',str(e)[:220],flush=True)
        except (serial.SerialException,OSError) as e:
            print('USB desconectado:',e,flush=True)
        finally:sp.close()
        time.sleep(2)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nFinalizado')
