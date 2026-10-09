#!/usr/bin/env python3
"""Instala PostgreSQL en esta misma EC2 para Movimiento GPS (TAREA3).

Uso (como usuario ubuntu, SIN sudo):

    python3 ~/SISTEMASEMBEBIDOS/TAREA3/backend/instalar_postgres_local.py
    python3 .../instalar_postgres_local.py --simular   # solo muestra qué haría

Qué hace (se puede ejecutar varias veces sin romper nada):
  1. Revisa memoria y disco. Si hay poca RAM y no hay swap, crea 1 GB de
     swap para que el servidor no se ponga lento si falta memoria.
  2. Instala PostgreSQL desde los repositorios de Ubuntu.
  3. Lo configura en modo liviano (~60-80 MB de RAM), solo accesible desde
     esta máquina (localhost), nunca desde internet.
  4. Crea el usuario y la base de datos "movimiento" con una contraseña
     aleatoria.
  5. Escribe la conexión en backend/.env (conserva el resto de valores y
     guarda un respaldo del .env anterior).
  6. Programa un respaldo diario automático (pg_dump, se guardan 7 días).
  7. Ejecuta actualizar_servidor.py: prueba la conexión, migra los datos
     antiguos y reinicia solo movimiento-api.
"""

import datetime
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

BACKEND = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(BACKEND, '.env')
FECHA = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
SIMULAR = '--simular' in sys.argv

USUARIO_BD = 'movimiento'
NOMBRE_BD = 'movimiento'

CONFIG_LIVIANA = """# Movimiento GPS (TAREA3): PostgreSQL liviano para una EC2 pequeña.
# Generado por instalar_postgres_local.py
listen_addresses = 'localhost'
max_connections = 30
shared_buffers = 64MB
effective_cache_size = 256MB
work_mem = 2MB
maintenance_work_mem = 32MB
wal_buffers = 4MB
random_page_cost = 1.1
"""

RESPALDO_CRON = """# Respaldo diario de la base de Movimiento GPS (TAREA3), se guardan 7 días.
30 3 * * * postgres pg_dump -Fc {bd} > /var/backups/movimiento/movimiento-$(date +\\%Y\\%m\\%d).dump && find /var/backups/movimiento -name '*.dump' -mtime +7 -delete
"""


def paso(texto):
    print(f'\n==> {texto}')


def ok(texto):
    print(f'    [OK] {texto}')


def aviso(texto):
    print(f'    [AVISO] {texto}')


def fallo(texto):
    print(f'    [ERROR] {texto}')
    sys.exit(1)


def ejecutar(comando, permitir_error=False, entrada=None, mostrar=True):
    """Ejecuta un comando. En modo simulación solo lo muestra."""
    if SIMULAR:
        if mostrar:
            print(f'    (simulación) {" ".join(comando)}')
        return subprocess.CompletedProcess(comando, 0, '', '')
    resultado = subprocess.run(comando, text=True, capture_output=True, input=entrada)
    if resultado.returncode != 0 and not permitir_error:
        print(resultado.stdout)
        print(resultado.stderr)
        fallo(f'Falló: {" ".join(comando)}')
    return resultado


def escribir_como_root(ruta, contenido, modo='644'):
    with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as temporal:
        temporal.write(contenido)
    ejecutar(['sudo', 'install', '-m', modo, temporal.name, ruta])
    os.unlink(temporal.name)


# ---------------------------------------------------------------------------
# Funciones puras (probadas por separado)
# ---------------------------------------------------------------------------
def leer_meminfo(texto):
    """Devuelve (ram_mb, swap_mb) a partir del contenido de /proc/meminfo."""
    valores = {}
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[0].endswith(':'):
            valores[partes[0][:-1]] = int(partes[1]) // 1024
    return valores.get('MemTotal', 0), valores.get('SwapTotal', 0)


