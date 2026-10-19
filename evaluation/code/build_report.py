"""Generate the canonical GitHub-readable Markdown evaluation report."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def fmt(v):return f'{v:.3f}' if v is not None else '不可计算'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf8'))
    f=json.loads((ROOT/'figures/index.json').read_text(encoding='utf8'))
    run=json.loads((ROOT/'results/run-manifest.json').read_text(encoding='utf8'))
    rows=[];paired=[];cuts=[];vector=[]
    for v in ['qc500','qc350']:
        for label,key in [('全部场景','all'),('仅基线可估计','baseline_ok')]:
            a=s[v]['holding'][key]['full'];b=s[v]['holding'][key]['retained'];p=s[v]['holding'][key]['paired_comparison']
            rows.append([v,label,a['n'],fmt(a['median']),b['n'],fmt(b['median']),f"{b['positive']}/{b['n']}"])
            paired.append([v,label,p['full']['n'],fmt(p['full']['median']),fmt(p['retained']['median'])])
        for q in s[v]['holding']['scenes']:
            cut=f"{q['cutoff']}/{q['n_aircraft']} ({q['cutoff_fraction']:.1%})" if q['cutoff'] is not None else '无合格峰值'
            cuts.append([v,q['scene_id'],cut,f"{q['full']['n']} → {q['retained']['n']}",fmt(q['full']['median']),fmt(q['retained']['median'])])
    for v in ['qc500','qc350','qc500_safe','qc350_safe']:
        q=s[v]['vectoring']['all']['full'];vector.append([v,q['n'],fmt(q['median']),f"{q['positive']}/{q['n']}"])
    text='''# 修复与筛选后的 Holding / Vectoring evaluation

更新日期：2026-10-19。本报告直接替换原 `evaluation-pilot.md`；当前结果、图和复现代码位于原有 `results/`、`figures/`、`code/`。Git 历史保留之前的已提交版本，不另设日期版本目录。完整剂量曲线仍保存；截断只决定相关性使用哪些点。

**结论范围：Holding 截断后的前段呈明显正相关，但峰值由同一批结果选择，因此这是事后、探索性的局部关联，不能视为独立验证，不能证明下降段无效，也不能证明算法已超出适用范围。** 完整范围仍然先升后降。Vectoring 不截断，清洗后正相关仍存在。五次随机顺序是小时内重复，不是五个独立小时；不报告确认性 p 值。

## 已修复的问题

- Holding 第二次转弯不再额外旋转起始朝向；先验证轨迹自然闭合，再吸附末点以消除浮点误差，避免原来的大幅跳跃。
- 原始轨迹除空缺、非有限值、地面记录、长度和间隔筛选外，增加经纬度范围、高度 −500 至 20000 m、水平速度以及垂直速度绝对值 ≤100 m/s 检查。整条飞机—小时被剔除，不通过插值修补异常跳变。主筛选水平速度 ≤500 m/s，严格敏感性筛选 ≤350 m/s；这是诊断阈值，并非已验证飞行包线。
- Vectoring 的候选机动增加左右两种偏移均 ≤500 m/s 的速度筛选。失败飞机仍留在合格基线点云中，但不注入。`safe` 仅为运行名，不保证全部物理可行性。改变坐标会改变速度，不能称为保持原速度。
- 相关性严格要求 `status=ok`、D 有限、至少五个有效点。报告分母按实际可计算曲线数生成；100% 剂量纳入最后一个可估计率分箱；飞机数不足时跳过对应子采样规模。
- 原先手工替换数字的报告脚本改为统一数据生成流程，避免旧数字重新覆盖报告。

## 实验条件

固定原来的 12 个小时与每小时 5 个随机注入顺序，不因清洗结果更换场景。先生成原飞机顺序及 Vectoring 左右方向，再移除不合格飞机，保留幸存飞机的相对顺序和方向。主筛选保留 761/771 条飞机—小时轨迹，严格筛选保留 652/771 条。

使用同一 frozen Encoder、sum pooling、未归一化 Euclidean 距离。每个场景按自身基线生成 64 个固定半径，估计器质量门槛不变：至少 30 个点、至少 8 个拟合尺度、尺度跨度至少 2 倍、相关积分区间 0.02–0.3、R²≥0.98。

Holding 每架增加 48 个五秒采样点；长度与 sum pooling 的混杂仍存在。尚未通过等长度对照或多样化 holding 对照解释下降机制。本报告没有将这些未采用的对照纳入结论。

## Holding 截断规则

每小时五个随机顺序共用一个截断点：计算每个剂量有效 D 的平均值，只允许至少三个有效重复的剂量参与选峰，取平均 D 首次达到全局最高值的位置。保留峰值及之前的全部剂量，不平滑、不逐曲线挑峰。峰前的局部下降仍保留，不是逐段删除所有负斜率。

## Holding：全部可用曲线

'''
    text+=table(['筛选','样本范围','完整曲线数','完整 ρ 中位数','截断曲线数','截断 ρ 中位数','截断正相关'],rows)
    text+='''

QC500 截断后 50 条曲线全部为正；原来的 60 条中，10 条因保留段有效点不足而不能计算。QC350 为 53 条中 52 条正相关，不能忽略这些分母变化。

## 同一批曲线的配对比较

'''+table(['筛选','样本范围','前后均可计算曲线数','完整 ρ 中位数','截断 ρ 中位数'],paired)
    text+='''

主筛选中，6 个基线有效小时的 30 条曲线全部保留，ρ 中位数从 0.191 升到 0.928；这个比较没有曲线数量变化，但仍存在峰值选取偏差。按小时先取重复中位数，QC500 截断后有 11 个可计算小时，11 个均为正，小时中位数为 0.904；QC350 同样为 11 个小时，中位数为 0.877。

## 每小时截断点

'''+table(['筛选','小时（UTC）','截断飞机数 / 场景飞机数','曲线数：完整 → 截断','完整小时 ρ','截断小时 ρ'],cuts)
    text+='''

QC500 的截断比例约 39%–59%，并非统一截掉 50% 以后。QC350 的 2026-09-30T15Z 没有任何剂量满足三个有效重复，未强行选峰；QC500 同一小时虽然存在合格峰值，但截断后各曲线不足五个有效点，仍不能计算相关性。

## Vectoring：完整范围，不截断

'''+table(['筛选','可计算曲线','ρ 中位数','正相关曲线'],vector)
    text+='''

主结果使用统一数据 `experiment-results.json` 中的 `qc500_safe.vectoring`（QC500 加候选机动速度筛选）。未进行候选机动筛选的 QC500 与 QC350 仅作为敏感性对照，保存在统一的 `experiment-results.json` 中。正相关支持对合成变形的响应，尚不能证明真实管制工作负荷的有效性。

## 飞机数量敏感性

在 QC500 的六个完整基线可估计小时中，N=30、40、50 的可估计率小时中位数分别为 52%、67%、92%；相对完整点云 D 的绝对差中位数分别为 0.235、0.126、0.048。每个规模随机子采样 50 次。严格筛选的 N=50 只有五个小时满足飞机数条件且基线有效；不能把样本组成变化误读成纯飞机数效应。

## 图

Matplotlib 生成 200 dpi PNG 和矢量 SVG。彩色表示 Holding 保留段，灰色表示排除段，黑线是各剂量可用重复的均值，橙色虚线和星号是所选峰值。缺失 D 不补零；参与均值的重复数可能变化。各图均保留完整范围作为参照。

'''
    for name in f['figures']:
        text+=f'### {name}\n\n![{name}](../figures/{name}.png)\n\n[矢量 SVG](../figures/{name}.svg)\n\n'
    text+='''## 数据和复现

- [全部统计与逐小时结果](../results/summary.json)
- [统一完整剂量数据](../results/experiment-results.json)
- [Holding 逐点保留与排除原因](../results/qc500-holding-point-selection.csv)
- [严格筛选逐点清单](../results/qc350-holding-point-selection.csv)
- [原始轨迹剔除清单](../results/quality_audit.json)
- [飞机数量敏感性数据](../results/aircraft-count-sensitivity.json)
- [运行环境和源文件哈希](../results/run-manifest.json)
- [统计规则和输入哈希](../results/analysis-manifest.json)
- [执行说明](../README.md)

从已保存完整结果重新生成统计、图和本报告，不需要原始轨迹或 checkpoint：

```bash
python evaluation/code/refresh_outputs.py
```

从原始轨迹重跑 Encoder 推理及全部实验，需要设置 `ATM_DATA_ZIP` 和 `ATM_ENCODER_CHECKPOINT`：

```bash
python evaluation/code/run_evaluation.py
python evaluation/code/refresh_outputs.py
```

'''
    text+=f"本次推理环境：PyTorch `{run['torch']}`，device `{run['device']}`。Checkpoint SHA256：`{run['checkpoint_sha256']}`。\n"
    (ROOT/'reports/evaluation-pilot.md').write_text(text,encoding='utf8')
    manifest=ROOT/'results/analysis-manifest.json';m=json.loads(manifest.read_text());m['matplotlib']=f['matplotlib'];m['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'code').glob('*.py')};manifest.write_text(json.dumps(m,indent=2),encoding='utf8')
    print('Updated reports/evaluation-pilot.md')
if __name__=='__main__':main()
