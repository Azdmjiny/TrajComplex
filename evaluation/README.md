# Evaluation

[当前实验报告](reports/evaluation-pilot.md) 包括几何修复、异常轨迹筛选、Holding 峰后截断、Vectoring 全范围结果及飞机数量敏感性分析。

报告、结果和图直接维护在原有目录；不使用日期版本目录。Git 历史保留旧的已提交文件。完整剂量数据始终保留，截断只改变相关性计算的取样范围。

**Holding 截断是根据同一批结果选峰的探索性分析，不是独立验证，不代表峰后数据无效或已经超出适用范围。** 原曲线、截断点、排除段和实际分母同时报告。Vectoring 不截断。

## 从保存的数据重建

需要 Python、NumPy、SciPy、Matplotlib；不需要 GPU、原始轨迹或 checkpoint。

```bash
python evaluation/code/refresh_outputs.py
```

该命令更新原文件：

- `results/synthetic-holding-evaluation-{pilot,summary}.json`：QC500 主分析。
- `results/synthetic-vectoring-evaluation-{pilot,summary}.json`：QC500 加候选机动速度筛选。
- `results/{holding,vectoring}-dose-response.csv`：完整点及是否进入相关性、排除原因。
- `results/summary.json`：完整与截断统计、同曲线配对比较及各敏感性设置。
- `figures/*.png`、`figures/*.svg`：Matplotlib 图。
- `reports/evaluation-pilot.md`：GitHub 可直接阅读的 Markdown 报告。

## 从原始轨迹重跑

设置 `ATM_DATA_ZIP`（OpenSky 原始 zip）和 `ATM_ENCODER_CHECKPOINT`（固定 checkpoint）后执行：

```bash
python evaluation/code/run_evaluation.py
python evaluation/code/refresh_outputs.py
```

使用同一批 12 个小时与原始随机种子。先生成原始飞机顺序和 Vectoring 左右方向，再过滤，确保敏感性设置中的幸存飞机保持配对顺序。

`run_holding_eval.py` 和 `run_vectoring_eval.py` 的历史入口也调用统一实验流程，避免只更新部分文件造成结果混用。`aircraft_count_sensitivity.py` 仅重跑飞机数部分。旧汇总和报告补丁入口统一调用 `refresh_outputs.py`，不再手工替换报告中的数字。

当前 checkpoint SHA256 必须匹配 `run_evaluation.py` 中冻结的 pilot checkpoint。运行环境记录在 `results/run-manifest.json`。原始轨迹、模型权重、推理缓存不包含在 Git 中。

## 验证

```bash
python -m unittest discover -s evaluation/code -p "test_*.py" -v
```

测试覆盖 Holding 自然闭合与速度连续性、异常轨迹筛选、Vectoring 候选机动筛选、共享峰值截断、最小重复数和无效 D 排除。测试几何函数不需要加载模型。

`results/experiment-results.json` 保存所有修复后的完整剂量曲线；`count-comparison.json` 保留清洗前参考与两级清洗后的飞机数敏感性结果。`legacy_replay` 标签仅用于飞机数的清洗前参考，未作为当前机动主结果。`safe` 标签仅表示候选机动速度筛选，不保证完整物理可行性。
