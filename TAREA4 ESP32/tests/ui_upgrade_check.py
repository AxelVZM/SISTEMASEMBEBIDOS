"""Browser acceptance test; synthetic observations stay in one temporary database."""
import os,sys,time,tempfile,subprocess,socket,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.store import Store
from backend.models import Settings,Observation
from playwright.sync_api import sync_playwright

def main():
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',8000))
        except OSError:raise SystemExit('Detén cualquier servidor del puerto 8000 antes de esta prueba.')
    with tempfile.TemporaryDirectory(prefix='detector-upgrade-ui-') as directory:
        store=Store(Path(directory)/'observations.sqlite3',ROOT/'data',Settings(dedup_ms=100))
        device='ble:AA:BB:CC:11:22:33'
        def emit(rssi):store.ingest(Observation(event='observation',tech='ble',mac=device[4:],rssi=rssi,name='PRUEBA SIMULADA Samsung',address_type='random'),time.time())
        emit(-50)
        server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,env={**os.environ,'DETECTOR_DATA':directory},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=.5);break
                except Exception:time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1500,'height':1100});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8000');page.wait_for_selector('#rows tr[data-id]')
                page.evaluate("document.querySelector('#notice').textContent='PRUEBA AUTOMATIZADA · DATOS SIMULADOS AISLADOS'")
                assert 'Backend' in page.locator('#componentHealth').inner_text()
                assert 'ESP32 desconectado — esperando conexión serial' in page.locator('#connection').inner_text()
                page.select_option('#scanProfile','exhaustive');page.click('#applyProfile')
                page.wait_for_function("document.querySelector('#activeProfile').textContent.includes('Exhaustivo')")
                settings=page.request.get('http://127.0.0.1:8000/api/settings').json();assert settings['wifi_ms']==16500
                settings['dedup_ms']=100;settings['profile']='custom';assert page.request.put('http://127.0.0.1:8000/api/settings',data=settings).ok
                page.click('#calibrationShortcut');page.select_option('#calibrationDevice',device);page.check('#calibrationAuthorized');page.fill('#calibrationSeconds','5');page.click('#startCalibration')
                page.wait_for_function("!document.querySelector('[data-distance=\"1\"]').disabled")
                for distance,rssi in [(1,-50),(3,-60),(5,-64),(10,-70)]:
                    page.click('[data-distance="'+str(distance)+'"]')
                    page.wait_for_function("document.querySelector('#calibrationProgress').textContent.includes('Capturando')")
                    for _ in range(15):emit(rssi);page.wait_for_timeout(200)
                    page.wait_for_function("!document.querySelector('#calibrationProgress').textContent.includes('Capturando')",timeout=10000)
                page.wait_for_function("!document.querySelector('#applyCalibration').disabled")
                page.click('#applyCalibration');page.wait_for_function("document.querySelector('#calibrationResults').textContent.includes('Calibración aplicada')")
                result=page.request.get('http://127.0.0.1:8000/api/settings').json();assert result['calibrated'];assert 1<result['loss_n']<3
                page.click('[data-close="calibrationDialog"]');page.click('#diagnosticsShortcut');page.locator('#errorsDialog').wait_for(state='visible');assert 'Comunicación' in page.locator('#errorsBody').inner_text();page.click('[data-close="errorsDialog"]')
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                # A stopped backend must be shown as unavailable, not as a still-active scanner.
                server.terminate();server.wait(timeout=10)
                page.wait_for_function("document.querySelector('#connection').textContent.includes('Backend sin respuesta')",timeout=12000)
                assert not errors,errors
                browser.close();print('PASS: estados, perfil real, calibración 1/3/5/10 m con ventanas y lecturas, aplicación, diagnóstico, móvil y pérdida del backend.')
        finally:
            if server.poll() is None:server.terminate();server.wait(timeout=10)
            store.db.close()
if __name__=='__main__':main()
