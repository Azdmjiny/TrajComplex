import json, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
EXPERIMENT=Path(__file__).resolve().parents[1]; base=EXPERIMENT/'results'; FIGURES=EXPERIMENT/'figures'; REPORTS=EXPERIMENT/'reports'
x=json.loads((base/'aircraft-count-sensitivity.json').read_text(encoding='utf8'))
valid_sids={s['scene_id'] for s in x['results'] if s['full_scene_baseline_D'] is not None}
summary=[]
for n in (30,40,50):
 rows=[s for s in x['results'] if s['n_aircraft']==n and s['scene_id'] in valid_sids]
 summary.append({'n_aircraft':n,'n_hours':len(rows),'median_valid_rate':float(np.median([s['valid_rate'] for s in rows])),'median_abs_delta_D':float(np.median([s['median_abs_delta_from_full_D'] for s in rows if s['median_abs_delta_from_full_D'] is not None])),'median_D_iqr':float(np.median([s['D_iqr'] for s in rows if s['D_iqr'] is not None]))})
fontp=r'C:\Windows\Fonts\arial.ttf'
try: title=ImageFont.truetype(fontp,27); font=ImageFont.truetype(fontp,18); small=ImageFont.truetype(fontp,15)
except: title=font=small=ImageFont.load_default()
im=Image.new('RGB',(1200,720),'white'); d=ImageDraw.Draw(im); d.text((55,25),'Aircraft count affects D estimation stability',font=title,fill='#11243a')
# two panels
for panel,(x0,x1,heading) in enumerate([(100,580,'Valid D estimates'),(680,1140,'Absolute deviation from full-scene D')]):
 y0,y1=590,165; d.text((x0,y1-45),heading,font=font,fill='#2a3f54');
 for q in np.linspace(0,1,6):
  y=y0-q*(y0-y1); d.line((x0,y,x1,y),fill='#e3e8ee',width=1); d.text((x0-52,y-8),f'{q:.0%}' if panel==0 else f'{q:.2f}',font=small,fill='#4a5968')
 d.line((x0,y0,x1,y0),fill='#28384a',width=2);d.line((x0,y0,x0,y1),fill='#28384a',width=2)
 xs=[x0+70,x0+230,x0+390]
 for xx,n in zip(xs,(30,40,50)):d.text((xx-14,y0+12),str(n),font=small,fill='#34495e')
 vals=[r['median_valid_rate'] if panel==0 else r['median_abs_delta_D'] for r in summary]
 if panel==1: vals=[min(1,v) for v in vals]
 def yv(v):return y0-v*(y0-y1)
 for i in range(2): d.line((xs[i],yv(vals[i]),xs[i+1],yv(vals[i+1])),fill='#2e79b8' if panel==0 else '#d2694a',width=4)
 for xx,v in zip(xs,vals):d.ellipse((xx-6,yv(v)-6,xx+6,yv(v)+6),fill='#2e79b8' if panel==0 else '#d2694a')
 d.text((x0+160,y0+52),'Aircraft in random subsample',font=small,fill='#34495e')
d.text((110,78),'Aggregated over six hours whose full point-cloud D was estimable; 50 random subsets per size/hour.',font=small,fill='#4a5562')
im.save(FIGURES/'aircraft-count-sensitivity.png')
# add findings to report
report=REPORTS/'evaluation-pilot.md'
s=report.read_text(encoding='utf8')
block='''\n## 飞机数量敏感性（同一批场景的随机子采样）\n\n另外对同 12 个小时场景做了点云样本数敏感性检查：每个小时随机抽取 30、40、50 架飞机各 50 次，比较 D 的可估计比例和相对完整小时点云 D 的绝对差异。为避免基线本身无法估计时误算偏差，偏差汇总只针对完整点云 D 可估计的 6 个小时。\n\n- 这 6 个小时里，D 可估计比例的场景中位数：30 架时 47%，40 架时 74%，50 架时 90%。\n- 与完整小时 D 的绝对差异中位数：30 架时 0.202，40 架时 0.129，50 架时 0.072；估计值的场景内 IQR 中位数也从 0.346 降到 0.104。\n\n这说明当前 D 对每小时飞机样本数较敏感：样本少时，估计更容易无法通过拟合门槛，且数值波动更大。因此“飞机数增加时 D 是否增加”不能作为复杂度有效性的预设检验；飞机数在本轮更适合作为估计稳定性控制因素。详细结果见 `../results/aircraft-count-sensitivity.csv` 与 [图](../figures/aircraft-count-sensitivity.png)。\n'''
if '## 飞机数量敏感性' not in s: s=s.replace('\n## 下一步建议\n',block+'\n## 下一步建议\n')
report.write_text(s,encoding='utf8')
print(json.dumps(summary,indent=2))

