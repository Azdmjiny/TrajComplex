import json, math, statistics, csv
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr, linregress
from PIL import Image, ImageDraw, ImageFont
EXPERIMENT=Path(__file__).resolve().parents[1]; BASE=EXPERIMENT/'results'; FIGURES=EXPERIMENT/'figures'; REPORTS=EXPERIMENT/'reports'
REPEATS=5
source=BASE/'synthetic-holding-evaluation-pilot.json'
out=BASE/'synthetic-holding-evaluation-summary.json'
doc=REPORTS/'evaluation-pilot.md'
fig1=FIGURES/'holding-dose-response.png'; fig2=FIGURES/'holding-d-estimability.png'
data=json.loads(source.read_text(encoding='utf-8'))
scenes={}
for trial in data['scenes']:
    scenes.setdefault(trial['scene_id'],[]).append(trial)

scene_summ=[]; run_rhos=[]; overall=[]
for sid,trials in scenes.items():
    curves=[t['dose_curve'] for t in trials]
    baseline=curves[0][0]['dimension']
    n=trials[0]['n_aircraft']
    scene_summary={'scene_id':sid,'n_aircraft':n,'baseline_D':baseline,'baseline_status':curves[0][0]['status'],'baseline_reason':curves[0][0]['reason']}
    for frac in [0,.25,.5,.75,1]:
        vals=[]
        for c in curves:
            j=round(frac*n)
            pt=c[min(j,len(c)-1)]
            if pt['dimension'] is not None: vals.append(pt['dimension'])
        scene_summary[f'D_at_{int(frac*100)}pct_mean']=float(np.mean(vals)) if vals else None
        scene_summary[f'D_at_{int(frac*100)}pct_n']=len(vals)
    scene_summ.append(scene_summary)
    for trial in trials:
        c=trial['dose_curve']; xs=np.array([p['holding_aircraft'] for p in c],float)
        ys=np.array([np.nan if p['dimension'] is None else p['dimension'] for p in c],float)
        mask=np.isfinite(ys)
        if mask.sum()>=5:
            rho=float(spearmanr(xs[mask],ys[mask]).statistic)
            run_rhos.append(rho)
        for p in c:
            overall.append((sid, p['holding_aircraft']/n, p['dimension'], baseline, p['status']))

valid_base=[x for x in scene_summ if x['baseline_D'] is not None]
# Treat hour as the independent unit: average random orders within each scene before the across-hour summary.
curve_rows=[]
for frac in [0,.25,.5,.75,1]:
    vals=[]
    for s in valid_base:
        v=s[f'D_at_{int(frac*100)}pct_mean']
        if v is not None: vals.append(v-s['baseline_D'])
    curve_rows.append({'holding_fraction':frac,'mean_delta_D':float(np.mean(vals)) if vals else None,'n_hours':len(vals),'hour_sd':float(np.std(vals,ddof=1)) if len(vals)>1 else None})

# Estimate reliability by treatment dose, in 10% bins.
bins=[]
for lo in np.arange(0,1.0,0.1):
    hi=lo+0.1
    vals=[x for x in overall if lo <= x[1] < hi or (hi>=1 and x[1]<=1 and lo<=x[1])]
    okay=sum(v[4]=='ok' for v in vals)
    bins.append({'dose_midpoint':float((lo+hi)/2),'n':len(vals),'estimable':okay,'rate':okay/len(vals) if vals else None})

rho_summary={'n_scene_replicates_with_at_least_5_finite_doses':len(run_rhos),'median_spearman_rho':float(np.median(run_rhos)) if run_rhos else None,'fraction_positive':float(np.mean(np.array(run_rhos)>0)) if run_rhos else None}
result={'pilot_scope':{'n_scenes':len(scenes),'repeats_per_scene':5,'scene_replicates':sum(map(len,scenes.values())),'dose_points':sum(len(t['dose_curve']) for t in data['scenes']),'encoder_checkpoint':data['checkpoint'],'device':data['device']},'dose_response_statistics':rho_summary,'delta_D_by_holding_fraction':curve_rows,'D_estimability_by_holding_fraction_bins':bins,'scene_summaries':scene_summ}
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
# CSV for inspection/reuse
with (BASE/'holding-dose-response.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['scene_id','replicate','holding_aircraft','holding_fraction','D','status','reason'])
    for t in data['scenes']:
        for p in t['dose_curve']:
            w.writerow([t['scene_id'],t['replicate'],p['holding_aircraft'],p['holding_aircraft']/t['n_aircraft'],p['dimension'],p['status'],p['reason']])

# Fonts/colors for clean report figures.
font_path=r'C:\Windows\Fonts\arial.ttf'
try: font=ImageFont.truetype(font_path,21); small=ImageFont.truetype(font_path,15); title=ImageFont.truetype(font_path,27)
except: font=small=title=ImageFont.load_default()
W,H=1200,720

def base_img(title_text):
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im); d.text((60,25),title_text,font=title,fill='#11243a'); return im,d

def axes(draw, x0=105,y0=595,x1=1130,y1=110):
    draw.line((x0,y0,x1,y0),fill='#28384a',width=3); draw.line((x0,y0,x0,y1),fill='#28384a',width=3)

