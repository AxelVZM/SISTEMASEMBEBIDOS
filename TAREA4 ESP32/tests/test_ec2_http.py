"""Prueba HTTP real en localhost; no contacta con AWS."""
import importlib.util
import json
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from werkzeug.serving import make_server
from servidor.app import create_app
from test_ec2 import TOKEN,status,wifi,ble
spec=importlib.util.spec_from_file_location('bridge_http',ROOT/'herramientas/puente_usb.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
with tempfile.TemporaryDirectory() as temp:
    app=create_app({'API_TOKEN':TOKEN,'DB_PATH':str(Path(temp)/'db.sqlite3')})
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    try:
        bridge.post_packets(origin,TOKEN,'esp32-principal','http-test',[status(),wifi(),ble()])
        request=urllib.request.Request(origin+'/api/live',headers={'Authorization':'Bearer '+TOKEN})
        with urllib.request.urlopen(request,timeout=3) as r:data=json.load(r)
        assert data['online'] and len(data['packets'])==3
        assert next(p for p in data['packets'] if p['kind']=='ble')['deviceType']=='projector'
        with urllib.request.urlopen(origin+'/',timeout=3) as r:assert b'ec2Remote' in r.read()
        print('OK: puente Python -> HTTP local -> SQLite -> API remota y pagina. Sin servicios AWS simulados como reales.')
    finally:server.shutdown();thread.join(timeout=3);server.server_close()
