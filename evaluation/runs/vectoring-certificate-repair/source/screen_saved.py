"""Screen frozen references only. Never import Encoder, D or correlation code."""
from pathlib import Path
import sys,json,time,hashlib,argparse
R=Path(__file__).resolve().parent;B=R.parent
CODE=B/'changi-publication-repo/evaluation/code';OLD=B/'vectoring-time-window-sensitivity-2026-10-27'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(CODE)]
import numpy as np
from scipy.interpolate import make_interp_spline
import vectoring_reference as ref
import vectoring_path as path
original_solver=path.minimize
def logged_solver(*a,**kw):
    fitted=original_solver(*a,**kw)
    print(json.dumps(dict(event='solver_return',success=bool(fitted.success),iterations=int(fitted.nit),message=str(fitted.message))),flush=True)
    return fitted
path.minimize=logged_solver
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--aircraft',nargs='*');parser.add_argument('--old-accepted',action='store_true');args=parser.parse_args()
out=R/args.output;out.mkdir(parents=True,exist_ok=False)
protected={str(p):sha(p) for folder in [OLD/'screening',OLD/'window-15s',OLD/'window-20s',B/'four-scene-vectoring-screen/screening',B/'vectoring-15km-star-2026-10-24/population-15km'] for p in folder.rglob('*') if p.is_file()}
codes={p.name:sha(p) for p in CODE.glob('vectoring_*.py')}
write(out/'manifest.json',dict(state='running',code_sha256=codes,protected_sources=protected,policy=path.policy(),new_reference_fits=0,new_encoder_calls=0,new_D_calls=0,physical_threshold_changes=0))
records=read(OLD/'screening/summary.json')['new_candidates']
tasks=[]
for r in records:
    if args.aircraft and r['icao24'] not in args.aircraft:continue
    tasks.append((r,OLD/'screening/references',False))
if args.old_accepted:
    active=B/'changi-publication-repo/evaluation/runs/segmented-15km/population'
    for f in sorted(active.glob('*-records.json')):
        for r in read(f):
            if not r['segmented_injectable']:continue
            r=dict(r,scene=f.name.removesuffix('-records.json'),reference_pass=True,paired_injectable=True)
            tasks.append((r,B/'four-scene-vectoring-screen/screening/references',True))
tasks.sort(key=lambda x:(x[0]['icao24']!='3c6709',x[0]['scene'],x[0]['icao24']))
results=[]
for old,refs,cached in tasks:
    sid,a=old['scene'],old['icao24'];started=time.monotonic()
    result=dict(scene=sid,icao24=a,origin='original_10s' if cached else 'new_quality_window',quality_windows=old.get('quality_windows'),old_paired_injectable=old['paired_injectable'],stages={},paired_injectable=False)
    arrays={}
    if not old['reference_pass']:
        result.update(status='unchanged_reference_rejection',reasons=old['rejection_reasons'])
    else:
        with np.load(refs/(sid+'-'+a+'.npz')) as z:
            ts=z['times'];zero=np.zeros(len(ts))
            fitted=ref.WholeTrackFit(float(z['epoch']),ts,z['raw_xy'],z['fitted_xy'],z['origin'],z['radii'],None,{})
            fitted.mapping=make_interp_spline(ts,np.eye(len(ts)),k=5,bc_type=([(3,zero),(4,zero)],[(3,zero),(4,zero)]))
            grid=z['grid'];reference=ref.maneuver_reference(fitted,grid,(len(grid)-60)//2)
        for peak in [5000.,15000.]:
            path.PEAK=peak;both=True
            for side,name in [(-1,'left'),(1,'right')]:
                detail={};begin=time.monotonic()
                try:
                    q=path.generate(reference,side,detail,sample_s=10)
                    arrays[f'{int(peak)}_{name}']=q;detail['accepted']=True
                except path.PathRejected as exc:
                    both=False;detail.update(accepted=False,rejection_reason=str(exc),last_witness=getattr(exc,'witness',None))
                detail['elapsed_s']=time.monotonic()-begin
                result['stages'].setdefault(str(int(peak)),{})[name]=detail
                write(out/(sid+'-'+a+'-in-progress.json'),result)
                print(json.dumps(dict(scene=sid,icao24=a,peak=peak,side=name,accepted=detail['accepted'],reason=detail.get('rejection_reason'),feedback=len(detail.get('failure_feedback',[])),solver_iterations=detail.get('solver_budget_used'),elapsed_s=detail['elapsed_s'])),flush=True)
            if not both:break
        result['paired_injectable']=both and '15000' in result['stages']
        result['status']='accepted' if result['paired_injectable'] else 'route_rejected'
        if result['paired_injectable']:
            for side,name in [(-1,'left'),(1,'right')]:
                arrays['segmented_'+name]=path.generate_segmented(reference,side,peak=15000.,sample_s=10.)
    result['elapsed_s']=time.monotonic()-started
    np.savez_compressed(out/(sid+'-'+a+'-routes.npz'),**arrays)
    write(out/(sid+'-'+a+'-record.json'),result);results.append(result)
    write(out/'summary.json',dict(state='running',records=results))
assert all(sha(Path(p))==h for p,h in protected.items())
write(out/'summary.json',dict(state='complete',records=results))
m=read(out/'manifest.json');m.update(state='complete',protected_sources_unchanged=True,code_unchanged=all(sha(CODE/name)==h for name,h in codes.items()))
write(out/'manifest.json',m)
print('SCREENING COMPLETE',flush=True)
