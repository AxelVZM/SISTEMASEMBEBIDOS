"""Calibrate from time-bounded observations of one explicitly authorized address."""
import json, math, statistics, uuid
from pydantic import BaseModel, Field
from typing import Literal
class StartCalibration(BaseModel):
    device_id: str = Field(min_length=1,max_length=64)
    authorized: Literal[True]
class CaptureCalibration(BaseModel):
    distance: Literal[1,3,5,10]
    seconds: int = Field(default=15,ge=5,le=120)

def fit_measurements(measurements):
    points={m['distance']:m for m in measurements if m.get('count',0)>=5}
    if set(points)!={1,3,5,10}:return {'valid':False,'reason':'Se requieren al menos 5 lecturas a 1, 3, 5 y 10 metros.'}
    xs=[math.log10(d) for d in sorted(points)];ys=[points[d]['median'] for d in sorted(points)]
    xm=statistics.mean(xs);ym=statistics.mean(ys)
    slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
    reference=ym-slope*xm;n=-slope/10
    residual=sum((y-reference-slope*x)**2 for x,y in zip(xs,ys));total=sum((y-ym)**2 for y in ys)
    result=dict(valid=False,rssi_ref=round(reference,3),loss_n=round(n,4),rmse_db=round(math.sqrt(residual/len(xs)),3),r_squared=round(1-residual/total,4) if total else None,
        quality='Baja: modelo RSSI, no medición exacta',warning='Ajuste válido sólo para este emisor/entorno. Obstáculos, orientación y potencia alteran la distancia.')
    if not 1<=n<=6 or not -100<=reference<=-20:result['reason']='Los parámetros quedan fuera de los límites del modelo; repetir mediciones.'
    elif total==0 or result['r_squared']<0.5:result['reason']='La señal no decrece consistentemente con la distancia; repetir mediciones.'
    else:result['valid']=True
    return result
class Calibration:
    def __init__(self,store):self.store=store
    def _row(self,identifier):
        row=self.store.db.execute('select * from calibration_sessions where id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('Sesión de calibración inexistente.')
        return row
    def start(self,device,now):
        with self.store.lock,self.store.db:
            if self.store.db.execute('select 1 from devices where id=?',(device,)).fetchone() is None:raise ValueError('Selecciona una dirección realmente observada.')
            identifier=uuid.uuid4().hex
            self.store.db.execute('insert into calibration_sessions(id,device,started,samples) values(?,?,?,?)',(identifier,device,now,json.dumps({'measurements':[],'capture':None})))
        return self.status(identifier,now)
    def status(self,identifier,now):
        with self.store.lock:
            row=self._row(identifier);samples=json.loads(row['samples']);capture=samples['capture']
            if capture:
                readings=[r[0] for r in self.store.db.execute('select rssi from observations where device=? and ts>=? and ts<=? and rssi is not null order by ts limit 5000',(row['device'],capture['start'],min(now,capture['end'])))]
                capture.update(received=len(readings),remaining_seconds=max(0,round(capture['end']-now,1)))
                if now>=capture['end']:
                    measurement=dict(distance=capture['distance'],count=len(readings),median=statistics.median(readings) if readings else None,stdev=round(statistics.pstdev(readings),2) if readings else None,start=capture['start'],end=capture['end'])
                    samples['measurements']=[m for m in samples['measurements'] if m['distance']!=measurement['distance']]+[measurement];samples['capture']=None
                    self.store.db.execute('update calibration_sessions set samples=?,fit=? where id=?',(json.dumps(samples),json.dumps(fit_measurements(samples['measurements'])),identifier));self.store.db.commit()
            return dict(id=identifier,device_id=row['device'],started=row['started'],**samples,fit=fit_measurements(samples['measurements']),applied=bool(row['applied']))
    def capture(self,identifier,distance,seconds,now):
        status=self.status(identifier,now)
        if status['capture']:raise ValueError('Ya hay una ventana de captura activa.')
        if now-status['started']>3600:raise ValueError('La sesión caducó. Inicia otra calibración.')
        with self.store.lock,self.store.db:
            samples=dict(measurements=status['measurements'],capture=dict(distance=distance,start=now,end=now+seconds))
            self.store.db.execute('update calibration_sessions set samples=?,applied=0 where id=?',(json.dumps(samples),identifier))
        return self.status(identifier,now)
    def mark_applied(self,identifier):
        with self.store.lock,self.store.db:self.store.db.execute('update calibration_sessions set applied=1 where id=?',(identifier,))
