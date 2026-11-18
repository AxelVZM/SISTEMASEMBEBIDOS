import importlib,json,time
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DETECTOR_DATA',str(tmp_path))
    import backend.main as module
    importlib.reload(module)
    with TestClient(module.app) as c: yield c,module

def test_api_without_hardware(client):
    c,m=client
    assert c.get('/').status_code==200
    assert c.get('/api/state').json()['devices']==[]
    config=c.get('/api/settings').json();assert config['port']=='COM6'
    config['channels']=[1,6,11];assert c.put('/api/settings',json=config).status_code==200
    config['channels']=[99];assert c.put('/api/settings',json=config).status_code==422
    assert c.get('/api/export/csv').status_code==200;assert c.get('/api/export/json').json()==[]
    assert c.post('/api/reset').json()=={'reset':True}
    assert c.get('/api/state',headers={'Origin':'https://untrusted.example'}).status_code==403

def test_api_real_pipeline_fixture(client):
    c,m=client
    from backend.parser import parse_line
    m.runtime.store.ingest(parse_line(b'{"event":"observation","tech":"ble","mac":"AA:BB:CC:11:22:33","name":"=HYPERLINK(test)","rssi":-65,"address_type":"random"}'),time.time())
    state=c.get('/api/state').json();assert state['stats']['total']==1
    assert state['stats']['observations']['ble']==1
    key=state['devices'][0]['id']
    assert len(c.get('/api/devices/'+key+'/history').json())==1
    assert "'=HYPERLINK(test)" in c.get('/api/export/csv').text
    with c.websocket_connect('/ws',headers={'Origin':'http://127.0.0.1:8000'}) as ws:
        assert ws.receive_json()['stats']['total']==1
