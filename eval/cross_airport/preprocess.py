"""Strict hourly trajectory preparation. Inputs remain read-only."""
import argparse,hashlib,json,math,time
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
def quality_reasons(observations, enu, max_horizontal_speed=500.0, *, position_times=None):
    if max_horizontal_speed is None:
        return []  # Explicit legacy reproduction only.
    a=np.asarray(observations); p=np.asarray(enu); reasons=[]
    if not np.isfinite(a).all() or not np.isfinite(p).all():
        return ['nonfinite']
    if np.any(np.abs(a[:,1])>90) or np.any(np.abs(a[:,2])>180):
        reasons.append('coordinate_range')
    if np.any((a[:,3]<-500)|(a[:,3]>20000)):
        reasons.append('altitude_range')
    dt=np.diff(a[:,0])
    if np.any(dt<=0):
        return reasons+['nonincreasing_time']
    horizontal_dt=dt if position_times is None else np.diff(np.asarray(position_times,float))
    if not np.isfinite(horizontal_dt).all() or np.any(horizontal_dt<=0):
        return reasons+['invalid_position_update_time']
    if np.any(np.linalg.norm(np.diff(p[:,:2],axis=0),axis=1)/horizontal_dt>max_horizontal_speed):
        reasons.append('horizontal_speed')
    if np.any(np.abs(np.diff(p[:,2]))/dt>100):
        reasons.append('vertical_speed')
    return reasons

def resample_positions(raw,enu,grid):
    """Interpolate supported horizontal updates; keep vertical snapshot timing."""
    raw=np.asarray(raw,float);enu=np.asarray(enu,float);grid=np.asarray(grid,float)
    if np.any(grid<max(raw[0,0],raw[0,4])) or np.any(grid>min(raw[-1,0],raw[-1,4])):
        raise ValueError('position_extrapolation')
    return np.column_stack((np.interp(grid,raw[:,4],enu[:,0]),
                            np.interp(grid,raw[:,4],enu[:,1]),
                            np.interp(grid,raw[:,0],enu[:,2])))

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def atomic_json(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+".partial")
    tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n","utf-8");tmp.replace(p)

def enu(lat,lon,h,origin):
    a=6378137.;e2=6.69437999014e-3
    def ecef(phi,lam,alt):
        phi=np.radians(phi);lam=np.radians(lam);n=a/np.sqrt(1-e2*np.sin(phi)**2)
        return np.stack(((n+alt)*np.cos(phi)*np.cos(lam),(n+alt)*np.cos(phi)*np.sin(lam),(n*(1-e2)+alt)*np.sin(phi)),axis=-1)
    d=ecef(np.asarray(lat),np.asarray(lon),np.asarray(h))-ecef(origin["lat"],origin["lon"],origin["elevation_m"])
    phi,lam=np.radians([origin["lat"],origin["lon"]]);sl,cl=np.sin(phi),np.cos(phi);so,co=np.sin(lam),np.cos(lam)
    return np.stack((-so*d[...,0]+co*d[...,1],-sl*co*d[...,0]-sl*so*d[...,1]+cl*d[...,2],cl*co*d[...,0]+cl*so*d[...,1]+sl*d[...,2]),axis=-1)

def circle_distance(lat,lon,origin):
    p1=np.radians(lat);p2=math.radians(origin["lat"]);dl=np.radians(lon-origin["lon"])
    h=np.sin((p1-p2)/2)**2+np.cos(p1)*math.cos(p2)*np.sin(dl/2)**2
    return 6371008.8*2*np.arcsin(np.sqrt(np.clip(h,0,1)))

def split_rows(a):
    # Missing observations and ground exclusions create real gaps.
    cut=np.flatnonzero((np.diff(a[:,0])!=CFG["sampling_s"])|(np.diff(a[:,0])<=0))+1
    return np.split(a,cut)

def strict_grid(a,hour):
    if len(a)<2:raise ValueError("too_short")
    if not np.isfinite(a).all():raise ValueError("nonfinite")
    if np.any(np.diff(a[:,0])<=0):raise ValueError("snapshot_time_not_advancing")
    if np.any(np.diff(a[:,4])<=0):raise ValueError("position_timestamp_not_advancing")
    if np.any(np.diff(a[:,4])>CFG["max_gap_s"]):raise ValueError("position_update_gap_over_20_s")
    if np.any(np.diff(a[:,0])!=CFG["sampling_s"]):raise ValueError("snapshot_gap_over_20_s")
    age=a[:,0]-a[:,4]
    if np.any((age<0)|(age>CFG["max_age_s"])):raise ValueError("position_age_out_of_range")
    if np.any(np.all(np.diff(a[:,1:3],axis=0)==0,axis=1)):raise ValueError("repeated_horizontal_position")
    lower=max(a[0,0],a[0,4],hour);upper=min(a[-1,0],a[-1,4],hour+3599.999)
    grid=np.arange(math.ceil(lower/CFG["sampling_s"])*CFG["sampling_s"],upper+1e-6,CFG["sampling_s"],dtype=np.float64)
    if len(grid)<CFG["min_points"]:raise ValueError("less_than_30_sampled_points")
    return grid

