import csv, gzip, io, json, math, os, random, sys, zipfile
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy.spatial.distance import pdist
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Encoder.trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig, estimate_complexity

DATA_ZIP = Path(os.environ["ATM_DATA_ZIP"]).expanduser()
CHECKPOINT = Path(os.environ["ATM_ENCODER_CHECKPOINT"]).expanduser()
AUDIT = Path(__file__).resolve().parents[1] / 'results' / 'opensky_track_eligibility_audit.json'
OUT = Path(__file__).resolve().parents[1] / 'results' / 'synthetic-holding-evaluation-pilot.json'
# WSSS origin from the dataset config, WGS84 ellipsoid.
LAT0, LON0, H0 = math.radians(1.3592111111111111), math.radians(103.989325), 6.66
A, E2 = 6378137.0, 6.69437999014e-3
MIN_RAW, MAX_GAP_S, SAMPLE_S = 16, 20, 5
TURN_RATE = math.radians(3.0)
LEG_S, REPEATS, MAX_SCENES = 60.0, 5, 12
SEED = 43


def llh_to_enu(lat, lon, h):
    lat, lon, h = np.radians(lat), np.radians(lon), np.asarray(h, dtype=float)
    def ecef(phi, lam, alt):
        n = A / np.sqrt(1 - E2 * np.sin(phi)**2)
        return np.stack(((n+alt)*np.cos(phi)*np.cos(lam), (n+alt)*np.cos(phi)*np.sin(lam), (n*(1-E2)+alt)*np.sin(phi)), axis=-1)
    p = ecef(lat, lon, h)
    o = ecef(np.asarray(LAT0), np.asarray(LON0), np.asarray(H0))
    d = p - o
    sl, cl, so, co = math.sin(LAT0), math.cos(LAT0), math.sin(LON0), math.cos(LON0)
    return np.stack((-so*d[...,0]+co*d[...,1], -sl*co*d[...,0]-sl*so*d[...,1]+cl*d[...,2], cl*co*d[...,0]+cl*so*d[...,1]+sl*d[...,2]), axis=-1)


def read_scene(z, member):
    tracks = {}
    with z.open(member) as raw:
        f = io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding='utf-8', newline='')
        for r in csv.DictReader(f):
            if r.get('onground','').lower() == 'true':
                continue
            try:
                t, lat, lon, alt = (float(r[k]) for k in ('time','lat','lon','geoaltitude'))
            except (ValueError, TypeError, KeyError):
                continue
            if not all(map(math.isfinite,(t,lat,lon,alt))):
                continue
            tracks.setdefault(r['icao24'], []).append((t,lat,lon,alt))
    kept={}
    for key, vals in tracks.items():
        vals.sort(key=lambda v:v[0])
        unique=[]
        for v in vals:
            if not unique or v[0] > unique[-1][0]: unique.append(v)
        if len(unique)<MIN_RAW or max((b[0]-a[0] for a,b in zip(unique,unique[1:])),default=0)>MAX_GAP_S:
            continue
        arr=np.asarray(unique,dtype=float)
        enu=llh_to_enu(arr[:,1],arr[:,2],arr[:,3])
        grid=np.arange(arr[0,0],arr[-1,0]+1e-6,SAMPLE_S)
        if len(grid)<30: continue
        sample=np.column_stack([np.interp(grid,arr[:,0],enu[:,j]) for j in range(3)])
        if np.isfinite(sample).all(): kept[key]=sample
    return kept


