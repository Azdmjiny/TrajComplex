"""Pilot: D versus number of aircraft in one frozen hourly scene.

Nested random orders: start at 5 aircraft, add one at a time to the full
scene. D is exploratory at low N (min_fit_points=4, R2>=0.90); the standard
gate (min_fit_points=8, R2>=0.94) is shown for comparison where estimable.
"""
import json, sys
from pathlib import Path
import numpy as np

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
REPO=ROOT/'tmp/WM4ATM'
BASE=ROOT/'deliverables/changi-dedup-evaluation-2026-10-26'
OUT=ROOT/'deliverables/changi-n-scaling-2026-10-26'
sys.path[:0]=[str(REPO),str(ROOT/'deliverables/evaluation-python-deps')]
from complexity.calculator import ComplexityConfig,estimate_complexity

KEY='2026-09-08-1h-20'
GRID=np.array(json.load(open(BASE/'radius-grid.json'))['radii'],float)
z=np.load(BASE/'embeddings'/f'{KEY}.npz'); V=np.asarray(z['embeddings'],float)
N=len(V); assert N==56
ORDERS=100
rng=np.random.default_rng(20261026)
orders=[rng.permutation(N) for _ in range(ORDERS)]
rows=[]
for n in range(5,N+1):
    vals=[]; vals_std=[]; reasons=[]
    for order in orders:
        sub=V[order[:n]]
        r=estimate_complexity(sub,config=ComplexityConfig(min_samples=n,min_fit_points=4,min_r_squared=.90),radii=GRID,scene_id=f'{KEY}-n{n}').to_dict()
        if r['status']=='ok': vals.append(r['dimension'])
        else: reasons.append(r['reason'])
        rs=estimate_complexity(sub,config=ComplexityConfig(min_samples=n,min_fit_points=8,min_r_squared=.94),radii=GRID,scene_id=f'{KEY}-n{n}-std').to_dict()
        if rs['status']=='ok': vals_std.append(rs['dimension'])
    row={'n':n,'attempted':ORDERS,'valid':len(vals),'valid_std':len(vals_std),
         'median':float(np.median(vals)) if vals else None,
         'p10':float(np.percentile(vals,10)) if vals else None,
         'p90':float(np.percentile(vals,90)) if vals else None,
         'median_std':float(np.median(vals_std)) if vals_std else None,
         'reasons':dict((k,reasons.count(k)) for k in sorted(set(reasons)))}
    rows.append(row)
    print(n,row['valid'],round(row['median'],3) if row['median'] is not None else None,row['valid_std'],round(row['median_std'],3) if row['median_std'] is not None else None)
json.dump({'scene':KEY,'N':N,'orders':ORDERS,'config_low':{'min_fit_points':4,'min_r_squared':.90,'min_samples':'n'},
           'config_standard':{'min_fit_points':8,'min_r_squared':.94,'min_samples':'n'},'rows':rows},
          open(OUT/'d_vs_n.json','w'),indent=2)