def process_hour(code,row,flights,altitude,output):
    began=time.perf_counter();hour=int(row.hour_utc);key=row.hour_utc_iso
    source=Path(row.raw_path)
    result={"airport":code,"hour_utc":hour,"hour_local":row.hour_local,"altitude_field":altitude,"status":"MISSING_RAW","raw_rows":0,"finite_airborne_rows":0,"assigned_rows":0,"unknown_or_ambiguous_rows":0,"minute_bins_all_airborne":0,"minute_bins_assigned":0,"selected_trajectories":0,"rejections":{},"source_sha256":None}
    if not source.is_file():return result
    digest=sha(source);result["source_sha256"]=digest
    record=output/f"{key}.json"
    marker=hashlib.sha256((sha(Path(__file__))+sha(CONFIG_PATH)+CFG.get("_metadata_hash","")).encode()).hexdigest()
    if record.exists():
        old=json.loads(record.read_text("utf-8"))
        npz=output/f"{key}.npz"
        if old.get("source_sha256")==digest and old.get("processor_hash")==marker and npz.exists() and sha(npz)==old.get("output_sha256"):return old
    frame=pd.read_csv(source,dtype={"icao24":str,"onground":str},keep_default_na=False)
    required=["time","icao24","lat","lon",altitude,"onground","lastposupdate","lastcontact","hour"]
    if any(x not in frame for x in required):raise ValueError("Missing raw columns")
    result["raw_rows"]=len(frame);bad=Counter()
    for col in ("time","lat","lon",altitude,"lastposupdate","lastcontact","hour"):
        frame[col]=pd.to_numeric(frame[col],errors="coerce")
    timestamps=frame["time"].to_numpy()
    if np.any(~np.isfinite(timestamps)) or np.any((timestamps<hour)|(timestamps>=hour+3600)|(timestamps%10!=0)|(frame["hour"].to_numpy()!=hour)):raise ValueError("Raw partition or strict snapshot grid mismatch")
    # A conflict cannot be resolved by arbitrarily choosing one receiver row.
    conflicts=frame.groupby(["icao24","time"])[["lat","lon",altitude,"onground","lastposupdate"]].nunique(dropna=False).max(axis=1)
    keys=set(conflicts[conflicts>1].index)
    conflict=np.array([(r.icao24,r.time) in keys for r in frame[["icao24","time"]].itertuples(index=False)])
    bad["conflicting_duplicate_rows"]=int(conflict.sum());frame=frame.loc[~conflict].drop_duplicates(["icao24","time"]).copy()
    finite=np.isfinite(frame[["time","lat","lon",altitude,"lastposupdate","lastcontact"]].to_numpy(float)).all(axis=1)
    ground=frame["onground"].str.lower().to_numpy()!="false"
    geo=(frame["lat"].abs().to_numpy()<=90)&(frame["lon"].abs().to_numpy()<=180)
    age=(frame["time"]-frame["lastposupdate"]).to_numpy();contact=(frame["time"]-frame["lastcontact"]).to_numpy()
    fresh=(age>=0)&(age<=CFG["max_age_s"])&(contact>=0)&(contact<=CFG["max_age_s"])
    circle=circle_distance(frame["lat"].to_numpy(),frame["lon"].to_numpy(),AIRPORTS[code])<=CFG["radius_m"]+.01
    valid=finite&~ground&geo&fresh&circle
    bad.update({"nonfinite_rows":int((~finite).sum()),"ground_or_unknown_ground_rows":int(ground.sum()),"invalid_coordinate_rows":int((~geo).sum()),"stale_or_invalid_age_rows":int((~fresh).sum()),"outside_circle_rows":int((~circle).sum())})
    frame=frame.loc[valid].copy();result["finite_airborne_rows"]=len(frame)
    result["minute_bins_all_airborne"]=len(np.unique((frame["time"].to_numpy()-hour)//60))
    candidates={};assigned_times=[];all_tracks=[];all_ids=[];all_times=[];decisions=[]
    for ident,g in frame.groupby("icao24",sort=True):
        g=g.sort_values("time");t=g["time"].to_numpy();assign=np.full(len(g),"",dtype=object);counts=np.zeros(len(g),int)
        for first,last,fid in flights.get(ident,[]):
            mask=(t>=first)&(t<=last);assign[mask]=fid;counts[mask]+=1
        matched=counts==1;result["assigned_rows"]+=int(matched.sum());result["unknown_or_ambiguous_rows"]+=int((~matched).sum())
        for fid in sorted(set(assign[matched])):
            f=g.iloc[np.flatnonzero(matched&(assign==fid))]
            assigned_times.extend(f["time"].to_numpy())
            arr=f[["time","lat","lon",altitude,"lastposupdate"]].to_numpy(float)
            for piece in split_rows(arr):
                try:
                    grid=strict_grid(piece,hour);xyz=enu(piece[:,1],piece[:,2],piece[:,3],AIRPORTS[code])
                    reasons=quality_reasons(piece[:,:4],xyz,CFG["max_horizontal_speed_m_s"],position_times=piece[:,4])
                    if reasons:raise ValueError("|".join(reasons))
                    sample=resample_positions(piece,xyz,grid)
                    if not np.isfinite(sample).all():raise ValueError("nonfinite_interpolation")
                    assert np.all(np.diff(grid)==10)
                    candidate=(sample,grid)
                    previous=candidates.get(fid)
                    if previous is None or len(sample)>len(previous[0]):candidates[fid]=candidate
                except ValueError as exc:bad[str(exc)]+=1
    result["minute_bins_assigned"]=len(np.unique((np.asarray(assigned_times)-hour)//60)) if assigned_times else 0
    for fid,(sample,grid) in sorted(candidates.items()):
        all_ids.append(fid);all_tracks.append(sample);all_times.append(grid)
    offsets=np.r_[0,np.cumsum([len(x) for x in all_tracks])].astype(np.int64)
    npz=output/f"{key}.npz";output.mkdir(parents=True,exist_ok=True)
    temp=npz.with_suffix(".npz.partial")
    with temp.open("wb") as handle:
        np.savez_compressed(handle,enu_m=np.concatenate(all_tracks) if all_tracks else np.empty((0,3)),time=np.concatenate(all_times) if all_times else np.empty(0),offsets=offsets,flight_ids=np.array(all_ids,dtype="U24"))
    temp.replace(npz)
    durations=np.array([x[-1]-x[0] for x in all_times])
    result.update(status="PREPROCESSED" if all_tracks else "NO_ELIGIBLE_TRAJECTORIES",selected_trajectories=len(all_tracks),duration_median_s=float(np.median(durations)) if len(durations) else None,rejections=dict(bad),processor_hash=marker,output_sha256=sha(npz),elapsed_seconds=time.perf_counter()-began,vertical_datum="barometric_ENU_proxy" if altitude=="baroaltitude" else "reported_geometric_height_reference_unverified",exclusion_counts_overlap=True)
    atomic_json(record,result);return result

def main():
    global CFG,AIRPORTS,CONFIG_PATH
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    p.add_argument('--hours',type=Path,required=True)
    p.add_argument('--flights',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();CONFIG_PATH=args.config.resolve()
    CFG=json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig'));AIRPORTS=CFG['airports']
    if CFG['sampling_s']!=10: raise ValueError('This strict preprocessing contract requires sampling_s=10')
    if args.output.exists(): raise FileExistsError('Choose a new output directory')
    plan=pd.read_csv(args.hours);meta=pd.read_csv(args.flights,dtype={'icao24':str},keep_default_na=False)
    if plan.duplicated(['airport','hour_utc']).any(): raise ValueError('Duplicate airport/hour')
    args.output.mkdir(parents=True)
    flights_by_airport={}
    for code in plan.airport.unique():
        selected=meta[(meta.estdepartureairport==code)|(meta.estarrivalairport==code)]
        selected=selected.drop_duplicates(['icao24','firstseen','lastseen','estdepartureairport','estarrivalairport'])
        groups={}
        for r in selected.itertuples(index=False):
            first,last=float(r.firstseen),float(r.lastseen)
            if not np.isfinite([first,last]).all() or last<first: raise ValueError('Invalid flight interval')
            ident=f'{r.icao24}|{int(first)}|{int(last)}|{r.estdepartureairport}|{r.estarrivalairport}'
            groups.setdefault(r.icao24,[]).append((first,last,hashlib.sha256(ident.encode()).hexdigest()[:24]))
        flights_by_airport[code]=groups
    CFG['_metadata_hash']=sha(args.flights);rows=[];audits=[]
    for row in plan.itertuples(index=False):
        source=Path(row.raw_path)
        if not source.is_absolute(): source=(args.hours.resolve().parent/source).resolve()
        row=row._replace(raw_path=str(source))
        if not source.is_file(): raise FileNotFoundError(source)
        if row.airport not in AIRPORTS: raise ValueError('Airport missing from config')
        if pd.Timestamp(row.hour_local).timestamp()!=int(row.hour_utc): raise ValueError('Local/UTC mismatch')
        result=process_hour(row.airport,row,flights_by_airport[row.airport],CFG['altitude'],args.output/row.airport)
        audits.append(result)
        rows.append(dict(airport=row.airport,hour_utc=row.hour_utc,hour_local=row.hour_local,
                         prepared_path=str((args.output/row.airport/(row.hour_utc_iso+'.npz')).resolve())))
    pd.DataFrame(rows).to_csv(args.output/'prepared_hours.csv',index=False)
    atomic_json(args.output/'preprocessing_audit.json',audits)

if __name__=='__main__': main()
