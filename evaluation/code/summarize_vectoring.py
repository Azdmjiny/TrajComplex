import json,csv,numpy as np
from pathlib import Path
from collections import defaultdict
from scipy.stats import spearmanr
from PIL import Image,ImageDraw,ImageFont
EXPERIMENT=Path(__file__).resolve().parents[1]; BASE=EXPERIMENT/'results'; FIGURES=EXPERIMENT/'figures'; REPORTS=EXPERIMENT/'reports'
data=json.loads((BASE/'synthetic-vectoring-evaluation-pilot.json').read_text(encoding='utf8'))
by=defaultdict(list); rhos=[]; total=ok=0; allrows=[]
for t in data['scenes']:
 by[t['scene_id']].append(t); n=t['n_vectoring_eligible']
 c=t['dose_curve']; xs=np.array([p['vectoring_aircraft'] for p in c]); ys=np.array([np.nan if p['dimension'] is None else p['dimension'] for p in c]); mask=np.isfinite(ys)
 if mask.sum()>=5:rhos.append(float(spearmanr(xs[mask],ys[mask]).statistic))
 total+=len(c);ok+=sum(mask)
 for p in c: allrows.append({'scene_id':t['scene_id'],'replicate':t['replicate'],'n_scene_aircraft':t['n_aircraft'],'n_vectoring_eligible':n,'vectoring_aircraft':p['vectoring_aircraft'],'vectoring_fraction':p['vectoring_aircraft']/n,'D':p['dimension'],'status':p['status'],'reason':p['reason']})
scenes=[]
for sid,ts in sorted(by.items()):
 first=ts[0]; base=first['dose_curve'][0]['dimension']; row={'scene_id':sid,'n_scene_aircraft':first['n_aircraft'],'n_vectoring_eligible':first['n_vectoring_eligible'],'baseline_D':base,'baseline_status':first['dose_curve'][0]['status'],'baseline_reason':first['dose_curve'][0]['reason']}
 for f in (0,.25,.5,.75,1):
  vals=[]
  for t in ts:
   ix=round(f*t['n_vectoring_eligible']); p=t['dose_curve'][min(ix,len(t['dose_curve'])-1)]
   if p['dimension'] is not None:vals.append(p['dimension'])
  row[f'D_{int(f*100)}pct_mean']=float(np.mean(vals)) if vals else None
  row[f'D_{int(f*100)}pct_n']=len(vals)
 scenes.append(row)
basevalid=[s for s in scenes if s['baseline_D'] is not None]
dose=[]
for f in (0,.25,.5,.75,1):
 vals=[s[f'D_{int(f*100)}pct_mean']-s['baseline_D'] for s in basevalid if s[f'D_{int(f*100)}pct_mean'] is not None]
 dose.append({'fraction':f,'mean_delta_D':float(np.mean(vals)) if vals else None,'n_hours':len(vals),'hour_sd':float(np.std(vals,ddof=1)) if len(vals)>1 else None})
bins=[]
for lo in np.arange(0,1,.1):
 hi=lo+.1; pts=[r for r in allrows if lo<=r['vectoring_fraction']<hi]
 good=sum(r['status']=='ok' for r in pts);bins.append({'midpoint':float((lo+hi)/2),'n':len(pts),'estimable':good,'rate':good/len(pts) if pts else None})
summary={'n_scenes':len(scenes),'n_replicates':len(data['scenes']),'n_estimate_points':total,'valid_points':ok,'valid_rate':ok/total,'baseline_estimable_scenes':len(basevalid),'per_curve_spearman':{'n_curves':len(rhos),'median':float(np.median(rhos)),'fraction_positive':float(np.mean(np.array(rhos)>0))},'dose_response':dose,'estimability_bins':bins,'scenes':scenes,'maneuver':data['maneuver']}
(BASE/'synthetic-vectoring-evaluation-summary.json').write_text(json.dumps(summary,indent=2,default=lambda o:o.item() if hasattr(o,'item') else str(o)),encoding='utf8')
with (BASE/'vectoring-dose-response.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
# figures
try:
 title=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',27); font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',18); small=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',15)
except: title=font=small=ImageFont.load_default()
def draw_axes(imtitle):
 im=Image.new('RGB',(1200,720),'white'); d=ImageDraw.Draw(im); d.text((55,25),imtitle,font=title,fill='#11243a'); return im,d
# dose response
im,d=draw_axes('D response to injected smooth vectoring')
fractions=[0,.25,.5,.75,1]
x0,y0,x1,y1=105,595,1130,140; ymin=-.01
scene_peaks=[s[f'D_{int(f*100)}pct_mean']-s['baseline_D'] for s in basevalid for f in fractions if s[f'D_{int(f*100)}pct_mean'] is not None]
ymax=max(scene_peaks+[q['mean_delta_D'] for q in dose if q['mean_delta_D'] is not None])+.03
px=lambda x:x0+x*(x1-x0); py=lambda y:y0-(y-ymin)/(ymax-ymin)*(y0-y1)
d.line((x0,y0,x1,y0),fill='#28384a',width=3);d.line((x0,y0,x0,y1),fill='#28384a',width=3)
for y in np.linspace(ymin,ymax,6):d.line((x0,py(y),x1,py(y)),fill='#e4e9ef',width=1);d.text((40,py(y)-8),f'{y:.2f}',font=small,fill='#34495e')
fractions=[0,.25,.5,.75,1]
for f in fractions:d.text((px(f)-18,y0+13),f'{int(f*100)}%',font=small,fill='#34495e')
d.text((110,80),f'Black: mean over {len(basevalid)} baseline-estimable hours; colored: individual hours; bars: bootstrap 95% CI',font=small,fill='#4a5562')
colors=['#2d79b8','#e07a2d','#3c9a70','#8d62aa','#d04f56','#548bba']
for i,s in enumerate(basevalid):
 pts=[]
 for f in fractions:
  v=s[f'D_{int(f*100)}pct_mean']
  if v is not None:pts.append((f,v-s['baseline_D']))
 for a,b in zip(pts,pts[1:]):d.line((px(a[0]),py(a[1]),px(b[0]),py(b[1])),fill=colors[i%len(colors)],width=2)
 for q in pts:d.ellipse((px(q[0])-4,py(q[1])-4,px(q[0])+4,py(q[1])+4),fill=colors[i%len(colors)])
