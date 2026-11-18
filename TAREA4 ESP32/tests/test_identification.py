"""Synthetic addresses and WPS records are confined to temporary test databases."""
import json,sqlite3,shutil,subprocess,os
from pathlib import Path
import pytest
from backend.models import Observation,Settings
from backend.identify import Identifier
from backend.store import Store
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def engine(tmp_path):
    (tmp_path/'name_rules.json').write_bytes((ROOT/'data/name_rules.json').read_bytes())
    with sqlite3.connect(tmp_path/'vendors.sqlite3') as db:
        db.executescript('create table oui(prefix text primary key,organization text,registry text);create table companies(id integer primary key,name text);')
        db.executemany('insert into oui values(?,?,?)',[
            ('001100','HONOR Device Co., Ltd.','MA-L'),
            ('001101','ZTE Corporation','MA-L'),
            ('001102','Intel Corporate','MA-L'),
            ('001103','Samsung Electronics','MA-L'),
            ('001104','Seiko Epson Corporation','MA-L'),
            ('001105','BenQ Corporation','MA-L'),
            ('001106','TP-LINK TECHNOLOGIES CO.,LTD.','MA-L'),
            ('001107','Brother Industries, LTD.','MA-L'),
            ('001108','Dell Inc.','MA-L'),
            ('001109','Hewlett Packard','MA-L'),
        ])
        db.executemany('insert into companies values(?,?)',[(76,"Apple, Inc."),(6,"Microsoft"),(117,"Samsung Electronics Co. Ltd."),(64,"Seiko Epson Corporation"),(101,"Hewlett-Packard Company")])
    return Identifier(tmp_path)

def test_honor_ap_classified_as_mobile_hotspot_celular(engine):
    r=engine.identify(Observation(event='observation',tech='wifi',mac='00:11:00:11:22:33',role='ap',frame_type='beacon'))
    assert r['brand']=='Honor';assert r['network_role']=='Punto de acceso';assert r['category']=='Celular';assert r['classification']=='Celular y Tablet';assert 'Hotspot' in r['detected_device']

def test_zte_explicit_wps_router_and_announced_model(engine):
    r=engine.identify(Observation(event='observation',tech='wifi',mac='00:11:01:11:22:33',role='ap',wps_manufacturer='ZTE',wps_model_name='ZXHN F680',wps_model_number='F680',wps_primary_device_type='00060050F2040002'))
    assert r['brand']=='ZTE';assert r['category']=='Router';assert r['classification']=='Router';assert r['detected_device']=='ZTE ZXHN F680';assert r['network_role']=='Punto de acceso';assert r['model']=='ZXHN F680';assert r['model_source']=='WPS (autodeclarado)';assert r['model_confidence']=='Media'

def test_hotspot_can_be_phone_and_ap(engine):
    r=engine.identify(Observation(event='observation',tech='wifi',mac='00:11:00:11:22:33',role='ap',wps_primary_device_type='000A0050F2040000'))
    assert r['category']=='Celular';assert r['classification']=='Celular y Tablet';assert r['network_role']=='Punto de acceso'

def test_intel_radio_vendor_classified_as_laptop(engine):
    r=engine.identify(Observation(event='observation',tech='wifi',mac='00:11:02:11:22:33',role='station'))
    assert r['radio_vendor']=='Intel Corporate';assert r['brand']=='Intel';assert r['category']=='Laptop';assert r['classification']=='Laptop';assert r['network_role']=='Estación'

@pytest.mark.parametrize('appearance,category',[(0x83,'Laptop'),(0x87,'Tablet'),(0xc0,'Reloj'),(0xc2,'Reloj inteligente'),(0x3c1,'Teclado'),(0x3c2,'Ratón'),(0x3c4,'Control de videojuegos'),(0xa03,'Cañón')])
def test_appearance_subtypes(engine,appearance,category):
    r=engine.identify(Observation(event='observation',tech='ble',mac='AA:BB:CC:11:22:33',appearance=appearance))
    assert r['category']==category;assert r['category_confidence']=='Alta'

