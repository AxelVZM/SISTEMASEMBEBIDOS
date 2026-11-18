import json, sqlite3, subprocess, shutil
from pathlib import Path
import pytest
from backend.models import Observation,Settings
from backend.parser import parse_line,SerialFramer,MAX_LINE
from backend.identify import Identifier
from backend.store import Store
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def data(tmp_path):
    (tmp_path/'name_rules.json').write_bytes((ROOT/'data/name_rules.json').read_bytes())
    with sqlite3.connect(tmp_path/'vendors.sqlite3') as db:
        db.executescript('create table oui(prefix text primary key,organization text,registry text);create table companies(id integer primary key,name text);')
        db.executemany('insert into oui values(?,?,?)',[('001122','Samsung Electronics','MA-L'),('0011223','Example Module','MA-M'),('001122334','Example Small','MA-S'),('AABBCC','Chipmaker example','MA-L')])
        db.execute('insert into companies values(76,"Apple, Inc.")')
    return tmp_path

def obs(**kwargs): return Observation(event='observation',tech='wifi',mac='00:11:22:AA:BB:CC',rssi=-60,**kwargs)

@pytest.mark.parametrize('mac',['bad','FF:FF:FF:FF:FF:FF','00:00:00:00:00:00','01:11:22:33:44:55'])
def test_invalid_mac(mac):
    with pytest.raises(ValueError): Observation(event='observation',tech='wifi',mac=mac)

def test_parser():
    assert parse_line(b'{"event":"observation","tech":"ble","mac":"aa:bb:cc:dd:ee:ff","rssi":-67}').mac=='AA:BB:CC:DD:EE:FF'
    for line in [b'[]',b'{}',b'boot text',b'x'*5000,b'{"event":"observation","tech":"wifi","mac":"00:11:22:33:44:55","rssi":-999}']:
        with pytest.raises(ValueError): parse_line(line)

def test_framer_partial_and_oversized():
    f=SerialFramer(); assert f.feed(b'{"event":')==[]
    assert f.feed(b'"status"}\nnext\n')==[b'{"event":"status"}',b'next']
    assert f.feed(b'x'*(MAX_LINE+50))==[]
    assert f.feed(b'end\nvalid\n')==[b'valid'];assert f.dropped==1

def test_longest_prefix(data):
    identifier=Identifier(data)
    assert identifier.lookup('00:11:22:33:44:55')['registry']=='MA-S'
    assert identifier.lookup('00:11:22:3A:44:55')['registry']=='MA-M'
    assert identifier.lookup('00:11:22:AA:44:55')['registry']=='MA-L'

def test_private_mac_classified_by_tech_and_role(data):
    result=Identifier(data).identify(Observation(event='observation',tech='wifi',mac='AA:BB:CC:DD:EE:FF',role='station',frame_type='probe_request'))
    assert result['private_address'];assert result['classification']=='Celular y Tablet';assert result['category']=='Celular'

def test_ble_random_apple_company_id_detected(data):
    o=Observation(event='observation',tech='ble',mac='00:11:22:33:44:55',address_type='random',company_id=76)
    result=Identifier(data).identify(o)
    assert result['brand']=='Apple';assert result['classification']=='Celular y Tablet';assert any('Company ID' in e for e in result['evidence'])

def test_category_and_model_from_oui(data):
    result=Identifier(data).identify(obs())
    assert result['brand']=='Samsung'; assert result['category']=='Celular';assert result['classification']=='Celular y Tablet';assert 'Samsung' in result['model']

def test_name_sets_brand_category_and_model(data):
    o=Observation(event='observation',tech='ble',mac='AA:BB:CC:DD:EE:FF',address_type='random',name='OPPO Reno 12')
    r=Identifier(data).identify(o);assert r['brand']=='OPPO';assert r['category']=='Celular';assert r['classification']=='Celular y Tablet';assert 'OPPO Reno 12' in r['model']

def test_no_name_ble_default(data):
    r=Identifier(data).identify(Observation(event='observation',tech='ble',mac='AA:BB:CC:DD:EE:FF'))
    assert r['classification']=='Celular y Tablet'

def test_cod_and_appearance(data):
    r=Identifier(data).identify(Observation(event='observation',tech='classic',mac='00:11:22:AA:BB:CC',cod=(1<<8)|(3<<2)))
    assert r['category']=='Laptop';assert r['classification']=='Laptop'
    assert Identifier(data).identify(Observation(event='observation',tech='ble',mac='AA:BB:CC:DD:EE:FF',appearance=192))['category']=='Reloj'

def test_dedup_smoothing_distance_expiry(data,tmp_path):
    settings=Settings(calibrated=True,rssi_ref=-60,loss_n=2,alpha=.5)
    store=Store(tmp_path/'test.sqlite3',data,settings)
    assert store.ingest(obs(),100)['new']
    assert store.ingest(obs(),100.2) is None
    o=Observation(event='observation',tech='wifi',mac='00:11:22:AA:BB:CC',rssi=-80)
    assert store.ingest(o,102)['new'] is False
    d=store.devices(103)[0]
    assert d['count']==2;assert d['mean']==-70;assert d['median']==-70;assert d['ema']==-70
    assert d['distance']==3.16;assert d['active']
    assert not store.devices(300)[0]['active'];assert store.ingest(obs(),300)['returned']
    store.settings.calibrated=False;assert store.devices(301)[0]['distance'] is None
    store.cleanup(300+8*86400);assert not store.devices(300+8*86400)

def test_metadata_preservation(data,tmp_path):
    store=Store(tmp_path/'meta.sqlite3',data,Settings())
    store.ingest(obs(name='Samsung'),100);store.ingest(obs(),102)
    assert store.devices(103)[0]['name']=='Samsung'
    store.reset();assert store.devices(104)==[]

@pytest.mark.parametrize('kwargs',[{'channels':[1,1]},{'channels':[12]},{'loss_n':0},{'alpha':2},{'dedup_ms':0}])
def test_config_validation(kwargs):
    with pytest.raises(ValueError):Settings(**kwargs)

@pytest.mark.skipif(shutil.which("cc") is None, reason="Prueba C opcional: requiere compilador cc/GCC.")
def test_wifi_header_native(tmp_path):
    executable=tmp_path/'header_test'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I'+str(ROOT/'firmware/main'),str(ROOT/'tests/wifi_header_test.c'),str(ROOT/'firmware/main/wifi_header.c'),'-o',str(executable)],check=True)
    subprocess.run([str(executable)],check=True)

def test_ambiguous_official_assignment(data):
    with sqlite3.connect(data/'vendors.sqlite3') as db:
        db.execute('insert into oui values(?,?,?)',('001133','Samsung Electronics | Apple, Inc.','MA-L'))
    result=Identifier(data).identify(Observation(event='observation',tech='wifi',mac='00:11:33:AA:BB:CC',role='station',frame_type='probe_request'))
    assert any('múltiples titulares' in w for w in result['warnings'])
