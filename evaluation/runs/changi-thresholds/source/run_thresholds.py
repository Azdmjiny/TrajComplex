"""Threshold review: 3h rolling primary D, 1h low-threshold exploratory D.

Reads the frozen dedup hourly embeddings and radius grid only. No Encoder calls.
"""
import hashlib, json, sys
from datetime import date
from pathlib import Path
import numpy as np

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
REPO=ROOT/'tmp/WM4ATM'
BASE=ROOT/'deliverables/changi-dedup-evaluation-2026-10-26'
OUT=ROOT/'deliverables/changi-threshold-review-2026-10-26'
sys.path[:0]=[str(REPO),str(ROOT/'deliverables/evaluation-python-deps')]
from complexity.calculator import ComplexityConfig,estimate_complexity

DATES=('2026-09-08','2026-09-11')
GRID=np.array(json.load(open(BASE/'radius-grid.json'))['radii'],float)
assert GRID.shape==(64,)

def load(day,hour):
    z=np.load(BASE/'embeddings'/f'{day}-1h-{hour:02d}.npz')
    ids=[str(x) for x in z['aircraft_ids'].tolist()]
    return ids,np.asarray(z['embeddings'],float)

def d(emb,min_samples,min_r2=0.94,scene=''):
    cfg=ComplexityConfig(min_samples=min_samples,min_r_squared=min_r2)
    return estimate_complexity(emb,config=cfg,radii=GRID,scene_id=scene).to_dict()

def stable_seed(label):
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8],'big')

rows=[]
for day in DATES:
    hour_data={h:load(day,h) for h in range(24)}
    for h in range(24):
        wins=[x for x in (h-1,h,h+1) if 0<=x<24]
        keep=[];seen=set()
        # Prefer the centre hour, then preceding, then following.
        order=[h]+[x for x in wins if x!=h]
        for x in order:
            ids,emb=hour_data[x]
            for ident,vec in zip(ids,emb):
                if ident not in seen:
                    seen.add(ident);keep.append(vec)
        v=np.asarray(keep)
        rec={'date':day,'hour':h,'window_hours':wins,'N':len(v)}
        rec['full']=d(v,30,0.90,f'{day}-3h-{h:02d}')
        # Fixed-N=30 stability, only if full N>=30.
        if len(v)>=30:
            rng=np.random.default_rng(stable_seed(f'changi-threshold-3h|{day}|{h}'))
            draws=[d(v[rng.choice(len(v),30,replace=False)],30,0.90) for _ in range(200)]
            ok=[x['dimension'] for x in draws if x['status']=='ok']
            rec['fixed30']={'valid':len(ok),'attempted':200,
                            'median':float(np.median(ok)) if ok else None,
                            'low':float(np.quantile(ok,.025)) if ok else None,
                            'high':float(np.quantile(ok,.975)) if ok else None,
                            'reasons':sorted({x['reason'] for x in draws if x['status']!='ok'})}
        else:
            rec['fixed30']={'valid':0,'attempted':0,'median':None,'low':None,'high':None,'reasons':['insufficient_samples']}
        # 1h exploratory variants.
        ids1,e1=hour_data[h]
        rec['one_hour']={'N':len(e1),'n20_r90':d(e1,20,0.90,f'{day}-1h-{h:02d}'),
                         'n15_r90':d(e1,15,0.90,f'{day}-1h-{h:02d}')}
        rows.append(rec)

json.dump(rows,open(OUT/'results/threshold-review.json','w'),indent=2)
for day in DATES:
    rr=[r for r in rows if r['date']==day]
    print(day)
    print(' 3h full ok',sum(r['full']['status']=='ok' for r in rr),'/24',
          'N range',min(r['N'] for r in rr),max(r['N'] for r in rr))
    print(' 3h fixed30 ok',sum(r['fixed30']['valid']==200 for r in rr),'/24')
    print(' 1h N20/R90 ok',sum(r['one_hour']['n20_r90']['status']=='ok' for r in rr),'/24')
    print(' 1h N15/R90 ok',sum(r['one_hour']['n15_r90']['status']=='ok' for r in rr),'/24')
    for r in rr:
        print(f"  {r['hour']:02d} N={r['N']:3d} 3h={r['full']['status']:12s} {str(r['full']['dimension'])[:6]:6s} "
              f"1hN={r['one_hour']['N']:2d} 1h={r['one_hour']['n20_r90']['status']:12s}")