@pytest.mark.parametrize('cod,category',[(0x10c,'Laptop'),(0x104,'Computadora'),(0x20c,'Celular'),(0x214,'Equipo telefónico'),(0x414,'Altavoz'),(0x418,'Audífonos'),(0x540,'Teclado'),(0x680,'Impresora'),(0x6c0,'Impresora multifunción')])
def test_classic_subclasses(engine,cod,category):
    r=engine.identify(Observation(event='observation',tech='classic',mac='AA:BB:CC:11:22:33',cod=cod));assert r['category']==category

def test_apple_company_id_detected_as_apple_celular(engine):
    r=engine.identify(Observation(event='observation',tech='ble',mac='AA:BB:CC:11:22:33',company_id=76,services=['180F']))
    assert r['brand']=='Apple';assert r['category']=='Celular';assert r['classification']=='Celular y Tablet';assert r['company_identifier_owner']=='Apple, Inc.';assert r['advertised_capabilities'][0]['name']=='Batería'

def test_conflicting_brand_and_type_reduce_confidence(engine):
    r=engine.identify(Observation(event='observation',tech='ble',mac='00:11:03:11:22:33',address_type='public',name='AirPods',appearance=0x40))
    assert r['brand_confidence']=='Baja';assert r['category_confidence']=='Baja';assert r['category']=='Teléfono';assert any('contradictorias' in w for w in r['warnings'])

def test_enrichment_survives_serial_dedup_and_short_names(tmp_path):
    store=Store(tmp_path/'obs.sqlite3',ROOT/'data',Settings())
    base=dict(event='observation',tech='ble',mac='AA:BB:CC:11:22:33',rssi=-60)
    store.ingest(Observation(**base),100)
    assert store.ingest(Observation(**base,name='Galaxy Watch',name_complete=True,name_source='scan_response',appearance=0xc2),100.1)
    assert store.ingest(Observation(**base,name='Galaxy',name_source='advertisement'),100.2) is None
    store.ingest(Observation(**base),102)
    d=store.devices(103)[0];assert d['name']=='Galaxy Watch';assert d['category']=='Reloj inteligente';store.db.close()

def test_new_settings_and_wps_validation():
    assert Settings().ble_active is True
    assert Settings(ble_active=True).firmware()['ble_active'] is True
    with pytest.raises(ValueError):Observation(event='observation',tech='wifi',mac='00:11:01:11:22:33',wps_primary_device_type='bad')

@pytest.mark.skipif(shutil.which('cc') is None,reason='Requiere compilador C nativo')
def test_native_wps_parser_bounds(tmp_path):
    binary=tmp_path/'wps-test'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I'+str(ROOT/'firmware/main'),str(ROOT/'tests/wifi_metadata_test.c'),str(ROOT/'firmware/main/wifi_metadata.c'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})

def test_chip_name_requires_a_real_vendor_match():
    from backend.identify import CHIPS
    assert CHIPS.search('Intel Corporate')
    assert CHIPS.search('Intelbras') is None
    assert CHIPS.search('Intelligent Systems') is None