rng=np.random.default_rng(43); means=[]
for f in fractions:
 arr=np.array([s[f'D_{int(f*100)}pct_mean']-s['baseline_D'] for s in basevalid if s[f'D_{int(f*100)}pct_mean'] is not None]);means.append(float(arr.mean()) if len(arr) else np.nan)
 boot=np.array([np.mean(rng.choice(arr,len(arr),replace=True)) for _ in range(3000)]) if len(arr)>1 else [arr.mean()]
 ci=np.quantile(boot,[.025,.975]);d.line((px(f),py(ci[0]),px(f),py(ci[1])),fill='#111111',width=4)
for i in range(len(fractions)-1):d.line((px(fractions[i]),py(means[i]),px(fractions[i+1]),py(means[i+1])),fill='#111111',width=5)
for f,m in zip(fractions,means):d.ellipse((px(f)-7,py(m)-7,px(f)+7,py(m)+7),fill='#111111')
d.text((440,660),'Vectoring aircraft / vectoring-eligible aircraft',font=small,fill='#34495e');d.text((20,330),'Change in D vs baseline',font=small,fill='#34495e')
im.save(FIGURES/'vectoring-dose-response.png')
# estimability
im,d=draw_axes('How often D remained estimable during vectoring injection');x0,y0,x1,y1=105,595,1130,150;px=lambda x:x0+x*(x1-x0);py=lambda y:y0-y*(y0-y1)
d.line((x0,y0,x1,y0),fill='#28384a',width=3);d.line((x0,y0,x0,y1),fill='#28384a',width=3)
for y in np.linspace(0,1,6):d.line((x0,py(y),x1,py(y)),fill='#e4e9ef',width=1);d.text((48,py(y)-8),f'{y:.0%}',font=small,fill='#34495e')
for i,b in enumerate(bins):
 if b['rate'] is None:continue
 if i:d.line((px(bins[i-1]['midpoint']),py(bins[i-1]['rate']),px(b['midpoint']),py(b['rate'])),fill='#d45b4d',width=4)
 d.ellipse((px(b['midpoint'])-6,py(b['rate'])-6,px(b['midpoint'])+6,py(b['rate'])+6),fill='#d45b4d')
for f in fractions:d.text((px(f)-18,y0+13),f'{int(f*100)}%',font=small,fill='#34495e')
d.text((110,85),'Unestimable D is missing, not zero.',font=small,fill='#4a5562');d.text((410,660),'Vectoring aircraft / vectoring-eligible aircraft',font=small,fill='#34495e');d.text((15,330),'Valid D estimates',font=small,fill='#34495e')
im.save(FIGURES/'vectoring-d-estimability.png')
# append report
report=REPORTS/'evaluation-pilot.md';s=report.read_text(encoding='utf8')
dose_text=', '.join(f"{int(q['fraction']*100)}% {q['mean_delta_D']:+.3f}" for q in dose[1:])
block=f'''\n## 平滑横向 Vectoring 注入\n\n按确认的规则，对每个小时中轨迹足够长的飞机逐架注入一次横向绕行：5 分钟内平滑偏移到 5 km，之后用 5 分钟平滑回到原航迹；左右方向随机，保持高度、采样时间和轨迹点数不变。每个场景有 35–63 架可注入飞机，仍保留该小时全部飞机的点云，每场景重复 5 个随机注入顺序。\n\n12 个场景中 6 个基线 D 可估计。60 条曲线的 Spearman 中位数为 {np.median(rhos):.3f}，其中 {np.mean(np.array(rhos)>0):.0%} 为正；在 6 个基线可估计小时中，平均 D 相对基线从 25%、50%、75%、100% 注入剂量分别变化 {dose_text}。方向上比 holding 实验更一致，但这是 6 个小时、单一绕行强度的合成几何实验，不能解释为真实 vectoring 工作负荷已经得到验证。2,800 个剂量点中 {ok} 个（{ok/total:.1%}）通过拟合门槛；基线可估计率仍为 6/12。\n\nVectoring 保持每条输入轨迹点数不变，因此减少了 holding 实验中 sum pooling 的长度混杂；但横向变形仍会改变轨迹方向、路程和 Encoder 表示。详细逐剂量结果见 `../results/vectoring-dose-response.csv` 和 `../results/synthetic-vectoring-evaluation-pilot.json`。\n\n![Vectoring 注入剂量与 D 变化](../figures/vectoring-dose-response.png)\n\n![Vectoring 下 D 可估计比例](../figures/vectoring-d-estimability.png)\n'''
if '## 平滑横向 Vectoring 注入' not in s:s=s.replace('\n## 飞机数量敏感性',block+'\n## 飞机数量敏感性')
report.write_text(s,encoding='utf8')
print(json.dumps({'n_scenes':len(scenes),'baseline_estimable':len(basevalid),'dose':dose,'valid_points':int(ok),'total_points':int(total),'rho_median':float(np.median(rhos)),'rho_positive':float(np.mean(np.array(rhos)>0))},indent=2))

