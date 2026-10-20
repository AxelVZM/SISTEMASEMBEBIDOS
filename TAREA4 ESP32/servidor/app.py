import hmac
import json
import os
import re
import sqlite3
import time
from functools import wraps
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

KINDS={'unknown','phone','laptop','computer','tablet','router','ap','network','projector','tv','display','printer','camera','audio','wearable','gaming','storage','media','peripheral','sensor'}
LEVELS={'declared','hint','role','conflict','unknown'}
MAC=re.compile(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}')
SENSOR=re.compile(r'[a-zA-Z0-9_-]{1,64}')
ONLINE_SECONDS=5

def integer(v,lo,hi):
    return isinstance(v,int) and not isinstance(v,bool) and lo<=v<=hi

def validate_packet(p):
    if not isinstance(p,dict) or p.get('kind') not in ('status','wifi','ble'):
        raise ValueError('Solo se aceptan paquetes status/wifi/ble')
    if not integer(p.get('b'),0,0xffffffff): raise ValueError('Sesión inválida')
    kind=p['kind']; out={}
    if kind=='status':
        if p.get('firmware') not in ('7.0','7.1','7.2'):raise ValueError('Versión de firmware incompatible')
        bounds={'ms':0xffffffff,'wifi':96,'ble':32,'wifiKnown':96,'bleKnown':32,'aps':96,'clients':96,'channel':11,'heap':0xffffffff,'minHeap':0xffffffff,'logBytes':0xffffffff,'wifiOmitted':0xffffffff,'bleOmitted':0xffffffff,'rxOmitted':0xffffffff,'bleRxOmitted':0xffffffff}
        for k,hi in bounds.items():
            if not integer(p.get(k),1 if k=='channel' else 0,hi):raise ValueError('Estado inválido: '+k)
            out[k]=p[k]
        for k in ('wifiReady','bleReady','storage','wifiCapacity','bleCapacity','oled','rtc','clock','watchdog'):
            if not isinstance(p.get(k),bool):raise ValueError('Estado booleano inválido')
            out[k]=p[k]
        for k in ('wifiError','bleError','storageError'):
            if not isinstance(p.get(k),str) or len(p[k])>300:raise ValueError('Texto de estado inválido')
            out[k]=p[k]
        if p.get('radio') not in ('Wi-Fi','BLE','Red'):raise ValueError('Fase inválida')
        epoch=p.get('epoch')
        if epoch is not None and not integer(epoch,1704067200,4102444799):raise ValueError('Fecha inválida')
        out.update(firmware=p['firmware'],radio=p['radio'],epoch=epoch,ttl=60000,netPaused=p.get('netPaused',False))
        if not isinstance(out['netPaused'],bool):raise ValueError('Pausa inválida')
    else:
        if not integer(p.get('slot'),0,95 if kind=='wifi' else 31) or not isinstance(p.get('mac'),str) or not MAC.fullmatch(p['mac']):raise ValueError('Fila/dirección inválida')
        rssi=p.get('rssi')
        if isinstance(rssi,bool) or not isinstance(rssi,(int,float)) or not -127<=rssi<=20:raise ValueError('RSSI inválido')
        if not integer(p.get('frames'),1,0xffffffff) or not integer(p.get('last'),0,0xffffffff):raise ValueError('Recepciones inválidas')
        out.update(slot=p['slot'],mac=p['mac'],rssi=rssi,frames=p['frames'],last=p['last'])
        fields={'name':64}
        if kind=='wifi':fields.update(role=80,ssid=32,nameSource=80,vendor=400,manufacturer=100,model=100,number=100,security=100)
        else:fields.update(company=400)
        for k,n in fields.items():
            v=p.get(k,'')
            if not isinstance(v,str) or len(v)>n:raise ValueError('Texto de fila inválido: '+k)
            out[k]=v
        if kind=='wifi':
            if not isinstance(p.get('local'),bool) or not integer(p.get('channel'),1,11):raise ValueError('Canal/tipo MAC inválido')
            out.update(local=p['local'],channel=p['channel'],wpsConflict=bool(p.get('wpsConflict',False)),wifiGeneration=p.get('wifiGeneration',0))
            if out['wifiGeneration'] not in (0,4,5,6):raise ValueError('Generación inválida')
        else:
            if not integer(p.get('addressType'),0,3):raise ValueError('Dirección BLE inválida')
            for k,hi in (('companyId',65535),('appearance',65535)):
                if p.get(k) is not None and not integer(p[k],0,hi):raise ValueError('Dato BLE inválido')
                out[k]=p.get(k)
            out.update(addressType=p['addressType'],companyConflict=bool(p.get('companyConflict',False)),disAdvertised=bool(p.get('disAdvertised',False)))
        if 'deviceType' in p:
            if p['deviceType'] not in KINDS or p.get('classLevel') not in LEVELS:raise ValueError('Clasificación inválida')
            out.update(deviceType=p['deviceType'],classLevel=p['classLevel'])
            for k,n in (('deviceLabel',80),('classEvidence',200)):
                if not isinstance(p.get(k),str) or len(p[k])>n:raise ValueError('Evidencia inválida')
                out[k]=p[k]
    out.update(kind=kind,b=p['b'])
    return out

