# Encoder → Complexity 当前接口交接

本文替代旧 ATSCC 框架交接说明，文件名保留以兼容已有文档链接。当前代码位于 `Encoder/` 和 `Complexity/`；旧 `ATSCC.load_model`、`encode_scene`、`TrainingConfig` 和小写 `complexity` 不再是本仓库入口。

## 当前模型与入口

- 冻结模型：`Encoder/encoder/encoder.pt`，对应 `d16_e120_t0p01_s43`，16 维、sum pooling、seed 43、第 30 轮。
- 主干：9 维特征输入，256 宽、4 层、4 头、FFN 512；逐 token L2，pooled embedding 不额外 L2。
- 仓库根目录导入：`from Encoder.trajectory_encoder.inference import FrozenEncoder` 和 `from Complexity import estimate_complexity`。
- 在 `Encoder/` 内运行原有示例时，仍使用 `from trajectory_encoder.inference import FrozenEncoder`；见 `Encoder/example.py`。
- Complexity 实现仅直接依赖 NumPy/SciPy；全项目统一安装根目录 `requirements.txt`，其中包含 Torch。环境安装见[根 README](../README.md#installation)，重训见[Encoder 部分](../README.md#encoder)、[PLAN.md](../Encoder/PLAN.md)、[PROTOCOL.md](../Encoder/PROTOCOL.md)。

## 输入与预处理契约

`FrozenEncoder.encode(enu_m, resample_from_1hz=True)` 一次处理一条轨迹：

- 输入有限实数 `(T,3)`，为相对 RKSI 的 east/north/up 米制坐标；不接受经纬高、NaN padding 或 Inf。
- 1 Hz 输入每 5 点采样并保留终点；已经按相同规则采样的 5s 输入使用 `resample_from_1hz=False`。采样后至少 30 点，否则报错。
- 内部构造 `[east,north,up,direction_e,direction_n,direction_u,radius,sin(theta),cos(theta)]`，使用 checkpoint 中训练集均值/标准差，不重新拟合。方向为前向差分，末点重复前一步方向。
- 返回字典含 `tokens: (T_sampled,16)`、`embedding: (16,)`、`n_points`、`pooling`、`preprocessor_id`。支持 pooling `sum`、`mean`、`gem2`（带符号 GeM-p2）。
- 权重按 strict state_dict 加载，模型设为 eval 并冻结参数。当前加载器使用 `torch.load(..., weights_only=False)`；只加载可信 checkpoint，不提供旧裸 state_dict 自动适配。

上游负责按 `[t_s,t_s+1h)` 切窗、坐标转换和飞机 ID 去重；每架飞机在一个小时场景中只贡献一个向量。模型不会推断小时或航班身份，也不会自动删掉过短轨迹。

## OpenSky 接入

`Encoder/opensky_scene.py` 将忽略的 `data/OpenSky_Changi_2026-09/sampled_10s/` 逐小时 CSV.gz 接入现有冻结 Encoder 与 Complexity。它筛选空中且位置/几何高度/时间有效的观测，按 ICAO24 和 UTC 小时分组，遇到超过 60 秒的断点即分段；每机每小时仅保留最长且至少含 16 个真实观测的片段。

脚本把 WGS84 转为相对 WSSS ARP 的 ENU 米制坐标，再在观测间线性插值到模型要求的 5 秒间隔，调用现有 checkpoint 的 `sum` pooling，并把每小时 `(N,16)` 向量送入既有复杂度质量门槛。生成 `hourly_embeddings.npz` 和含逐场景诊断/筛选轨迹清单的 `hourly_complexity.json`。所有结果默认写在被忽略的 `data/.../encoder_scenes/`。

先仅跑一小时试算：

```bash
python Encoder/opensky_scene.py --pattern '2026-09-01T00Z.csv.gz'
```

确认输出后处理全部月份（720 小时）：

```bash
python Encoder/opensky_scene.py
```

可用 `--input-dir`、`--output-dir`、`--checkpoint`、`--device`、`--max-gap-seconds` 覆盖默认值。当前 checkpoint 在韩国 RKSI 数据训练，而此数据来自新加坡 WSSS；10 秒轨迹的 5 秒中间点是线性估计，几何高度基准也可能与机场标高存在偏差。因此这条链路已能运行，但输出应视为域迁移探索结果，不应当作经验证的 WSSS 复杂度结论；报告会保留这些限制，并仅在既有质量门槛通过时给出维数。
## 从轨迹接入复杂度

在仓库根目录执行，`hour_tracks` 为上游已经组织好的同一小时 1 Hz 轨迹列表：

```python
import numpy as np
from Encoder.trajectory_encoder.inference import FrozenEncoder
from Complexity import ComplexityConfig, estimate_complexity

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
vectors = [encoder.encode(track, resample_from_1hz=True)["embedding"]
           for track in hour_tracks]
points = np.stack(vectors) if vectors else np.empty((0, encoder.settings["dimension"]))
result = estimate_complexity(
    points, scene_id="hour_01", config=ComplexityConfig(normalize=False),
)
print(result.status, result.dimension, result.reason)
np.save("hour_01.npy", points)
```

传递的是 `(N,16)` 数组，不是 token 序列、返回字典或单条 `(16,)` 向量。空场景可传 `(0,16)`；不足样本或拟合不合格返回 `unestimable`，不能记为复杂度 0。默认门槛、显式尺度及 JSON 字段见[根 README 的 Complexity 部分](../README.md#complexity)。

单小时保存为 `.npy`，多小时保存为 `scene_id -> (N_s,D)` 的 `.npz`：

```python
np.savez("hours.npz", hour_01=z1, hour_02=z2)
```

```bash
python -m pip install -r requirements.txt
python -m Complexity --help
python -m Complexity hour_01.npy -o hour_01.complexity.json
python -m Complexity hours.npz -o hours.complexity.json
```

**`Encoder/encoder/embeddings.npz` 不是小时场景档案。** 它按 `sum/mean/gem2` 保存全部 16183 条轨迹，不能直接作为多小时输入，也不能把三个 pooling 当三个场景。场景间比较应固定 checkpoint、预处理、pooling、归一化与尺度规则，不能为得到数字而降低质量门槛。

## 训练效果记录

当前模型的逐轮日志在 `Encoder/experiment_logs/d16_e120_t0p01_s43/`：`history.json` 记录训练/验证损失，`status.json` 记录完成状态和最佳轮次，`validation.json` 与 `untrained_validation.json` 提供验证表示评估。

独立 TEST 及基线对照见 `Encoder/reports/test_results.json`、`untrained_test_results.json`、`confounding_and_route.json`；汇总见 [RESULTS_ZH.md](../Encoder/reports/RESULTS_ZH.md)，三种子与 pooling 对照见 `three_seed_summary.json`、`probe_summary.csv`。

训练损失下降并不等于下游复杂度有效。当前报告明确指出：代表模型四项几何代理均未超过两种基线中的较强者，尚未证明训练带来的额外代理预测能力。数据缺绝对时间和真实航班 ID，真实小时场景的相关维数有效性未验证。

## 验证命令

在仓库根目录，使用已装好相应依赖的 Python：

```bash
python -m unittest discover -s Complexity/tests -v
python Encoder/verify_delivery.py
python Encoder/example.py --checkpoint Encoder/encoder/encoder.pt --input Encoder/encoder/example_input_output.npz
```

第一项覆盖复杂度算法与单/多场景 CLI；后两项检查权重校验、冻结加载和真实轨迹推理，不代替真实小时场景的研究验证。`Encoder/trajectory_encoder/checks.py` 还需要 prepared 数据及 CUDA，不属于纯 CPU 交付验证命令。
