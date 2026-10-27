#!/usr/bin/env python3
"""Exploratory segmented Vectoring experiment for Holding v7 scenes.

Newly authored runner: it uses the frozen Encoder and D estimator as model
components, but does not call the legacy Vectoring evaluation pipeline.
NIC/NACp evidence is absent for these hours, so this is not uncertainty-certified.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/Changi_paper_datasets_latest_2026-10-27'
RAW=DATA/'01_raw_observations/hourly_10s'
CHECKPOINT=ROOT/'Encoder/encoder/encoder.pt'
SCENES=['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z',
        '2026-09-15T06Z','2026-09-18T00Z','2026-09-20T04Z','2026-09-23T10Z',
        '2026-09-25T23Z','2026-09-28T07Z','2026-09-30T15Z']
ALL_SCENES=['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z',
            '2026-09-12T15Z',*SCENES[4:]]
SCENE_INDEX={s:i for i,s in enumerate(ALL_SCENES)}
DT=10.; WINDOW=61; PEAK=15000.; RAMP=150.; PLATEAU_END=450.; BLEND=30.
REPEATS=10; EVENT_CAP=30; SEED=20261027
LAT0=math.radians(1.3592111111111111); LON0=math.radians(103.989325); H0=6.66
A=6378137.; E2=6.69437999014e-3
CHECKPOINT_SHA='bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976'
PREPROCESSOR_ID='52fabdb80ff5221882becc2e326e0e51089dbcf324a155bf7330f41442fa1477'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def write_json(p,x): Path(p).write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf8')
def write_csv(p,rows):
 if not rows: Path(p).write_text('',encoding='utf8'); return
 with Path(p).open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r))); w.writeheader(); w.writerows(rows)
def ecef(lat,lon,h):
 n=A/np.sqrt(1-E2*np.sin(lat)**2)
 return np.stack(((n+h)*np.cos(lat)*np.cos(lon),(n+h)*np.cos(lat)*np.sin(lon),(n*(1-E2)+h)*np.sin(lat)),axis=-1)
def to_enu(lat,lon,h):
 lat,lon,h=np.radians(np.asarray(lat,float)),np.radians(np.asarray(lon,float)),np.asarray(h,float)
 d=ecef(lat,lon,h)-ecef(np.asarray(LAT0),np.asarray(LON0),np.asarray(H0))
 sl,cl,so,co=math.sin(LAT0),math.cos(LAT0),math.sin(LON0),math.cos(LON0)
 return np.stack((-so*d[...,0]+co*d[...,1],-sl*co*d[...,0]-sl*so*d[...,1]+cl*d[...,2],cl*co*d[...,0]+cl*so*d[...,1]+sl*d[...,2]),axis=-1)

def read_scene(path):
 """Independent reader matching the Holding v7 basic-QC contract."""
 grouped={}
 with gzip.open(path,'rt',encoding='utf8',newline='') as f:
  for r in csv.DictReader(f):
   if r.get('onground','').lower()=='true': continue
   try: x=[float(r[k]) for k in ('time','lat','lon','baroaltitude','geoaltitude','lastposupdate')]
   except (ValueError,TypeError,KeyError): continue
   if np.isfinite(x).all(): grouped.setdefault(r.get('icao24',''),[]).append(x)
 tracks={}; rejected=[]
 for aid,rows in sorted(grouped.items()):
  rows.sort(key=lambda x:x[0]); unique=[]
  for r in rows:
   if not unique or r[0]>unique[-1][0]: unique.append(r)
  a=np.asarray(unique,float); why=[]
  if len(a)<16: why.append('fewer_than_16_raw_records')
  if len(a)>1 and (np.diff(a[:,0])>20).any(): why.append('snapshot_gap_over_20s')
  if len(a)>1 and (np.diff(a[:,5])<=0).any(): why.append('position_time_not_advancing')
  if len(a)>1 and (np.diff(a[:,5])>20).any(): why.append('position_gap_over_20s')
  age=a[:,0]-a[:,5]
  if (age<0).any() or (age>15).any(): why.append('stale_position_update')
  if (np.abs(a[:,1])>90).any() or (np.abs(a[:,2])>180).any(): why.append('coordinate_range')
  if ((a[:,3]<-500)|(a[:,3]>20000)).any(): why.append('barometric_altitude_range')
  if len(a)>1 and np.all(np.diff(a[:,1:3],axis=0)==0,axis=1).any(): why.append('repeated_raw_position')
  if len(a)>1 and (np.abs(np.diff(a[:,3])/np.diff(a[:,0]))>100).any(): why.append('vertical_speed_over_100m_s')
  if why: rejected.append({'icao24':aid,'reasons':sorted(set(why))}); continue
  start=max(a[0,0],a[0,5]); stop=min(a[-1,0],a[-1,5]); grid=np.arange(start,stop+1e-7,DT)
  if len(grid)<30: rejected.append({'icao24':aid,'reasons':['fewer_than_30_grid_points']}); continue
  xyz=to_enu(a[:,1],a[:,2],a[:,3]); speed=np.linalg.norm(np.diff(xyz[:,:2],axis=0),axis=1)/np.diff(a[:,5])
  if (speed>500).any(): rejected.append({'icao24':aid,'reasons':['horizontal_speed_over_500m_s']}); continue
  p=np.column_stack((np.interp(grid,a[:,5],xyz[:,0]),np.interp(grid,a[:,5],xyz[:,1]),np.interp(grid,a[:,0],xyz[:,2])))
  if not np.isfinite(p).all(): rejected.append({'icao24':aid,'reasons':['nonfinite_resampled_track']}); continue
  tracks[aid]=p
 return tracks,rejected

def segment(track,start,side):
 """Create a 600s trapezoidal chord-normal stimulus and replace 61 points."""
 source=track[start:start+WINDOW].copy()
 if source.shape!=(WINDOW,3) or side not in (-1,1): raise ValueError('invalid_window_or_side')
 chord=source[-1,:2]-source[0,:2]; length=np.linalg.norm(chord)
 if length<=1.: raise ValueError('ambiguous_window_chord')
 normal=side*np.array([-chord[1],chord[0]])/length
 t=np.arange(WINDOW)*DT; dense=np.arange(601,dtype=float)
 center=np.column_stack([PchipInterpolator(t,source[:,j])(dense) for j in (0,1)])
 off=np.zeros(601); up=(dense<RAMP); flat=(dense>=RAMP)&(dense<=PLATEAU_END); down=dense>PLATEAU_END
 off[up]=PEAK*dense[up]/RAMP; off[flat]=PEAK; off[down]=PEAK*(600-dense[down])/(600-PLATEAU_END)
 k=int(BLEND); kernel=np.ones(k)/k
 off=np.convolve(np.r_[np.zeros(k//2),off,np.zeros(k-1-k//2)],kernel,'valid'); off[0]=off[-1]=0.
 # Calibrate the requested peak against the sampled source polyline, as a
 # distance-to-route target rather than assuming the chord-normal value equals it.
 line=source[:,:2]; a=line[:-1]; ab=np.diff(line,axis=0); denom=np.sum(ab*ab,axis=1)
 if (denom<=1e-12).any(): raise ValueError('zero_length_reference_segment')
 measured=0.
 for _ in range(3):
  displaced=center+off[:,None]*normal
  delta=displaced[:,None,:]-a[None,:,:]
  u=np.clip(np.sum(delta*ab[None,:,:],axis=2)/denom[None,:],0.,1.)
  nearest=a[None,:,:]+u[:,:,None]*ab[None,:,:]
  measured=float(np.linalg.norm(displaced[:,None,:]-nearest,axis=2).min(axis=1).max())
  if measured<=1.: raise ValueError('segment_cross_track_unresolved')
  if abs(measured-PEAK)<=.01: break
  off*=PEAK/measured; off[0]=off[-1]=0.
 out=source.copy(); out[:,:2]=np.column_stack([np.interp(t,dense,center[:,j]+off*normal[j]) for j in (0,1)])
 out[0]=source[0]; out[-1]=source[-1]
 v=np.diff(out[:,:2],axis=0)/DT; acc=np.diff(v,axis=0)/DT
 return out,{'side':side,'peak_target_m':PEAK,'peak_measured_m':measured,'max_sampled_speed_m_s':float(np.linalg.norm(v,axis=1).max()),
             'min_sampled_speed_m_s':float(np.linalg.norm(v,axis=1).min()),
             'max_sampled_acceleration_m_s2':float(np.linalg.norm(acc,axis=1).max()),'motion_certified':False}

def candidate_windows(track):
 out=[]
 # Slots are disjoint and fixed from the trajectory's first grid point.
 for start in range(0,len(track)-WINDOW+1,WINDOW):
  sides={}; diag={}; rejected={}
  for side in (-1,1):
   try: sides[side],diag[side]=segment(track,start,side)
   except (ValueError,FloatingPointError,np.linalg.LinAlgError) as e: rejected[str(side)]=str(e)
  if len(sides)==2: out.append({'start':start,'sides':sides,'diagnostics':diag,'rejection_reasons':{}})
  else: out.append({'start':start,'sides':sides,'diagnostics':diag,'rejection_reasons':rejected})
 return out

def draw_events(scene,pool,rep,max_events):
 seed=SEED+SCENE_INDEX[scene]*100003+rep; rng=np.random.default_rng(seed)
 # Fresh per-repeat copy; windows never leak across repeats.
 remaining={a:list(ws) for a,ws in pool.items() if ws}; events=[]
 for i in range(max_events):
  ids=sorted(a for a,ws in remaining.items() if ws)
  if not ids: break
  aid=ids[int(rng.integers(len(ids)))]; j=int(rng.integers(len(remaining[aid]))); w=remaining[aid].pop(j); side=int(rng.choice([-1,1]))
  events.append({'scene_id':scene,'replicate':rep,'seed':seed,'event':i+1,'icao24':aid,'window_start_index':w['start'],
    'window_end_index':w['start']+WINDOW-1,'window_start_offset_s':w['start']*DT,'side':side,
    'diagnostics':w['diagnostics'][side],'_trajectory':w['sides'][side]})
 return seed,events

def main():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,default=ROOT/'eval/results/vectoring-segmented-exploratory-2026-10-27-v1'); args=ap.parse_args(); out=args.output.resolve()
 if out.exists(): raise SystemExit(f'Output exists; choose a new path: {out}')
 if sha(CHECKPOINT)!=CHECKPOINT_SHA: raise SystemExit('epoch-90 checkpoint hash mismatch')
 sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'complexity')); import torch
 from Encoder.trajectory_encoder.inference import FrozenEncoder
 from calculator import ComplexityConfig,estimate_complexity
 torch.set_num_threads(2); enc=FrozenEncoder(CHECKPOINT,pooling='sum',device='cpu')
 if enc.preprocess['preprocessor_id']!=PREPROCESSOR_ID: raise SystemExit('Encoder preprocessing contract mismatch')
 cfg=ComplexityConfig(normalize=False,min_samples=15,min_r_squared=.90); started=time.monotonic(); out.mkdir(parents=True)
 scene_data={}; audit=[]; enc_calls=0; d_calls=0
 for scene in SCENES:
  tracks,rejected=read_scene(RAW/f'{scene}.csv.gz'); all_windows={a:candidate_windows(p) for a,p in tracks.items()}
  pool={a:[w for w in ws if w['sides']] for a,ws in all_windows.items()}; pool={a:w for a,w in pool.items() if w}
  ids=sorted(tracks); base=np.asarray([enc.encode(tracks[a])['embedding'] for a in ids]); enc_calls+=len(ids)
  pos=pdist(base); pos=pos[pos>0]
  if not len(pos) or pos.min()==pos.max(): raise RuntimeError(f'{scene}: degenerate baseline radius range')
  radii=np.geomspace(pos.min(),pos.max(),64); base_result=estimate_complexity(base,config=cfg,radii=radii,scene_id=scene).to_dict(); d_calls+=1
  scene_data[scene]={'tracks':tracks,'ids':ids,'id_index':{a:i for i,a in enumerate(ids)},'pool':pool,'base':base,'radii':radii,'base_result':base_result}
  audit.append({'scene_id':scene,'background_qc500':len(tracks),'rejected_preprocess':len(rejected),
    'aircraft_with_injectable_windows':len(pool),'injectable_windows':sum(map(len,pool.values())),
    'baseline_status':base_result['status'],'baseline_D':base_result['dimension'],'baseline_R2':base_result['r_squared'],
    'candidate_window_counts':{a:len(w) for a,w in pool.items()},
    'rejected_windows':{a:[{'start_index':w['start'],'reasons':w['rejection_reasons']} for w in ws if not w['sides']]
                        for a,ws in all_windows.items() if any(not w['sides'] for w in ws)},
    'preprocessing_rejections':rejected})
  print(json.dumps({'scene':scene,'background':len(tracks),'candidate_windows':sum(map(len,pool.values())),'baseline_D':base_result['dimension']}),flush=True)
 dose_max=min(EVENT_CAP,min(x['injectable_windows'] for x in audit))
 if dose_max<1: raise RuntimeError('no common dose available across all scenes')
 policy={'state':'complete','scenes':SCENES,'excluded_scene':'2026-09-12T15Z','repeats_per_scene':REPEATS,'common_max_events':dose_max,
  'event_cap_before_common_limit':EVENT_CAP,'dose':'number of vectoring events; aircraft sampled with replacement',
  'repeat_rule':'Repeated aircraft are allowed, but each event uses a different window from that aircraft; candidate windows are disjoint 61-point slots and are drawn without replacement within each replicate.',
  'window_rule':'600 seconds = 61 samples at 10-second cadence; replace in place and preserve original total trajectory point count.',
  'segment_geometry':{'shape':'150s outward linear ramp, 300s plateau, 150s return ramp; 30s moving-average corner blend','peak_offset_m':PEAK,'baseline':'PCHIP through observed points in the selected window; normal fixed to endpoint chord','altitude':'preserved point-for-point'},
  'processing':'Holding v7 basic QC, barometric altitude, position lastposupdate clock, altitude snapshot clock, bounded strict-10s interpolation, no extrapolation/fill, WGS84 ENU.',
  'quality_boundary':'No NIC/NACp data; no uncertainty-radius fit/certificate. Segment paths are schematic and not aircraft motion-certified.',
  'encoder_checkpoint_sha256':CHECKPOINT_SHA,'preprocessor_id':enc.preprocess['preprocessor_id'],'device':'cpu','seed_base':SEED,
  'complexity':cfg.__dict__,'dose_metric':'Each aircraft contributes one embedding regardless of its number of applied windows. Full cloud D is recomputed at every dose.',
  'delta_D':'relative to the same scene baseline','rho':'Spearman of median-of-scene-medians Delta-D over the full common dose range; descriptive only.'}
 write_json(out/'policy.json',policy)
 all_events=[]; all_doses=[]; sequences=[]
 for scene in SCENES:
  sd=scene_data[scene]; base=sd['base']; tracks=sd['tracks']; pool=sd['pool']; ix=sd['id_index']
  for rep in range(REPEATS):
   seed,events=draw_events(scene,pool,rep,dose_max); current=base.copy(); touched=set(); curve=[]
   for dose in range(dose_max+1):
    if dose==0: result=sd['base_result']
    else: result=estimate_complexity(current,config=cfg,radii=sd['radii'],scene_id=scene).to_dict(); d_calls+=1
    d=result['dimension'] if result['status']=='ok' else None; bd=sd['base_result']['dimension']
    row={'scene_id':scene,'replicate':rep,'seed':seed,'dose_events':dose,'unique_aircraft_injected':len(touched),
         'D':d,'delta_D':d-bd if d is not None and bd is not None else None,'fit_status':result['status'],
         'fit_reason':result['reason'],'R2':result['r_squared'],'fit_scales':len(result['fit_indices'])}
    curve.append(row); all_doses.append(row)
    if dose<dose_max:
     e=events[dose]; aid=e['icao24']; modified=tracks[aid].copy()
     for old in events[:dose+1]:
      if old['icao24']!=aid: continue
      w=next(w for w in pool[aid] if w['start']==old['window_start_index']); s=old['window_start_index']
      modified[s:s+WINDOW]=w['sides'][old['side']]
     assert len(modified)==len(tracks[aid])
     assert np.array_equal(modified[:,2],tracks[aid][:,2])
     current[ix[aid]]=enc.encode(modified)['embedding']; enc_calls+=1; touched.add(aid)
     assert current.shape==base.shape and len(current)==len(sd['ids'])
     all_events.append({k:v for k,v in e.items() if not k.startswith('_')})
   sequences.append({'scene_id':scene,'replicate':rep,'seed':seed,'n_aircraft':len(sd['ids']),
     'n_injectable_windows':sum(map(len,pool.values())),'actual_events':len(events),'dose_curve':curve})
  print(json.dumps({'scene':scene,'sequences':REPEATS,'dose_max':dose_max}),flush=True)

 scene_dose=[]
 for scene in SCENES:
  for dose in range(dose_max+1):
   vals=[r['delta_D'] for r in all_doses if r['scene_id']==scene and r['dose_events']==dose and r['delta_D'] is not None]
   scene_dose.append({'scene_id':scene,'dose_events':dose,'attempts':REPEATS,'valid_D':len(vals),
    'median_delta_D':float(np.median(vals)) if vals else None,'q1_delta_D':float(np.quantile(vals,.25)) if vals else None,
    'q3_delta_D':float(np.quantile(vals,.75)) if vals else None,'min_delta_D':float(np.min(vals)) if vals else None,'max_delta_D':float(np.max(vals)) if vals else None})
 overall=[]
 for dose in range(dose_max+1):
  sm=[r['median_delta_D'] for r in scene_dose if r['dose_events']==dose and r['median_delta_D'] is not None]
  pooled=[r['delta_D'] for r in all_doses if r['dose_events']==dose and r['delta_D'] is not None]
  overall.append({'dose_events':dose,'estimable_scenes':len(sm),'median_of_scene_medians_delta_D':float(np.median(sm)) if sm else None,
    'q1_scene_median_delta_D':float(np.quantile(sm,.25)) if sm else None,'q3_scene_median_delta_D':float(np.quantile(sm,.75)) if sm else None,
    'pooled_sequence_q1_delta_D':float(np.quantile(pooled,.25)) if pooled else None,'pooled_sequence_q3_delta_D':float(np.quantile(pooled,.75)) if pooled else None})
 for row in overall:
  row['n_estimable_scenes']=sum(r['scene_id'] in [x['scene_id'] for x in scene_dose if x['dose_events']==row['dose_events'] and x['median_delta_D'] is not None]
                                for r in audit)
 valid=[r for r in overall if r['median_of_scene_medians_delta_D'] is not None]; rho=None
 if len(valid)>=5 and len({r['median_of_scene_medians_delta_D'] for r in valid})>1:
  rho=float(spearmanr([r['dose_events'] for r in valid],[r['median_of_scene_medians_delta_D'] for r in valid]).statistic)
  if not np.isfinite(rho): rho=None
 write_json(out/'scene-population-audit.json',audit); write_json(out/'injection-events.json',all_events)
 write_json(out/'sequence-results.json',sequences); write_json(out/'dose-results.json',all_doses)
 write_csv(out/'scene-dose-summary.csv',scene_dose); write_csv(out/'overall-dose-summary.csv',overall)
 per_scene_rho=[]
 for scene in SCENES:
  rows=[r for r in scene_dose if r['scene_id']==scene and r['median_delta_D'] is not None]
  value=None
  if len(rows)>=5 and len({r['median_delta_D'] for r in rows})>1:
   value=float(spearmanr([r['dose_events'] for r in rows],[r['median_delta_D'] for r in rows]).statistic)
   if not np.isfinite(value): value=None
  per_scene_rho.append({'scene_id':scene,'baseline_status':scene_data[scene]['base_result']['status'],
    'baseline_D':scene_data[scene]['base_result']['dimension'],'estimable_doses':len(rows),'rho_median_curve':value,
    'reason':None if value is not None else 'insufficient_valid_doses_or_variation'})
 write_json(out/'rho-summary.json',{'primary_estimand':'Spearman rho of median-of-scene-medians Delta-D by event dose',
  'rho_median_curve':rho,'n_doses':len(valid),'n_scenes':len(SCENES),
  'scene_count_by_dose':{str(r['dose_events']):r['n_estimable_scenes'] for r in overall},
  'baseline_unestimable_scenes':[r['scene_id'] for r in audit if r['baseline_D'] is None],
  'per_scene':per_scene_rho,'sequence_level_rho_reported':False,
  'interpretation':'descriptive exploratory association'})
 import os; os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
 import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
 fig,ax=plt.subplots(figsize=(11,6)); cmap=plt.get_cmap('tab10')
 for i,scene in enumerate(SCENES):
  rs=[r for r in scene_dose if r['scene_id']==scene and r['median_delta_D'] is not None]
  if rs: ax.plot([r['dose_events'] for r in rs],[r['median_delta_D'] for r in rs],marker='o',ms=2.5,lw=1.2,color=cmap(i%10),label=scene)
 xs=[r['dose_events'] for r in valid]; ys=[r['median_of_scene_medians_delta_D'] for r in valid]
 if xs:
  lo=[r['pooled_sequence_q1_delta_D'] for r in valid]; hi=[r['pooled_sequence_q3_delta_D'] for r in valid]
  ax.fill_between(xs,lo,hi,color='#D6DEE7',alpha=.65,label='IQR across valid sequences'); ax.plot(xs,ys,color='#173B57',lw=3,label='Median of scene medians')
 ax.axhline(0,color='#777',lw=.7); ax.set_xlabel('Vectoring events'); ax.set_ylabel('Delta D from scene baseline')
 ax.set_title(f'Exploratory segmented Vectoring (rho={rho:.3f})' if rho is not None else 'Exploratory segmented Vectoring')
 ax.grid(alpha=.2); ax.legend(ncol=2,fontsize=8); fig.tight_layout(); fig.savefig(out/'vectoring-segmented-dose-response.png',dpi=160); plt.close(fig)
 report=['# Segment Vectoring — exploratory evaluation (2026-10-27)','',
  f'使用 Holding v7 的 11 个场景（排除 2026-09-12T15Z），每场景 {REPEATS} 条随机序列，公共 dose 为 0–{dose_max} 个注入事件。','',
  '## 注入定义','',
  '每次事件选择一架合格飞机的一段 600 秒轨迹，用 segment 轨迹替换该窗口原有 61 个 10 秒点；不增删点。同一架飞机可以重复被抽中，但每次使用该飞机另一个互不重叠窗口。一个场景点云里该飞机始终只贡献一个 embedding。注入窗口从小时轨迹起点开始按 61 点分槽；两侧均能生成才进入候选池。','',
  'Segment 几何为沿窗口端点弦线法向的 15 km 梯形偏移：150 秒外移、300 秒平台、150 秒返回，30 秒移动平均处理转折。局部名义中心线由观测点 PCHIP 插值。每个 dose 重新生成受影响飞机的完整固定长度轨迹，并重新计算全场 D。','',
  '## 数据处理','',
  '使用数据包中与 Holding v7 相同的 11 个小时文件。沿用基础 QC：过滤地面/无效/重复记录，要求气压高度，位置使用 lastposupdate、垂直坐标使用 snapshot 时间，在支持范围内对齐严格 10 秒网格，不外推、不填补；限制位置年龄、记录间隔、速度和高度，并转为 WGS84 局部 ENU。','',
  '这些小时没有 NIC/NACp，因此不做位置不确定度半径拟合或质量认证。PCHIP 和 segment 几何是名义轨迹构造，segment 运动没有飞机级可行性认证；结果只作探索性敏感性分析，不能与旧 Vectoring 认证结果直接等同。','',
  '## 评估','',
  f"固定 epoch-90 Encoder 和预处理契约。每场景以基线正距离范围生成 64 个尺度；D 至少 15 个样本、R²≥0.90。失败 D 保留为缺失。有效基线场景为 {sum(x['baseline_D'] is not None for x in audit)}/{len(audit)}；基线不可估场景为 {', '.join(x['scene_id'] for x in audit if x['baseline_D'] is None) or '无'}。公共 dose 上限是 30 与所有场景有效窗口总数最小值中的较小者。主 rho 为跨场景中位数 Delta-D 曲线的 Spearman 相关，仅为描述统计，不作因果解释。",'',
  '![Segment Vectoring dose response](vectoring-segmented-dose-response.png)','',
  '完整窗口筛选、拒绝原因、事件顺序、随机种子、逐剂量结果、图、policy 和哈希均保存在本目录。']
 (out/'report.md').write_text('\n'.join(report),encoding='utf8')
 manifest={'state':'complete','date':'2026-10-27','data_root':str(DATA),'data_manifest_sha256':sha(DATA/'MANIFEST.json'),
  'source_hour_sha256':{scene:sha(RAW/(scene+'.csv.gz')) for scene in SCENES},
  'checkpoint_sha256':CHECKPOINT_SHA,'preprocessor_id':enc.preprocess['preprocessor_id'],'config':cfg.__dict__,
  'policy_sha256':sha(out/'policy.json'),'runner_sha256':sha(Path(__file__)),'n_scenes':len(SCENES),
  'repeats_per_scene':REPEATS,'dose_max':dose_max,'n_sequences':len(sequences),'n_dose_records':len(all_doses),
  'n_events':len(all_events),'encoder_calls':enc_calls,'D_calls':d_calls,'rho_median_curve':rho,'elapsed_s':time.monotonic()-started,
  'files':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='run-manifest.json'}}
 write_json(out/'run-manifest.json',manifest)
 print('COMPLETE '+json.dumps({'scenes':len(SCENES),'dose_max':dose_max,'sequences':len(sequences),'dose_records':len(all_doses),'events':len(all_events),'rho':rho,'output':str(out)}),flush=True)
if __name__=='__main__': main()
