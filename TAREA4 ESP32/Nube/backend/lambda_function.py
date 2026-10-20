import base64
import gzip
import hashlib
import hmac
import json
import os
import time
import uuid
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

# Conectar con la base de datos DynamoDB
dynamodb = boto3.resource('dynamodb')
tabla = dynamodb.Table(os.environ.get('TABLA_DYNAMODB', 'RegistroESP32'))

# Lambda corre en UTC; Perú es UTC-5 todo el año (no usa horario de verano)
ZONA_PE = timezone(timedelta(hours=-5))
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
MAX_EQUIPOS = 100        # Igual que MAX_ENVIO en el ESP32
MAX_ROUTERS = 60         # Igual que MAX_ENVIO_ROUTERS en el ESP32
DIAS_RETENCION = 7       # Con TTL activado sobre el atributo "expira", DynamoDB borra lo más antiguo
MAX_HORAS_RESUMEN = 168  # 7 días
MAX_HORAS_EQUIPOS = 24   # Las vistas por equipo leen el detalle completo: se limitan a 1 día

# Los clientes se presentan con alias; los BSSID de AP sí se exponen al panel.
# Define la variable de entorno SAL_ALIAS en la Lambda con un texto aleatorio largo.
SAL_ALIAS = os.environ.get('SAL_ALIAS', '').encode()

# Tabla de titulares IEEE (prefijos de 24, 28 o 36 bits), generada a partir del registro público de la IEEE.
# Debe subirse junto a este archivo; si falta, el fabricante sale como "Desconocido".
ARCHIVO_OUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oui.txt.gz')
_tabla_oui = None

# Permite que el index.html (abierto desde otro dominio o desde archivo) lea la API
CABECERAS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': os.environ.get('ORIGEN_PANEL', '*'),
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}


def a_numero(valor):
    # DynamoDB devuelve los números como Decimal, que json.dumps no sabe serializar
    if isinstance(valor, Decimal):
        return int(valor) if valor % 1 == 0 else float(valor)
    raise TypeError(f"Tipo no serializable: {type(valor)}")


def respuesta(codigo, cuerpo):
    return {
        'statusCode': codigo,
        'headers': CABECERAS,
        'body': json.dumps(cuerpo, default=a_numero, ensure_ascii=False),
    }


def metodo_http(event):
    # REST API (payload v1) usa httpMethod; HTTP API (payload v2) lo pone en requestContext
    return (event.get('httpMethod')
            or event.get('requestContext', {}).get('http', {}).get('method')
            or 'POST')  # Prueba desde la consola de Lambda


def lambda_handler(event, context):
    metodo = metodo_http(event)
    try:
        if metodo == 'OPTIONS':
            return respuesta(200, {})
        if metodo == 'GET':
            return consultar(event.get('queryStringParameters') or {})
        if metodo == 'POST':
            return guardar(event)
        return respuesta(405, {'error': 'Método no permitido'})
    except (ValueError, KeyError) as e:
        print("Petición inválida:", repr(e))
        return respuesta(400, {'error': 'Datos inválidos'})
    except Exception as e:
        print("Error interno:", repr(e))
        return respuesta(500, {'error': 'Error interno'})


# ---------- POST: lo llama el ESP32 cada ciclo ----------
def guardar(event):
    if 'body' in event:
        cuerpo = event['body'] or '{}'
        if event.get('isBase64Encoded'):
            cuerpo = base64.b64decode(cuerpo).decode('utf-8')
        if not isinstance(cuerpo,str) or len(cuerpo.encode('utf-8'))>128*1024:
            raise ValueError('Cuerpo inválido o demasiado grande')
        # parse_float=Decimal: DynamoDB rechaza los float de Python
        datos = json.loads(cuerpo, parse_float=Decimal)
    else:
        datos = event

    datos = validar_captura(datos)

    # Acepta el nombre nuevo y el anterior que usa el firmware
    total = int(datos.get('total_detectado', datos.get('total_dispositivos', 0)))
    routers = int(datos.get('routers', 0))
    equipos = datos.get('equipos_detectados', [])
    if not isinstance(equipos, list):
        equipos = []
    lista_routers = datos.get('routers_detectados', [])
    if not isinstance(lista_routers, list):
        lista_routers = []

    item = {
        'id_registro': str(uuid.uuid5(uuid.NAMESPACE_URL, datos['sensor'] + ':' + datos['ciclo_id'])) if datos.get('ciclo_id') else str(uuid.uuid4()),
        'fecha_hora': datetime.now(ZONA_PE).strftime(FORMATO_FECHA),
        'sensor': str(datos.get('sensor', '')),
        'total_detectado': total,
        'routers': routers,
        'detalle_equipos': equipos[:MAX_EQUIPOS],
        'detalle_routers': lista_routers[:MAX_ROUTERS],
        'duracion_s': datos.get('duracion_s', 0),
        'ble_total': datos.get('ble_total', 0),
        'detalle_ble': datos.get('ble_detectados', []),
        'clientes_enviados': len(equipos[:MAX_EQUIPOS]),
        'routers_enviados': len(lista_routers[:MAX_ROUTERS]),
        'expira': int(time.time()) + DIAS_RETENCION * 86400,
    }
    tabla.put_item(Item=item)

    print(f"Éxito: Registro {item['id_registro']} guardado con {total} equipos.")
    return respuesta(200, {'ok': True, 'id_registro': item['id_registro']})


