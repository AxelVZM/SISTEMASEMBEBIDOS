import importlib,json,math,sqlite3,time,asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.models import Observation,Settings,Status,PROFILES
from backend.parser import parse_line
from backend.runtime import Runtime
from backend.store import Store
from backend.calibration import Calibration,fit_measurements
ROOT=Path(__file__).resolve().parents[1]

def app_client(tmp_path,monkeypatch):
    monkeypatch.setenv('DETECTOR_DATA',str(tmp_path))
    import backend.main as module
    importlib.reload(module)
    return TestClient(module.app),module

def test_corrupt_settings_no_longer_prevents_startup(tmp_path,monkeypatch):
    config=tmp_path/'settings.json';config.write_text('{broken')
    client,module=app_client(tmp_path,monkeypatch)
    with client as c:
        assert c.get('/').status_code==200
        health=c.get('/api/health').json();assert health['backend']['active'];assert health['configuration_error']
        assert c.get('/api/settings').json()['port']=='COM6';assert config.read_text()=='{broken'
        assert c.put('/api/settings',json=Settings().model_dump()).status_code==200
        assert len(list(tmp_path.glob('settings.invalid.*.json')))==1
        assert c.get('/api/health').json()['configuration_error'] is None

def test_corrupt_database_keeps_panel_available(tmp_path,monkeypatch):
    original=b'this is not a database';(tmp_path/'observations.sqlite3').write_bytes(original)
    client,module=app_client(tmp_path,monkeypatch)
    with client as c:
        assert c.get('/').status_code==200
        health=c.get('/api/health').json();assert health['status']=='degraded';assert not health['database']['available']
        assert c.get('/api/state').json()['devices']==[];assert c.get('/api/export/json').status_code==503
        assert c.get('/api/diagnostics').json()['errors']
    assert (tmp_path/'observations.sqlite3').read_bytes()==original

def test_health_requires_actual_scan_confirmation(tmp_path):
    rt=Runtime(ROOT,tmp_path);rt.connected=True;rt.last_status=time.time();rt.status={'firmware':'1.0.0','phase':'wifi'}
    assert rt.health()['firmware']['responding'];assert not rt.health()['scanner_active']
    rt.status.update(wifi_scanning=True,ble_scanning=False,classic_scanning=False)
    assert rt.health()['scanners']['wifi']['active']
    rt.last_status-=30;assert not rt.health()['scanner_active'];rt.store.db.close()

def test_profiles_send_real_scheduler_values(tmp_path,monkeypatch):
    client,module=app_client(tmp_path,monkeypatch)
    async def idle(rt):await asyncio.Event().wait()
    monkeypatch.setattr(module,'serial_loop',idle)
    with client as c:
        module.runtime.connected=True
        for profile,expected in PROFILES.items():
            response=c.post('/api/profiles/'+profile);assert response.status_code==200
            settings=c.get('/api/settings').json();assert settings['profile']==profile
            command=module.runtime.commands.get_nowait()
            for key,value in expected.items():assert settings[key]==command[key]==value
            assert module.runtime.pending;assert module.runtime.applied is None
        assert c.post('/api/profiles/decorative').status_code==404
        module.runtime.connected=False;assert c.post('/api/scanner/recover').status_code==409

@pytest.mark.parametrize('v',[1,2])
def test_protocol_legacy_observations(v):
    obs=parse_line(json.dumps(dict(event='observation',v=v,tech='wifi',mac='04:B2:47:97:D9:8C',rssi=-60)).encode())
    assert obs.v==v

def test_protocol_v2_type_aliases():
    o=parse_line(b'{"type":"detection","protocol_version":2,"technology":"ble","mac":"AA:BB:CC:11:22:33","rssi":-65,"timestamp_ms":500}')
    assert o.event=='observation' and o.tech=='ble' and o.uptime_ms==500

@pytest.mark.parametrize('value',[
    dict(event='observation',v=3,tech='wifi',mac='04:B2:47:97:D9:8C'),
    dict(event='status',type='detection'),dict(type='mystery'),dict(type='detection',v=1,protocol_version=2),
    dict(type='detection',tech='wifi',technology='ble',mac='04:B2:47:97:D9:8C')])
def test_protocol_incompatible_messages_rejected(value):
    with pytest.raises(ValueError):parse_line(json.dumps(value).encode())

def test_extended_heartbeat_is_valid():
    sample=dict(type='heartbeat',v=2,firmware='2.0.0',boot_id=10,phase='WIFI_SCAN',uptime_ms=5000,free_heap=80000,minimum_free_heap=75000,queue_dropped=2,
        wifi_scanning=True,ble_scanning=False,classic_scanning=False,events_captured=100,wifi_listen_ms=5000,channels_visited=[1,6,11],channel_events=[0]*11)
    parsed=parse_line(json.dumps(sample).encode());assert parsed['event']=='heartbeat';assert parsed['events_captured']==100
    sample['channel_events']=[-1]*11
    with pytest.raises(ValueError):parse_line(json.dumps(sample).encode())

