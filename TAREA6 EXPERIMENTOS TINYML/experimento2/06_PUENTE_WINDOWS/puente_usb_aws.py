import argparse,requests,serial,time,math
from datetime import datetime

def safe_float(x):
    try:
        n=float(x)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def parse(line):
    a=[i.strip() for i in line.strip().split(',')]
    if a[0]=='CAL' and len(a)==10:
        t,h=safe_float(a[1]),safe_float(a[2]);pred,led=a[3],a[5];pp=list(map(safe_float,a[6:9]));lat=safe_float(a[9]);mode='CALIBRACION' if led==a[4] else 'TINYML_O_CALIBRACION'
    elif a[0]=='TINYML' and len(a)==8:
        t,h=safe_float(a[1]),safe_float(a[2]);pred,led=a[3],a[3];pp=list(map(safe_float,a[4:7]));lat=safe_float(a[7]);mode='TINYML'
    elif a[0]=='DHT22' and len(a)==3:
        t,h=safe_float(a[1]),safe_float(a[2]);pred,led='SIN_MODELO','DESCONOCIDO';pp=[None]*3;lat=0;mode='SIN_TINYML'
    else:return None
    if t is None or h is None or not (-40<=t<=80 and 0<=h<=100):return None
    return dict(temperatura=t,humedad=h,clase_red=pred,clase_led=led,p_frio=pp[0],p_templado=pp[1],p_caliente=pp[2],latencia_us=lat,modo=mode)

p=argparse.ArgumentParser(description='Puente USB ESP32-CAM a AWS')
p.add_argument('--port',default='COM10');p.add_argument('--url',default='https://18.191.113.248/ESP32/experimento2/api/ingest');p.add_argument('--token',required=True);p.add_argument('--insecure',action='store_true',help='Solo para pruebas; desactiva verificacion TLS')
a=p.parse_args();print('Conectando',a.port,'->',a.url)
while True:
    try:
        with serial.Serial(port=None,baudrate=115200,timeout=2,rtscts=False,dsrdtr=False) as ser:
            ser.dtr=False;ser.rts=False;ser.port=a.port;ser.open()
            print('Puerto abierto. Cierra el monitor serie de Arduino.')
            while True:
                line=ser.readline().decode('utf-8','replace').strip()
                if not line:continue
                record=parse(line)
                if not record:
                    if line.startswith('ERROR'):print('ESP32:',line)
                    continue
                try:
                    r=requests.post(a.url,json=record,headers={'X-API-Key':a.token},timeout=8,verify=not a.insecure)
                    if r.ok:print(datetime.now().strftime('%H:%M:%S'),record['temperatura'],'C',record['clase_red'],'-> AWS OK')
                    else:print('AWS',r.status_code,r.text[:120]);time.sleep(3)
                except requests.RequestException as e:print('Error de envio:',e);time.sleep(3)
    except (serial.SerialException,OSError) as e:
        print('Puerto no disponible:',e,'; reintentando en 5 segundos');time.sleep(5)