# ---------- GET: lo llama el index.html ----------
#   ?vista=resumen&horas=N   -> conteos por ciclo + equipos del último ciclo
#   ?vista=equipos&horas=N   -> un resumen por cada equipo visto en el periodo
#   ?vista=equipo&id=X&horas=N -> historial ciclo a ciclo de un equipo
#   ?vista=routers&horas=N   -> un resumen por cada router / punto de acceso
def consultar(parametros):
    vista = parametros.get('vista', 'resumen')
    if vista == 'equipos':
        return respuesta(200, vista_equipos(desde_hace(leer_horas(parametros, MAX_HORAS_EQUIPOS))))
    if vista == 'routers':
        return respuesta(200, vista_routers(desde_hace(leer_horas(parametros, MAX_HORAS_EQUIPOS))))
    if vista == 'equipo':
        id_equipo = str(parametros.get('id', ''))
        return respuesta(200, vista_equipo(desde_hace(leer_horas(parametros, MAX_HORAS_EQUIPOS)), id_equipo))
    return respuesta(200, vista_resumen(desde_hace(leer_horas(parametros, MAX_HORAS_RESUMEN))))


def leer_horas(parametros, maximo):
    try:
        horas = int(parametros.get('horas', 24))
    except (TypeError, ValueError):
        horas = 24
    return min(max(horas, 1), maximo)


def desde_hace(horas):
    return (datetime.now(ZONA_PE) - timedelta(hours=horas)).strftime(FORMATO_FECHA)


def escanear(desde, proyeccion):
    opciones = {
        # Los registros sin "routers" los guardó la primera Lambda: hora en UTC (5 h adelantada)
        # y filas vacías creadas por las consultas GET del dashboard. Se ignoran.
        'FilterExpression': Attr('fecha_hora').gte(desde) & Attr('routers').exists(),
        'ProjectionExpression': proyeccion,
    }
    items = []
    while True:
        pagina = tabla.scan(**opciones)
        items.extend(pagina['Items'])
        if 'LastEvaluatedKey' not in pagina:
            break
        opciones['ExclusiveStartKey'] = pagina['LastEvaluatedKey']
    # El formato "YYYY-MM-DD HH:MM:SS" se ordena bien como texto
    items.sort(key=lambda r: r['fecha_hora'])
    return items


def alias_de(mac):
    if len(SAL_ALIAS)<32:
        raise RuntimeError('Configurar SAL_ALIAS con al menos 32 caracteres')
    firma = hmac.new(SAL_ALIAS, normalizar_mac(mac).encode(), hashlib.sha256).hexdigest()
    return 'EQ-' + firma[:12].upper()


def tabla_oui():
    global _tabla_oui
    if _tabla_oui is None:
        _tabla_oui = {}
        try:
            with gzip.open(ARCHIVO_OUI, 'rt', encoding='utf-8') as archivo:
                for linea in archivo:
                    prefijo, _, nombre = linea.rstrip('\n').partition('\t')
                    _tabla_oui[prefijo] = nombre
        except OSError as e:
            print("Aviso: no se pudo leer la tabla OUI:", repr(e))
    return _tabla_oui


def normalizar_mac(mac):
    limpio = str(mac).replace(':','').replace('-','').upper()
    if not re.fullmatch(r'[0-9A-F]{12}',limpio):
        raise ValueError('MAC inválida')
    if int(limpio[:2],16)&1 or limpio=='000000000000':
        raise ValueError('MAC de origen inválida')
    return ':'.join(limpio[i:i+2] for i in range(0,12,2))


