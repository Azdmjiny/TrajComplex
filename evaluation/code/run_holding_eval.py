import csv, gzip, io, json, math, os, random, sys, zipfile
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy.spatial.distance import pdist
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from complexity.calculator import ComplexityConfig, estimate_complexity
from trajectory_quality import quality_reasons
from position_timeline import position_grid, resample_positions

# WSSS origin from the dataset config, WGS84 ellipsoid.
LAT0, LON0, H0 = math.radians(1.3592111111111111), math.radians(103.989325), 6.66
A, E2 = 6378137.0, 6.69437999014e-3
MIN_RAW, MAX_GAP_S, SAMPLE_S = 16, 20, 10
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


def read_scene(z, member, *, max_horizontal_speed=500.0, audit=None, vectoring_source=None):
    tracks = {}; barometric = {}
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
            try:
                lp=float(r['lastposupdate'])
            except (ValueError,TypeError,KeyError):
                lp=float('nan')
            tracks.setdefault(r['icao24'], []).append((t,lat,lon,alt,lp))
            try: barometric[(r['icao24'],t)]=float(r['baroaltitude'])
            except (KeyError,ValueError,TypeError): barometric[(r['icao24'],t)]=float('nan')
    kept={}
    for key, vals in tracks.items():
        vals.sort(key=lambda v:v[0])
        unique=[]
        for v in vals:
            if not unique or v[0] > unique[-1][0]: unique.append(v)
        if len(unique)<MIN_RAW or max((b[0]-a[0] for a,b in zip(unique,unique[1:])),default=0)>MAX_GAP_S:
            continue
        original=np.asarray(unique,dtype=float)
        baro=np.array([barometric[(key,t)] for t in original[:,0]])
        if not np.isfinite(baro).all():
            if audit is not None:audit.append({'icao24':key,'reasons':['missing_barometric_altitude']})
            continue
        # Keep geometric altitude as identity evidence, never as a barometric fallback.
        source=np.column_stack((original,original[:,3]))
        source[:,3]=baro
        arr=source[:,:4]
        enu=llh_to_enu(arr[:,1],arr[:,2],arr[:,3])
        # Horizontal coordinates belong to lastposupdate, not snapshot time.
        # Invalid updates reject the track even when speed QC is disabled.
        try:
            grid=position_grid(source,SAMPLE_S)
        except ValueError as exc:
            if audit is not None: audit.append({'icao24':key,'reasons':[str(exc)]})
            continue
        reasons = quality_reasons(arr, enu, max_horizontal_speed, position_times=source[:,4])
        if audit is not None:
            audit.append({'icao24': key, 'reasons': reasons})
        if reasons:
            continue
        if len(grid)<30: continue
        assert np.all(np.diff(grid)==SAMPLE_S)
        sample=resample_positions(source,enu,grid)
        if np.isfinite(sample).all():
            kept[key]=sample
            if vectoring_source is not None:
                vectoring_source[key]=source.copy()
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


def append_equal_duration_pair(p):
    """Existing racetrack geometry relocated to endpoint; matched straight arm."""
    tangent = p[-1,:2] - p[-2,:2]
    if not np.isfinite(tangent).all() or np.linalg.norm(tangent) == 0:
        raise ValueError('undefined_endpoint_heading')
    # Same local speed rule as the original Holding, evaluated at the endpoint.
    speed_samples = np.linalg.norm(np.diff(p[-4:,:2], axis=0), axis=1) / SAMPLE_S
    usable = speed_samples[speed_samples > 1]
    if not len(usable):
        raise ValueError('no_existing_rule_speed_support')
    speed = float(np.median(usable))
    if speed > 500:
        raise ValueError('endpoint_speed_over_existing_500_m_s')
    phi = float(np.arctan2(tangent[1], tangent[0]))
    omega, dt = TURN_RATE, SAMPLE_S
    nturn, nleg = int(round(np.pi/omega/dt)), int(round(LEG_S/dt))
    assert 2*(nturn+nleg)*dt == 240 and dt == 10
    cur = p[-1,:2].copy(); z = p[-1,2]
    loop = []
    for _ in range(2):
        origin = cur.copy()
        direction = np.array([np.cos(phi), np.sin(phi)])
        for k in range(1,nleg+1):
            loop.append(np.r_[origin+direction*speed*dt*k, z])
        origin = loop[-1][:2].copy()
        for k in range(1,nturn+1):
            theta = phi+omega*dt*k
            xy = origin + speed/omega*np.array([np.sin(theta)-np.sin(phi), -np.cos(theta)+np.cos(phi)])
            loop.append(np.r_[xy,z])
        cur = loop[-1][:2].copy(); phi += np.pi
    extra_h = np.asarray(loop)
    closure = float(np.linalg.norm(extra_h[-1]-p[-1]))
    if closure > 1e-6: raise ValueError('circuit_did_not_close_naturally')
    extra_h[-1] = p[-1]
    direction = tangent/np.linalg.norm(tangent)
    extra_s = np.column_stack((p[-1,:2]+np.arange(1,25)[:,None]*dt*speed*direction, np.full(24,z)))
    holding, straight = np.vstack((p,extra_h)), np.vstack((p,extra_s))
    assert holding.shape == straight.shape == (len(p)+24,3)
    for q in (holding,straight):
        np.testing.assert_array_equal(q[:len(p)],p)
        assert np.isfinite(q).all()
        np.testing.assert_array_equal(q[len(p):,2],np.full(24,z))
        assert np.max(np.linalg.norm(np.diff(q[len(p)-1:,:2],axis=0),axis=1)/dt) <= 500+1e-9
    np.testing.assert_allclose(extra_h[:nleg],extra_s[:nleg],rtol=0,atol=1e-8)
    return holding,straight,dict(speed_m_s=speed,heading_rad=float(np.arctan2(tangent[1],tangent[0])),
        speed_samples_m_s=speed_samples.tolist(),added_points=24,added_duration_s=240,
        continuous_path_length_m=240*speed,closure_error_m=closure,
        sampled_holding_path_length_m=float(np.linalg.norm(np.diff(holding[len(p)-1:,:2],axis=0),axis=1).sum()),
        sampled_straight_path_length_m=float(np.linalg.norm(np.diff(straight[len(p)-1:,:2],axis=0),axis=1).sum()))