def actualizar_env(texto, nuevos):
    """Reemplaza/agrega claves en el contenido de un .env conservando el resto.

    Las claves de conexión que no estén en `nuevos` (p. ej. DATABASE_URL de
    una configuración anterior) se comentan para que no tengan prioridad.
    """
    claves_bd = {'DATABASE_URL', 'PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSSLMODE', 'PGSSLROOTCERT', 'PGPOOL_MAX'}
    pendientes = dict(nuevos)
    lineas = []
    for linea in texto.splitlines():
        coincidencia = re.match(r'^\s*([A-Z0-9_]+)\s*=', linea)
        clave = coincidencia.group(1) if coincidencia else None
        if clave in pendientes:
            lineas.append(f'{clave}={pendientes.pop(clave)}')
        elif clave in claves_bd:
            lineas.append(f'# {linea}  (desactivado por instalar_postgres_local.py)')
        else:
            lineas.append(linea)
    if pendientes:
        if lineas and lineas[-1].strip():
            lineas.append('')
        lineas.append('# PostgreSQL local (instalar_postgres_local.py)')
        lineas.extend(f'{clave}={valor}' for clave, valor in pendientes.items())
    return '\n'.join(lineas) + '\n'


def leer_valor_env(texto, clave):
    for linea in texto.splitlines():
        coincidencia = re.match(rf'^\s*{clave}\s*=\s*(.*)$', linea)
        if coincidencia:
            return coincidencia.group(1).strip().strip('"').strip("'")
    return None


# ---------------------------------------------------------------------------
# Pasos
# ---------------------------------------------------------------------------
def revisar_recursos():
    paso('1/7 Memoria y disco')
    with open('/proc/meminfo', encoding='utf-8') as archivo:
        ram_mb, swap_mb = leer_meminfo(archivo.read())
    libre_gb = shutil.disk_usage('/').free / 1024 ** 3
    ok(f'RAM {ram_mb} MB · swap {swap_mb} MB · disco libre {libre_gb:.1f} GB')
    if libre_gb < 2:
        fallo('Hay menos de 2 GB libres en el disco. Libera espacio antes de instalar PostgreSQL.')
    if swap_mb == 0 and ram_mb < 2048:
        if libre_gb < 3:
            aviso('Poca RAM y poco disco: no se crea swap. Vigila la memoria con "free -h".')
            return
        ejecutar(['sudo', 'fallocate', '-l', '1G', '/swapfile'])
        ejecutar(['sudo', 'chmod', '600', '/swapfile'])
        ejecutar(['sudo', 'mkswap', '/swapfile'])
        ejecutar(['sudo', 'swapon', '/swapfile'])
        fstab = '' if SIMULAR else open('/etc/fstab', encoding='utf-8').read()
        if '/swapfile' not in fstab:
            ejecutar(['sudo', 'tee', '-a', '/etc/fstab'], entrada='/swapfile none swap sw 0 0\n')
        # Usar la swap solo como reserva, no en uso normal.
        escribir_como_root('/etc/sysctl.d/99-movimiento-swap.conf', 'vm.swappiness=10\n')
        ejecutar(['sudo', 'sysctl', '-p', '/etc/sysctl.d/99-movimiento-swap.conf'])
        ok('Swap de 1 GB creada como reserva de memoria')
    else:
        ok('No hace falta crear swap')


def instalar_postgres():
    paso('2/7 Instalando PostgreSQL')
    if shutil.which('psql') and os.path.isdir('/etc/postgresql'):
        ok('PostgreSQL ya estaba instalado')
    else:
        env = ['sudo', 'env', 'DEBIAN_FRONTEND=noninteractive']
        ejecutar(env + ['apt-get', 'update', '-q'])
        ejecutar(env + ['apt-get', 'install', '-y', '-q', 'postgresql', 'postgresql-contrib'])
        ok('Instalado')
    versiones = ['16'] if SIMULAR else sorted(os.listdir('/etc/postgresql'), key=lambda v: float(v))
    if not versiones:
        fallo('No se encontró la configuración en /etc/postgresql.')
    version = versiones[-1]
    ok(f'Versión {version}')
    return version


def configurar_postgres(version):
    paso('3/7 Configuración liviana (solo localhost)')
    conf_d = f'/etc/postgresql/{version}/main/conf.d'
    ejecutar(['sudo', 'mkdir', '-p', conf_d])
    escribir_como_root(f'{conf_d}/movimiento.conf', CONFIG_LIVIANA)
    ejecutar(['sudo', 'systemctl', 'enable', 'postgresql'])
    ejecutar(['sudo', 'systemctl', 'restart', 'postgresql'])
    ok('PostgreSQL configurado, reiniciado y activado al arrancar la EC2')


def psql(sql, base='postgres'):
    return ejecutar(['sudo', '-u', 'postgres', 'psql', '-d', base, '-v', 'ON_ERROR_STOP=1', '-tAc', sql])


