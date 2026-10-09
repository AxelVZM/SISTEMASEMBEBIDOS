#!/usr/bin/env python3
"""Actualiza Movimiento GPS (TAREA3) en el servidor AWS en un solo paso.

Uso (como usuario ubuntu, SIN sudo, después de `git pull`):

    python3 ~/SISTEMASEMBEBIDOS/TAREA3/backend/actualizar_servidor.py

Qué hace:
  1. Respalda la carpeta data/ del backend.
  2. Instala dependencias (npm install --omit=dev).
  3. Busca la configuración de Nginx que contiene /movimiento, la respalda y
     reemplaza SOLO los bloques `location /movimiento...` por los de
     nginx-movimiento.conf. Los bloques de TAREA2 no se tocan.
  4. Comprueba la configuración (nginx -t). Si falla, restaura el respaldo.
  5. Recarga Nginx y reinicia SOLO el proceso PM2 movimiento-api.
  6. Verifica API, Nginx y WebSocket.
"""

import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request

BACKEND = os.path.dirname(os.path.abspath(__file__))
BLOQUES = os.path.join(BACKEND, 'nginx-movimiento.conf')
PROCESO_PM2 = 'movimiento-api'
RESPALDOS_NGINX = '/etc/nginx/respaldos-movimiento'
FECHA = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

PATRON_LOCATION = re.compile(r'^[ \t]*location\s+(?:[=~^*]+\s*)?/movimiento[^{]*\{', re.MULTILINE)


def paso(texto):
    print(f'\n==> {texto}')


def ok(texto):
    print(f'    [OK] {texto}')


def fallo(texto):
    print(f'    [ERROR] {texto}')
    sys.exit(1)


def ejecutar(comando, cwd=None, permitir_error=False):
    resultado = subprocess.run(comando, cwd=cwd, text=True, capture_output=True)
    if resultado.returncode != 0 and not permitir_error:
        print(resultado.stdout)
        print(resultado.stderr)
        fallo(f'Falló: {" ".join(comando)}')
    return resultado


def fin_de_bloque(texto, inicio_llave):
    """Devuelve la posición justo después de la llave que cierra el bloque."""
    profundidad = 0
    for i in range(inicio_llave, len(texto)):
        if texto[i] == '{':
            profundidad += 1
        elif texto[i] == '}':
            profundidad -= 1
            if profundidad == 0:
                fin = i + 1
                # Incluir el salto de línea final.
                if fin < len(texto) and texto[fin] == '\n':
                    fin += 1
                return fin
    raise ValueError('Llaves desbalanceadas en la configuración de Nginx')


def reemplazar_bloques(config, nuevos):
    coincidencias = list(PATRON_LOCATION.finditer(config))
    if not coincidencias:
        return None
    sangria = re.match(r'[ \t]*', coincidencias[0].group(0)).group(0)
    nuevos_con_sangria = ''.join(
        (sangria + linea if linea.strip() else linea) for linea in nuevos.splitlines(True)
    )
    resultado = []
    ultimo = 0
    insertado = False
    for coincidencia in coincidencias:
        inicio = coincidencia.start()
        if inicio < ultimo:
            continue  # bloque anidado dentro de otro ya eliminado
        fin = fin_de_bloque(config, coincidencia.end() - 1)
        hueco = config[ultimo:inicio]
        # Entre dos bloques eliminados solo hay espacios: no se conserva.
        if not (insertado and not hueco.strip()):
            resultado.append(hueco)
        if not insertado:
            resultado.append(nuevos_con_sangria.rstrip('\n') + '\n')
            insertado = True
        ultimo = fin
    resultado.append(config[ultimo:])
    return ''.join(resultado)


def buscar_config_nginx():
    candidatos = []
    for carpeta in ('/etc/nginx/sites-enabled', '/etc/nginx/conf.d'):
        if os.path.isdir(carpeta):
            for nombre in sorted(os.listdir(carpeta)):
                candidatos.append(os.path.realpath(os.path.join(carpeta, nombre)))
    candidatos.append('/etc/nginx/nginx.conf')
    for ruta in dict.fromkeys(candidatos):
        try:
            with open(ruta, encoding='utf-8') as archivo:
                if PATRON_LOCATION.search(archivo.read()):
                    return ruta
        except (OSError, UnicodeDecodeError):
            continue
    return None


def obtener(url):
    with urllib.request.urlopen(url, timeout=5) as respuesta:
        return respuesta.status, respuesta.read().decode('utf-8', 'replace')


def probar_websocket(host, puerto, ruta):
    peticion = (
        f'GET {ruta} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
        'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n'
    )
    with socket.create_connection((host, puerto), timeout=5) as conexion:
        conexion.sendall(peticion.encode())
        return conexion.recv(200).decode('latin-1', 'replace').split('\r\n')[0]


