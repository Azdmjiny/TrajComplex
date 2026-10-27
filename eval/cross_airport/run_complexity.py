"""Frozen Encoder inference and full-scale correlation slopes."""
import argparse,hashlib,json,os,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist
from scipy.stats import linregress

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fit(p):
    result=dict(dimension=None,r_squared=None,fit_intercept=None,fit_scale_count=0,radius_ratio=None,zero_distance_pairs=None,n_unique=int(len(np.unique(p,axis=0))),unfiltered_status='UNDEFINED',undefined_reason='')
    rr,cc=np.full(64,np.nan),np.full(64,np.nan)
    def fail(reason):
        result['undefined_reason']=reason
        return result,rr,cc
    if not np.isfinite(p).all():return fail('nonfinite_input')
    if len(p)<2:return fail('fewer_than_two_points')
    dist=np.sort(pdist(p.astype(np.float64),metric='euclidean'))
    if not np.isfinite(dist).all():return fail('nonfinite_distances')
    result['zero_distance_pairs']=int(np.count_nonzero(dist==0))
    pos=dist[dist>0]
    if not len(pos):return fail('all_pair_distances_zero')
    if pos[0]==pos[-1]:return fail('no_positive_distance_scale_range')
    rr=np.geomspace(pos[0],pos[-1],64)
    cc=np.searchsorted(dist,rr,side='left')/len(dist)
    ix=np.flatnonzero(cc>0)
    result['fit_scale_count']=len(ix)
    if len(ix)<2:return fail('fewer_than_two_log_defined_scales')
    x,y=np.log(rr[ix]),np.log(cc[ix])
    if np.ptp(x)==0:return fail('no_log_radius_variation')
    slope,intercept=np.linalg.lstsq(np.column_stack([x,np.ones(len(x))]),y,rcond=None)[0]
    if not np.isfinite([slope,intercept]).all():return fail('nonfinite_OLS')
    ss=float(np.sum((y-y.mean())**2))
    r2=float(1-np.sum((y-slope*x-intercept)**2)/ss) if ss>0 else None
    check=linregress(x,y)
    np.testing.assert_allclose([slope,intercept],[check.slope,check.intercept],rtol=1e-9,atol=1e-10)
    if r2 is not None:np.testing.assert_allclose(r2,check.rvalue**2,rtol=1e-9,atol=1e-10)
    result.update(dimension=float(slope),fit_intercept=float(intercept),r_squared=r2,radius_ratio=float(rr[ix[-1]]/rr[ix[0]]),unfiltered_status='COMPUTED_UNFILTERED')
    return result,rr,cc

class SafeFrozenEncoder:
    def __init__(self, checkpoint, device, expected_sha):
        if sha(checkpoint) != expected_sha:
            raise ValueError("Frozen checkpoint SHA256 mismatch")
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.settings, self.preprocess = state["settings"], state["preprocess"]
        assert state["epoch"] == 90 and self.settings["dimension"] == 16
        assert self.settings["pooling"] == "sum" and self.settings["seed"] == 43
        assert self.preprocess["preprocessing"]["min_points"] == 30
        assert self.preprocess["preprocessing"]["stride_s"] == 10
        assert self.preprocess["preprocessing"]["include_endpoint"] is False
        self.device = torch.device(device)
        self.model = TrajectoryEncoder(16, **self.settings["model"])
        self.model.load_state_dict(state["state_dict"], strict=True)
        self.model.eval().requires_grad_(False).to(self.device)
        self.mean = np.array(self.preprocess["mean"])
        self.std = np.array(self.preprocess["std"])


    def encode(self, trajectories, batch_size=32, extra_padding=0):
        if not trajectories:
            return np.empty((0, 16), dtype=np.float32)
        embeddings = []
        for start in range(0, len(trajectories), batch_size):
            batch = trajectories[start:start + batch_size]
            length = max(map(len, batch)) + extra_padding
            x = np.zeros((len(batch), length, 9), dtype=np.float32)
            valid = np.zeros((len(batch), length), dtype=bool)
            for i, p in enumerate(batch):
                assert p.ndim == 2 and p.shape[1] == 3 and len(p) >= 30 and np.isfinite(p).all()
                x[i, :len(p)] = (features(p) - self.mean) / self.std
                valid[i, :len(p)] = True
            tokens = self.model(torch.from_numpy(x).to(self.device), torch.from_numpy(valid).to(self.device))
            embeddings.append(tokens.sum(dim=1).cpu().numpy())
        cloud = np.concatenate(embeddings)
        assert cloud.shape == (len(trajectories), 16) and np.isfinite(cloud).all()
        return cloud

def main():
    global torch,features,TrajectoryEncoder
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    p.add_argument('--hours',type=Path,required=True,help='prepared_hours.csv')
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--device',default='cpu');p.add_argument('--batch-size',type=int,default=32)
    args=p.parse_args()
    cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    if cfg['n_radii']!=64: raise ValueError('This estimator uses exactly 64 radii')
    if args.output.exists(): raise FileExistsError('Choose a new output directory')
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    sys.path.insert(0,str(args.repo_root.resolve()/'Encoder'))
    import torch
    from trajectory_encoder.data import features
    from trajectory_encoder.model import TrajectoryEncoder
    SafeFrozenEncoder.encode=torch.inference_mode()(SafeFrozenEncoder.encode)
    torch.manual_seed(cfg['seed']);torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    enc=SafeFrozenEncoder(args.checkpoint,args.device,cfg['checkpoint_sha256'])
    plan=pd.read_csv(args.hours)
    if plan.duplicated(['airport','hour_utc']).any(): raise ValueError('Duplicate airport/hour')
    args.output.mkdir(parents=True);rows=[]
    for row in plan.itertuples(index=False):
        path=Path(row.prepared_path)
        if not path.is_absolute(): path=args.hours.resolve().parent/path
        with np.load(path,allow_pickle=False) as z:
            xyz=z['enu_m'];off=z['offsets'];times=z['time'];ids=z['flight_ids']
            if xyz.shape!=(len(times),3) or off[0]!=0 or off[-1]!=len(times) or len(ids)!=len(off)-1: raise ValueError('Invalid prepared arrays')
            if np.any(times<int(row.hour_utc)) or np.any(times>=int(row.hour_utc)+3600) or np.any(times%10): raise ValueError('Time outside hour/grid')
            if len(set(ids.tolist()))!=len(ids): raise ValueError('Duplicate flight IDs')
            if np.any(np.diff(off)<30): raise ValueError('Short trajectory')
            tracks=[xyz[a:b] for a,b in zip(off[:-1],off[1:])]
            for a,b in zip(off[:-1],off[1:]):
                if not np.all(np.diff(times[a:b])==10): raise ValueError('Invalid sampling')
            cloud=enc.encode(tracks,batch_size=args.batch_size)
            result,radii,corr=fit(cloud)
            dst=args.output/row.airport;dst.mkdir(exist_ok=True)
            np.savez_compressed(dst/f'{int(row.hour_utc)}.npz',embeddings=cloud,flight_ids=ids,radii=radii,correlation=corr)
        rows.append(dict(airport=row.airport,hour_utc=row.hour_utc,hour_local=row.hour_local,N=len(tracks),**result))
    pd.DataFrame(rows).to_csv(args.output/'hourly_D.csv',index=False,float_format='%.12g')
    (args.output/'config.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')

if __name__=='__main__': main()
