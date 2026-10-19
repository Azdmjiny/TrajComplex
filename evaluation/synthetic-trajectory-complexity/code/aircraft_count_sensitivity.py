import sys,json,zipfile,csv
from pathlib import Path
import numpy as np
from scipy.spatial.distance import pdist
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_holding_eval as h
from complexity.calculator import ComplexityConfig,estimate_complexity
import torch
from Encoder.trajectory_encoder.inference import FrozenEncoder
base=Path(__file__).resolve().parents[1] / 'results'
raw=json.loads((base/'synthetic-holding-evaluation-pilot.json').read_text(encoding='utf-8'))
scenes=sorted({x['scene_id'] for x in raw['scenes']})
meta_by={x['file']:x for x in json.loads(h.AUDIT.read_text(encoding='utf-8'))['hours']}
enc=FrozenEncoder(h.CHECKPOINT,pooling='sum',device='cuda' if torch.cuda.is_available() else 'cpu')
cfg=ComplexityConfig(normalize=False); reps=50; targets=[30,40,50]
rows=[]; summaries=[]
with zipfile.ZipFile(h.DATA_ZIP) as z:
 for si,sid in enumerate(scenes,1):
  member=f'OpenSky_Changi_2026-09/sampled_10s/{sid}.csv.gz'
  tracks=h.read_scene(z,member); ids=sorted(tracks)
  emb=np.asarray([enc.encode(tracks[k])['embedding'] for k in ids])
  ds=pdist(emb); pos=ds[ds>0]
  if len(pos)<2: continue
  radii=np.geomspace(float(pos.min()),float(pos.max()),cfg.n_radii)
  full=estimate_complexity(emb,config=cfg,radii=radii,scene_id=sid)
  scene_rows=[]
  for n in targets+[len(ids)]:
   if n>len(ids) or (n==targets[-1] and n==len(ids)): pass
   nr=1 if n==len(ids) else reps
   for rep in range(nr):
    idx=np.arange(len(ids)) if n==len(ids) else np.random.default_rng(42000+si*1000+n*31+rep).choice(len(ids),n,replace=False)
    res=estimate_complexity(emb[idx],config=cfg,radii=radii,scene_id=sid)
    row={'scene_id':sid,'n_aircraft':n,'replicate':rep,'status':res.status,'reason':res.reason,'D':res.dimension,'r_squared':res.r_squared}
    rows.append(row); scene_rows.append(row)
  for n in sorted(set(targets+[len(ids)])):
   rr=[r for r in scene_rows if r['n_aircraft']==n]
   vals=[r['D'] for r in rr if r['D'] is not None]
   summaries.append({'scene_id':sid,'n_aircraft':n,'n_repeats':len(rr),'valid_count':len(vals),'valid_rate':len(vals)/len(rr),'D_median':float(np.median(vals)) if vals else None,'D_iqr':float(np.quantile(vals,.75)-np.quantile(vals,.25)) if vals else None,'full_scene_baseline_D':full.dimension,'full_scene_status':full.status,'median_abs_delta_from_full_D':float(np.median(np.abs(np.asarray(vals)-full.dimension))) if vals and full.dimension is not None else None})
  print(f'[{si}/{len(scenes)}] {sid}: {len(ids)} tracks, full D {full.dimension}, status {full.status}',flush=True)
out={'purpose':'Evaluate sensitivity/stability of scene D to aircraft sample count by random subsampling; this does not treat aircraft count as an expected positive complexity label.','selection':scenes,'repeats_per_subsample_n':reps,'target_sample_sizes':targets,'full_sample_size':'all eligible aircraft per scene','complexity_config':cfg.__dict__,'results':summaries,'rows':rows}
(base/'aircraft-count-sensitivity.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
with (base/'aircraft-count-sensitivity.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['scene_id','n_aircraft','replicate','status','reason','D','r_squared']);w.writeheader();w.writerows(rows)
print(json.dumps({'summary':summaries,'out':str(base/'aircraft-count-sensitivity.json')},indent=2))
