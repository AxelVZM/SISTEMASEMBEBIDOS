import argparse,requests,serial,time,math,sys
from urllib.parse import urlparse

def number(x):
    try:
        x=float(x)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None

def parse(line):
    a=[x.strip() for x in line.split(',')]
    if a[0]=='CAL' and len(a)==10:
        t,h=number(a[1]),number(a[2]); pred,led=a[3],a[5]
        prob=list(map(number,a[6:9]));lat=number(a[9]);mode='CALIBRACION' if led==a[4] else 'TINYML'
    elif a[0]=='TINYML' and len(a)==8:
        t,h=number(a[1]),number(a[2]);pred=led=a[3];prob=list(map(number,a[4:7]));lat=number(a[7]);mode='TINYML'
    elif a[0]=='DHT22' and len(a)==3:
        t,h=number(a[1]),number(a[2]);pred='SIN_MODELO';led='DESCONOCIDO';prob=[None]*3;lat=0;mode='SIN_TINYML'
    else:return None
    if t is None or h is None or not -40<=t<=80 or not 0<=h<=100:return None
    return dict(temperatura=t,humedad=h,clase_red=pred,clase_led=led,p_frio=prob[0],p_templado=prob[1],p_caliente=prob[2],latencia_us=lat,modo=mode)

p=argparse.ArgumentParser()
p.add_argument('--port',default='COM10');p.add_argument('--url',default='https://18.191.113.248/ESP32/experimento2/api/ingest')
p.add_argument('--token',default='');p.add_argument('--insecure',action='store_true',help='SOLO pruebas en una red de confianza; no valida TLS')
a=p.parse_args();u=urlparse(a.url);headers={'Origin':f'{u.scheme}://{u.netloc}'}
if a.token:headers['X-API-Key']=a.token
print('USB:',a.port,'  Destino:',a.url,flush=True)
if a.insecure:
 print('AVISO: --insecure omite la validacion HTTPS; usar solo para diagnostico.',flush=True)
while True:
    try:
        ser=serial.Serial(port=None,baudrate=115200,timeout=3,rtscts=False,dsrdtr=False)
        ser.dtr=False;ser.rts=False;ser.port=a.port;ser.open()
        print('COM abierto; esperando CAL,TINYML o DHT22...',flush=True)
        try:
            while True:
                line=ser.readline().decode('utf-8','replace').strip()
                if not line:continue
                rec=parse(line)
                if not rec:
                    if line.startswith('ERROR'):print('ERROR ESP32:',line,flush=True)
                    continue
                try:
                    r=requests.post(a.url,json=rec,headers=headers,timeout=(4,8),verify=not a.insecure)
                    print('Temperatura:',rec['temperatura'],'Clase:',rec['clase_red'],'AWS:',r.status_code, r.text[:100] if not r.ok else 'OK',flush=True)
                except requests.RequestException as e:print('Error HTTPS:',str(e)[:210],flush=True)
        finally:ser.close()
    except (OSError,serial.SerialException) as e:
        print('COM ocupado/no disponible:',e,'Reintento 5 segundos.',flush=True)
        time.sleep(5)