def add_racetrack(p):
    # Insert one closed racetrack at the midpoint; preserve all observed points.
    idx=len(p)//2
    if idx<1 or idx>=len(p)-1: raise ValueError('track too short for insertion')
    tangent=p[min(idx+1,len(p)-1),:2]-p[max(idx-1,0),:2]
    speed_samples=np.linalg.norm(np.diff(p[max(0,idx-3):min(len(p),idx+4),:2],axis=0),axis=1)/SAMPLE_S
    speed=float(np.median(speed_samples[speed_samples>1])) if np.any(speed_samples>1) else 220.0
    heading=math.atan2(tangent[1],tangent[0]); v=np.array([math.cos(heading),math.sin(heading)])
    omega=TURN_RATE; dt=SAMPLE_S; turn_s=math.pi/omega; n=int(round(turn_s/dt)); leg_n=int(round(LEG_S/dt))
    start=p[idx,:2]; z=p[idx,2]; loop=[np.array([start[0],start[1],z])]
    # straight leg
    for k in range(1,leg_n+1): loop.append(np.r_[start+v*(speed*dt*k),z])
    cur=loop[-1][:2]; phi=heading
    # right/left standard-rate 180 degree turn, constant speed
    for k in range(1,n+1):
        th=phi+omega*dt*k
        xy=cur+np.array([(speed/omega)*(math.sin(th)-math.sin(phi)), -(speed/omega)*(math.cos(th)-math.cos(phi))])
        loop.append(np.r_[xy,z])
    phi += math.pi; cur=loop[-1][:2]
    for k in range(1,leg_n+1): loop.append(np.r_[cur+np.array([math.cos(phi),math.sin(phi)])*(speed*dt*k),z])
    phi += math.pi; cur=loop[-1][:2]
    for k in range(1,n+1):
        th=phi+omega*dt*k
        xy=cur+np.array([(speed/omega)*(math.sin(th)-math.sin(phi)), -(speed/omega)*(math.cos(th)-math.cos(phi))])
        loop.append(np.r_[xy,z])
    loop=np.asarray(loop)
    # Numerically the closed circuit returns to its anchor; pin endpoint to anchor to avoid drift.
    loop[-1]=p[idx]
    return np.concatenate((p[:idx+1],loop[1:],p[idx+1:]),axis=0), speed, idx


def estimate(points, radii, cfg, scene_id):
    r=estimate_complexity(points, config=cfg, radii=radii, scene_id=scene_id)
    return {'status':r.status,'reason':r.reason,'dimension':r.dimension,'slope':r.fit_slope,'r_squared':r.r_squared,'n_samples':r.n_samples,'n_unique':r.n_unique,'n_fit_scales':len(r.fit_indices),'fit_radius_range':r.fit_radius_range,'warnings':r.warnings}


