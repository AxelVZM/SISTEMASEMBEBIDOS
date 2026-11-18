"""Official datasets only. Atomic update; network errors never replace a good database."""
import argparse, csv, hashlib, io, json, sqlite3, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
SOURCES={'MA-L':'https://standards-oui.ieee.org/oui/oui.csv','MA-M':'https://standards-oui.ieee.org/oui28/mam.csv','MA-S':'https://standards-oui.ieee.org/oui36/oui36.csv',
'SIG':'https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/company_identifiers/company_identifiers.yaml'}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ESP32-Detector/1.0 (local registry update)'})
    with urllib.request.urlopen(req,timeout=45) as response: return response.read()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--source-dir',type=Path,help='CSV/YAML oficiales descargados manualmente'); args=p.parse_args()
    root=ROOT/'data'; tmp=root/'vendors.tmp.sqlite3'; tmp.unlink(missing_ok=True)
    db=sqlite3.connect(tmp)
    db.executescript('create table oui(prefix text primary key,organization text,registry text); create table companies(id integer primary key,name text);')
    manifest={'updated_utc':datetime.now(timezone.utc).isoformat(),'sources':[]}; failures=[]
    for name,url in SOURCES.items():
        try:
            filename={'MA-L':'oui.csv','MA-M':'mam.csv','MA-S':'oui36.csv','SIG':'company_identifiers.yaml'}[name]
            content=(args.source_dir/filename).read_bytes() if args.source_dir else fetch(url)
            text=content.decode('utf-8-sig'); count=0
            if name=='SIG':
                records=yaml.safe_load(text)['company_identifiers']
                for row in records:
                    db.execute('insert or replace into companies values(?,?)',(int(row['value']),row['name'])); count+=1
            else:
                for row in csv.DictReader(io.StringIO(text)):
                    prefix=row['Assignment'].strip().upper()
                    if len(prefix)!={'MA-L':6,'MA-M':7,'MA-S':9}[name]: raise ValueError('Longitud de asignación inesperada')
                    int(prefix,16)
                    old=db.execute('select organization from oui where prefix=?',(prefix,)).fetchone()
                    organizations=set(old[0].split(' | ')) if old else set()
                    organizations.add(row['Organization Name'])
                    db.execute('insert or replace into oui values(?,?,?)',(prefix,' | '.join(sorted(organizations)),name)); count+=1
            if count<100: raise ValueError('Registro incompleto o formato inesperado')
            unique_count=db.execute('select count(*) from companies').fetchone()[0] if name=='SIG' else db.execute('select count(*) from oui where registry=?',(name,)).fetchone()[0]
            manifest['sources'].append(dict(registry=name,url=url,records=count,unique_records=unique_count,sha256=hashlib.sha256(content).hexdigest()))
            print(name,count)
        except Exception as e: failures.append(f'{name}: {e}')
    if failures:
        db.close(); tmp.unlink(missing_ok=True)
        print('No se reemplaza la base. Descarga los archivos oficiales y usa --source-dir.\n'+'\n'.join(failures),file=sys.stderr); return 1
    db.commit(); db.close(); tmp.replace(root/'vendors.sqlite3')
    (root/'vendors_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8'); return 0
if __name__=='__main__': sys.exit(main())