def crear_usuario_y_base(texto_env):
    paso('4/7 Usuario y base de datos')
    # Se reutiliza la contraseña si ya se instaló antes (no rompe la conexión).
    anterior_host = leer_valor_env(texto_env, 'PGHOST')
    anterior_clave = leer_valor_env(texto_env, 'PGPASSWORD')
    clave = anterior_clave if anterior_host in ('127.0.0.1', 'localhost') and anterior_clave else secrets.token_urlsafe(24)
    existe = psql(f"SELECT 1 FROM pg_roles WHERE rolname = '{USUARIO_BD}'").stdout.strip() == '1'
    accion = 'ALTER' if existe else 'CREATE'
    # La contraseña se pasa por stdin para que no aparezca en la lista de procesos.
    ejecutar(
        ['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-q'],
        entrada=f"{accion} ROLE {USUARIO_BD} LOGIN PASSWORD '{clave}';\n",
    )
    if psql(f"SELECT 1 FROM pg_database WHERE datname = '{NOMBRE_BD}'").stdout.strip() != '1':
        ejecutar(['sudo', '-u', 'postgres', 'createdb', '-O', USUARIO_BD, NOMBRE_BD])
        ok(f'Base "{NOMBRE_BD}" creada')
    else:
        ok(f'La base "{NOMBRE_BD}" ya existía (se conservan sus datos)')
    ok(f'Usuario "{USUARIO_BD}" {"actualizado" if existe else "creado"}')
    return clave


def escribir_env(texto_env, clave):
    paso('5/7 Conexión en backend/.env')
    if os.path.exists(ENV):
        respaldo = f'{ENV}.respaldo-{FECHA}'
        if not SIMULAR:
            shutil.copy2(ENV, respaldo)
        ok(f'Respaldo del .env anterior: {respaldo}')
    nuevo = actualizar_env(texto_env, {
        'PGHOST': '127.0.0.1',
        'PGPORT': '5432',
        'PGUSER': USUARIO_BD,
        'PGPASSWORD': clave,
        'PGDATABASE': NOMBRE_BD,
        'PGSSLMODE': 'disable',  # Conexión local: no sale de la máquina.
        'PGPOOL_MAX': '5',
    })
    if SIMULAR:
        print('    (simulación) .env resultante (contraseña oculta):')
        print('    ' + nuevo.replace(clave, '********').replace('\n', '\n    '))
        return
    with open(ENV, 'w', encoding='utf-8') as archivo:
        archivo.write(nuevo)
    os.chmod(ENV, 0o600)
    ok('Escrito (permisos 600: solo el usuario ubuntu puede leerlo)')


def programar_respaldos():
    paso('6/7 Respaldo diario automático')
    ejecutar(['sudo', 'mkdir', '-p', '/var/backups/movimiento'])
    ejecutar(['sudo', 'chown', 'postgres:postgres', '/var/backups/movimiento'])
    ejecutar(['sudo', 'chmod', '700', '/var/backups/movimiento'])
    escribir_como_root('/etc/cron.d/movimiento-respaldo', RESPALDO_CRON.format(bd=NOMBRE_BD))
    ok('Todos los días a las 03:30 en /var/backups/movimiento (se guardan 7 días)')


def actualizar_servidor():
    paso('7/7 Actualizando el servidor (prueba conexión, migra datos, reinicia)')
    script = os.path.join(BACKEND, 'actualizar_servidor.py')
    if SIMULAR:
        print(f'    (simulación) python3 {script}')
        return
    resultado = subprocess.run([sys.executable, script])
    if resultado.returncode != 0:
        fallo('actualizar_servidor.py terminó con errores (mira los mensajes de arriba).')


def main():
    if os.geteuid() == 0:
        fallo('Ejecuta el script SIN sudo (como ubuntu). El script usa sudo solo donde hace falta.')
    if SIMULAR:
        print('MODO SIMULACIÓN: no se cambia nada en el sistema.')
    texto_env = open(ENV, encoding='utf-8').read() if os.path.exists(ENV) else ''
    revisar_recursos()
    version = instalar_postgres()
    configurar_postgres(version)
    clave = crear_usuario_y_base(texto_env)
    escribir_env(texto_env, clave)
    programar_respaldos()
    actualizar_servidor()
    print('\nPostgreSQL local listo. Comprueba: curl http://127.0.0.1:8080/api/health')


if __name__ == '__main__':
    main()
