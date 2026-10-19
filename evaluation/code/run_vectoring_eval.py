import csv,json,sys,zipfile,math,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.distance import pdist

import run_holding_eval as h
from complexity.calculator import ComplexityConfig,estimate_complexity
import torch
from Encoder.trajectory_encoder.inference import FrozenEncoder

BASE=Path(__file__).resolve().parents[1] / 'results'
OUT=BASE/'synthetic-vectoring-evaluation-pilot.json'
RAW=json.loads((BASE/'synthetic-holding-evaluation-pilot.json').read_text(encoding='utf8'))
SIDS=sorted({x['scene_id'] for x in RAW['scenes']})
TURN_S=300; RETURN_S=300; SAMPLE=5; MAX_OFFSET=5000.; REPEATS=5; SEED=43019

def add_vectoring(p,side):
    # A 10-minute smooth lateral bump: 5 min to max offset, then 5 min back.
    half=int(TURN_S/SAMPLE); total=2*half
    if len(p)<total+1: raise ValueError('track shorter than vectoring maneuver duration')
    start=(len(p)-total)//2
    end=start+total+1
    q=p.copy(); seg=p[start:end]
    u=np.linspace(0.,1.,len(seg))
    offset=MAX_OFFSET*0.5*(1-np.cos(2*np.pi*u))*side
    tangent=np.gradient(seg[:,:2],axis=0)
    norm=np.linalg.norm(tangent,axis=1,keepdims=True)
    tangent=tangent/np.maximum(norm,1e-9)
    normal=np.column_stack((-tangent[:,1],tangent[:,0]))
    q[start:end,:2]=seg[:,:2]+offset[:,None]*normal
    return q,start,end

def est(emb,radii,cfg,sid):
    r=estimate_complexity(emb,config=cfg,radii=radii,scene_id=sid)
    return {'status':r.status,'reason':r.reason,'dimension':r.dimension,'r_squared':r.r_squared,'n_samples':r.n_samples,'n_fit_scales':len(r.fit_indices)}

def main():
    dev='cuda' if torch.cuda.is_available() else 'cpu'; enc=FrozenEncoder(h.CHECKPOINT,pooling='sum',device=dev)
    cfg=ComplexityConfig(normalize=False); results=[]
    with zipfile.ZipFile(h.DATA_ZIP) as z:
      for si,sid in enumerate(SIDS,1):
        tracks=h.read_scene(z,f'OpenSky_Changi_2026-09/sampled_10s/{sid}.csv.gz')
        ids=sorted(tracks); eligible=[i for i,k in enumerate(ids) if len(tracks[k])>=121]
        emb=np.asarray([enc.encode(tracks[k])['embedding'] for k in ids]); d=pdist(emb); positive=d[d>0]
        if len(positive)<2: continue
        radii=np.geomspace(float(positive.min()),float(positive.max()),cfg.n_radii)
        base=est(emb,radii,cfg,sid); scene_reps=[]
        print(f'[{si}/{len(SIDS)}] {sid}: N={len(ids)}, vectoring-eligible={len(eligible)}, baseline D={base["dimension"]}',flush=True)
        for rep in range(REPEATS):
          rng=np.random.default_rng(SEED+si*997+rep); order=rng.permutation(eligible); cur=emb.copy(); curve=[{'vectoring_aircraft':0,'vectoring_fraction_of_eligible':0.,**base}]
          for k,idx in enumerate(order,1):
            side=int(rng.choice([-1,1])); modified,start,end=add_vectoring(tracks[ids[int(idx)]],side)
            cur[int(idx)]=enc.encode(modified)['embedding']; r=est(cur,radii,cfg,sid)
            curve.append({'vectoring_aircraft':k,'vectoring_fraction_of_eligible':k/len(eligible),'side':side,'start_index':start,'end_index':end,**r})
            if k%25==0: print(f'  rep {rep+1}/{REPEATS}, vectoring {k}/{len(eligible)}, D={r["dimension"]}',flush=True)
          scene_reps.append({'scene_id':sid,'replicate':rep,'n_aircraft':len(ids),'n_vectoring_eligible':len(eligible),'dose_curve':curve})
          obj={'experiment':'smooth lateral vectoring injection and scene correlation dimension','checkpoint':h.CHECKPOINT.name,'checkpoint_sha256':hashlib.sha256(h.CHECKPOINT.read_bytes()).hexdigest(),'device':dev,'encoder_pooling':'sum','distance':'Euclidean, unnormalized embeddings','preprocessor_id':'d69735dd5a1587c6720a4f5867a860e6a3b47fdb9ba81b239f80e1dfa5afeb35','maneuver':{'outbound_seconds':TURN_S,'return_seconds':RETURN_S,'max_lateral_offset_m':MAX_OFFSET,'profile':'offset = max/2 * (1 - cos(2*pi*u)), u from 0 to 1 over 10 minutes; smooth start, midpoint, and return','side':'randomly selected left/right for each aircraft intervention','altitude':'unchanged','speed':'original sample times and speed retained; coordinates shifted laterally','insertion':'centered on trajectory midpoint; original start/end positions preserved'},'scene_selection':SIDS,'repeats_per_scene':REPEATS,'complexity_config':cfg.__dict__,'completed_scene_replicates':len(results)+len(scene_reps),'scenes':results+scene_reps}
          OUT.write_text(json.dumps(obj,indent=2),encoding='utf8')
        results.extend(scene_reps)
    print('finished',OUT,'replicates',sum(len(x) for x in results),flush=True)
if __name__=='__main__': main()
