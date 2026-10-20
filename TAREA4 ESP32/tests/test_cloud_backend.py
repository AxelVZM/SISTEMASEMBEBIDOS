"""Pruebas aisladas: no conectan con AWS ni requieren boto3 instalado."""
import copy, importlib.util, json, os, sys, types, unittest
from pathlib import Path
os.environ['SAL_ALIAS']='test-only-salt-with-more-than-thirty-two-characters'
class Tabla:
    def __init__(self): self.items={}
    def put_item(self,Item): self.items[Item['id_registro']]=copy.deepcopy(Item)
    def scan(self,**kwargs): return {'Items':list(self.items.values())}
tabla=Tabla()
boto=types.ModuleType('boto3');boto.resource=lambda *a:types.SimpleNamespace(Table=lambda n:tabla)
class Attr:
    def __init__(self,*a):pass
    def gte(self,*a):return self
    def exists(self):return self
    def __and__(self,other):return self
sys.modules['boto3']=boto
sys.modules['boto3.dynamodb']=types.ModuleType('boto3.dynamodb')
conditions=types.ModuleType('boto3.dynamodb.conditions');conditions.Attr=Attr
sys.modules['boto3.dynamodb.conditions']=conditions
spec=importlib.util.spec_from_file_location('backend',Path(__file__).resolve().parents[1]/'Nube/backend/lambda_function.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Pruebas(unittest.TestCase):
    def setUp(self):
        tabla.items.clear();m._tabla_oui={'AABBCC':'Titular grande','AABBCCD':'Titular mediano','AABBCCDDE':'Titular pequeño'}
        self.d={'sensor':'10:20:30:40:50:60','ciclo_id':'boot-1','total_detectado':2,'routers':1,
          'equipos_detectados':[{'mac':'8E:E5:9B:2A:CF:4E','rssi':-40,'canal':1,'tipo':'Cliente (Celular)','modelo_wps':'Modelo publicado','fabricante_wps':'Marca publicada'},
          {'mac':'A8:BB:CC:DD:EE:FF','rssi':-50,'canal':6}],
          'routers_detectados':[{'mac':'7A:3B:8F:12:0D:E1','rssi':-60,'canal':11,'ssid':'SSID de prueba','modelo_wps':'Modelo AP'}]}
    def post(self,d):return m.lambda_handler({'httpMethod':'POST','body':json.dumps(d)},None)
    def test_local_no_fabricante_ieee(self):
        self.assertIsNone(m.fabricante_de('AA:BB:CC:DD:EE:FF'))
        self.assertEqual(m.tipo_simple('8E:E5:9B:2A:CF:4E'),'local')
        self.assertEqual(m.tipo_simple('A8:BB:CC:DD:EE:FF'),'universal')
    def test_prefijo_mas_largo(self):
        m._tabla_oui={'A8BBCC':'L','A8BBCCD':'M','A8BBCCDDE':'S'}
        self.assertEqual(m.fabricante_de('a8-bb-cc-dd-ee-ff'),'S')
        del m._tabla_oui['A8BBCCDDE'];self.assertEqual(m.fabricante_de('A8:BB:CC:DD:EE:FF'),'M')
    def test_reintento_idempotente(self):
        self.assertEqual(self.post(self.d)['statusCode'],200);self.post(self.d)
        self.assertEqual(len(tabla.items),1)
    def test_post_get_y_wps_local(self):
        self.post(self.d)
        for vista in ['resumen','equipos','equipo','routers']:
            r=m.lambda_handler({'httpMethod':'GET','queryStringParameters':{'vista':vista}},None)
            self.assertEqual(r['statusCode'],200);json.loads(r['body'])
        equipo=m.vista_equipos('')['equipos'][0]
        self.assertEqual(equipo['modelo_wps'],'Modelo publicado')
        self.assertFalse(equipo['tipo_confirmado'])
        ap=m.vista_routers('')['routers'][0]
        self.assertFalse(ap['hotspot']);self.assertEqual(ap['modelo_wps'],'Modelo AP')
    def test_rechaza_invalidos(self):
        for cambio in [{'sensor':'mal'},{'total_detectado':-1},{'equipos_detectados':{}},{'total_detectado':1}]:
            d=copy.deepcopy(self.d);d.update(cambio);self.assertEqual(self.post(d)['statusCode'],400)
        d=copy.deepcopy(self.d);d['equipos_detectados'][0]['rssi']=-200
        self.assertEqual(self.post(d)['statusCode'],400)
    def test_mac_y_metodos(self):
        for mac in ['00:00:00:00:00:00','FF:FF:FF:FF:FF:FF','mal']:
            with self.assertRaises(ValueError):m.normalizar_mac(mac)
        self.assertEqual(m.lambda_handler({'httpMethod':'OPTIONS'},None)['statusCode'],200)
        self.assertEqual(m.lambda_handler({'httpMethod':'DELETE'},None)['statusCode'],405)
    def test_alias_canonico_y_sin_mac(self):
        self.assertEqual(m.alias_de('a8-bb-cc-dd-ee-ff'),m.alias_de('A8:BB:CC:DD:EE:FF'))
        self.post(self.d)
        salida=json.dumps(m.vista_equipos(''))
        self.assertNotIn('8E:E5:9B',salida)
    def test_ble_local_y_conteos_separados(self):
        self.d['ble_total']=1
        self.d['ble_detectados']=[{'mac':'C3:00:00:00:00:01','nombre':'BLE prueba','rssi':-60,'tipo_direccion':1,'company_id':76}]
        self.assertEqual(self.post(self.d)['statusCode'],200)
        guardado=next(iter(tabla.items.values()))
        self.assertEqual(guardado['ble_total'],1)
        self.assertEqual(guardado['total_detectado'],2)
        self.assertEqual(len(guardado['detalle_ble']),1)
        self.d['ble_total']=0
        self.assertEqual(self.post(self.d)['statusCode'],400)
    def test_payload_generado_por_v71(self):
        archivo=Path(__file__).with_name('payload_cloud.json')
        d=json.loads(archivo.read_text())
        self.assertEqual(self.post(d)['statusCode'],200)
        guardado=next(iter(tabla.items.values()))
        self.assertEqual(guardado['total_detectado'],50)
        self.assertEqual(len(guardado['detalle_equipos']),24)
    def test_clasificacion_visible(self):
        self.d['equipos_detectados'][0].update(deviceType='phone',deviceLabel='Telefono / celular',classLevel='hint',classEvidence='Nombre anunciado')
        self.assertEqual(self.post(self.d)['statusCode'],200)
        eq=m.vista_equipos('')['equipos'][0]
        self.assertEqual(eq['deviceType'],'phone')
        self.assertEqual(eq['classLevel'],'hint')
    def test_utf8_y_escapado(self):
        self.d['equipos_detectados'][0]['modelo_wps']='Modelo "á" \\ Z'
        self.post(self.d)
        self.assertEqual(m.vista_equipos('')['equipos'][0]['modelo_wps'],'Modelo "á" \\ Z')
if __name__=='__main__':unittest.main()