@pytest.mark.parametrize('kwargs,expected_brand,expected_class,expected_device_sub',[
    (dict(tech='ble',mac='AA:BB:CC:11:22:01',name='Galaxy S24 Ultra'), 'Samsung', 'Celular', 'Galaxy S24 Ultra'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:02',name='Redmi Note 13 Pro'), 'Redmi', 'Celular', 'Redmi Note 13 Pro'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:03',company_id=76,manufacturer_data='0E03010203'), 'Apple', 'Celular', 'iPhone'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:04',name='iPad Air'), 'Apple', 'Tablet', 'iPad Air'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:05',name='Galaxy Tab S9'), 'Samsung', 'Tablet', 'Galaxy Tab S9'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:06',company_id=6,manufacturer_data='01100000'), 'Microsoft', 'Tablet', 'Tablet Windows'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:07',name='ThinkPad X1 Carbon'), 'Lenovo', 'Laptop', 'ThinkPad X1 Carbon'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:08',company_id=6,manufacturer_data='010F0000'), 'Microsoft', 'Laptop', 'Laptop Windows'),
    (dict(tech='wifi',mac='00:11:08:11:22:09',role='station'), 'Dell', 'Laptop', 'Laptop Dell'),
    (dict(tech='wifi',mac='00:11:09:11:22:09',role='ap'), 'HP', 'Router', 'Router HP'),  # AP con OUI HP sin nombre de impresora = Router, no impresora
    (dict(tech='wifi',mac='00:11:09:11:22:19',role='station'), 'HP', 'Laptop', 'Laptop HP'),
    (dict(tech='wifi',mac='AA:BB:CC:11:22:10',role='ap',ssid='DIRECT-42-HP LaserJet M404'), 'HP', 'Impresora', 'HP LaserJet M404'),
    (dict(tech='wifi',mac='00:11:04:11:22:11',role='ap',wps_model_name='EcoTank L3250'), 'Epson', 'Impresora', 'Epson EcoTank L3250'),
    (dict(tech='wifi',mac='00:11:07:11:22:12',role='station'), 'Brother', 'Impresora', 'Impresora Brother'),
    (dict(tech='wifi',mac='00:11:06:11:22:13',role='ap',ssid='TP-Link_Archer_AX55'), 'TP-Link', 'Router', 'TP-Link_Archer_AX55'),
    (dict(tech='wifi',mac='AA:BB:CC:11:22:14',role='ap',name='MikroTik-hAP-ax3'), 'MikroTik', 'Router', 'MikroTik-hAP-ax3'),
    (dict(tech='wifi',mac='00:11:04:11:22:15',role='ap',wps_device_name='EPSON_Projector',wps_model_name='PowerLite E20',wps_primary_device_type='00070050F2040003'), 'Epson', 'Cañón', 'Epson PowerLite E20'),
    (dict(tech='wifi',mac='00:11:04:11:22:25',role='station'), 'Epson', 'Cañón', 'Cañón Epson'),
    (dict(tech='wifi',mac='00:11:05:11:22:16',role='station',name='BenQ MW560'), 'BenQ', 'Cañón', 'BenQ MW560'),
    (dict(tech='ble',mac='AA:BB:CC:11:22:17',name='Optoma HD28e'), 'Optoma', 'Cañón', 'Optoma HD28e'),
])
def test_six_target_classifications_and_device_detection(engine,kwargs,expected_brand,expected_class,expected_device_sub):
    r=engine.identify(Observation(event='observation',**kwargs))
    target={'Celular':'Celular y Tablet','Tablet':'Celular y Tablet'}.get(expected_class,expected_class)
    assert r['brand']==expected_brand
    assert r['category']==expected_class
    assert r['device_type']==expected_class
    assert r['classification']==target
    assert r['target_class']==target
    assert r['is_target_class'] is True
    assert expected_device_sub in r['detected_device']
    assert r['model']!='No identificable'


@pytest.mark.parametrize('fields,brand,model_part', [
    (dict(wps_manufacturer='samsung', wps_model_name='SM-A546E'), 'Samsung', 'Galaxy A54 5G'),
    (dict(wps_model_name='iPhone14,7', wps_manufacturer='Apple'), 'Apple', 'iPhone 14'),
    (dict(wps_model_name='XT2343-2'), 'Motorola', 'moto g54'),
    (dict(wps_model_name='2201117TG'), 'Redmi', 'Redmi Note 11'),
    (dict(vendor_ies='0000F022,506F9A09', wps_device_name='Galaxy A54', wps_primary_device_type='000A0050F2040005'), 'Samsung', 'Galaxy A54'),
])
def test_phone_model_codes_and_p2p(engine, fields, brand, model_part):
    r = engine.identify(Observation(event='observation', tech='wifi', mac='DA:11:22:33:44:55', role='station', **fields))
    assert r['classification'] == 'Celular y Tablet' and r['brand'] == brand and model_part in r['detected_device']


