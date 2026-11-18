"""Standard-library-only Windows launcher. No network access during normal startup."""
import argparse, importlib.util, json, os, socket, sqlite3, subprocess, sys, time, urllib.error, urllib.request, webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8000'
MODULES=('fastapi','uvicorn','serial','yaml','websockets')

def venv_python(root=ROOT):return root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def port_occupied():
    with socket.socket() as sock:
        sock.settimeout(.4);return sock.connect_ex(('127.0.0.1',8000))==0

def health_request():
    try:
        with urllib.request.urlopen(BASE+'/api/health',timeout=1) as response:body=json.loads(response.read(200000))
        if body.get('service')=='esp32-detector' and body.get('api_version','').startswith('2.') and isinstance(body.get('backend'),dict):return body
    except (OSError,ValueError,urllib.error.URLError):pass
    return None

def inspect_dependencies(python):
    try:
        code='import importlib.util,json,sys; print(json.dumps(dict(version=sys.version,missing=[m for m in '+repr(MODULES)+' if importlib.util.find_spec(m) is None])))'
        result=subprocess.run([str(python),'-c',code],capture_output=True,text=True,timeout=20)
        if result.returncode:return {'error':result.stderr.strip() or result.stdout.strip()}
        data=json.loads(result.stdout)
        if data['missing']:return {'error':'Faltan dependencias: '+', '.join(data['missing'])}
        # Import the real app too: catch bad dependencies/import errors before uvicorn starts.
        imported=subprocess.run([str(python),'-c','import backend.main; print("Importación FastAPI correcta")'],cwd=ROOT,capture_output=True,text=True,timeout=20)
        if imported.returncode:return {'error':imported.stderr[-2000:]}
        return data
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:return {'error':str(error)}

def inspect_files(root=ROOT):
    required=('backend/main.py','backend/requirements.txt','frontend/index.html','frontend/app.js','frontend/style.css','data/vendors.sqlite3','data/name_rules.json')
    return [name for name in required if not (root/name).is_file()]

def diagnostics():
    print('ESP32 Detector 2.0 — Diagnóstico local\nCarpeta:',ROOT,'\nPython del lanzador:',sys.version.replace('\n',' '))
    python=venv_python();print('Entorno virtual:',python,'OK' if python.exists() else 'NO EXISTE')
    print('Dependencias/importaciones:',json.dumps(inspect_dependencies(python) if python.exists() else {'error':'Ejecuta INSTALAR.bat'},ensure_ascii=False))
    print('Archivos faltantes:',inspect_files() or 'ninguno')
    data=Path(os.environ.get('DETECTOR_DATA',ROOT/'data'))
    for path in (ROOT/'data/vendors.sqlite3',data/'observations.sqlite3'):
        if not path.exists():print(path.name,': aún no creada' if path.name=='observations.sqlite3' else ': FALTA');continue
        try:
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1) as db:print(path.name,':',db.execute('pragma quick_check').fetchone()[0])
        except sqlite3.Error as error:print(path.name,': ERROR:',error)
    config=data/'settings.json'
    if config.exists():
        try:json.loads(config.read_text(encoding='utf-8'));print('settings.json: JSON legible (validación de parámetros en /api/health)')
        except (ValueError,OSError) as error:print('settings.json inválido; backend usará valores predeterminados:',error)
    print('Puerto 8000:', 'OCUPADO' if port_occupied() else 'LIBRE')
    print('Servidor detectado:',json.dumps(health_request(),ensure_ascii=False))
    if python.exists():
        result=subprocess.run([str(python),'-m','serial.tools.list_ports','-v'],cwd=ROOT,check=False)
        if result.returncode:print('No se pudo enumerar puertos seriales. Revisa las dependencias.')
    print('COM6 puede estar desconectado; esto no impide abrir el panel.')
    return 0

def install():
    if sys.version_info[:2]!=(3,12):
        print('Usa Python 3.12 x64 y su lanzador py. El backend se verificó con esa versión.');return 1
    python=venv_python()
    if not python.exists():
        print('Se creará el entorno virtual local .venv.');subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
    print('Se instalarán las dependencias de backend y pruebas. Esta instalación requiere Internet; el inicio normal no lo requiere.')
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'backend/requirements-lock.txt'),'-r',str(ROOT/'tests/requirements.txt')],cwd=ROOT,check=True)
    result=inspect_dependencies(python)
    if result.get('error'):print(result['error']);return 1
    print('Instalación terminada. Abre INICIAR.bat.');return 0

def start(no_browser=False,smoke_test=False):
    missing=inspect_files()
    if missing:print('La carpeta está incompleta. Faltan:',', '.join(missing));return 1
    python=venv_python()
    if not python.exists():print('No hay entorno virtual. Ejecuta INSTALAR.bat primero.');return 1
    check=inspect_dependencies(python)
    if check.get('error'):print(check['error'],'\nEjecuta DIAGNOSTICAR.bat o INSTALAR.bat.');return 1
    if port_occupied():
        health=health_request()
        if health:
            print('ESP32 Detector ya está activo. Se reutiliza el servidor; no se inicia otro proceso.')
            if not no_browser and not smoke_test:webbrowser.open(BASE)
            return 0
        print('El puerto 8000 está ocupado por otro servicio o una versión antigua. No se cerrará ese proceso.\nCierra la instancia anterior y ejecuta DIAGNOSTICAR.bat. Comando útil: netstat -ano | findstr :8000');return 1
    print('Iniciando backend local. COM6 no es necesario para abrir el panel.\nMantén esta consola abierta. Ctrl+C detiene el servidor.\nPanel:',BASE,flush=True)
    process=subprocess.Popen([str(python),'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT)
    try:
        end=time.monotonic()+30;health=None
        while time.monotonic()<end:
            if process.poll() is not None:print('El servidor terminó antes de iniciar. El error aparece arriba.');return 1
            health=health_request()
            if health:break
            time.sleep(.2)
        if not health:print('El servidor no respondió a tiempo. Consulta el error de esta consola.');return 1
        print('Backend listo:',health['status'],'—',health['message'],flush=True)
        if smoke_test:
            with urllib.request.urlopen(BASE,timeout=3) as response:
                if response.status!=200 or b'OBSERVATORIO' not in response.read():return 1
            print('Prueba de inicio y HTML aprobada.');return 0
        if not no_browser:
            if not webbrowser.open(BASE):print('No se pudo abrir el navegador automáticamente. Abre:',BASE)
        return process.wait()
    except KeyboardInterrupt:print('\nDeteniendo el servidor iniciado por este lanzador.');return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','diagnose','install']);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--smoke-test',action='store_true');args=parser.parse_args()
    try:return diagnostics() if args.action=='diagnose' else install() if args.action=='install' else start(args.no_browser,args.smoke_test)
    except (OSError,subprocess.SubprocessError) as error:print('ERROR:',error,'\nEjecuta DIAGNOSTICAR.bat para revisar la instalación.');return 1
if __name__=='__main__':raise SystemExit(main())
