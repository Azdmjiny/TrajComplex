from pathlib import Path
p=Path(__file__).resolve().parents[1] / 'reports' / 'evaluation-pilot.md'
s=p.read_text(encoding='utf8')
s=s.replace('- 使用 OpenSky Changi 2026-09 原始 10 秒轨迹；每小时一场景，每个点对应一架飞机的整段小时轨迹。', '- 使用 OpenSky Changi 2026-09 原始 10 秒轨迹；每小时一场景，每个点对应一架飞机的整段小时轨迹。只保留空中且经纬度、几何高度均有效的记录；要求每条轨迹至少 16 个 10 秒观测、最大相邻间隔不超过 20 秒，再转为 WSSS 局部 ENU 坐标并线性插值到 5 秒采样。数据集查询范围内并非全部都是樟宜进场航班，因此结果按 OpenSky 查询区域的航迹场景解释。可行性审计中，720 小时有 615 小时可留下至少 30 架轨迹，有 424 小时至少 50 架。')
s=s.replace('- 对每个小时固定使用基线点云的 64 个半径尺度，以便每个剂量下的 D 在相同半径上估计。', '- 对每个小时固定使用基线点云的 64 个半径尺度，以便每个剂量下的 D 在相同半径上估计。质量门槛沿用仓库默认值：至少 30 个点、相关积分区间 0.02–0.3、至少 8 个拟合尺度、尺度跨度至少 2 倍、拟合 R²≥0.98。')
s=s.replace('详细结果见 `../results/aircraft-count-sensitivity.csv` 与 [图](../figures/aircraft-count-sensitivity.png)。', '详细结果见 `../results/aircraft-count-sensitivity.csv`、`../results/aircraft-count-sensitivity.json` 与 [图](../figures/aircraft-count-sensitivity.png)。')
p.write_text(s,encoding='utf8')
