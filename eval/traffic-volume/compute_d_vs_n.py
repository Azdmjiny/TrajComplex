"""No-gate raw log-log slope versus N for all 720 raw hourly scenes."""
import json, time
from pathlib import Path
import numpy as np
from scipy.spatial.distance import pdist

BASE=Path(__file__).resolve().parent
OUT=BASE/'results'; OUT.mkdir(exist_ok=True)
GRID=np.array(json.load(open(BASE/'radius-grid.json'))['radii'],float)
ORDERS=20
meta=json.load(open(BASE/'encoding-summary.json'))
bykey={r['key']:r for r in meta['rows']}

def raw_slope(V, radii=GRID):
    if len(V)<2: return None
    d=np.sort(pdist(V,metric='euclidean'))
    if d.size==0 or not np.isfinite(d).all(): return None
    c=np.searchsorted(d,radii,side='left')/d.size
    ok=(c>0)&(c<1)
    r=radii[ok]; cc=c[ok]
    if len(r)<2: return None
    lr=np.log(r); lc=np.log(cc)
    cr=lr-lr.mean(); cC=lc-lc.mean()
    den=float(cr@cr)
    if den<=np.finfo(float).eps: return None
    slope=float((cr@cC)/den)
    return slope

rows=[]; t0=time.time()
archive=np.load(BASE/'embeddings.npz')
for fi,key in enumerate(sorted(archive.files),1):
    m=bykey[key]
    V=np.asarray(archive[key],float); N=len(V)
    rng=np.random.default_rng(20261026+fi)
    orders=[rng.permutation(N) for _ in range(ORDERS)]
    curve=[]; valid=[]
    for n in range(5,N+1):
        vals=[raw_slope(V[o[:n]]) for o in orders]
        vals=[x for x in vals if x is not None and np.isfinite(x)]
        curve.append(float(np.median(vals)) if vals else None)
        valid.append(len(vals))
    rows.append(dict(key=key,local_date=m['local_date'],local_hour=m['local_hour'],N=N,curve=curve,valid=valid))
    if fi%80==0: print(f'{fi}/720, {time.time()-t0:.0f}s',flush=True)
json.dump(dict(orders=ORDERS,start_n=5,config='raw log-log slope; all scales with 0<C(r)<1; no C bounds, no radius-ratio gate, no R2 gate, min 2 scales',rows=rows),
          open(OUT/'d-vs-n-no-gate.json','w'),indent=2)
print('DONE',len(rows),'sec',round(time.time()-t0,1))