def test_calibration_regression_and_bad_measurements():
    samples=[dict(distance=d,count=10,median=-50-20*math.log10(d)) for d in (1,3,5,10)]
    fit=fit_measurements(samples);assert fit['valid'];assert fit['loss_n']==2;assert fit['rssi_ref']==-50
    assert not fit_measurements(samples[:2])['valid']
    assert not fit_measurements([dict(distance=d,count=10,median=-60) for d in (1,3,5,10)])['valid']
    assert not fit_measurements([dict(distance=d,count=10,median=-60+20*math.log10(d)) for d in (1,3,5,10)])['valid']

def test_calibration_only_selected_address_inside_window(tmp_path):
    store=Store(tmp_path/'obs.sqlite3',ROOT/'data',Settings())
    selected=Observation(event='observation',tech='ble',mac='AA:BB:CC:11:22:33',rssi=-50)
    other=Observation(event='observation',tech='ble',mac='AA:BB:CC:11:22:44',rssi=-90)
    store.ingest(selected,100);service=Calibration(store);session=service.start('ble:'+selected.mac,101)
    service.capture(session['id'],1,5,102)
    with pytest.raises(ValueError):service.capture(session['id'],3,5,102.1)
    for ts in (103,104,105,106,107):store.ingest(selected,ts);store.ingest(other,ts)
    result=service.status(session['id'],108)
    assert result['measurements'][0]['count']==5;assert result['measurements'][0]['median']==-50
    assert not result['fit']['valid'];store.db.close()

def test_migration_preserves_legacy_rows(tmp_path):
    path=tmp_path/'legacy.sqlite3';o=Observation(event='observation',tech='wifi',mac='04:B2:47:97:D9:8C',rssi=-60,channel=6)
    with sqlite3.connect(path) as db:
        db.executescript('create table devices(id text primary key,tech text,mac text,first real,last real,count integer,ema real,metadata text);create table observations(id integer primary key,device text,ts real,rssi integer,metadata text);')
        db.execute('insert into devices values(?,?,?,?,?,?,?,?)',('wifi:'+o.mac,'wifi',o.mac,10,20,7,-60,o.model_dump_json()))
        db.execute('insert into observations values(?,?,?,?,?)',(42,'wifi:'+o.mac,20,-60,o.model_dump_json()))
    store=Store(path,ROOT/'data',Settings());device=store.devices(21)[0]
    assert device['count']==7;assert device['first_ts']==10
    history=store.history(device['id']);assert history[0]['id']==42;assert history[0]['channel']==6
    assert store.db.execute('pragma user_version').fetchone()[0]==2
    with sqlite3.connect(tmp_path/'legacy.pre-v2.sqlite3') as backup:assert backup.execute('select id from observations').fetchone()[0]==42
    store.ingest(o,30);latest=store.history(device['id'])[-1];assert json.loads(latest['identification'])['identification_evidence'];store.db.close()

def test_calibration_api_requires_authorization_and_complete_fit(tmp_path,monkeypatch):
    client,module=app_client(tmp_path,monkeypatch)
    with client as c:
        o=Observation(event='observation',tech='ble',mac='AA:BB:CC:11:22:33',rssi=-50)
        module.runtime.store.ingest(o,time.time())
        assert c.post('/api/calibration/start',json=dict(device_id='ble:'+o.mac,authorized=False)).status_code==422
        session=c.post('/api/calibration/start',json=dict(device_id='ble:'+o.mac,authorized=True)).json()
        assert c.post('/api/calibration/'+session['id']+'/apply').status_code==400
        assert c.post('/api/calibration/'+session['id']+'/capture',json=dict(distance=2,seconds=5)).status_code==422
        assert c.post('/api/calibration/'+session['id']+'/capture',json=dict(distance=1,seconds=5)).status_code==200


def test_health_detects_database_closed_after_start(tmp_path):
    rt=Runtime(ROOT,tmp_path);rt.store.db.close()
    assert not rt.health()['database']['available']

def test_launcher_rejects_foreign_port_and_reuses_own_server(tmp_path,monkeypatch):
    from scripts import launcher
    executable=tmp_path/'python.exe';executable.write_bytes(b'fixture')
    monkeypatch.setattr(launcher,'venv_python',lambda:executable)
    monkeypatch.setattr(launcher,'inspect_dependencies',lambda p:{'missing':[]})
    monkeypatch.setattr(launcher,'port_occupied',lambda:True)
    monkeypatch.setattr(launcher,'health_request',lambda:None)
    assert launcher.start(no_browser=True)==1
    monkeypatch.setattr(launcher,'health_request',lambda:{'service':'esp32-detector'})
    assert launcher.start(no_browser=True)==0

def test_launcher_detects_missing_files_and_env(tmp_path,monkeypatch):
    from scripts import launcher
    assert 'frontend/index.html' in launcher.inspect_files(tmp_path)
    monkeypatch.setattr(launcher,'venv_python',lambda:tmp_path/'missing-python')
    assert launcher.start(no_browser=True)==1


def test_future_database_version_is_not_downgraded(tmp_path,monkeypatch):
    path=tmp_path/'observations.sqlite3'
    with sqlite3.connect(path) as db:db.execute('pragma user_version=99')
    client,module=app_client(tmp_path,monkeypatch)
    with client as c:
        assert c.get('/').status_code==200
        assert not c.get('/api/health').json()['database']['available']
    with sqlite3.connect(path) as db:assert db.execute('pragma user_version').fetchone()[0]==99
