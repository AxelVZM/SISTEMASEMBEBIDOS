"""Isolated browser fixtures: roles, brand/type confidence, WPS and BLE opt-in."""
import os,sys,time,tempfile,subprocess,socket,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.store import Store
from backend.models import Settings,Observation
from playwright.sync_api import sync_playwright

def main():
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',8000))
        except OSError:raise SystemExit('Cierra el servidor en 8000 antes de la prueba.')
    with tempfile.TemporaryDirectory(prefix='detector-identity-ui-') as directory:
        store=Store(Path(directory)/'observations.sqlite3',ROOT/'data',Settings())
        records=[dict(tech='wifi',mac='AA:BB:CC:11:22:01',role='ap',wps_manufacturer='HONOR',frame_type='beacon'),dict(tech='wifi',mac='AA:BB:CC:11:22:02',role='ap',wps_manufacturer='ZTE',wps_model_name='ZXHN F680',wps_primary_device_type='00060050F2040002'),dict(tech='ble',mac='AA:BB:CC:11:22:03',name='MacBook PRUEBA SIMULADA',appearance=0x83),dict(tech='classic',mac='AA:BB:CC:11:22:04',cod=0x418)]
        for record in records:store.ingest(Observation(event='observation',rssi=-60,**record),time.time())
        store.db.close()
        server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,env={**os.environ,'DETECTOR_DATA':directory},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=.5);break
                except Exception:time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1500,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:8000');page.wait_for_function('document.querySelectorAll("#rows tr[data-id]").length===4')
                page.evaluate("document.querySelector('#notice').textContent='PRUEBA AUTOMATIZADA · DATOS SIMULADOS AISLADOS'")
                page.check('#techView');assert 'ROL WI-FI' in page.locator('thead').first.inner_text().upper()
                page.select_option('#brand','Honor');row=page.locator('#rows tr[data-id]');assert row.count()==1
                assert 'Honor' in row.locator('td').nth(2).inner_text();assert 'Punto de acceso' in row.locator('td').nth(10).inner_text()
                page.click('#clearFilters');page.select_option('#brand','ZTE');row=page.locator('#rows tr[data-id]');assert 'Router' in row.locator('td').nth(1).inner_text();assert 'ZXHN F680' in row.inner_text()
                row.click();page.locator('#detailBody .detail-grid').first.wait_for();assert 'WPS' in page.locator('#detailBody').inner_text();page.click('[data-close="detailDialog"]')
                page.click('#clearFilters');page.select_option('#role','Punto de acceso');assert page.locator('#rows tr[data-id]').count()==2
                page.click('#clearFilters');page.select_option('#category','Laptop');assert page.locator('#rows tr[data-id]').count()==1
                page.click('#settingsButton');page.check('#bleActive');page.click('button[type="submit"]');page.wait_for_function("document.querySelector('#saveStatus').textContent.includes('Guardado')")
                assert page.request.get('http://127.0.0.1:8000/api/settings').json()['ble_active'] is True
                page.click('[data-close="settingsDialog"]')
                exported=page.request.get('http://127.0.0.1:8000/api/export/csv').text();assert 'network_role' in exported and 'brand_confidence' in exported
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors;browser.close();print('PASS: Honor AP sin tipo inventado, ZTE router WPS, Laptop BLE, filtros de rol/tipo, confianza, CSV y BLE activo opcional; sin errores JS.')
        finally:server.terminate();server.wait(timeout=10)
if __name__=='__main__':main()
