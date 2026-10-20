import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from servidor.app import create_app
spec=importlib.util.spec_from_file_location('bridge',ROOT/'herramientas/puente_usb.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
TOKEN='test-ec2-key-not-a-real-token-'+('a'*32)

def status(ms=1000,boot=1):
    return dict(kind='status',firmware='7.2',b=boot,ms=ms,ttl=60000,wifi=1,ble=1,aps=0,clients=1,wifiKnown=1,bleKnown=1,wifiCapacity=False,bleCapacity=False,wifiOmitted=0,bleOmitted=0,rxOmitted=0,bleRxOmitted=0,radio='Wi-Fi',channel=6,wifiReady=True,bleReady=True,wifiError='',bleError='',storage=True,storageError='',logBytes=100,heap=100000,minHeap=90000,oled=False,rtc=False,clock=True,epoch=1792510000,watchdog=True,resetReason=1,netPaused=False)

def wifi():
    return dict(kind='wifi',b=1,slot=0,mac='8E:E5:9B:2A:CF:4E',local=True,role='Cliente',ssid='',name='MacBook de prueba',nameSource='WPS',vendor='No inferible: MAC local',manufacturer='',model='',number='',rssi=-45,channel=6,frames=8,last=900,deviceType='laptop',deviceLabel='Laptop',classLevel='hint',classEvidence='Nombre anunciado')

def ble():
    return dict(kind='ble',b=1,slot=0,mac='C3:00:00:00:00:01',addressType=1,name='Proyector',companyId=None,company='No anunciado',companyConflict=False,appearance=0x0a03,disAdvertised=False,rssi=-60,frames=1,last=900,deviceType='projector',deviceLabel='Cañón / proyector',classLevel='declared',classEvidence='Appearance BLE anunciado')

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=1000
        self.config={'TESTING':True,'API_TOKEN':TOKEN,'DB_PATH':str(Path(self.temp.name)/'db.sqlite3'),'NOW':lambda:self.now}
        self.app=create_app(self.config);self.client=self.app.test_client();self.auth={'Authorization':'Bearer '+TOKEN}
    def tearDown(self):self.temp.cleanup()
    def post(self,packets=None,source='test-source'):
        return self.client.post('/api/ingest',json={'sensor_id':'esp32-principal','source_id':source,'packets':packets or [status(),wifi(),ble()]},headers=self.auth)
    def live(self):return self.client.get('/api/live',headers=self.auth).get_json()
    def test_auth_and_static(self):
        self.assertEqual(self.client.get('/api/live').status_code,401)
        with self.client.get('/') as r:self.assertEqual(r.status_code,200)
        with self.client.get('/ec2.js') as r:self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/.env').status_code,404)
        self.assertEqual(self.client.get('/api/health').status_code,200)
    def test_firmware_flow_and_types(self):
        self.assertEqual(self.post().status_code,200)
        d=self.live();self.assertTrue(d['online']);self.assertEqual(len(d['packets']),3)
        self.assertEqual(d['packets'][0]['wifi'],1)
        self.assertEqual(next(p for p in d['packets'] if p['kind']=='ble')['deviceType'],'projector')
    def test_missing_sensor_is_offline(self):self.assertFalse(self.live()['online'])
    def test_stale_status_not_refreshed_by_duplicates(self):
        self.post();self.now+=6;self.post();self.assertFalse(self.live()['online'])
        self.post([status(7000)]);self.assertTrue(self.live()['online'])
    def test_boot_clears_old_rows(self):
        self.post();self.post([status(100,2)]);d=self.live();self.assertEqual(len(d['packets']),1);self.assertEqual(d['packets'][0]['b'],2)
    def test_no_mixed_boots(self):self.assertEqual(self.post([status(),dict(wifi(),b=2)]).status_code,400)
    def test_sensor_lease(self):
        self.post();self.assertEqual(self.post(source='another-source').status_code,409)
        self.now+=9;self.assertEqual(self.post([status(10000)],source='another-source').status_code,200)
    def test_rejects_bad_types(self):
        for p in [dict(status(),wifi=True),dict(wifi(),slot=96),dict(wifi(),deviceType='inventado'),dict(status(),kind='network',password='private-value')]:
            self.assertEqual(self.post([p]).status_code,400)
    def test_unknown_fields_not_stored(self):
        self.post([dict(status(),password='private-value')]);self.assertNotIn('private-value',json.dumps(self.live()))
    def test_out_of_order_status_and_history(self):
        self.post();self.now+=6;self.post([status(7000)]);self.post([status(2000)])
        self.assertEqual(self.live()['packets'][0]['ms'],7000)
        rows=self.client.get('/api/history',headers=self.auth).get_json()['points'];self.assertEqual(len(rows),2)
    def test_persistence(self):
        self.post();other=create_app(self.config).test_client();self.assertTrue(other.get('/api/live',headers=self.auth).get_json()['online'])
    def test_payload_limit(self):
        r=self.client.post('/api/ingest',data='x'*(257*1024),headers={**self.auth,'Content-Type':'application/json'});self.assertEqual(r.status_code,413)
    def test_retention(self):
        self.post();self.now+=8*86400;self.post([status(9999)])
        points=self.client.get('/api/history?hours=24',headers=self.auth).get_json()['points'];self.assertEqual(len(points),1)

class BridgeTests(unittest.TestCase):
    def test_bounded_buffer_and_ack(self):
        b=bridge.PacketBuffer();b.add(status())
        for i in range(1000):b.add(dict(wifi(),slot=i%96))
        self.assertLessEqual(len(b.snapshot()),97)
        old=b.snapshot();b.add(dict(wifi(),last=1001));b.ack(old)
        self.assertEqual(len(b.snapshot()),1)
        b.clear();self.assertEqual(b.snapshot(),[])
    def test_boot_and_no_credentials(self):
        b=bridge.PacketBuffer();self.assertFalse(b.add({'kind':'network','password':'value'}))
        b.add(status());b.add(wifi());b.add(status(1,2));self.assertEqual(len(b.snapshot()),1)
    def test_server_url(self):
        self.assertEqual(bridge.server_origin('https://example.org/esp32/'),'https://example.org/esp32')
        self.assertEqual(bridge.server_origin('http://localhost:8010'),'http://localhost:8010')
        with self.assertRaises(ValueError):bridge.server_origin('http://example.org')
        with self.assertRaises(ValueError):bridge.server_origin('https://user:pass@example.org')

if __name__=='__main__':unittest.main()
