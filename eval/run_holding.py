#!/usr/bin/env python3
"""Independent 10-second Changi Holding injection experiment."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,sys,time
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/Changi_paper_datasets_latest_2026-10-27'
RAW=DATA/'01_raw_observations/hourly_10s'
CHECKPOINT=ROOT/'Encoder/encoder/encoder.pt'
ALL_SCENES=['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z','2026-09-12T15Z','2026-09-15T06Z','2026-09-18T00Z','2026-09-20T04Z','2026-09-23T10Z','2026-09-25T23Z','2026-09-28T07Z','2026-09-30T15Z']
EXCLUDED_SCENES=['2026-09-12T15Z']
SCENES=[s for s in ALL_SCENES if s not in EXCLUDED_SCENES]
SCENE_SEED_INDEX={s:i for i,s in enumerate(ALL_SCENES)}
DT=10.; MAX_SPEED=500.; MAX_GAP=20.; MAX_AGE=15.; TURN=math.radians(3); LEG=60.
REPEATS=10; MAX_EVENTS=30; SEED=20261027; MIN_TAIL=24
LAT0,LON0,H0=math.radians(1.3592111111111111),math.radians(103.989325),6.66
A,E2=6378137.,6.69437999014e-3

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def llh_to_enu(lat,lon,alt):
 lat,lon,alt=np.radians(lat),np.radians(lon),np.asarray(alt,float)
 def ecef(phi,lam,h):
  n=A/np.sqrt(1-E2*np.sin(phi)**2)
  return np.stack(((n+h)*np.cos(phi)*np.cos(lam),(n+h)*np.cos(phi)*np.sin(lam),(n*(1-E2)+h)*np.sin(phi)),axis=-1)
 xyz=ecef(lat,lon,alt); origin=ecef(np.asarray(LAT0),np.asarray(LON0),np.asarray(H0)); d=xyz-origin
 sl,cl,so,co=math.sin(LAT0),math.cos(LAT0),math.sin(LON0),math.cos(LON0)
 return np.stack((-so*d[...,0]+co*d[...,1],-sl*co*d[...,0]-sl*so*d[...,1]+cl*d[...,2],cl*co*d[...,0]+cl*so*d[...,1]+sl*d[...,2]),axis=-1)
def read_hour(path):
 """Read airborne snapshots; bounded-align to strict 10s ENU tracks."""
 raw={}
 with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
  for r in csv.DictReader(f):
   if r.get('onground','').lower()=='true': continue
   try: t,lat,lon,baro,geo,pt=(float(r[k]) for k in ('time','lat','lon','baroaltitude','geoaltitude','lastposupdate'))
   except (KeyError,TypeError,ValueError): continue
   if np.isfinite([t,lat,lon,baro,geo,pt]).all(): raw.setdefault(r.get('icao24',''),[]).append((t,lat,lon,baro,geo,pt))
 kept={}; rejected=[]
 for aid,records in sorted(raw.items()):
  records.sort(key=lambda r:r[0]); unique=[]
  for r in records:
   if not unique or r[0]>unique[-1][0]: unique.append(r)
  a=np.asarray(unique,float); why=[]
  if len(a)<16: why.append('fewer_than_16_raw_records')
  if len(a)>1 and (np.diff(a[:,0])<=0).any(): why.append('nonincreasing_snapshot_time')
  if len(a)>1 and (np.diff(a[:,0])>MAX_GAP).any(): why.append('snapshot_gap_over_20s')
  if len(a)>1 and (np.diff(a[:,5])<=0).any(): why.append('position_time_not_advancing')
  if len(a)>1 and (np.diff(a[:,5])>MAX_GAP).any(): why.append('position_gap_over_20s')
  age=a[:,0]-a[:,5]
  if (age<0).any() or (age>MAX_AGE).any(): why.append('stale_position_update')
  if (np.abs(a[:,1])>90).any() or (np.abs(a[:,2])>180).any(): why.append('coordinate_range')
  if (a[:,3]<-500).any() or (a[:,3]>20000).any(): why.append('barometric_altitude_range')
  if len(a)>1 and np.all(np.diff(a[:,1:3],axis=0)==0,axis=1).any(): why.append('repeated_raw_position')
  if len(a)>1 and (np.abs(np.diff(a[:,3])/np.diff(a[:,0]))>100).any(): why.append('vertical_speed_over_100m_s')
  if why: rejected.append({'icao24':aid,'reasons':why}); continue
  start=max(a[0,0],a[0,5]); stop=min(a[-1,0],a[-1,5]); grid=np.arange(start,stop+1e-7,DT)
  if len(grid)<30: rejected.append({'icao24':aid,'reasons':['fewer_than_30_grid_points']}); continue
  enu=llh_to_enu(a[:,1],a[:,2],a[:,3]); sp=np.linalg.norm(np.diff(enu[:,:2],axis=0),axis=1)/np.diff(a[:,5])
  if (sp>MAX_SPEED).any(): rejected.append({'icao24':aid,'reasons':['horizontal_speed_over_500m_s']}); continue
  p=np.column_stack((np.interp(grid,a[:,5],enu[:,0]),np.interp(grid,a[:,5],enu[:,1]),np.interp(grid,a[:,0],enu[:,2])))
  if not np.isfinite(p).all(): rejected.append({'icao24':aid,'reasons':['nonfinite_resampled_track']}); continue
  kept[aid]=p
 return kept,rejected
def racetrack(anchor,heading,speed):
 nturn=int(round((math.pi/TURN)/DT)); nleg=int(round(LEG/DT)); assert 2*(nturn+nleg)==24
 phi=float(heading); z=float(anchor[2]); cur=np.asarray(anchor[:2],float).copy(); out=[]
 for _ in range(2):
  origin=cur.copy(); direction=np.array([math.cos(phi),math.sin(phi)])
  for k in range(1,nleg+1): out.append(np.r_[origin+direction*speed*DT*k,z])
  origin=np.asarray(out[-1][:2]).copy()
  for k in range(1,nturn+1):
   theta=phi+TURN*DT*k; xy=origin+speed/TURN*np.array([math.sin(theta)-math.sin(phi),-math.cos(theta)+math.cos(phi)])
   out.append(np.r_[xy,z])
  cur=np.asarray(out[-1][:2]).copy(); phi+=math.pi
 block=np.asarray(out); closure=float(np.linalg.norm(block[-1]-anchor))
 if closure>1e-6: raise ValueError('racetrack_not_closed')
 block[-1]=anchor
 return block,closure
def candidate(track):
 idx=len(track)//2
 if len(track)-idx-1<MIN_TAIL: return None,'fewer_than_24_original_tail_points'
 tangent=track[min(idx+1,len(track)-1),:2]-track[max(0,idx-1),:2]
 if not np.isfinite(tangent).all() or np.linalg.norm(tangent)==0: return None,'undefined_midpoint_heading'
 v=np.linalg.norm(np.diff(track[max(0,idx-3):min(len(track),idx+4),:2],axis=0),axis=1)/DT; v=v[v>1.]
 if not len(v): return None,'no_midpoint_speed_support'
 speed=float(np.median(v))
 if speed>MAX_SPEED: return None,'midpoint_speed_over_500m_s'
 heading=float(math.atan2(tangent[1],tangent[0])); block,closure=racetrack(track[idx],heading,speed)
 return {'index':idx,'speed':speed,'heading':heading,'block':block,'closure':closure},None
def inject_trim(state,cand,prior_events=0):
 p,tags=state; anchor=cand['index']; idx=anchor; before=len(p)
 while idx+1<len(tags) and tags[idx+1]=='holding': idx+=1
 if idx>=len(p): raise ValueError('midpoint_anchor_out_of_range')
 q=np.concatenate((p[:idx+1],cand['block'],p[idx+1:]),axis=0); kinds=tags[:idx+1]+['holding']*24+tags[idx+1:]
 removed=Counter(kinds[-24:]); q=q[:-24]; kinds=kinds[:-24]
 assert len(q)==before and len(kinds)==before
 return (q,kinds),removed
def estimate(p,radii,cfg,scene,fn): return fn(p,config=cfg,radii=radii,scene_id=scene).to_dict()
def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,default=ROOT/'eval/results/holding-2026-10-27'); args=ap.parse_args(); out=args.output.resolve()
 if out.exists(): raise SystemExit(f'Output exists; choose a new path: {out}')
 if sha(CHECKPOINT)!='bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976': raise SystemExit('Epoch-90 checkpoint hash mismatch')
 sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'complexity')); import torch
 from Encoder.trajectory_encoder.inference import FrozenEncoder
 from calculator import ComplexityConfig,estimate_complexity
 cfg=ComplexityConfig(normalize=False,min_samples=15,min_r_squared=.90); torch.set_num_threads(2)
 enc=FrozenEncoder(CHECKPOINT,pooling='sum',device='cpu')
 if enc.preprocess['preprocessor_id']!='52fabdb80ff5221882becc2e326e0e51089dbcf324a155bf7330f41442fa1477': raise SystemExit('Encoder preprocessing contract mismatch')
 policy={'scenes':SCENES,'excluded_scenes':EXCLUDED_SCENES,'scene_seed_index_preserved_from':ALL_SCENES,'repeats_per_scene':REPEATS,'max_events_per_sequence':MAX_EVENTS,'repeat_anchor_order':'Keep extant Holding blocks contiguous after the original midpoint in event order; insert each new block after retained blocks, then trim exactly the final 24 points regardless of whether they are original or synthetic','sampling':'uniform with replacement among QC500 plus geometry eligible aircraft; repeated draw means a new event','injection':'each event inserts 24 10-second closed racetrack points at fixed original midpoint then deletes transformed track final 24 points','racetrack':'60s straight, 180 degree turn, 60s opposite straight, 180 degree turn; 3 deg/s; constant midpoint median speed and altitude','tail_rule':'at least 24 original samples after midpoint for pool entry; later trimming may remove original or synthesized samples','preprocessing':'valid airborne records; barometric altitude; position lastposupdate clock, altitude snapshot clock; bounded strict 10s interpolation; no extrapolation or fill; WGS84 ENU','quality':{'horizontal_speed_m_s_max':500,'vertical_speed_m_s_max':100,'altitude_m':[-500,20000],'record_gap_s_max':20,'position_age_s_max':15},'complexity':cfg.__dict__,'checkpoint_sha256':sha(CHECKPOINT),'preprocessor_id':enc.preprocess['preprocessor_id'],'device':str(enc.device),'seed_base':20261027,'straight_control':False,'peak_truncation':False}
 out.mkdir(parents=True); (out/'policy.json').write_text(json.dumps(policy,indent=2))
 manifest={'state':'running','date':'2026-10-27','data_root':str(DATA),'data_manifest_sha256':sha(DATA/'MANIFEST.json'),'checkpoint':str(CHECKPOINT),'checkpoint_sha256':sha(CHECKPOINT),'device':str(enc.device),'torch':torch.__version__,'numpy':np.__version__,'scipy':__import__('scipy').__version__,'policy_sha256':sha(out/'policy.json'),'runner_sha256':sha(Path(__file__)),'config':cfg.__dict__}
 (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2)); events=[]; doses=[]; seqs=[]; pops=[]; started=time.monotonic()
 for scene in SCENES:
  tracks,rejected=read_hour(RAW/f'{scene}.csv.gz'); ids=sorted(tracks)
  candidates={}; audit=[]
  for aid in ids:
   c,reason=candidate(tracks[aid])
   if c is None: audit.append({'icao24':aid,'eligible':False,'reason':reason})
   else:
    candidates[aid]=c; audit.append({'icao24':aid,'eligible':True,'midpoint_index':c['index'],'speed_m_s':c['speed'],'heading_rad':c['heading'],'closure_error_m':c['closure'],'original_points':len(tracks[aid]),'original_tail_points':len(tracks[aid])-c['index']-1})
  pool=sorted(candidates)
  if not pool: raise RuntimeError(f'{scene}: no eligible injection aircraft')
  base_z={a:enc.encode(tracks[a])['embedding'] for a in ids}; base=np.asarray([base_z[a] for a in ids],float)
  pos=pdist(base); pos=pos[pos>0]
  if not len(pos) or pos.min()==pos.max(): raise RuntimeError(f'{scene}: no baseline radius range')
  radii=np.geomspace(pos.min(),pos.max(),64); baseline=estimate(base,radii,cfg,scene,estimate_complexity)
  pops.append({'scene_id':scene,'background_qc500':len(ids),'eligible_pool':len(pool),'rejected_preprocess':len(rejected),'baseline_status':baseline['status'],'baseline_D':baseline['dimension'],'baseline_R2':baseline['r_squared'],'candidate_audit':audit,'preprocessing_rejections':rejected})
  for rep in range(REPEATS):
   seed=SEED+SCENE_SEED_INDEX[scene]*100003+rep; rng=np.random.default_rng(seed); seq=rng.choice(pool,size=MAX_EVENTS,replace=True).tolist()
   current={a:(tracks[a].copy(),['original']*len(tracks[a])) for a in ids}; z=base.copy(); baseline_ok=baseline['status']=='ok' and baseline['dimension'] is not None
   actual_events=0
   for dose in range(MAX_EVENTS+1):
    m=baseline if dose==0 else estimate(z,radii,cfg,scene,estimate_complexity); ok=m['status']=='ok' and m['dimension'] is not None; d=m['dimension'] if ok else None
    held=sum(t=='holding' for p,tags in current.values() for t in tags); touched=len({e['icao24'] for e in events if e['scene_id']==scene and e['repeat']==rep})
    doses.append({'scene_id':scene,'repeat':rep,'seed':seed,'dose_events':dose,'unique_aircraft_injected':touched,'retained_holding_points':held,'retained_holding_seconds':held*DT,'D':d,'delta_D':d-baseline['dimension'] if ok and baseline_ok else None,'fit_status':m['status'],'fit_reason':m['reason'],'R2':m['r_squared'],'fit_scales':len(m['fit_indices'])})
    if dose==MAX_EVENTS: break
    aid=seq[dose]; prior=current[aid][1].count('holding')
    state,removed=inject_trim(current[aid],candidates[aid],prior)
    current[aid]=state; z[ids.index(aid)]=enc.encode(state[0])['embedding']; actual_events+=1
    n_occ=sum(x==aid for x in seq[:dose+1]); held_air=sum(t=='holding' for t in state[1])
    events.append({'scene_id':scene,'repeat':rep,'seed':seed,'event':dose+1,'icao24':aid,'occurrence':n_occ,'fixed_midpoint_original_index':candidates[aid]['index'],'injected_seconds':240,'trimmed_points':24,'trimmed_original_points':removed['original'],'trimmed_holding_points':removed['holding'],'aircraft_retained_holding_points':held_air,'aircraft_retained_holding_seconds':held_air*DT,'speed_m_s':candidates[aid]['speed'],'closure_error_m':candidates[aid]['closure']})
   seq_rows=[r for r in doses if r['scene_id']==scene and r['repeat']==rep]
   valid_doses=sum(r['D'] is not None for r in seq_rows)
   seqs.append({'scene_id':scene,'repeat':rep,'seed':seed,'planned_max_events':MAX_EVENTS,'actual_events':actual_events,'stop_reason':None,'unique_aircraft_drawn':len(set(seq[:actual_events])),'pool_size':len(pool),'valid_doses':valid_doses,'total_doses':actual_events+1,'final_retained_holding_seconds':doses[-1]['retained_holding_seconds']})
  print(json.dumps({'scene':scene,'N':len(ids),'eligible':len(pool),'baseline_D':baseline['dimension'],'elapsed_s':round(time.monotonic()-started,1)}),flush=True)
 (out/'scene-population-audit.json').write_text(json.dumps(pops,indent=2))
 def write_csv(name,rows):
  with (out/name).open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
 write_csv('dose-results.csv',doses); write_csv('injection-events.csv',events); write_csv('sequence-summary.csv',seqs)
 summary=[]
 for scene in SCENES:
  for dose in range(MAX_EVENTS+1):
   rr=[r for r in doses if r['scene_id']==scene and r['dose_events']==dose]; dd=np.array([r['delta_D'] for r in rr if r['delta_D'] is not None],float); rs=np.array([r['R2'] for r in rr if r['R2'] is not None],float)
   summary.append({'scene_id':scene,'dose_events':dose,'attempts':len(rr),'valid_D':len(dd),'D_success_rate':len(dd)/len(rr) if rr else None,'R2_available':len(rs),'R2_pass_rate':sum(r['R2'] is not None and r['R2']>=cfg.min_r_squared for r in rr)/len(rr) if rr else None,'median_delta_D':float(np.median(dd)) if len(dd) else None,'q1_delta_D':float(np.quantile(dd,.25)) if len(dd) else None,'q3_delta_D':float(np.quantile(dd,.75)) if len(dd) else None,'min_delta_D':float(dd.min()) if len(dd) else None,'max_delta_D':float(dd.max()) if len(dd) else None,'median_R2':float(np.median(rs)) if len(rs) else None,'min_R2':float(rs.min()) if len(rs) else None,'max_R2':float(rs.max()) if len(rs) else None,'median_retained_holding_s':float(np.median([r['retained_holding_seconds'] for r in rr])) if rr else None})
 write_csv('scene-dose-summary.csv',summary)
 scene_rhos=[]
 for scene in SCENES:
  curve=[r for r in summary if r['scene_id']==scene and r['median_delta_D'] is not None]
  rho=float(spearmanr([r['dose_events'] for r in curve],[r['median_delta_D'] for r in curve]).statistic) if len(curve)>=5 and len({r['median_delta_D'] for r in curve})>1 else None
  scene_rhos.append({'scene_id':scene,'n_doses':len(curve),'rho_median_curve':rho,'reason':None if rho is not None else 'insufficient_baseline_or_variation'})
 write_csv('scene-rho-summary.csv',scene_rhos)
 overall=[]
 for dose in range(MAX_EVENTS+1):
  rr=[r for r in doses if r['dose_events']==dose]
  scene_medians=[]
  for scene in SCENES:
   ss=[r for r in summary if r['scene_id']==scene and r['dose_events']==dose]
   if ss and ss[0]['median_delta_D'] is not None: scene_medians.append(ss[0]['median_delta_D'])
  dd=np.asarray(scene_medians,float)
  overall.append({'dose_events':dose,'attempts':len(rr),'valid_D':int(sum(r['D'] is not None for r in rr)),
   'baseline_estimable_scene_count':len(dd),'median_of_scene_median_delta_D':float(np.median(dd)) if len(dd) else None,
   'q1_scene_median_delta_D':float(np.quantile(dd,.25)) if len(dd) else None,'q3_scene_median_delta_D':float(np.quantile(dd,.75)) if len(dd) else None,'min_scene_median_delta_D':float(dd.min()) if len(dd) else None,'max_scene_median_delta_D':float(dd.max()) if len(dd) else None,
   'median_retained_holding_s':float(np.median([r['retained_holding_seconds'] for r in rr])) if rr else None})
 write_csv('overall-dose-summary.csv',overall)
 overall_curve=[r for r in overall if r['median_of_scene_median_delta_D'] is not None]
 overall_rho=float(spearmanr([r['dose_events'] for r in overall_curve],[r['median_of_scene_median_delta_D'] for r in overall_curve]).statistic) if len(overall_curve)>=5 and len({r['median_of_scene_median_delta_D'] for r in overall_curve})>1 else None
 (out/'rho-summary.json').write_text(json.dumps({'primary_estimand':'Spearman rho of the across-scene median-of-scene-medians Delta-D curve','rho_median_curve':overall_rho,'n_doses':len(overall_curve),'per_scene':scene_rhos,'sequence_level_rho_reported':False},indent=2))
 import os
 os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(3,4,figsize=(17,11),sharex=True)
 for ax,scene in zip(axes.flat,SCENES):
  for rep in range(REPEATS):
   rr=[r for r in doses if r['scene_id']==scene and r['repeat']==rep]
   ax.scatter([r['dose_events'] for r in rr],[np.nan if r['delta_D'] is None else r['delta_D'] for r in rr],s=11,alpha=.35,color='#4C78A8',edgecolors='none')
  ax.axhline(0,color='#777',lw=.6);ax.set_title(scene);ax.grid(alpha=.2)
  ss=[r for r in summary if r['scene_id']==scene]
  xs=[r['dose_events'] for r in ss if r['median_delta_D'] is not None]
  med=[r['median_delta_D'] for r in ss if r['median_delta_D'] is not None]
  lo=[r['q1_delta_D'] for r in ss if r['median_delta_D'] is not None];hi=[r['q3_delta_D'] for r in ss if r['median_delta_D'] is not None]
  if xs: ax.plot(xs,med,color='#C44E52',lw=2.0,marker='o',ms=2.5);ax.fill_between(xs,lo,hi,color='#C44E52',alpha=.16)
 fig.supxlabel('Injection events');fig.supylabel('Delta D');fig.tight_layout()
 fig.savefig(out/'holding-delta-dose.png',dpi=160);plt.close(fig)
 xs=[r['dose_events'] for r in overall if r['median_of_scene_median_delta_D'] is not None]
 med=[r['median_of_scene_median_delta_D'] for r in overall if r['median_of_scene_median_delta_D'] is not None]
 lo=[r['q1_scene_median_delta_D'] for r in overall if r['median_of_scene_median_delta_D'] is not None]
 hi=[r['q3_scene_median_delta_D'] for r in overall if r['median_of_scene_median_delta_D'] is not None]
 pooled_lo=[];pooled_hi=[]
 for dose in xs:
  vals=[r['delta_D'] for r in doses if r['dose_events']==dose and r['delta_D'] is not None]
  pooled_lo.append(float(np.quantile(vals,.25)));pooled_hi.append(float(np.quantile(vals,.75)))
 fig,ax=plt.subplots(figsize=(11,6)); cmap=plt.get_cmap('tab10'); scene_handles=[]
 ax.fill_between(xs,pooled_lo,pooled_hi,color='#D6DEE7',alpha=.65,lw=0,zorder=1,label='IQR across valid sequences')
 for si,scene in enumerate(SCENES):
  ss=[r for r in summary if r['scene_id']==scene and r['median_delta_D'] is not None]
  if not ss: continue
  sx=[r['dose_events'] for r in ss]; sm=[r['median_delta_D'] for r in ss]
  line,=ax.plot(sx,sm,color=cmap(si%10),lw=1.2,alpha=.85,zorder=2,label=scene);scene_handles.append(line)
 ax.plot(xs,med,color='#173B57',lw=3.2,zorder=3,label='Common trend (median)')
 ax.axhline(0,color='#777',lw=.7,zorder=0);ax.set_xlabel('Injection events');ax.set_ylabel('Delta D');ax.set_title(f'Individual scenes and common dose trend (Spearman rho={overall_rho:.3f})' if overall_rho is not None else 'Individual scenes and common dose trend')
 ax.grid(alpha=.2);ax.legend(handles=[plt.Rectangle((0,0),1,1,color='#D6DEE7',alpha=.65,label='IQR across valid sequences'),*scene_handles,plt.Line2D([0],[0],color='#173B57',lw=3.2,label='Common trend (median scene median)')],title='Dose response',ncol=2,fontsize=8,frameon=True);fig.tight_layout();fig.savefig(out/'holding-cross-scene-summary.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(3,4,figsize=(17,11),sharex=True)
 for ax,scene in zip(axes.flat,SCENES):
  rr_scene=[r for r in doses if r['scene_id']==scene]
  ax.scatter([r['dose_events'] for r in rr_scene],[np.nan if r['D'] is None else r['D'] for r in rr_scene],s=11,alpha=.35,color='#4C78A8',edgecolors='none')
  dose_medians=[]
  for dose in range(MAX_EVENTS+1):
   vals=[r['D'] for r in rr_scene if r['dose_events']==dose and r['D'] is not None]
   dose_medians.append((dose,float(np.median(vals)),float(np.quantile(vals,.25)),float(np.quantile(vals,.75))) if vals else None)
  curve=[r for r in dose_medians if r is not None]
  if curve:
   ax.plot([r[0] for r in curve],[r[1] for r in curve],color='#C44E52',lw=2,marker='o',ms=2.5)
   ax.fill_between([r[0] for r in curve],[r[2] for r in curve],[r[3] for r in curve],color='#C44E52',alpha=.16)
  ax.set_title(scene);ax.grid(alpha=.2)
 fig.supxlabel('Injection events');fig.supylabel('D');fig.tight_layout()
 fig.savefig(out/'holding-absolute-D.png',dpi=160);plt.close(fig)
 manifest.update(state='complete',rho_median_curve=overall_rho,elapsed_s=time.monotonic()-started,n_scenes=len(SCENES),n_sequences=len(seqs),n_dose_records=len(doses),n_injection_events=len(events))
 (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2))
 report=['# Holding injection experiment — 2026-10-27','',
 f'{len(SCENES)} fixed Changi scenes; excluded by request: {", ".join(EXCLUDED_SCENES)}. Ten random sequences per included scene; exactly thirty injection events per sequence. Each event inserts a 240-second racetrack at the original midpoint and deletes the transformed track final 24 ten-second samples. Sampling is with replacement among QC500 and geometry-eligible aircraft; repeated draws create repeated interventions. No straight control or outcome-selected cutoff is used.','',
 'Each injection adds 24 points and trims 24 points, preserving trajectory length. Repeated events can cause trimming of original or earlier synthetic samples; retained Holding time is reported separately from event count.','',
 'The reader filters invalid, ground, duplicate-time and QC-failing records. It requires barometric altitude, uses lastposupdate for horizontal time and snapshot time for altitude, aligns supported observations to a strict ten-second grid without extrapolation or filling, and converts WGS84 positions to local ENU. QC500 limits are 500 m/s horizontal speed, 100 m/s vertical speed, altitude -500 to 20,000 m, gaps at most 20 seconds and position update age at most 15 seconds.','',
 'The injection pool additionally requires at least 24 original samples after midpoint and valid midpoint heading and speed. Other QC500 aircraft remain in the scene background. The level closed racetrack uses local median speed, 60-second straight legs and 180-degree turns at 3 degrees/second.','',
 'The frozen epoch-90 Encoder is verified by SHA-256 and preprocessing ID. Complexity uses at least 15 scene samples, 64 geometric radii and the R-squared >= 0.90 fit gate. Failed D estimates remain missing. Delta D is relative to the sequence baseline. Spearman rho is descriptive association, not causal evidence.','',
 '## Main result','',
 '![Delta D by injection events](holding-delta-dose.png)','',
 'Each sequence is shown only as unconnected dose-level points. The solid line joins the median Delta D at each dose; the shaded band is the interquartile range across the ten sequences. Gaps indicate unavailable estimates. No sequence-level rho is calculated. Per-scene rho is calculated from that scene median curve; primary cross-scene rho is calculated from the median-of-scene-medians curve.','',
 '![Scene-level curves, pooled IQR range, and median trend](holding-cross-scene-summary.png)','',f'Thin colored lines show each estimable scene median Delta D, with a scene legend. The single background band is the IQR across all valid sequence-level Delta D estimates pooled across estimable scenes at each dose, so it includes within-scene sequence variation as well as differences across scenes. The thick line is the equal-weight median of scene medians. Spearman rho is calculated from that common trend and equals {overall_rho:.3f} across {len(overall_curve)} doses.','',
 '## Absolute D','',
 '![Absolute D by injection events](holding-absolute-D.png)','',
 'Absolute-D panels use the same display rule: unconnected sequence points with a per-dose median and interquartile band. The Delta-D aggregate curve, rather than the absolute-D panel, is the basis for the primary rho.','',
 '## Output files','',
 '- overall-dose-summary.csv and holding-cross-scene-summary.png: median of scene medians, IQR, and aggregate-curve rho.','- scene-rho-summary.csv and rho-summary.json: rho from each scene median curve and the primary cross-scene median curve.',
 'This is a synthetic sensitivity experiment; it does not establish operational workload validity or aircraft-specific flight feasibility.','']
 (out/'report.md').write_text('\n'.join(report),encoding='utf-8')
 manifest['files']={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='run-manifest.json'}
 (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print('COMPLETE',len(SCENES),len(seqs),len(doses),len(events),flush=True)
if __name__=='__main__': main()
