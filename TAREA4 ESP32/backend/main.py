import asyncio, contextlib, csv, io, json, logging, os, time, uuid, queue, sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from .models import Settings, PROFILES
from .calibration import Calibration, StartCalibration, CaptureCalibration
from .runtime import Runtime as RuntimeState
from .parser import parse_line, MAX_LINE, SerialFramer
from .store import Store
from .network_scanner import scan_connected_network

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('DETECTOR_DATA',ROOT/'data'))
CONFIG=DATA/'settings.json'
logging.basicConfig(level=logging.INFO)
log=logging.getLogger('detector')

def load_settings():
    if CONFIG.exists(): return Settings.model_validate_json(CONFIG.read_text(encoding='utf-8'))
    return Settings()

class Runtime(RuntimeState):
    def __init__(self): super().__init__(ROOT,DATA)

runtime=None

def browser_origin():
    return os.environ.get("DETECTOR_USB_ORIGIN", "")

async def ingest_serial(rt, framer, raw):
    before=framer.dropped
    records=framer.feed(raw)
    rt.invalid+=framer.dropped-before
    if framer.dropped>before:rt.error('Línea serial excesiva descartada.','protocol')
    for buffer in records:
        try:
            event=parse_line(buffer)
            rt.last_event=time.time()
            if hasattr(event,'mac'):
                rt.last_detection=time.time();rt.received_observations+=1;change=None
                if rt.store:
                    try:change=await asyncio.to_thread(rt.store.ingest,event,time.time())
                    except sqlite3.Error as error:
                        rt.storage_dropped+=1;rt.db_error=str(error);rt.error('No se pudo guardar una observación.','sqlite')
                else:rt.storage_dropped+=1
                if change and (change['new'] or change['returned']): rt.new_events=(rt.new_events+[dict(**change,time=time.time())])[-20:]
            elif event['event'] in ('status','heartbeat'):
                was_ready=rt.status.get('boot_id') != event.get('boot_id')
                if rt.last_status and was_ready:
                    rt.firmware_restarts+=1;rt.error('Nuevo arranque ESP32: '+str(event.get('reset_reason','motivo no informado')),'firmware')
                rt.status=event;rt.last_status=time.time()
                if was_ready or rt.applied is None and rt.pending is None:
                    queue_config(rt)
            elif event['event']=='ack':
                if event.get('id')==rt.pending:
                    rt.applied=event; rt.pending=None
            elif event['event']=='error': rt.error(event.get('message','Error firmware'))
        except (ValueError,UnicodeError) as e:
            rt.invalid+=1
            if 'protocolo' in str(e):rt.protocol_errors+=1
            if buffer.lstrip().startswith(b'{'): rt.error('Evento serial inválido: '+str(e)[:160],'protocol')

async def serial_loop(rt):
    import serial
    while True:
        port=None
        try:
            rt.serial_task_state='connecting'
            port=await asyncio.to_thread(serial.Serial,rt.settings.port,rt.settings.baud,timeout=0.25,write_timeout=1)
            # Opening a dev board may reset it via DTR/RTS. Wait for boot, no input flush.
            rt.connected=True;rt.retry_port=False;rt.applied=None;rt.serial_error='';rt.serial_task_state='reading';rt.reconnects+=1;framer=SerialFramer()
            while not rt.commands.empty():rt.commands.get_nowait()
            while True:
                if rt.retry_port: break
                while not rt.commands.empty():
                    command=rt.commands.get_nowait()
                    await asyncio.to_thread(port.write,(json.dumps(command)+'\n').encode())
                raw=await asyncio.to_thread(port.read_until,b'\n',512)
                if not raw: continue
                await ingest_serial(rt, framer, raw)
        except asyncio.CancelledError: raise
        except (serial.SerialException,OSError) as e:
            msg='Puerto serial no disponible (inexistente, ocupado o desconectado): '+str(e)
            rt.serial_error=msg;rt.serial_task_state='retrying'
            if msg!=rt.last_error:rt.error(msg,'serial')
        finally:
            rt.connected=False; rt.pending=None
            if port:
                with contextlib.suppress(Exception):await asyncio.to_thread(port.close)
        await asyncio.sleep(2)

def queue_config(rt):
    rt.pending=uuid.uuid4().hex[:12];rt.pending_since=time.time()
    rt.commands.put_nowait(dict(command='configure',id=rt.pending,**rt.settings.firmware()))

async def housekeeping(rt):
    while True:
        if rt.store:
            try:rt.store.available();rt.store.cleanup(time.time());rt.db_error=''
            except sqlite3.Error as error:
                message='SQLite no disponible: '+str(error)[:180]
                if message!=rt.db_error:rt.error(message,'sqlite')
                rt.db_error=message
        else:rt.open_database()
        await asyncio.sleep(15)

