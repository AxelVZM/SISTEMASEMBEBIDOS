"""Optional browser integration. Fixtures live only in a temporary database."""
import os,sys,subprocess,tempfile,time,urllib.request,socket,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.models import Observation,Settings
from backend.store import Store
from playwright.sync_api import sync_playwright

def main():
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',8000))
        except OSError:raise SystemExit('Cierra el servidor del puerto 8000 antes de la prueba visual.')
    with tempfile.TemporaryDirectory(prefix='detector-ui-test-') as directory:
        folder=Path(directory);store=Store(folder/'observations.sqlite3',ROOT/'data',Settings())
        now=time.time()
        for i,(tech,name,rssi) in enumerate([('ble','Samsung Galaxy PRUEBA SIMULADA',-52),('classic','AirPods PRUEBA SIMULADA',-73),('wifi','',-85)]):
            store.ingest(Observation(event='observation',tech=tech,mac=f'AA:BB:CC:00:00:{i+1:02X}',rssi=rssi,name=name,role='ap' if tech=='wifi' else 'unknown'),now-10)
        store.db.close()
        server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,env={**os.environ,'DETECTOR_DATA':directory},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:urllib.request.urlopen('http://127.0.0.1:8000/api/state',timeout=.5);break
                except Exception:time.sleep(.1)
            else:raise AssertionError('Servidor de prueba no disponible')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1500,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8000')
                page.wait_for_function('document.querySelectorAll("#rows tr[data-id]").length===3')
                page.evaluate("document.querySelector('#notice').textContent='PRUEBA AUTOMATIZADA · DATOS SIMULADOS Y AISLADOS'")
                page.select_option('#tech','ble');assert page.locator('#rows tr[data-id]').count()==1
                page.locator('#rows tr[data-id]').click();page.wait_for_selector('#detailBody .detail-grid');assert 'Nombre autodeclarado' in page.locator('#detailBody').inner_text()
                page.click('[data-close="detailDialog"]');page.click('#clearFilters');page.fill('#search','AirPods');assert page.locator('#rows tr[data-id]').count()==1
                page.click('#clearFilters');page.click('#settingsButton');page.fill('input[name="channels"]','1,6,11');page.check('#calibrated');page.click('button[type="submit"]');page.wait_for_function('document.querySelector("#saveStatus").textContent.includes("Guardado")');page.click('[data-close="settingsDialog"]')
                page.wait_for_timeout(2300);assert '≈' in page.locator('#rows').inner_text()
                with page.expect_download() as download:page.click('a[href="/api/export/csv"]')
                assert download.value.suggested_filename=='dispositivos.csv'
                page.click('#errorsButton');page.locator('#errorsDialog').wait_for(state='visible');page.click('[data-close="errorsDialog"]')
                page.click('#themeButton');assert page.locator('html').get_attribute('data-theme')=='light'
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                page.on('dialog',lambda d:d.accept());page.click('#resetButton');page.wait_for_function('document.querySelectorAll("#rows tr[data-id]").length===0')
                assert not errors,errors;browser.close()
                print('PASS: fixtures aislados, WebSocket, filtros, detalle, calibración, ajustes, CSV, diagnóstico, temas, móvil y reinicio.')
        finally:
            server.terminate();server.wait(timeout=10)
if __name__=='__main__':main()