def main():
    audit=json.loads(AUDIT.read_text(encoding='utf-8'))
    eligible=[x for x in audit['hours'] if x['qualifying_aircraft_gap20s_min16']>=50]
    eligible.sort(key=lambda x:x['file'])
    # Evenly spaced deterministic scenes across the month; all satisfy >=50 eligible tracks.
    idxs=np.linspace(0,len(eligible)-1,min(MAX_SCENES,len(eligible))).round().astype(int)
    selected=[eligible[i] for i in idxs]
    dev='cuda' if __import__('torch').cuda.is_available() else 'cpu'
    encoder=FrozenEncoder(CHECKPOINT, pooling='sum', device=dev)
    print('device',dev,'selected scenes',len(selected),flush=True)
    cfg=ComplexityConfig(normalize=False)
    results=[]
    with zipfile.ZipFile(DATA_ZIP) as z:
        for si, meta in enumerate(selected,1):
            member=f"OpenSky_Changi_2026-09/sampled_10s/{meta['file']}.csv.gz"
            tracks=read_scene(z,member)
            ids=sorted(tracks)
            embeddings=[]
            for i,ident in enumerate(ids):
                embeddings.append(encoder.encode(tracks[ident])['embedding'])
                if (i+1)%25==0: print(f'{meta["file"]}: encoded {i+1}/{len(ids)}',flush=True)
            base=np.asarray(embeddings,dtype=float)
            d=pdist(base,metric='euclidean')
            positive=d[d>0]
            if len(positive)<2:
                print('skip collapsed baseline',meta['file'],flush=True); continue
            radii=np.geomspace(float(positive.min()),float(positive.max()),cfg.n_radii)
            baseline=estimate(base,radii,cfg,meta['file'])
            scene={'scene_id':meta['file'],'n_aircraft':len(ids),'baseline':baseline,'repeats':[],'radii':radii.tolist()}
            print(f'[{si}/{len(selected)}] {meta["file"]}: N={len(ids)} baseline D={baseline["dimension"]} {baseline["status"]}',flush=True)
            for rep in range(REPEATS):
                rng=np.random.default_rng(SEED+si*1009+rep)
                order=rng.permutation(len(ids))
                current=base.copy(); curve=[]
                curve.append({'holding_aircraft':0,**baseline})
                for k,flight_idx in enumerate(order,1):
                    modified,speed,anchor=add_racetrack(tracks[ids[int(flight_idx)]])
                    current[int(flight_idx)]=encoder.encode(modified)['embedding']
                    est=estimate(current,radii,cfg,meta['file'])
                    curve.append({'holding_aircraft':k,**est,'mean_ground_speed_m_s':speed,'insert_index':anchor})
                    if k%25==0: print(f'  rep {rep+1}/{REPEATS}, holding {k}/{len(ids)}, D={est["dimension"]}',flush=True)
                results.append({'scene_id':meta['file'],'replicate':rep,'n_aircraft':len(ids),'dose_curve':curve})
                partial={'experiment':'Encoder-based scene correlation-dimension response to progressively injected synthetic racetrack holding','checkpoint':CHECKPOINT.name,'device':dev,'encoder_pooling':'sum','distance':'Euclidean, unnormalized embeddings','gap_policy_seconds':MAX_GAP_S,'raw_min_points':MIN_RAW,'resampling_seconds':SAMPLE_S,'holding_geometry':{'straight_leg_seconds_each':LEG_S,'turn_rate_deg_s':3.0,'turn_duration_seconds_each':60.0,'circuit_duration_seconds':2*LEG_S+2*60.0,'altitude':'held constant at insertion altitude','speed':'median local groundspeed estimated from adjacent ENU samples','insertion':'midpoint of track; preserve original observations and add one complete closed circuit'},'scene_selection':{'selected_hours':len(selected),'selection':'evenly spaced over the month among hours with >=50 qualifying aircraft'},'repeats_per_scene':REPEATS,'complexity_config':cfg.__dict__,'completed_scene_replicates':len(results),'scenes':results}
                OUT.write_text(json.dumps(partial,indent=2),encoding='utf-8')
            scenes_done=si
    output={'experiment':'Encoder-based scene correlation-dimension response to progressively injected synthetic racetrack holding','checkpoint':CHECKPOINT.name,'device':dev,'encoder_pooling':'sum','distance':'Euclidean, unnormalized embeddings','gap_policy_seconds':MAX_GAP_S,'raw_min_points':MIN_RAW,'resampling_seconds':SAMPLE_S,'holding_geometry':{'straight_leg_seconds_each':LEG_S,'turn_rate_deg_s':3.0,'turn_duration_seconds_each':60.0,'circuit_duration_seconds':2*LEG_S+2*60.0,'altitude':'held constant at insertion altitude','speed':'median local groundspeed estimated from adjacent ENU samples','insertion':'midpoint of track; preserve original observations and add one complete closed circuit','note':'synthetic operational proxy; validate geometry and dose-response before generalizing'},'scene_selection':{'eligible_hours_gap20_min16_at_least_50_aircraft':len(eligible),'selected_hours':len(selected),'selection':'evenly spaced over the month among hours with >=50 qualifying aircraft'},'repeats_per_scene':REPEATS,'complexity_config':cfg.__dict__,'scenes':results}
    OUT.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print('saved',OUT,'rows',sum(len(r['dose_curve']) for r in results),flush=True)

if __name__=='__main__': main()


