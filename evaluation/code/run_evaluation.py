"""Rebuild corrected evaluation outputs in the canonical evaluation directories.

No checkpoint or raw data is committed. Set ATM_DATA_ZIP and
ATM_ENCODER_CHECKPOINT before running. The original 12 scenes and seed ordering
are frozen below so QC does not silently select easier replacement scenes.
"""
import argparse,hashlib,json,sys,zipfile,time,csv
from pathlib import Path
import numpy as np
from scipy.spatial.distance import pdist
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
import run_holding_eval as h
import run_vectoring_eval as v
from Encoder.trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig,estimate_complexity
import torch

SCENES=['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z','2026-09-12T15Z','2026-09-15T06Z','2026-09-18T00Z','2026-09-20T04Z','2026-09-23T10Z','2026-09-25T23Z','2026-09-28T07Z','2026-09-30T15Z']
VARIANTS={'qc500':500.,'qc350':350.,'qc500_safe':500.,'qc350_safe':350.}
def dump(name,obj):
    (ROOT/'results'/name).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--counts-only',action='store_true');args=ap.parse_args()
    torch.set_num_threads(2);cfg=ComplexityConfig(normalize=False)
    sha=hashlib.sha256(h.CHECKPOINT.read_bytes()).hexdigest()
    expected='d3abfc192a2e7a0f84bb1c4207ee04cfc4a4880755530da475124c5f711753ea'
    if sha!=expected:raise ValueError('Checkpoint differs from the frozen pilot checkpoint')
    enc=FrozenEncoder(h.CHECKPOINT,pooling='sum',device='cuda' if torch.cuda.is_available() else 'cpu')
    results={name:{kind:dict(variant=name,kind=kind,scenes=[]) for kind in ['holding','vectoring'] if not(name.endswith('_safe') and kind=='holding')} for name in VARIANTS}
    counts={v:[] for v in ['legacy_replay','qc500','qc350']};countrows=[];quality=[];geometry=[];start=time.time()
    with zipfile.ZipFile(h.DATA_ZIP) as z:
      for si,sid in enumerate(SCENES,1):
        member=f'OpenSky_Changi_2026-09/sampled_10s/{sid}.csv.gz'
        tracks=h.read_scene(z,member,max_horizontal_speed=None);ids=sorted(tracks);kept={}
        for name,limit in [('qc500',500.),('qc350',350.)]:
            aa=[];kept[name]=set(h.read_scene(z,member,max_horizontal_speed=limit,audit=aa))
            quality.append(dict(scene=sid,variant=name,before=len(ids),after=len(kept[name]),rejected=[r for r in aa if r['reasons']]))
        base=np.asarray([enc.encode(tracks[k])['embedding'] for k in ids])
        if not args.counts_only:
            fixed=np.asarray([enc.encode(h.add_racetrack(tracks[k])[0])['embedding'] for k in ids])
            eligible=[i for i,k in enumerate(ids) if len(tracks[k])>=121];left=base.copy();right=base.copy();speed_ok=set()
            for i in eligible:
                speeds=[]
                for side,arr in [(-1,left),(1,right)]:
                    q,_,_=v.add_vectoring(tracks[ids[i]],side);arr[i]=enc.encode(q)['embedding']
                    speed=float(np.linalg.norm(np.diff(q[:,:2],axis=0),axis=1).max()/5);speeds.append(speed)
                    geometry.append(dict(scene=sid,icao24=ids[i],side=side,max_horizontal_speed_m_s=speed))
                if max(speeds)<=500:speed_ok.add(i)
            for name in VARIANTS:
                retain=kept[name.split('_')[0]];ix=[i for i,k in enumerate(ids) if k in retain];index={j:i for i,j in enumerate(ix)}
                for kind,output in results[name].items():
                    b=base[ix].astype(float) if kind=='holding' else base[ix].copy()
                    pos=pdist(b);pos=pos[pos>0];radii=np.geomspace(pos.min(),pos.max(),64);baseline=h.estimate(b,radii,cfg,sid)
                    usable=[i for i in eligible if i in index and (not name.endswith('_safe') or i in speed_ok)]
                    for rep in range(5):
                        rng=np.random.default_rng((43+si*1009+rep) if kind=='holding' else (43019+si*997+rep))
                        order=rng.permutation(len(ids) if kind=='holding' else eligible)
                        assignments=[(int(j),0 if kind=='holding' else int(rng.choice([-1,1]))) for j in order]
                        assignments=[(j,side) for j,side in assignments if j in index and (kind=='holding' or j in usable)]
                        cur=b.copy();key=kind+'_aircraft';curve=[{key:0,**baseline}]
                        for k,(j,side) in enumerate(assignments,1):
                            cur[index[j]]=fixed[j] if kind=='holding' else (left if side<0 else right)[j]
                            curve.append({key:k,**h.estimate(cur,radii,cfg,sid)})
                        row=dict(scene_id=sid,replicate=rep,n_aircraft=len(ix),dose_curve=curve)
                        if kind=='vectoring':row['n_vectoring_eligible']=len(usable)
                        output['scenes'].append(row)
        for name in counts:
            ix=list(range(len(ids))) if name=='legacy_replay' else [i for i,k in enumerate(ids) if k in kept[name]]
            b=base[ix];pos=pdist(b);pos=pos[pos>0];radii=np.geomspace(pos.min(),pos.max(),64);full=estimate_complexity(b,config=cfg,radii=radii)
            for n in [30,40,50]:
                if n>len(b):continue
                vals=[]
                for rep in range(50):
                    sample=np.random.default_rng(42000+si*1000+n*31+rep).choice(len(b),n,replace=False)
                    r=estimate_complexity(b[sample],config=cfg,radii=radii)
                    countrows.append(dict(variant=name,scene_id=sid,n_aircraft=n,replicate=rep,status=r.status,reason=r.reason,D=r.dimension,r_squared=r.r_squared))
                    if r.dimension is not None:vals.append(r.dimension)
                counts[name].append(dict(scene=sid,n=n,full_D=full.dimension,valid=len(vals),repeats=50,valid_rate=len(vals)/50,median_abs_delta=float(np.median(np.abs(np.asarray(vals)-full.dimension))) if vals and full.dimension is not None else None))
        print(f'{si}/12 {sid}; elapsed {time.time()-start:.1f}s',flush=True)
    dump('count-comparison.json',counts)
    dump('aircraft-count-sensitivity.json',dict(primary_variant='qc500',repeats_per_subsample_n=50,target_sample_sizes=[30,40,50],results=counts['qc500'],comparisons=counts,rows=countrows,complexity_config=cfg.__dict__))
    with (ROOT/'results/aircraft-count-sensitivity.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(countrows[0]));w.writeheader();w.writerows(countrows)
    if args.counts_only:return
    dump('experiment-results.json',results);dump('quality_audit.json',quality);dump('injected_geometry_audit.json',geometry)
    dump('run-manifest.json',dict(checkpoint_sha256=sha,device=str(enc.device),torch=torch.__version__,numpy=np.__version__,config=cfg.__dict__,scenes=SCENES,seed_policy='Original order and random sides generated before filtering; survivors keep relative order and side',primary_holding='qc500',primary_vectoring='qc500_safe',thresholds=dict(primary_horizontal_m_s=500,sensitivity_horizontal_m_s=350,vertical_m_s=100,altitude_m=[-500,20000]),source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'code').glob('*.py')}))
    print('Full evaluation saved. Run refresh_outputs.py to rebuild summaries, plots and Markdown.')
if __name__=='__main__':main()