# Figure 1: per-hour average dose curves and across-hour mean delta.
im,d=base_img('How estimated D changes as holding is added')
xs=[0,.25,.5,.75,1]; x0,y0,x1,y1=105,595,1130,110
vals=[r['mean_delta_D'] for r in curve_rows if r['mean_delta_D'] is not None]
ymin=min(-.15,min(vals)-.08) if vals else -.2; ymax=max(vals)+.1 if vals else 1
# include zero baseline
def px(x): return x0+x*(x1-x0)
def py(y): return y0-(y-ymin)/(ymax-ymin)*(y0-y1)
axes(d,x0,y0,x1,y1)
for y in np.linspace(ymin,ymax,6):
    d.line((x0,py(y),x1,py(y)),fill='#e4e9ef',width=1); d.text((35,py(y)-9),f'{y:.2f}',font=small,fill='#34495e')
for x in xs:
    d.line((px(x),y0,px(x),y0+7),fill='#28384a',width=2); d.text((px(x)-18,y0+14),f'{int(x*100)}%',font=small,fill='#34495e')
if ymin<=0<=ymax:d.line((x0,py(0),x1,py(0)),fill='#68798b',width=2)
# Plot each independent hour with valid baseline.
colors=['#2d79b8','#e07a2d','#3c9a70','#8d62aa','#d04f56','#548bba','#b18a2f','#518a8e','#a6547c','#74824a','#4b6a9a','#c26a45']
scene_curve={}
for i,s in enumerate(valid_base):
    pts=[]
    for frac in xs:
        v=s[f'D_at_{int(frac*100)}pct_mean']
        if v is not None: pts.append((frac,v-s['baseline_D']))
    scene_curve[s['scene_id']]=pts
    for a,b in zip(pts,pts[1:]): d.line((px(a[0]),py(a[1]),px(b[0]),py(b[1])),fill=colors[i%len(colors)],width=2)
    for a in pts: d.ellipse((px(a[0])-4,py(a[1])-4,px(a[0])+4,py(a[1])+4),fill=colors[i%len(colors)])
# Mean with bootstrap CI across hours.
rng=np.random.default_rng(43); means=[]; cis=[]
for j,frac in enumerate(xs):
    arr=np.array([s[f'D_at_{int(frac*100)}pct_mean']-s['baseline_D'] for s in valid_base if s[f'D_at_{int(frac*100)}pct_mean'] is not None])
    means.append(float(arr.mean()) if len(arr) else np.nan)
    boot=np.array([np.mean(rng.choice(arr,size=len(arr),replace=True)) for _ in range(3000)]) if len(arr)>1 else np.array([arr.mean()])
    cis.append((float(np.quantile(boot,.025)),float(np.quantile(boot,.975))))
for j,(m,ci) in enumerate(zip(means,cis)):
    if not np.isfinite(m):continue
    d.line((px(xs[j]),py(ci[0]),px(xs[j]),py(ci[1])),fill='#101820',width=4)
for a,b in zip(enumerate(means),enumerate(means[1:],1)):
    i,va=a; j,vb=b
    if np.isfinite(va) and np.isfinite(vb):d.line((px(xs[i]),py(va),px(xs[j]),py(vb)),fill='#111111',width=5)
for x,m in zip(xs,means):
    if np.isfinite(m): d.ellipse((px(x)-7,py(m)-7,px(x)+7,py(m)+7),fill='#111111')
d.text((440,660),'Aircraft with one injected racetrack holding / scene aircraft',font=small,fill='#34495e')
d.text((22,330),'Change in D vs baseline',font=small,fill='#34495e')
d.text((112,75),f'Black: mean across {len(valid_base)} baseline-estimable hours; colored: individual hours; bars: bootstrap 95% CI',font=small,fill='#4a5562')
im.save(fig1)

# Figure 2: estimability fraction over dose.
im,d=base_img('How often the D estimator returned a valid estimate')
axes(d)
for y in np.linspace(0,1,6):
    yy=y0-y*(y0-y1); d.line((x0,yy,x1,yy),fill='#e4e9ef',width=1); d.text((48,yy-8),f'{y:.0%}',font=small,fill='#34495e')
for b in bins:
    if b['rate'] is not None:
        x=px(b['dose_midpoint']); y=y0-b['rate']*(y0-y1); d.ellipse((x-6,y-6,x+6,y+6),fill='#d45b4d');
for a,b in zip(bins,bins[1:]):
    if a['rate'] is not None and b['rate'] is not None:
        d.line((px(a['dose_midpoint']),y0-a['rate']*(y0-y1),px(b['dose_midpoint']),y0-b['rate']*(y0-y1)),fill='#d45b4d',width=4)
for x in [0,.25,.5,.75,1]: d.text((px(x)-16,y0+14),f'{int(100*x)}%',font=small,fill='#34495e')
d.text((420,660),'Aircraft with injected holding / scene aircraft',font=small,fill='#34495e')
d.text((30,318),'Valid D estimates',font=small,fill='#34495e')
d.text((112,75),'An unestimable D is counted as missing, not treated as zero.',font=small,fill='#4a5562')
im.save(fig2)