def test_apple_vendor_ie_with_random_mac(engine):
    r = engine.identify(Observation(event='observation', tech='wifi', mac='DA:11:22:33:44:55', role='station', vendor_ies='0017F20A,00101802'))
    assert r['brand'] == 'Apple' and r['classification'] == 'Celular y Tablet' and r['radio_vendor'] == 'Broadcom'


def test_unknown_numeric_code_is_not_xiaomi(engine):
    r = engine.identify(Observation(event='observation', tech='wifi', mac='DA:11:22:33:44:55', role='station', wps_model_name='2024123ABC'))
    assert r['brand'] != 'Xiaomi'


@pytest.mark.parametrize('fields,cls,model_part,certainty', [
    (dict(frame_type='red_local', name='MacBook-Pro-de-Luis (192.168.1.8)', wps_model_name='MacBookPro18,3', wps_manufacturer='Apple'), 'Laptop', 'MacBook Pro 14', 'Alta'),
    (dict(frame_type='red_local', name='iPad-de-Pam (192.168.1.9)', wps_model_name='iPad13,18', wps_manufacturer='Apple', wps_primary_device_type='00010050F2040005'), 'Tablet', 'iPad (10.ª gen.)', 'Alta'),
    (dict(wps_manufacturer='samsung', wps_model_name='SM-A566B'), 'Celular', 'Galaxy A56 5G', 'Alta'),
    (dict(), 'Celular', 'Celular', 'Baja'),
])
def test_laptops_tablets_and_plain_summary(engine, fields, cls, model_part, certainty):
    r = engine.identify(Observation(event='observation', tech='wifi', mac='DA:11:22:33:44:55', role='station', **fields))
    target={'Celular':'Celular y Tablet','Tablet':'Celular y Tablet'}.get(cls,cls)
    assert r['classification'] == target and model_part in r['detected_device'] and r['certainty'] == certainty and r['how_identified']
    assert '192.168' not in r['detected_device']


@pytest.mark.parametrize('kwargs,cls,sub', [
    (dict(tech='ble', mac='AA:BB:CC:11:33:01', company_id=76, manufacturer_data='0701'), 'Audífonos', 'Audífonos'),
    (dict(tech='ble', mac='AA:BB:CC:11:33:02', name='AirPods Pro'), 'Audífonos', 'Audífonos'),
    (dict(tech='classic', mac='AA:BB:CC:11:33:03', cod=0x240404), 'Audífonos', 'Audífonos'),
    (dict(tech='wifi', mac='AA:BB:CC:11:33:04', role='ap', ssid='Samsung Smart TV'), 'Smart TV', 'Smart TV'),
    (dict(tech='ble', mac='AA:BB:CC:11:33:05', name='BRAVIA 4K'), 'Smart TV', 'Smart TV'),
])
def test_new_target_tv_and_headphones(engine, kwargs, cls, sub):
    r = engine.identify(Observation(event='observation', **kwargs))
    assert r['classification'] == cls and r['is_target_class'] is True


def test_phone_and_tablet_share_one_target(engine):
    phone = engine.identify(Observation(event='observation', tech='ble', mac='AA:BB:CC:11:44:01', name='Galaxy S24'))
    tablet = engine.identify(Observation(event='observation', tech='ble', mac='AA:BB:CC:11:44:02', name='iPad Air'))
    assert phone['classification'] == tablet['classification'] == 'Celular y Tablet'
    assert phone['category'] == 'Celular' and tablet['category'] == 'Tablet'  # subtipo granular conservado


def test_hp_oui_access_point_is_not_printer(engine):
    for ssid in ('RCUcito 2100', 'RCU - ALUMNOS', 'RCU-WIFI'):
        r = engine.identify(Observation(event='observation', tech='wifi', mac='3C:52:82:11:22:10', role='ap', ssid=ssid))
        assert r['classification'] != 'Impresora', f'{ssid} no debe ser impresora'
    # una impresora real sí se detecta
    r = engine.identify(Observation(event='observation', tech='wifi', mac='3C:52:82:11:22:10', role='ap', ssid='DIRECT-42-HP LaserJet M404'))
    assert r['classification'] == 'Impresora'