async def lan_loop(rt):
    """Periodically scan the connected Wi-Fi/LAN network (ARP, UPnP/SSDP, NetBIOS, PJLink, IPP)
    while ESP32 serial_loop simultaneously captures external networks and Bluetooth."""
    await asyncio.sleep(2)
    while True:
        if rt.store and not os.environ.get('DETECTOR_DISABLE_LAN_SCAN'):
            try:
                discovered = await asyncio.to_thread(scan_connected_network)
                now = time.time()
                for obs in discovered:
                    await asyncio.to_thread(rt.store.ingest, obs, now)
            except Exception as error:
                log.debug('Escaneo LAN omitido: %s', error)
        await asyncio.sleep(25)

@asynccontextmanager
async def lifespan(app):
    global runtime
    runtime=Runtime()
    tasks=[asyncio.create_task(housekeeping(runtime)),asyncio.create_task(lan_loop(runtime))]
    if browser_origin():
        runtime.serial_task_state = "waiting_browser"
    else:
        tasks.append(asyncio.create_task(serial_loop(runtime)))
    try: yield
    finally:
        for task in tasks: task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError): await task
        if runtime.store:runtime.store.db.close()

app=FastAPI(title='ESP32 Observatorio',lifespan=lifespan)

@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):
        return Response('Origen no permitido',status_code=403)
    if request.url.hostname not in ('127.0.0.1','localhost','testserver'):
        return Response('Host no permitido',status_code=403)
    return await call_next(request)

@app.get('/api/state')
def state(): return runtime.snapshot()

@app.get('/api/devices/{key:path}/history')
def history(key:str): return require_store().history(key)

@app.get('/api/settings')
def settings(): return runtime.settings

@app.put('/api/settings')
def set_settings(value:Settings):
    return save_settings(value)

def save_settings(value):
    port_changed=value.port!=runtime.settings.port
    try:
        if runtime.config_error and CONFIG.exists():
            backup=CONFIG.with_name('settings.invalid.'+str(int(time.time()))+'.json')
            if not backup.exists():backup.write_bytes(CONFIG.read_bytes())
        temp=CONFIG.with_suffix('.tmp');temp.write_text(value.model_dump_json(indent=2),encoding='utf-8');temp.replace(CONFIG)
    except OSError as error:raise HTTPException(503,'No se puede guardar configuración: '+str(error))
    runtime.config_error='';runtime.settings=value
    if runtime.store:runtime.store.settings=value
    runtime.retry_port=port_changed
    if runtime.connected and not port_changed:queue_config(runtime)
    return dict(saved=True,hardware='pendiente de ACK' if runtime.connected else 'se aplicará al conectar',settings=value)

def require_store():
    if not runtime.store or runtime.db_error:raise HTTPException(503,runtime.db_error or 'SQLite no disponible')
    return runtime.store

@app.get('/api/health')
def health():return runtime.health()
@app.get('/api/diagnostics')
def diagnostics():return runtime.diagnostics()
@app.get('/api/ports')
def serial_ports():
    from serial.tools import list_ports
    return [dict(port=p.device,description=p.description) for p in list_ports.comports()]
@app.get('/api/profiles')
def profiles():return PROFILES
@app.post('/api/profiles/{profile}')
def apply_profile(profile:str):
    if profile not in PROFILES:raise HTTPException(404,'Perfil no encontrado')
    return save_settings(Settings.model_validate({**runtime.settings.model_dump(),**PROFILES[profile],'profile':profile}))
@app.post('/api/calibration/start')
def calibration_start(value:StartCalibration):
    try:return Calibration(require_store()).start(value.device_id,time.time())
    except ValueError as error:raise HTTPException(400,str(error))
@app.get('/api/calibration/{identifier}')
def calibration_status(identifier:str):
    try:return Calibration(require_store()).status(identifier,time.time())
    except ValueError as error:raise HTTPException(404,str(error))
@app.post('/api/calibration/{identifier}/capture')
def calibration_capture(identifier:str,value:CaptureCalibration):
    try:return Calibration(require_store()).capture(identifier,value.distance,value.seconds,time.time())
    except ValueError as error:raise HTTPException(400,str(error))
@app.post('/api/calibration/{identifier}/apply')
def calibration_apply(identifier:str):
    service=Calibration(require_store())
    try:status=service.status(identifier,time.time())
    except ValueError as error:raise HTTPException(404,str(error))
    if not status['fit']['valid']:raise HTTPException(400,status['fit'].get('reason','Calibración incompleta'))
    fit=status['fit'];result=save_settings(Settings.model_validate({**runtime.settings.model_dump(),'rssi_ref':fit['rssi_ref'],'loss_n':fit['loss_n'],'calibrated':True}))
    service.mark_applied(identifier);return result