# Human-readable Chinese summary.
rows='\n'.join(f"| {s['scene_id']} | {s['n_aircraft']} | {s['baseline_status']}"+(f" ({s['baseline_D']:.3f})" if s['baseline_D'] is not None else f" ({s['baseline_reason']})")+" |" for s in scene_summ)
trend='、'.join(f"{int(x['holding_fraction']*100)}%: {x['mean_delta_D']:+.3f}（{x['n_hours']} 个小时场景）" if x['mean_delta_D'] is not None else f"{int(x['holding_fraction']*100)}%: 无有效值" for x in curve_rows)
report=f'''# 合成 Racetrack Holding 对复杂度 D 的 pilot evaluation\n\n## 这轮实验想回答什么\n\n检查 Encoder + 点云经验关联维数是否会随着场景中加入的 holding 数量而变化。这个实验是在检验指标对人工注入机动的响应，不等于证明真实运行复杂度已经被准确预测。\n\n## 怎么做\n\n- 使用 OpenSky Changi 2026-09 原始 10 秒轨迹；每小时一场景，每个点对应一架飞机的整段小时轨迹。\n- 用提供的 16 维 Encoder、sum pooling，把每架轨迹编码为一个点；用未归一化 Euclidean distance 和现有的相关维数估计器计算 D。\n- 从 9 月中满足数据条件的小时中，按日期均匀抽取 {len(scenes)} 个场景，每小时至少 50 架可用飞机；每场景做 {REPEATS} 个随机飞机顺序。\n- 每次随机选一架飞机，在轨迹中点插入一圈合成 racetrack holding，然后重新编码该轨迹、更新点云并重算 D；逐架递增，直到该小时每架可用飞机都加过一圈。\n- Holding 的 pilot 几何规则：每段直飞 60 秒，转弯率 3°/秒、每次 180° 转弯 60 秒；速度取局部轨迹地速，高度固定；完整一圈约 4 分钟。\n- 对每个小时固定使用基线点云的 64 个半径尺度，以便每个剂量下的 D 在相同半径上估计。\n\n## 结果\n\n12 个场景共 {sum(map(len,scenes.values()))} 条随机剂量曲线、{sum(len(t['dose_curve']) for t in data['scenes'])} 个 D 估计点。每条曲线中，在至少 5 个剂量点有可估计 D 的 {rho_summary['n_scene_replicates_with_at_least_5_finite_doses']} 条，其 Spearman 相关系数中位数为 {rho_summary['median_spearman_rho']:.3f}，其中 {rho_summary['fraction_positive']:.0%} 为正。这个逐曲线统计包含同一小时的重复顺序，只作描述，不能把随机顺序当独立小时样本。\n\n对基线 D 可估计的 {len(valid_base)}/{len(scenes)} 个小时，先在每个小时内平均 5 个随机顺序，再比较 D 相对基线的变化：{trend}。在部分小时里，加入一些 holding 后 D 上升；继续加到很高剂量时，曲线有时变平或下降，且部分剂量的拟合未通过估计器质量门槛。\n\n| 小时场景 | 可用飞机数 | 基线 D |\n|---|---:|---|\n{rows}\n\n## 初步解释\n\n1. 这轮结果有初步的方向性信号：在可估计的小时里，增加 holding 往往会让 D 高于基线，说明表示可能对轨迹机动变化有响应。\n2. 响应不是稳定单调的；部分基线或处理后的 D 无法通过尺度拟合条件。因此现阶段不能得出“holding 越多，复杂度必然越高”的强结论。\n3. 每条 holding 让轨迹多 48 个 5 秒采样点，而当前 Encoder 使用 sum pooling。D 的变化可能同时来自新机动形状和序列长度/向量模长变化；后续需要把这个混杂单独分析。\n4. 这些是合成几何注入实验。它验证的是算法对可控轨迹变化的敏感性，不代表 OpenSky 中有对应的真实 holding 标签，也不直接证明复杂度标签对应真实管制负荷。\n\n## 下一步建议\n\n先检查不可估计原因、D 的 log-log 曲线和序列长度效应，再扩大到更多小时。飞机数量实验应通过同一小时点云的随机子采样评估估计稳定性，不能把“飞机数越多，D 必须越大”当作预设规律。Vectoring 也可以采用同样的逐架注入、逐次重算流程，但其几何定义（偏航角、持续时间、横向偏移）需要先固定，避免挑一个特定强度后误读为一般结论。\n\n## 图\n\n- [Holding 剂量与 D 变化](../figures/{fig1.name})\n- [不同剂量下 D 的可估计比例](../figures/{fig2.name})\n- [逐场景、逐重复结果 CSV](../results/{(BASE/'holding-dose-response.csv').name})\n'''
doc.write_text(report,encoding='utf-8')
print(json.dumps({'scenes':len(scenes),'baseline_estimable':len(valid_base),'runs_with_rho':rho_summary,'delta_curve':curve_rows,'estimability':bins,'report':str(doc),'figures':[str(fig1),str(fig2)]},ensure_ascii=False,indent=2))

