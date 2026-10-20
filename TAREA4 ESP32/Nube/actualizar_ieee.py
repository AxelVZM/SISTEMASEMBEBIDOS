"""Actualiza los tres registros IEEE sin instalar dependencias. Conserva el fichero si falla."""
import csv, gzip, io, json, hashlib, urllib.request
from pathlib import Path
from datetime import datetime, timezone

FUENTES={'MA-L':('https://standards-oui.ieee.org/oui/oui.csv',6),
         'MA-M':('https://standards-oui.ieee.org/oui28/mam.csv',7),
         'MA-S':('https://standards-oui.ieee.org/oui36/oui36.csv',9)}

def actualizar(destino):
    registros={}; informe={'fecha_utc':datetime.now(timezone.utc).isoformat(),'fuentes':{}}
    for tipo,(url,n) in FUENTES.items():
        with urllib.request.urlopen(url,timeout=60) as r: datos=r.read()
        filas=list(csv.DictReader(io.StringIO(datos.decode('utf-8-sig'))))
        cuenta=0
        for fila in filas:
            prefijo=fila['Assignment'].strip().upper(); nombre=fila['Organization Name'].strip()
            if len(prefijo)!=n or any(c not in '0123456789ABCDEF' for c in prefijo): raise ValueError('Prefijo inválido')
            registros[prefijo]=nombre.replace('\t',' ').replace('\n',' ');cuenta+=1
        if not cuenta:raise ValueError('Registro vacío')
        informe['fuentes'][tipo]={'url':url,'registros':cuenta,'sha256_csv':hashlib.sha256(datos).hexdigest()}
    destino=Path(destino); temporal=destino.with_suffix('.tmp')
    with gzip.open(temporal,'wt',encoding='utf-8') as f:
        for p,nombre in sorted(registros.items()):f.write(p+'\t'+nombre+'\n')
    temporal.replace(destino)
    destino.with_name('ieee_fuentes.json').write_text(json.dumps(informe,indent=2),encoding='utf-8')
    print('Prefijos actualizados:',len(registros))

if __name__=='__main__':
    actualizar(Path(__file__).resolve().parent/'backend/oui.txt.gz')