@app.get('/api/errors')
def errors():
    try:return runtime.store.errors() if runtime.store else list(runtime.memory_errors)[-50:][::-1]
    except sqlite3.Error:return list(runtime.memory_errors)[-50:][::-1]

@app.post('/api/reset')
def reset():
    require_store().reset(); runtime.new_events=[]
    return {'reset':True}

@app.get('/api/export/{kind}')
def export(kind:str):
    devices=require_store().devices(time.time())
    if kind=='json': return Response(json.dumps(devices,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename=dispositivos.json'})
    if kind!='csv': raise HTTPException(404)
    output=io.StringIO(); fields=['classification','detected_device','detected_brand','certainty','how_identified','source','classification_confidence','classification_source','device_type','network_role','brand_confidence','category_confidence','model_confidence','role_confidence','model_source','mac','tech','name','brand','organization','model','category','rssi','mean','median','ema','distance','confidence','first','last','count','private_address']
    writer=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore'); writer.writeheader()
    for d in devices:
        safe={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in d.items()}
        writer.writerow(safe)
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=dispositivos.csv'})

@app.websocket('/api/browser-usb')
async def browser_usb(ws: WebSocket):
    rt = runtime
    origin = browser_origin()
    if not origin or ws.headers.get("origin") != origin or rt.connected:
        await ws.close(code=1008)
        return
    # Claim before the first await so two tabs cannot interleave USB data.
    rt.connected = True
    rt.status = {}
    rt.applied = rt.pending = None
    rt.last_status = 0
    rt.serial_task_state = "browser_usb"
    rt.reconnects += 1
    while not rt.commands.empty():
        rt.commands.get_nowait()
    framer = SerialFramer()
    try:
        await ws.accept()
        await ws.send_json({"ready": True})
        while True:
            while not rt.commands.empty():
                await ws.send_json({"command": rt.commands.get_nowait()})
            try:
                message = await asyncio.wait_for(ws.receive(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            if message["type"] == "websocket.disconnect":
                break
            chunk = message.get("bytes")
            if chunk is None or len(chunk) > 16384:
                await ws.close(code=1003)
                break
            await ingest_serial(rt, framer, chunk)
    except (WebSocketDisconnect, OSError):
        pass
    finally:
        rt.connected = False
        rt.pending = None
        rt.serial_task_state = "waiting_browser"

@app.websocket('/ws')
async def websocket(ws:WebSocket):
    if ws.headers.get('origin') not in ('http://localhost:8000','http://127.0.0.1:8000'):
        await ws.close(code=1008); return
    await ws.accept();runtime.websocket_clients+=1
    try:
        while True:
            await ws.send_json(await asyncio.to_thread(runtime.snapshot)); await asyncio.sleep(2)
    except (WebSocketDisconnect,RuntimeError):pass
    except Exception as error:
        runtime.websocket_errors+=1;runtime.error('WebSocket: '+str(error)[:150],'websocket')
    finally:runtime.websocket_clients-=1

app.mount('/assets',StaticFiles(directory=ROOT/'frontend',check_dir=False),name='assets')
@app.get('/')
def index():
    path=ROOT/'frontend/index.html'
    if not path.exists():return HTMLResponse('<h1>Panel HTML no encontrado</h1><p>Conserva la carpeta frontend junto al backend.</p><a href="/api/diagnostics">Diagnóstico</a>',status_code=503)
    if browser_origin():
        page = path.read_text(encoding='utf-8')
        control = '<button id="usbConnect" type="button">Conectar ESP32</button><span id="usbMessage" role="status"></span>'
        page = page.replace('<time id="clock">', control + '<time id="clock">')
        return HTMLResponse(page.replace('</head>', '<script src="/assets/web-serial.js" defer></script></head>'))
    return FileResponse(path)

@app.post('/api/scanner/recover')
def recover_scanner():
    if not runtime.connected:raise HTTPException(409,'ESP32 no conectado por serial')
    runtime.commands.put_nowait(dict(command='recover',id=uuid.uuid4().hex[:12]))
    return {'requested':True,'message':'Recuperación solicitada; espera un nuevo heartbeat para confirmar.'}

@app.post('/api/network/scan')
async def trigger_network_scan():
    store = require_store()
    discovered = await asyncio.to_thread(scan_connected_network)
    now = time.time()
    ingested = 0
    for obs in discovered:
        await asyncio.to_thread(store.ingest, obs, now)
        ingested += 1
    return {'scanned': True, 'discovered': ingested, 'message': f'Escaneo de red local completado: {ingested} equipos analizados (ARP/UPnP/NetBIOS/PJLink/IPP).'}
