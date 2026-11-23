import os, csv, time, threading, hmac
from pathlib import Path
from collections import deque
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file
ROOT=Path(__file__).resolve().parent
app=Flask(__name__, static_folder=None)
TOKEN=os.environ.get('TINYML_INGEST_TOKEN','')
CSV=ROOT/'mediciones_ec2.csv'
HEAD=['fecha','temperatura','humedad','clase_red','clase_referencia','clase_led','p_frio','p_templado','p_caliente','latencia_us','modo']
lock=threading.Lock()
recent=deque(maxlen=200)
latest=None
n=0

def reference(t):
    return 'FRIO' if t<12 else 'TEMPLADO' if t<21 else 'CALIENTE'

def asfloat(v,low,high):
    if v is None or v=='':return None
    a=float(v)
    if not (low<=a<=high):raise ValueError('valor fuera de rango')
    return a

@app.get('/health')
def health():return jsonify(ok=True,service='experimento2',records=n)
@app.get('/api/state')
def state():
    with lock:return jsonify(latest=latest,history=list(recent),records=n,received_at=latest.get('fecha') if latest else None)
@app.post('/api/ingest')
def ingest():
    global latest,n
    auth=request.headers.get('X-API-Key','')
    # Token opcional. Si no existe en el servicio, solo se permite la petición
    # originada desde el mismo sitio. Esto NO reemplaza una autenticación real.
    if TOKEN:
        if not hmac.compare_digest(auth,TOKEN):return jsonify(error='no autorizado'),401
    else:
        origen=request.headers.get('Origin','')
        esperado=f'{request.headers.get("X-Forwarded-Proto",request.scheme)}://{request.host}'
        if not origen or origen != esperado:
            return jsonify(error='origen no permitido'),403
    if request.content_length and request.content_length > 4096:return jsonify(error='solicitud demasiado grande'),413
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(error='JSON invalido'),400
    try:
        t=asfloat(data.get('temperatura'),-40,80)
        h=asfloat(data.get('humedad'),0,100)
        if t is None or h is None:raise ValueError('faltan lecturas')
        pred=str(data.get('clase_red','SIN_MODELO'))[:20]
        led=str(data.get('clase_led','DESCONOCIDO'))[:20]
        if pred not in ('FRIO','TEMPLADO','CALIENTE','SIN_MODELO'):raise ValueError('clase red incorrecta')
        if led not in ('FRIO','TEMPLADO','CALIENTE','DESCONOCIDO'):raise ValueError('led incorrecto')
        probs=[asfloat(data.get(c),0,1) for c in ('p_frio','p_templado','p_caliente')]
        latency=asfloat(data.get('latencia_us',0),0,100000000)
        mode=str(data.get('modo','DESCONOCIDO'))[:35]
        row=dict(fecha=datetime.now(timezone.utc).isoformat(timespec='seconds'),temperatura=t,humedad=h,clase_red=pred,clase_referencia=reference(t),clase_led=led,p_frio=probs[0],p_templado=probs[1],p_caliente=probs[2],latencia_us=latency,modo=mode)
    except (ValueError,TypeError,OverflowError) as exc:return jsonify(error=str(exc)),400
    with lock:
        new=not CSV.exists() or CSV.stat().st_size==0
        with CSV.open('a',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,HEAD)
            if new:w.writeheader()
            w.writerow(row)
        latest=row;recent.append(row);n+=1
    return jsonify(ok=True),200

@app.get('/dataset')
def dataset():
    if not CSV.exists():return 'Todavia no hay registros',404
    return send_file(CSV,as_attachment=True,download_name='mediciones_ec2.csv')

@app.get('/')
def home():return send_file(ROOT/'index.html')

if CSV.exists():
    try:
        with CSV.open(encoding='utf-8',newline='') as f:
            for r in csv.DictReader(f):
                n+=1;latest=r;recent.append(r)
    except Exception as e:print('No se pudo cargar CSV:',e)