def create_app(config=None):
    app=Flask(__name__,static_folder=None)
    app.config.update(API_TOKEN=os.environ.get('ORBITA_API_TOKEN',''),DB_PATH=os.environ.get('ORBITA_DB_PATH','datos/orbita.sqlite3'),MAX_CONTENT_LENGTH=256*1024,NOW=time.time)
    if config:app.config.update(config)
    token=app.config['API_TOKEN']
    if not isinstance(token,str) or len(token)<32:raise RuntimeError('ORBITA_API_TOKEN debe tener al menos 32 caracteres; ejecuta herramientas/configurar_servidor.py')
    path=Path(app.config['DB_PATH']);path.parent.mkdir(parents=True,exist_ok=True)
    @contextmanager
    def db():
        conn=sqlite3.connect(path,timeout=10);conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            with conn:yield conn
        finally:conn.close()
    with db() as c:
        c.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sensors(id TEXT PRIMARY KEY,boot INTEGER NOT NULL,status TEXT,received REAL NOT NULL,status_received REAL NOT NULL,source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS packets(sensor TEXT NOT NULL,kind TEXT NOT NULL,slot INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(sensor,kind,slot),FOREIGN KEY(sensor) REFERENCES sensors(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS history(sensor TEXT NOT NULL,at INTEGER NOT NULL,wifi INTEGER NOT NULL,ble INTEGER NOT NULL,boot INTEGER NOT NULL,PRIMARY KEY(sensor,at));
        CREATE INDEX IF NOT EXISTS history_time ON history(at);''')
    def auth(f):
        @wraps(f)
        def wrapped(*a,**kw):
            supplied=request.headers.get('Authorization','')
            if not hmac.compare_digest(supplied.encode(),('Bearer '+token).encode()):return jsonify(error='Token inválido o ausente'),401
            return f(*a,**kw)
        return wrapped
    def sensor_arg():
        value=request.args.get('sensor','esp32-principal')
        if not SENSOR.fullmatch(value):raise ValueError('ID de sensor inválido')
        return value
    @app.errorhandler(ValueError)
    def bad(error):return jsonify(error=str(error)),400
    @app.errorhandler(413)
    def large(error):return jsonify(error='Carga demasiado grande'),413
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        if request.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        return response
    web=Path(__file__).resolve().parents[1]/'web'
    @app.get('/')
    def page():return send_from_directory(web,'index.html')
    @app.get('/ec2.js')
    def script():return send_from_directory(web,'ec2.js')
    @app.get('/api/health')
    def health():return jsonify(ok=True,version='ec2-1',firmware='7.2')
    @app.post('/api/ingest')
    @auth
    def ingest():
        body=request.get_json()
        if not isinstance(body,dict):raise ValueError('Objeto JSON requerido')
        sid=body.get('sensor_id');source=body.get('source_id')
        if not isinstance(sid,str) or not SENSOR.fullmatch(sid) or not isinstance(source,str) or not SENSOR.fullmatch(source):raise ValueError('ID de sensor/emisor inválido')
        rows=body.get('packets')
        if not isinstance(rows,list) or not 1<=len(rows)<=256:raise ValueError('Se requieren 1–256 paquetes')
        packets=[validate_packet(p) for p in rows]
        if len({p['b'] for p in packets})!=1:raise ValueError('No mezclar sesiones de arranque')
        now=app.config['NOW']();boot=packets[0]['b'];accepted=0
        with db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM sensors WHERE id=?',(sid,)).fetchone()
            if old and old['source']!=source and now-old['received']<8:return jsonify(error='ID de sensor ocupado por otro puente activo'),409
            statuses=[p for p in packets if p['kind']=='status']
            if not old or old['boot']!=boot:
                if not statuses:raise ValueError('La sesión nueva necesita estado del ESP32')
                if not old and c.execute('SELECT COUNT(*) FROM sensors').fetchone()[0]>=16:raise ValueError('Capacidad de 16 sensores alcanzada')
                c.execute('DELETE FROM packets WHERE sensor=?',(sid,))
                c.execute('INSERT INTO sensors(id,boot,status,received,status_received,source) VALUES(?,?,NULL,?,0,?) ON CONFLICT(id) DO UPDATE SET boot=excluded.boot,status=NULL,status_received=0,received=excluded.received,source=excluded.source',(sid,boot,now,source))
                old=c.execute('SELECT * FROM sensors WHERE id=?',(sid,)).fetchone()
            c.execute('UPDATE sensors SET received=?,source=? WHERE id=?',(now,source,sid))
            previous=json.loads(old['status']) if old['status'] else None
            for p in statuses:
                if previous:
                    delta=(p['ms']-previous['ms'])&0xffffffff
                    if delta==0 or delta>=0x80000000:continue
                c.execute('UPDATE sensors SET status=?,status_received=? WHERE id=?',(json.dumps(p,ensure_ascii=False),now,sid));previous=p;accepted+=1
                last=c.execute('SELECT MAX(at) FROM history WHERE sensor=?',(sid,)).fetchone()[0]
                if last is None or int(now*1000)-last>=5000:c.execute('INSERT OR IGNORE INTO history VALUES(?,?,?,?,?)',(sid,int(now*1000),p['wifi'],p['ble'],boot))
            for p in packets:
                if p['kind']=='status':continue
                prior=c.execute('SELECT payload FROM packets WHERE sensor=? AND kind=? AND slot=?',(sid,p['kind'],p['slot'])).fetchone()
                if prior:
                    prior=json.loads(prior[0]);delta=(p['last']-prior['last'])&0xffffffff
                    if delta>=0x80000000:continue
                c.execute('INSERT INTO packets VALUES(?,?,?,?) ON CONFLICT(sensor,kind,slot) DO UPDATE SET payload=excluded.payload',(sid,p['kind'],p['slot'],json.dumps(p,ensure_ascii=False)));accepted+=1
            c.execute('DELETE FROM history WHERE at<?',(int((now-7*86400)*1000),))
        return jsonify(ok=True,accepted=accepted)
    @app.get('/api/live')
    @auth
    def live():
        sid=sensor_arg();now=app.config['NOW']()
        with db() as c:
            sensor=c.execute('SELECT * FROM sensors WHERE id=?',(sid,)).fetchone()
            if not sensor:return jsonify(sensor_id=sid,online=False,packets=[],server_time=now,last_seen=None)
            packets=[json.loads(r[0]) for r in c.execute('SELECT payload FROM packets WHERE sensor=? ORDER BY kind,slot',(sid,))]
        status=json.loads(sensor['status']) if sensor['status'] else None
        return jsonify(sensor_id=sid,online=bool(status and now-sensor['status_received']<ONLINE_SECONDS),packets=([status] if status else [])+packets,server_time=now,last_seen=sensor['status_received'])
    @app.get('/api/history')
    @auth
    def history():
        sid=sensor_arg();now=app.config['NOW']()
        try:hours=max(1,min(24,int(request.args.get('hours',4))))
        except (TypeError,ValueError):raise ValueError('Horas inválidas')
        with db() as c:rows=c.execute('SELECT at AS time,wifi,ble,boot FROM history WHERE sensor=? AND at>=? ORDER BY at DESC LIMIT 4000',(sid,int((now-hours*3600)*1000))).fetchall()
        return jsonify(points=[dict(r) for r in reversed(rows)])
    return app
