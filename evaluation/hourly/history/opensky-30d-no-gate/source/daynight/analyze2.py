"""Robust day/night Plan A summary and Plan C Tobit sensitivity."""
import json, numpy as np
from pathlib import Path
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
SRC=ROOT/'deliverables/opensky-30d-daynight-2026-10-26'
rows=json.load(open(ROOT/'deliverables/opensky-30d-no-gate-2026-10-26/results/d-vs-n-no-gate.json'))['rows']
obs=[]
for r in rows:
    if not r['curve']: continue
    obs.append(dict(key=r['key'],day=r['local_date'],hour=r['local_hour'],N=r['N'],D=r['curve'][-1],
                    night=0 if 7<=r['local_hour']<19 else 1))
assert len(obs)==718

def design(obs): return np.array([[1,r['N'],r['night'],r['N']*r['night']] for r in obs],float)
def nll_factory(obs,c,N0):
    X=design(obs); y=np.array([r['D'] for r in obs]); cens=np.array([r['N']<N0]); yo=np.where(cens,c,y)
    def nll(th):
        b=th[:4]; s=np.exp(th[4]); mu=X@b
        ll=np.where(cens,norm.logcdf((c-mu)/s),norm.logpdf((yo-mu)/s)-np.log(s))
        return -ll.sum()
    return nll

def fit_global(obs,c=1.0,N0=20):
    nll=nll_factory(obs,c,N0)
    bounds=[(0,2),(-.02,.05),(-1.5,1),(-.02,.05),(-4,0)]
    r=differential_evolution(nll,bounds,seed=20261026,tol=1e-7,polish=True,maxiter=400,popsize=10)
    return r.x,r.fun

def fit_local(obs,c=1.0,N0=20,start=None):
    nll=nll_factory(obs,c,N0)
    if start is None: start=np.array([1.4,.005,-.2,.005,np.log(.25)])
    r=minimize(nll,start,method='L-BFGS-B')
    return r.x,r.fun

c=1.0; N0=20
main,main_nll=fit_global(obs,c,N0)
# cluster bootstrap
rng=np.random.default_rng(20261026); days=sorted({r['day'] for r in obs}); boots=[]
for _ in range(200):
    pick=rng.choice(days,len(days),replace=True)
    sample=[r for d in pick for r in obs if r['day']==d]
    b,_=fit_local(sample,c,N0,main)
    boots.append(b)
boots=np.array(boots)
ci={n:[float(np.percentile(boots[:,i],2.5)),float(np.percentile(boots[:,i],97.5))] for i,n in enumerate(['intercept','N','night','Nxnight'])}
# sensitivity
sens=[]
for cc in [0.8,1.0,1.2]:
    for nn in [15,20,30]:
        b,nll=fit_global(obs,cc,nn)
        sens.append(dict(floor=cc,N_threshold=nn,beta=b.tolist(),nll=float(nll),
                         night_effect_at_25=float(b[2]+25*b[3]),night_effect_at_30=float(b[2]+30*b[3]),
                         night_effect_at_35=float(b[2]+35*b[3])))
# exact-N A summaries
curve_by={r['key']:r for r in rows}; a_curve={}
for n in range(5,55):
    for label,flag in [('day',0),('night',1)]:
        vals=[]
        for r in obs:
            if r['night']!=flag: continue
            cr=curve_by[r['key']]['curve']
            if n<=r['N'] and cr[n-5] is not None: vals.append(cr[n-5])
        if vals:
            a_curve.setdefault(str(n),{})[label]=dict(n=len(vals),median=float(np.median(vals)),
                p10=float(np.percentile(vals,10)),p90=float(np.percentile(vals,90)))
json.dump(dict(main=dict(beta=main.tolist(),sigma=float(np.exp(main[4])),nll=float(main_nll)),
               ci=ci,sensitivity=sens,exact_full=a_curve,floor=c,N_threshold=N0,
               day_definition='07:00<=local_hour<19:00',n_day=sum(r['night']==0 for r in obs),n_night=sum(r['night']==1 for r in obs)),
          open(SRC/'results/daynight-model.json','w'),indent=2)
print('main',main,np.exp(main[4]),main_nll); print('ci',ci)
for s in sens: print(s['floor'],s['N_threshold'],np.round(s['beta'],3),'N30',round(s['night_effect_at_30'],3))