def main():
    if os.geteuid() == 0:
        fallo('Ejecuta el script SIN sudo (como ubuntu). El script usa sudo solo para Nginx.')

    paso('1/6 Respaldo de datos')
    datos = os.path.join(BACKEND, 'data')
    if os.path.isdir(datos):
        destino = os.path.join(BACKEND, f'data.bak-{FECHA}')
        shutil.copytree(datos, destino)
        ok(f'Copia en {destino}')
    else:
        ok('No hay carpeta data/ todavía (se creará sola)')

    paso('2/6 Instalando dependencias del backend')
    ejecutar(['npm', 'install', '--omit=dev'], cwd=BACKEND)
    ok('npm install terminado')

    paso('3/6 Configurando Nginx')
    with open(BLOQUES, encoding='utf-8') as archivo:
        nuevos = ''.join(l for l in archivo.readlines() if not l.lstrip().startswith('#')).strip('\n') + '\n'
    ruta = buscar_config_nginx()
    if ruta is None:
        fallo('No encontré ningún "location /movimiento" en /etc/nginx. Revisa la configuración manualmente.')
    ok(f'Archivo encontrado: {ruta}')
    with open(ruta, encoding='utf-8') as archivo:
        original = archivo.read()
    nuevo = reemplazar_bloques(original, nuevos)
    if nuevo == original:
        ok('La configuración ya estaba actualizada')
    else:
        # El respaldo va fuera de sites-enabled para que Nginx no lo cargue.
        ejecutar(['sudo', 'mkdir', '-p', RESPALDOS_NGINX])
        respaldo = os.path.join(RESPALDOS_NGINX, f'{os.path.basename(ruta)}.{FECHA}')
        ejecutar(['sudo', 'cp', ruta, respaldo])
        ok(f'Respaldo en {respaldo}')
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as temporal:
            temporal.write(nuevo)
        ejecutar(['sudo', 'cp', temporal.name, ruta])
        os.unlink(temporal.name)

        prueba = ejecutar(['sudo', 'nginx', '-t'], permitir_error=True)
        if prueba.returncode != 0:
            print(prueba.stderr)
            ejecutar(['sudo', 'cp', respaldo, ruta])
            fallo('nginx -t falló. Se restauró la configuración anterior; no se cambió nada.')
        ok('nginx -t correcto')

    paso('4/6 Recargando Nginx')
    ejecutar(['sudo', 'systemctl', 'reload', 'nginx'])
    ok('Nginx recargado (TAREA2 sigue funcionando igual)')

    paso(f'5/6 Reiniciando solo {PROCESO_PM2}')
    lista = ejecutar(['pm2', 'jlist'])
    procesos = [p.get('name') for p in json.loads(lista.stdout or '[]')]
    if PROCESO_PM2 in procesos:
        ejecutar(['pm2', 'restart', PROCESO_PM2, '--update-env'])
    else:
        ejecutar(['pm2', 'start', 'server.js', '--name', PROCESO_PM2], cwd=BACKEND)
    ejecutar(['pm2', 'save'])
    ok(f'{PROCESO_PM2} reiniciado. Procesos PM2: {", ".join(filter(None, procesos))}')

    paso('6/6 Verificando')
    import time
    time.sleep(2)
    errores = 0
    for nombre, url in (
        ('API directa', 'http://127.0.0.1:8080/api/health'),
        ('API vía Nginx', 'http://127.0.0.1/movimiento/api/health'),
        ('Métricas', 'http://127.0.0.1/movimiento/api/metrics'),
        ('Panel web', 'http://127.0.0.1/movimiento/'),
    ):
        try:
            estado, cuerpo = obtener(url)
            ok(f'{nombre}: HTTP {estado} {cuerpo[:80] if "api" in url else ""}')
        except Exception as error:  # noqa: BLE001
            errores += 1
            print(f'    [ERROR] {nombre}: {error}')
    try:
        linea = probar_websocket('127.0.0.1', 80, '/movimiento/ws')
        if ' 101 ' in linea:
            ok(f'WebSocket vía Nginx: {linea}')
        else:
            errores += 1
            print(f'    [ERROR] WebSocket vía Nginx respondió: {linea}')
    except Exception as error:  # noqa: BLE001
        errores += 1
        print(f'    [ERROR] WebSocket: {error}')

    if errores:
        print('\nHubo errores. Revisa: pm2 logs movimiento-api --lines 30')
        sys.exit(1)
    print('\nTodo listo. Abre en el navegador: http://18.191.113.248/movimiento/')


if __name__ == '__main__':
    main()
