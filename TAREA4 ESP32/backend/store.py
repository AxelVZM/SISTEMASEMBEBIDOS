import json, sqlite3, statistics, math, threading
from datetime import datetime, timezone
from pathlib import Path
from .identify import Identifier
from .device_types import TARGET_CLASSES

def iso(ts): return datetime.fromtimestamp(ts,timezone.utc).isoformat()

class Store:
    def __init__(self, path, data, settings):
        self.db=sqlite3.connect(path,check_same_thread=False); self.db.row_factory=sqlite3.Row
        self.lock=threading.RLock(); self.settings=settings; self.identifier=Identifier(data)
        if self.db.execute('pragma user_version').fetchone()[0]>2:
            self.db.close();raise ValueError('Versión SQLite posterior a la soportada; no se modifica la base.')
        tables={r[0] for r in self.db.execute("select name from sqlite_master where type='table'")}
        if 'observations' in tables and self.db.execute('pragma user_version').fetchone()[0]<2:
            backup=Path(path).with_name(Path(path).stem+'.pre-v2.sqlite3')
            if not backup.exists() and self.db.execute('select count(*) from observations').fetchone()[0]:
                with sqlite3.connect(backup) as target:self.db.backup(target)
        self.db.executescript('''pragma journal_mode=WAL;
        create table if not exists devices(id text primary key, tech text, mac text, first real, last real, count integer, ema real, metadata text);
        create table if not exists observations(id integer primary key, device text, ts real, rssi integer, metadata text);
        create index if not exists obs_device_time on observations(device,ts);
        create index if not exists obs_time on observations(ts);
        create table if not exists errors(id integer primary key, ts real, message text);
        '''); self.db.commit()
        self.migrate()

    def migrate(self):
        # Additive and transactional: preserve all rows and keys from the original schema.
        with self.lock, self.db:
            self.db.execute('begin immediate')
            for table,columns in {'devices':{'identification':'text'},'observations':{'channel':'integer','identification':'text'}}.items():
                present={r[1] for r in self.db.execute('pragma table_info('+table+')')}
                for name,kind in columns.items():
                    if name not in present: self.db.execute('alter table '+table+' add column '+name+' '+kind)
            self.db.execute('create index if not exists obs_channel_time on observations(channel,ts)')
            self.db.execute('create index if not exists devices_last on devices(last)')
            self.db.execute('create index if not exists devices_tech on devices(tech)')
            self.db.execute('create table if not exists calibration_sessions(id text primary key,device text,started real,samples text,fit text,applied integer default 0)')
            self.db.execute('pragma user_version=2')
            # Backfill the queryable channel without rewriting or deleting legacy metadata.
            self.db.execute("update observations set channel=json_extract(metadata,'$.channel') where channel is null and json_valid(metadata) and json_extract(metadata,'$.tech')='wifi'")

    def available(self):
        with self.lock: return self.db.execute('select 1').fetchone()[0]==1

    def ingest(self,obs,now):
        key=obs.tech+':'+obs.mac
        if obs.rssi is not None and obs.rssi < self.settings.min_rssi: return None
        with self.lock:
            old=self.db.execute('select * from devices where id=?',(key,)).fetchone()
            prior=json.loads(old['metadata']) if old else {}
            fields=('name','name_source','appearance','cod','company_id','manufacturer_data','services','wps_manufacturer','wps_model_name','wps_model_number','wps_device_name','wps_primary_device_type','ssid','vendor_ies','role','frame_type','tx_power')
            enriched=False
            for evidence_key in fields:
                if evidence_key in ('name','name_source') and prior.get('name_complete') and not obs.name_complete:continue
                value=getattr(obs,evidence_key)
                if evidence_key=='services':
                    if set(value)-set(prior.get(evidence_key,[])):enriched=True
                elif value not in (None,'',[],'unknown') and value!=prior.get(evidence_key):enriched=True
            if old and (now-old['last'])*1000 < self.settings.dedup_ms and not enriched:return None
            ema=obs.rssi
            if old and old['ema'] is not None:
                ema=old['ema'] if obs.rssi is None else self.settings.alpha*obs.rssi+(1-self.settings.alpha)*old['ema']
            # Preserve previously announced metadata on sparse follow-up packets.
            meta=dict(prior)
            for k,v in obs.model_dump().items():
                if k in ('name','name_source','name_complete') and prior.get('name_complete') and not obs.name_complete:continue
                if k=='services':
                    meta[k]=list(dict.fromkeys(meta.get(k,[])+v))[:16];continue
                if v is not None and v not in ('',[], 'unknown'):meta[k]=v
            payload=json.dumps(meta,ensure_ascii=False)
            from .models import Observation
            identification=json.dumps(self.identifier.identify(Observation.model_validate(meta)),ensure_ascii=False)
            self.db.execute('insert into devices(id,tech,mac,first,last,count,ema,metadata,identification) values(?,?,?,?,?,?,?,?,?) on conflict(id) do update set last=excluded.last,count=excluded.count,ema=excluded.ema,metadata=excluded.metadata,identification=excluded.identification',
                (key,obs.tech,obs.mac,old['first'] if old else now,now,old['count']+1 if old else 1,ema,payload,identification))
            self.db.execute('insert into observations(device,ts,rssi,metadata,channel,identification) values(?,?,?,?,?,?)',(key,now,obs.rssi,json.dumps(obs.model_dump(),ensure_ascii=False),obs.channel,identification))
            self.db.commit()
            return {'id':key,'new':old is None, 'returned':bool(old and now-old['last']>self.settings.expiry_seconds)}

    def devices(self,now):
        from .models import Observation
        output=[]
        with self.lock:
            for r in self.db.execute('select * from devices order by last desc').fetchall():
                meta=json.loads(r['metadata']); obs=Observation.model_validate(meta)
                readings=[x[0] for x in self.db.execute('select rssi from observations where device=? and rssi is not null order by ts desc limit 15',(r['id'],))]
                median=statistics.median(readings) if readings else None
                distance=None
                if median is not None and self.settings.calibrated:
                    distance=round(10**((self.settings.rssi_ref-median)/(10*self.settings.loss_n)),2)
                proximity='Distancia desconocida' if distance is None else ('Muy cerca' if distance<1 else 'Cerca' if distance<3 else 'Distancia media' if distance<10 else 'Lejos')
                output.append(dict(id=r['id'],tech=r['tech'],mac=r['mac'],name=obs.name,ssid=obs.ssid,wps_device_name=obs.wps_device_name,source='Red local' if obs.frame_type=='red_local' else {'wifi':'Wi-Fi (ESP32)','ble':'Bluetooth LE','classic':'Bluetooth'}[obs.tech],rssi=readings[0] if readings else None,
                    mean=round(statistics.mean(readings),2) if readings else None,median=median,ema=round(r['ema'],2) if r['ema'] is not None else None,
                    distance=distance,proximity=proximity,channel=obs.channel,filtered_rssi=round(r['ema'],2) if r['ema'] is not None else None,estimation_quality='Baja: RSSI calibrado, sin precisión garantizada' if distance is not None else 'No disponible: requiere calibración y RSSI',signal_strength='Desconocida' if median is None else 'Fuerte' if median>=-50 else 'Media' if median>=-70 else 'Débil',first=iso(r['first']),last=iso(r['last']),first_ts=r['first'],last_ts=r['last'],count=r['count'],
                    active=now-r['last']<=self.settings.expiry_seconds, **self.identifier.identify(obs)))
        return output

    def history(self,key):
        with self.lock:
            return [dict(r) for r in self.db.execute('select id,ts,rssi,metadata,channel,identification from observations where device=? order by ts desc limit ?',(key,self.settings.history_limit))][::-1]

    def stats(self,devices,now):
        from collections import Counter
        with self.lock:
            tech=dict(self.db.execute('select tech,sum(count) from devices group by tech').fetchall())
            timeline=[dict(r) for r in self.db.execute('select cast(ts/60 as integer)*60 as minute,count(*) as observations from observations where ts>=? group by minute order by minute',(now-3600,))]
            new=[dict(r) for r in self.db.execute('select cast(first/60 as integer)*60 as minute,count(*) as devices from devices where first>=? group by minute order by minute',(now-3600,))]
            channels={str(r[0]):r[1] for r in self.db.execute('select channel,count(*) from observations where channel is not null group by channel')}
        target_classes={k:sum(1 for d in devices if d.get('classification')==k) for k in TARGET_CLASSES}
        return dict(channel_activity=channels,physical_devices_estimate=None,physical_devices_note='No se estima el número de equipos físicos ni se enlazan direcciones privadas.',manufacturers=len({d['brand'] for d in devices if d['brand']!='Desconocido'}),total=len(devices),active=sum(d['active'] for d in devices),unknown=sum(d['brand']=='Desconocido' for d in devices),identified=sum(d['brand']!='Desconocido' for d in devices),
                    classified=sum(1 for d in devices if d.get('classification') in TARGET_CLASSES),
                    target_classes=target_classes,classifications=dict(Counter(d.get('classification','Sin clasificar') for d in devices)),
                    observations=tech,categories=dict(Counter(d['category'] for d in devices)),brands=dict(Counter(d['brand'] for d in devices)),technologies=dict(Counter(d['tech'] for d in devices)),
                    signals=dict(Counter('Sin RSSI' if d['rssi'] is None else '≥ -50' if d['rssi']>=-50 else '-70 a -51' if d['rssi']>=-70 else '< -70' for d in devices)),timeline=timeline,new_per_minute=new)

    def cleanup(self,now):
        cutoff=now-self.settings.retention_days*86400
        with self.lock:
            self.db.execute('delete from observations where ts<?',(cutoff,))
            self.db.execute('delete from devices where last<?',(cutoff,))
            self.db.execute('delete from errors where ts<?',(cutoff,))
            self.db.execute('delete from calibration_sessions where started<?',(cutoff,))
            self.db.commit()

    def error(self,message,now):
        with self.lock:
            self.db.execute('insert into errors(ts,message) values(?,?)',(now,str(message)[:400])); self.db.execute('delete from errors where id not in (select id from errors order by id desc limit 200)'); self.db.commit()

    def errors(self):
        with self.lock: return [dict(r) for r in self.db.execute('select * from errors order by id desc limit 50')]

    def reset(self):
        with self.lock:
            self.db.executescript('delete from devices; delete from observations;'); self.db.commit()