def mac_aleatoria(mac):
    # Localmente administrada no significa necesariamente aleatoria ni celular.
    return bool(int(normalizar_mac(mac)[:2],16)&2)


def fabricante_de(mac):
    """Titular del bloque IEEE, no necesariamente marca comercial ni chip."""
    if mac_aleatoria(mac):
        return None
    limpio=normalizar_mac(mac).replace(':','')
    registro=tabla_oui()
    for longitud in (9,7,6):
        nombre=registro.get(limpio[:longitud])
        if nombre:
            return 'Desconocido' if nombre=='Private' else nombre
    return 'Desconocido'


def validar_captura(datos):
    if not isinstance(datos,dict): raise ValueError('Objeto requerido')
    datos=dict(datos)
    datos['sensor']=normalizar_mac(datos.get('sensor',''))
    if 'total_detectado' not in datos and 'total_dispositivos' in datos:
        datos['total_detectado']=datos['total_dispositivos']
    for clave,limite in (('equipos_detectados',MAX_EQUIPOS),('routers_detectados',MAX_ROUTERS)):
        filas=datos.get(clave,[])
        if not isinstance(filas,list) or len(filas)>limite: raise ValueError('Demasiadas filas')
        limpias=[]; vistas=set()
        for original in filas:
            if not isinstance(original,dict): raise ValueError('Fila inválida')
            fila={}; fila['mac']=normalizar_mac(original.get('mac',''))
            if fila['mac'] in vistas: raise ValueError('MAC duplicada en captura')
            vistas.add(fila['mac'])
            for campo in ('rssi','rssi_ultimo','canal','paquetes','visible_s','wifi','beacons'):
                if campo not in original: continue
                numero=original[campo]
                if isinstance(numero,bool) or not isinstance(numero,(int,Decimal)) or int(numero)!=numero:
                    raise ValueError('Número inválido')
                numero=int(numero)
                inferior,superior=(-127,0) if campo.startswith('rssi') else ((1,14) if campo=='canal' else (0,2**32-1))
                if not inferior<=numero<=superior: raise ValueError('Valor fuera de rango')
                fila[campo]=numero
            for campo in ('tipo','ssid','seguridad','fabricante_wps','modelo_wps','nombre_anunciado','deviceType','deviceLabel','classLevel','classEvidence'):
                v=original.get(campo,'')
                if not isinstance(v,str): raise ValueError('Texto requerido')
                fila[campo]=''.join(c for c in v if ord(c)>=32)[:96]
            limpias.append(fila)
        datos[clave]=limpias
    for clave,defecto,maximo in (('total_detectado',len(datos['equipos_detectados']),200),('routers',len(datos['routers_detectados']),100),('duracion_s',30,3600)):
        valor=datos.get(clave,defecto)
        if isinstance(valor,bool) or not isinstance(valor,(int,Decimal)) or int(valor)!=valor or not 0<=valor<=maximo: raise ValueError('Conteo inválido')
        datos[clave]=int(valor)
    if datos['total_detectado']<len(datos['equipos_detectados']) or datos['routers']<len(datos['routers_detectados']): raise ValueError('Conteo menor que detalle')
    ciclo=datos.get('ciclo_id','')
    if not isinstance(ciclo,str) or len(ciclo)>96: raise ValueError('Ciclo inválido')
    ble=datos.get('ble_detectados',[])
    if not isinstance(ble,list) or len(ble)>16:raise ValueError('Detalle BLE inválido')
    limpios=[]
    for fila in ble:
        if not isinstance(fila,dict):raise ValueError('Fila BLE inválida')
        mac=str(fila.get('mac','')).upper()
        if not re.fullmatch(r'([0-9A-F]{2}:){5}[0-9A-F]{2}',mac):raise ValueError('MAC BLE inválida')
        nombre=fila.get('nombre','');rssi=fila.get('rssi',-127);tipo=fila.get('tipo_direccion',0);company=fila.get('company_id')
        if not isinstance(nombre,str) or len(nombre)>64 or not isinstance(rssi,int) or isinstance(rssi,bool) or not -127<=rssi<=0 or not isinstance(tipo,int) or isinstance(tipo,bool) or not 0<=tipo<=3 or (company is not None and (not isinstance(company,int) or isinstance(company,bool) or not 0<=company<=65535)):raise ValueError('Campos BLE inválidos')
        limpio={'mac':mac,'nombre':nombre,'rssi':rssi,'tipo_direccion':tipo,'company_id':company}
        for clave in ('deviceType','deviceLabel','classLevel','classEvidence'):
            valor=fila.get(clave,'')
            if not isinstance(valor,str) or len(valor)>160:raise ValueError('Clasificación BLE inválida')
            limpio[clave]=valor
        limpios.append(limpio)
    total_ble=datos.get('ble_total',0)
    if not isinstance(total_ble,int) or isinstance(total_ble,bool) or not len(limpios)<=total_ble<=32:raise ValueError('Conteo BLE inválido')
    datos['ble_detectados']=limpios;datos['ble_total']=total_ble
    return datos


