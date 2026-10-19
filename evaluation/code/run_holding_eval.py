import csv, gzip, io, json, math, os, random, sys, zipfile
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy.spatial.distance import pdist
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Encoder.trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig, estimate_complexity
from trajectory_quality import quality_reasons

DATA_ZIP = Path(os.environ["ATM_DATA_ZIP"]).expanduser()
CHECKPOINT = Path(os.environ["ATM_ENCODER_CHECKPOINT"]).expanduser()
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


def read_scene(z, member, *, max_horizontal_speed=500.0, audit=None):
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
        reasons = quality_reasons(arr, enu, max_horizontal_speed)
        if audit is not None:
            audit.append({'icao24': key, 'reasons': reasons})
        if reasons:
            continue
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
    # The second straight leg already points opposite to the first leg.
    # Start the second turn at that heading; do not rotate it again.
    cur=loop[-1][:2]
    for k in range(1,n+1):
        th=phi+omega*dt*k
        xy=cur+np.array([(speed/omega)*(math.sin(th)-math.sin(phi)), -(speed/omega)*(math.cos(th)-math.cos(phi))])
        loop.append(np.r_[xy,z])
    loop=np.asarray(loop)
    # Numerically the closed circuit returns to its anchor; pin endpoint to anchor to avoid drift.
    if not np.allclose(loop[-1], p[idx], rtol=0, atol=1e-6):
        raise ValueError('Holding circuit did not close naturally')
    loop[-1]=p[idx]
    return np.concatenate((p[:idx+1],loop[1:],p[idx+1:]),axis=0), speed, idx


def estimate(points, radii, cfg, scene_id):
    r=estimate_complexity(points, config=cfg, radii=radii, scene_id=scene_id)
    return {'status':r.status,'reason':r.reason,'dimension':r.dimension,'slope':r.fit_slope,'r_squared':r.r_squared,'n_samples':r.n_samples,'n_unique':r.n_unique,'n_fit_scales':len(r.fit_indices),'fit_radius_range':r.fit_radius_range,'warnings':r.warnings}
