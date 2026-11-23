"""Panel local USB para ESP32-CAM DHT22. No requiere Wi-Fi."""
from flask import Flask, jsonify, request, send_file
from serial.tools import list_ports
import serial, threading, time, csv, re, io, json, uuid
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
CSV = ROOT / 'resultados_tinyml.csv'
FIELDS = ['fecha','sesion','temperatura','humedad','clase_red','clase_referencia','clase_led','p_frio','p_templado','p_caliente','latencia_us','fuente','modo']
VALID = ('FRIO','TEMPLADO','CALIENTE')
app = Flask(__name__)
lock = threading.RLock()
stop_event = None
worker = None
state = dict(connected=False,port='',recording=False,session='',error='',latest=None,history=[],counts={c:0 for c in VALID},raw=[],bytes_rx=0,lines_rx=0,valid_rx=0,last_valid=None,opened_at=None,notices=[])
if CSV.exists():
    try:
        with CSV.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                if r['clase_referencia'] in VALID:state['counts'][r['clase_referencia']]+=1
    except (OSError, KeyError): pass

def reference(t):
    return 'FRIO' if t<12 else 'TEMPLADO' if t<21 else 'CALIENTE'

def finite(v):
    try:
        f=float(v)
        return f if f==f and abs(f)!=float('inf') else None
    except (ValueError,TypeError):return None

def read_line(line):
    a=[v.strip() for v in line.strip().split(',')]
    if len(a)==10 and a[0]=='CAL':
        t,h=finite(a[1]),finite(a[2]);p=[finite(x) for x in a[6:9]]
        if t is None or h is None: return None
        cl=a[3] if a[3] in VALID else 'SIN_MODELO'
        ref=reference(t)
        led=a[5] if a[5] in VALID else 'DESCONOCIDO'
        return dict(temperatura=t,humedad=h,clase_red=cl,clase_referencia=ref,clase_led=led,p_frio=p[0],p_templado=p[1],p_caliente=p[2],latencia_us=int(finite(a[9]) or 0),fuente='CAL',modo='CALIBRACION' if led==ref else 'INYECTADO_O_TINYML')
    if len(a)==8 and a[0]=='TINYML':
        t,h=finite(a[1]),finite(a[2]);p=[finite(x) for x in a[4:7]]
        if t is None or h is None:return None
        cl=a[3] if a[3] in VALID else 'SIN_MODELO'
        return dict(temperatura=t,humedad=h,clase_red=cl,clase_referencia=reference(t),clase_led=cl,p_frio=p[0],p_templado=p[1],p_caliente=p[2],latencia_us=int(finite(a[7]) or 0),fuente='TINYML',modo='TINYML')
    if len(a)==3 and a[0]=='DHT22':
        t,h=finite(a[1]),finite(a[2]);tipo='DHT22'
    else:
        m=re.search(r'Temperatura:\s*(-?\d+(?:\.\d+)?)[^|]*\|\s*Humedad:\s*(\d+(?:\.\d+)?)\s*%',line)
        if not m:return None
        t,h=finite(m.group(1)),finite(m.group(2));tipo='TEXTO'
    if t is None or h is None:return None
    return dict(temperatura=t,humedad=h,clase_red='SIN_MODELO',clase_referencia=reference(t),clase_led='DESCONOCIDO',p_frio=None,p_templado=None,p_caliente=None,latencia_us=0,fuente=tipo,modo='SIN_TINYML')

def run_reader(port,ev):
    try:
        with serial.Serial(port=None,baudrate=115200,timeout=0.4,rtscts=False,dsrdtr=False) as ser:
            ser.dtr=False;ser.rts=False;ser.port=port;ser.open()
            with lock:state.update(connected=True,opened_at=time.time(),error='')
            pending=b''
            while not ev.is_set():
                chunk=ser.read(ser.in_waiting or 1)
                if not chunk:continue
                with lock:state['bytes_rx']+=len(chunk)
                pending+=chunk
                if len(pending)>32768:pending=b''
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    msg=line.decode('utf-8','replace').strip()
                    with lock:
                        state['lines_rx']+=1
                        state['raw']=(state['raw']+[msg[:240]])[-20:]
                    r=read_line(msg)
                    if r is None:continue
                    if not (-40<=r['temperatura']<=80 and 0<=r['humedad']<=100):continue
                    r.update(fecha=datetime.now().astimezone().isoformat(timespec='seconds'))
                    with lock:
                        state['valid_rx']+=1;state['last_valid']=time.time()
                        r['sesion']=state['session'] if state['recording'] else ''
                        state['latest']=r
                        state['history']=(state['history']+[r])[-150:]
                        if state['recording']:
                            new=not CSV.exists() or CSV.stat().st_size==0
                            with CSV.open('a',newline='',encoding='utf-8') as f:
                                w=csv.DictWriter(f,FIELDS)
                                if new:w.writeheader()
                                w.writerow(r)
                            state['counts'][r['clase_referencia']]+=1
    except Exception as ex:
        with lock:state['error']=str(ex)
    finally:
        with lock:state.update(connected=False,recording=False)

@app.get('/')
def home():return send_file(ROOT/'index.html')
@app.get('/api/ports')
def ports():return jsonify([{'port':p.device,'description':p.description} for p in list_ports.comports()])
@app.get('/api/state')
def status():
    with lock:return jsonify(state)
@app.post('/api/connect')
def connect():
    global stop_event,worker
    port=(request.get_json(silent=True) or {}).get('port','')
    if port not in {p.device for p in list_ports.comports()}:return jsonify(error='Puerto no disponible'),400
    with lock:
        if worker and worker.is_alive():return jsonify(error='Desconecta el puerto actual primero'),409
        stop_event=threading.Event()
        state.update(port=port,error='',latest=None,history=[],bytes_rx=0,lines_rx=0,valid_rx=0,raw=[],last_valid=None,opened_at=None)
        worker=threading.Thread(target=run_reader,args=(port,stop_event),daemon=True);worker.start()
    return jsonify(ok=True)
@app.post('/api/disconnect')
def disconnect():
    global stop_event,worker
    if stop_event:stop_event.set()
    if worker:worker.join(2)
    return jsonify(ok=True)
@app.post('/api/record')
def record():
    with lock:
        if not state['connected']:return jsonify(error='Conecta primero'),400
        state.update(recording=True,session=uuid.uuid4().hex[:10])
    return jsonify(ok=True)
@app.post('/api/pause')
def pause():
    with lock:state['recording']=False
    return jsonify(ok=True)
@app.get('/dataset')
def dataset():
    if not CSV.exists():return 'No hay datos grabados todavía',404
    return send_file(CSV,as_attachment=True,download_name=CSV.name,mimetype='text/csv')

if __name__=='__main__':
    print('Panel disponible en http://127.0.0.1:8765')
    app.run(host='127.0.0.1',port=8765,threaded=True,debug=False)