def entero(valor, defecto=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def tipo_simple(mac):
    return 'local' if mac_aleatoria(mac) else 'universal'


def clientes(item):
    # Los registros del firmware antiguo incluían routers en la lista: se ignoran
    for e in item.get('detalle_equipos') or []:
        mac = str(e.get('mac', ''))
        tipo = str(e.get('tipo', ''))
        if mac and 'Router' not in tipo:
            try: mac=normalizar_mac(mac)
            except ValueError: continue
            yield mac, e


def vista_resumen(desde):
    items = escanear(desde, 'id_registro, fecha_hora, total_detectado, routers, detalle_equipos')

    registros = []
    for it in items:
        celulares = fijos = 0
        for mac, e in clientes(it):
            if tipo_simple(mac) == 'local':
                celulares += 1
            else:
                fijos += 1
        total = entero(it.get('total_detectado'))
        routers = entero(it.get('routers'))
        # El firmware antiguo sumaba los routers al total y los listaba como "Router ...":
        # se recalcula con la lista (completa mientras no pasara de 50 equipos)
        routers_en_lista = sum(1 for e in it.get('detalle_equipos') or [] if 'Router' in str(e.get('tipo', '')))
        if routers_en_lista:
            total = celulares + fijos
            routers = routers_en_lista
        registros.append({
            'id_registro': it.get('id_registro'),
            'fecha_hora': it['fecha_hora'],
            'total_detectado': total,
            'routers': routers,
            'celulares': celulares,
            'fijos': fijos,
        })

    ultimo_ciclo = []
    if items:
        ultimo_ciclo = [{
            'id': alias_de(mac),
            'tipo': tipo_simple(mac),
            'rssi': entero(e.get('rssi'), -100),
        } for mac, e in clientes(items[-1])]

    return {'registros': registros, 'ultimo_ciclo': ultimo_ciclo}


def vista_equipos(desde):
    items = escanear(desde, 'fecha_hora, detalle_equipos')

    equipos = {}
    for it in items:
        fecha = it['fecha_hora']
        for mac, e in clientes(it):
            alias = alias_de(mac)
            rssi = entero(e.get('rssi'), -100)
            d = equipos.get(alias)
            if d is None:
                d = equipos[alias] = {
                    'id': alias,
                    'tipo': tipo_simple(mac),
                    'fabricante': fabricante_de(mac),
                    'fabricante_wps': '', 'modelo_wps': '', 'nombre_anunciado': '',
                    'estado_identificacion': 'sin_identificacion',
                    'tipo_confirmado': False,
                    'deviceType':'unknown','deviceLabel':'Sin determinar','classLevel':'unknown','classEvidence':'',
                    'primera_vez': fecha,
                    'ciclos': 0,
                    'rssi_max': rssi,
                    'paquetes': 0,
                    '_suma_rssi': 0,
                }
            d['ciclos'] += 1
            d['_suma_rssi'] += rssi
            d['rssi_max'] = max(d['rssi_max'], rssi)
            d['rssi_ultimo'] = rssi
            d['ultima_vez'] = fecha
            d['canal'] = entero(e.get('canal'))
            d['paquetes'] += entero(e.get('paquetes'), 1)
            for campo in ('fabricante_wps','modelo_wps','nombre_anunciado','deviceType','deviceLabel','classLevel','classEvidence'):
                if e.get(campo): d[campo]=texto(e[campo])
            if d['modelo_wps']: d['estado_identificacion']='anunciada_no_autenticada'
            elif d['fabricante_wps']: d['estado_identificacion']='fabricante_anunciado_no_autenticado'
            elif d['fabricante'] not in (None,'Desconocido'): d['estado_identificacion']='solo_titular_ieee'

    ultimo = items[-1]['fecha_hora'] if items else None
    lista = []
    for d in equipos.values():
        d['rssi_prom'] = round(d.pop('_suma_rssi') / d['ciclos'], 1)
        d['presente'] = d['ultima_vez'] == ultimo
        lista.append(d)
    lista.sort(key=lambda d: (d['ultima_vez'], d['ciclos']), reverse=True)

    return {
        'ciclos_totales': len(items),
        'primer_ciclo': items[0]['fecha_hora'] if items else None,
        'ultimo_ciclo': ultimo,
        'equipos': lista,
    }


def vista_equipo(desde, id_equipo):
    items = escanear(desde, 'fecha_hora, detalle_equipos')

    # Un punto por ciclo; rssi = None cuando el equipo no se detectó (huecos en la gráfica)
    historial = []
    for it in items:
        punto = {'fecha_hora': it['fecha_hora'], 'rssi': None}
        for mac, e in clientes(it):
            if alias_de(mac) == id_equipo:
                punto.update(
                    rssi=entero(e.get('rssi'), -100),
                    rssi_ultimo=entero(e.get('rssi_ultimo'), entero(e.get('rssi'), -100)),
                    paquetes=entero(e.get('paquetes'), 1),
                    canal=entero(e.get('canal')),
                )
                break
        historial.append(punto)

    return {'id': id_equipo, 'historial': historial}


def texto(valor):
    return str(valor or '').strip()


def vista_routers(desde):
    # Solo ciclos del firmware que envía routers: así "presente" se compara con el último de ellos
    items = [it for it in escanear(desde, 'fecha_hora, detalle_routers') if 'detalle_routers' in it]

    routers = {}
    for it in items:
        fecha = it['fecha_hora']
        for r in it.get('detalle_routers') or []:
            mac = texto(r.get('mac')).upper()
            try: mac=normalizar_mac(mac)
            except ValueError: continue
            rssi = entero(r.get('rssi'), -100)
            d = routers.get(mac)
            if d is None:
                d = routers[mac] = {
                    'mac': mac,
                    'fabricante': fabricante_de(mac),
                    'fabricante_wps': '', 'modelo_wps': '', 'nombre_anunciado': '',
                    'estado_identificacion': 'sin_identificacion',
                    'tipo_confirmado': False,
                    'deviceType':'unknown','deviceLabel':'Sin determinar','classLevel':'unknown','classEvidence':'',
                    'primera_vez': fecha,
                    'ciclos': 0,
                    'rssi_max': rssi,
                    '_suma_rssi': 0,
                    'ssid': '',
                    'fabricante_wps': '',
                    'modelo_wps': '',
                }
            d['ciclos'] += 1
            d['_suma_rssi'] += rssi
            d['rssi_max'] = max(d['rssi_max'], rssi)
            d['rssi_ultimo'] = rssi
            d['ultima_vez'] = fecha
            d['canal'] = entero(r.get('canal'))
            d['seguridad'] = texto(r.get('seguridad')) or 'Desconocida'
            d['wifi'] = entero(r.get('wifi'))
            # Se conservan los últimos textos no vacíos
            for campo in ('ssid', 'fabricante_wps', 'modelo_wps','deviceType','deviceLabel','classLevel','classEvidence'):
                if texto(r.get(campo)):
                    d[campo] = texto(r.get(campo))

    ultimo = items[-1]['fecha_hora'] if items else None
    lista = []
    for d in routers.values():
        d['rssi_prom'] = round(d.pop('_suma_rssi') / d['ciclos'], 1)
        d['presente'] = d['ultima_vez'] == ultimo
        d['oculta'] = not d['ssid']
        d['hotspot'] = False  # No se infiere hotspot por MAC local o SSID único.
        d['mac_local'] = mac_aleatoria(d['mac'])
        d['estado_identificacion'] = 'anunciada_no_autenticada' if d['modelo_wps'] else 'sin_modelo'
        if d['hotspot']:
            d['mac'] = alias_de(d['mac'])
            d['ssid'] = ''
            d['fabricante_wps'] = d['modelo_wps'] = ''
        lista.append(d)
    lista.sort(key=lambda d: (d['presente'], d['rssi_ultimo']), reverse=True)

    return {
        'ciclos_totales': len(items),
        'ultimo_ciclo': ultimo,
        'routers': lista,
    }
