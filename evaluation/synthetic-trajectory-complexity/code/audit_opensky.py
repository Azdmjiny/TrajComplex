import csv, gzip, io, zipfile, json, math, os, statistics, time
from collections import defaultdict
from pathlib import Path
zip_path = os.environ["ATM_DATA_ZIP"]
out_path = Path(__file__).resolve().parents[1] / 'results' / 'opensky_track_eligibility_audit.json'
MIN_RAW=16  # 10 s observations -> at least 31 samples after 5 s interpolation
GAP_LIMITS=(20,30,60)
rows_out=[]
start=time.time()
with zipfile.ZipFile(zip_path) as z:
    files=[n for n in z.namelist() if '/sampled_10s/' in n and n.endswith('.csv.gz') and not n.startswith('__MACOSX/')]
    for fi,name in enumerate(files,1):
        per=defaultdict(list); total=airborne=coordalt=0
        with z.open(name) as raw:
            f=io.TextIOWrapper(gzip.GzipFile(fileobj=raw),encoding='utf-8',newline='')
            for row in csv.DictReader(f):
                total+=1
                if row.get('onground','').lower()=='true': continue
                airborne+=1
                try:
                    t=float(row['time']); lat=float(row['lat']); lon=float(row['lon']); alt=float(row['geoaltitude'])
                    if not all(map(math.isfinite,(t,lat,lon,alt))): continue
                except (ValueError,TypeError,KeyError): continue
                coordalt+=1
                per[row['icao24']].append(t)
        stats={g:0 for g in GAP_LIMITS}; eligible=0; lengths=[]
        for ts in per.values():
            ts.sort()
            # one hour track remains eligible when >=16 valid points and no long internal gap
            if len(ts)>=MIN_RAW:
                gaps=[b-a for a,b in zip(ts,ts[1:])]
                for g in GAP_LIMITS:
                    if max(gaps,default=0)<=g: stats[g]+=1
            # keep lengths for basic distribution
            lengths.append(len(ts))
        rows_out.append({'file':name.rsplit('/',1)[-1].replace('.csv.gz',''),'rows':total,'airborne_rows':airborne,'valid_xyz_rows':coordalt,'unique_valid_aircraft':len(per),'qualifying_aircraft_gap20s_min16':stats[20],'qualifying_aircraft_gap30s_min16':stats[30],'qualifying_aircraft_gap60s_min16':stats[60],'aircraft_with_16plus_valid_xyz':sum(1 for x in lengths if x>=MIN_RAW)})
        if fi%120==0: print(f'{fi}/{len(files)} files scanned; elapsed {time.time()-start:.0f}s')
result={'zip':Path(zip_path).name,'assumption':'eligibility audit only; complete xyz observations, airborne rows, >=16 raw 10-sec records, max internal gap <= listed threshold; thresholds are not final preprocessing decisions','minimum_raw_points':MIN_RAW,'hours':rows_out,'summary':{}}
for key in ('qualifying_aircraft_gap20s_min16','qualifying_aircraft_gap30s_min16','qualifying_aircraft_gap60s_min16'):
 vals=[x[key] for x in rows_out]
 result['summary'][key]={'hours_at_least_30_aircraft':sum(v>=30 for v in vals),'hours_at_least_50_aircraft':sum(v>=50 for v in vals),'median_per_hour':statistics.median(vals),'min':min(vals),'max':max(vals)}
out_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result['summary'],indent=2)); print('saved',out_path,'elapsed',round(time.time()-start,1),'s')

