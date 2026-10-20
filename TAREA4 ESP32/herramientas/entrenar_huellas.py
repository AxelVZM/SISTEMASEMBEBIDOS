"""Catálogo experimental por coincidencia exacta. Sin dependencias externas.
python herramientas/entrenar_huellas.py train.json test.json --output web/wifi_catalog.json
Los dispositivos físicos Y las sesiones de test deben ser ajenos al entrenamiento.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

def read(path):
    rows=json.loads(Path(path).read_text())
    if not isinstance(rows,list) or not rows:raise ValueError('Se requiere una lista no vacía de capturas etiquetadas')
    for r in rows:
        for k in ('device_id','session_id','type','brand','model','source'):
            if not isinstance(r.get(k),str) or not r[k].strip() or len(r[k])>160:raise ValueError('Etiqueta/procedencia faltante: '+k)
        if r['type'] not in ('phone','laptop','unknown'):raise ValueError('type: phone, laptop o unknown')
        if r.get('fingerprintComplete') is not True or r.get('fingerprintVersion')!=1 or not re.fullmatch(r'(?:[0-9a-f]{2}){1,96}',r.get('fingerprint','')):raise ValueError('Huella v1 inválida')
    return rows

def train(train_rows,test_rows):
    for key in ('device_id','session_id'):
        if {r[key] for r in train_rows}&{r[key] for r in test_rows}:raise ValueError('Fuga de datos entre train/test: '+key)
    grouped=defaultdict(list)
    for r in train_rows:grouped[r['fingerprint']].append(r)
    candidates={}
    for fp,rows in grouped.items():
        labels={(r['type'],r['brand'],r['model']) for r in rows}
        devices={r['device_id'] for r in rows}
        if len(labels)!=1 or len(devices)<2:continue
        kind,brand,model=next(iter(labels))
        if kind=='unknown':continue
        candidates[fp]={'fingerprint':fp,'type':kind,'brand':brand,'model':model,'devices':len(devices),'sources':sorted({r['source'] for r in rows})}
    tested=defaultdict(list); correct=accepted=0
    for r in test_rows:
        e=candidates.get(r['fingerprint'])
        if e:
            accepted+=1;ok=(e['type'],e['brand'],e['model'])==(r['type'],r['brand'],r['model']);correct+=ok
            tested[r['fingerprint']].append((r,ok))
    entries=[]
    for fp,checks in tested.items():
        if checks and all(ok for _,ok in checks):
            e=candidates[fp];e.update(validated=True,validationDevices=len({r['device_id'] for r,_ in checks}));entries.append(e)
    # Report pre-selection held-out performance. This set gates entries and is NOT an independent final evaluation.
    report={'test_rows':len(test_rows),'accepted_before_gate':accepted,'correct_before_gate':correct,'coverage':accepted/len(test_rows),'precision':correct/accepted if accepted else None,'entries_released':len(entries),'note':'Validación usada para seleccionar entradas; evaluar de nuevo en un tercer conjunto independiente. Métricas por fila, no por equipo.'}
    return {'schema':1,'entries':entries,'validation':report}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('train');ap.add_argument('test');ap.add_argument('--output',required=True);a=ap.parse_args()
    try:result=train(read(a.train),read(a.test))
    except (ValueError,KeyError) as e:ap.error(str(e))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['validation'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
