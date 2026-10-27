"""Strict 10-second barometric input reader, without Encoder or D imports.

Functions copied from the completed 10-second evaluation reader. Source-time
alignment and QC thresholds are unchanged. The historical Holding entrypoint
remains untouched. No missing position or altitude is filled.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import csv, gzip, io, math
import numpy as np
from trajectory_quality import quality_reasons
from position_timeline import position_grid, resample_positions
LAT0, LON0, H0 = math.radians(1.3592111111111111), math.radians(103.989325), 6.66
A, E2 = 6378137.0, 6.69437999014e-3
MIN_RAW, MAX_GAP_S, SAMPLE_S = 16, 20, 10


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
