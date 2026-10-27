"""Encode all 720 raw hourly scenes, no candidate/QC/dedup screening."""
import gzip, json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
REPO=ROOT/'tmp/WM4ATM'
SRC=ROOT/'deliverables/opensky-month-coverage/source-tracks'
OUT=ROOT/'deliverables/opensky-30d-no-gate-2026-10-26'
sys.path[:0]=[str(REPO),str(ROOT/'deliverables/evaluation-python-deps'),str(REPO/'evaluation/code')]
from Encoder.trajectory_encoder.inference import FrozenEncoder
from position_timeline import position_grid,resample_positions
from vectoring_inputs import llh_to_enu
import torch

ckpt=ROOT/'deliverables/encoder-10s/encoder/encoder.pt'
device='cuda' if torch.cuda.is_available() else 'cpu'
enc=FrozenEncoder(ckpt,pooling='sum',device=device)
assert enc.preprocess['preprocessing']['stride_s']==10
files=sorted(SRC.glob('2026-*.json.gz'))
assert len(files)==720
rows=[]; t0=time.time(); total=0; failures=[]
for fi,p in enumerate(files,1):
    key=p.name.replace('.json.gz','')
    utc=datetime.fromisoformat(key.replace('Z','+00:00'))
    local=utc+timedelta(hours=8)
    with gzip.open(p,'rt',encoding='utf8') as f: tracks=json.load(f)
    ids=[]; embs=[]
    for t in tracks:
        raw=np.asarray(t.get('source_records',[]),float)
        try:
            grid=position_grid(raw,10)
            enu=llh_to_enu(raw[:,1],raw[:,2],raw[:,3])
            q=resample_positions(raw,enu,grid)
            if len(q)<30 or not np.isfinite(q).all():
                failures.append(dict(key=key,icao24=t.get('icao24'),reason='encoder_input_invalid')); continue
            e=enc.encode(q)['embedding']
            if e.shape!=(16,) or not np.isfinite(e).all():
                failures.append(dict(key=key,icao24=t.get('icao24'),reason='embedding_invalid')); continue
            ids.append(str(t.get('icao24'))); embs.append(e)
        except Exception as exc:
            failures.append(dict(key=key,icao24=t.get('icao24'),reason=type(exc).__name__+':'+str(exc)[:80]))
    v=np.asarray(embs,float)
    np.savez_compressed(OUT/'embeddings'/f'{key}.npz',embeddings=v,aircraft_ids=np.asarray(ids))
    rows.append(dict(key=key,local_date=str(local.date()),local_hour=int(local.hour),N=len(ids),raw_tracks=len(tracks)))
    total+=len(ids)
    if fi%40==0: print(f'{fi}/720 hours, {total} embeddings, {len(failures)} failures, {time.time()-t0:.0f}s',flush=True)
json.dump(dict(rows=rows,failures=failures,total_embeddings=total,device=device,checkpoint=str(ckpt)),
          open(OUT/'encoding-summary.json','w'),indent=2)
print('DONE',total,'failures',len(failures),'sec',round(time.time()-t0,1))
