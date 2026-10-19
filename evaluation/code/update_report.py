from pathlib import Path
import os
import json, hashlib
EXPERIMENT=Path(__file__).resolve().parents[1]; base=EXPERIMENT/'results'; report_dir=EXPERIMENT/'reports'
ck=Path(os.environ["ATM_ENCODER_CHECKPOINT"]).expanduser()
sha=hashlib.sha256(ck.read_bytes()).hexdigest()
pilot=base/'synthetic-holding-evaluation-pilot.json'; data=json.loads(pilot.read_text(encoding='utf8'))
data['checkpoint_sha256']=sha; data['preprocessor_id']='d69735dd5a1587c6720a4f5867a860e6a3b47fdb9ba81b239f80e1dfa5afeb35'; data['torch_version']='2.14.0+cu130'; data['gpu']='NVIDIA GeForce RTX 5060 Laptop GPU'
pilot.write_text(json.dumps(data,indent=2),encoding='utf8')
summary=base/'synthetic-holding-evaluation-summary.json'; s=json.loads(summary.read_text(encoding='utf8')); s['checkpoint_sha256']=sha; s['preprocessor_id']=data['preprocessor_id']; s['torch_version']=data['torch_version']; s['gpu']=data['gpu']; summary.write_text(json.dumps(s,indent=2),encoding='utf8')
report=report_dir/'evaluation-pilot.md'; text=report.read_text(encoding='utf8')
text=text.replace('12 个场景共 60 条随机剂量曲线、3915 个 D 估计点。每条曲线中，在至少 5 个剂量点有可估计 D 的 60 条，其 Spearman 相关系数中位数为 -0.052，其中 45% 为正。这个逐曲线统计包含同一小时的重复顺序，只作描述，不能把随机顺序当独立小时样本。', '12 个场景共 60 条随机剂量曲线、3915 个 D 估计点；其中 3281 个通过质量门槛（83.8%），其余 634 个均因 log-log 拟合 R² 未达到 0.98 而标为不可估计。每条曲线都有至少 5 个有效 D 点；逐曲线 Spearman 相关系数中位数为 -0.052，45% 为正。这表明整体没有稳定的单调递增关系。逐曲线统计包含同一小时的重复顺序，只作描述，不能把随机顺序当独立小时样本。')
text=text.replace('在部分小时里，加入一些 holding 后 D 上升；继续加到很高剂量时，曲线有时变平或下降，且部分剂量的拟合未通过估计器质量门槛。', '在基线可估计的小时里，平均 D 在 25%–75% 注入剂量高于基线，但到全体飞机都注入时回落到接近基线；这是一个非单调的“先升后降”形状，而非“holding 越多 D 越高”。全剂量点仅 4 个小时仍可估计，需谨慎解读。')
text=text.replace('## 这轮实验想回答什么', '## 这轮实验想回答什么')
text=text.replace('## 怎么做\n', f'## 怎么做\n\n- Encoder checkpoint SHA256：`{sha}`；预处理器 ID：`{data["preprocessor_id"]}`；PyTorch `{data["torch_version"]}`，CUDA 推理。\n')
text=text.replace('1. 这轮结果有初步的方向性信号：在可估计的小时里，增加 holding 往往会让 D 高于基线，说明表示可能对轨迹机动变化有响应。\n2. 响应不是稳定单调的；部分基线或处理后的 D 无法通过尺度拟合条件。因此现阶段不能得出“holding 越多，复杂度必然越高”的强结论。', '1. 指标对这类合成机动有反应：基线可估计的小时在中等注入剂量下，平均 D 高于基线。\n2. 响应不具备稳定的剂量单调性：全曲线 Spearman 中位数约为 0，正相关只占 45%，高剂量时平均增幅回落。基线 D 只有 6/12 个小时通过 R² 门槛，现阶段不能得出“holding 越多，复杂度必然越高”的强结论。')
report.write_text(text,encoding='utf8')
print(sha)
