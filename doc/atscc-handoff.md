# Encoder → Complexity 当前接口交接

本文替代旧 ATSCC 框架交接说明，文件名保留以兼容已有文档链接。当前代码位于 `Encoder/` 和 `Complexity/`；旧 `ATSCC.load_model`、`encode_scene`、`TrainingConfig` 和小写 `complexity` 不再是本仓库入口。

## 当前模型与入口

- 冻结模型：`Encoder/encoder/encoder.pt`，对应 `d16_e120_t0p01_s43`，16 维、sum pooling、seed 43、第 30 轮。
- 主干：9 维特征输入，256 宽、4 层、4 头、FFN 512；逐 token L2，pooled embedding 不额外 L2。
- 仓库根目录导入：`from Encoder.trajectory_encoder.inference import FrozenEncoder` 和 `from Complexity import estimate_complexity`。
- 在 `Encoder/` 内运行原有示例时，仍使用 `from trajectory_encoder.inference import FrozenEncoder`；见 `Encoder/example.py`。
- Complexity 实现仅直接依赖 NumPy/SciPy；全项目统一安装根目录 `requirements.txt`，其中包含 Torch。环境安装见[根 README](../README.md#installation)，重训见[Encoder 部分](../README.md#encoder)、[PLAN.md](../Encoder/PLAN.md)、[PROTOCOL.md](../Encoder/PROTOCOL.md)。

## 输入与预处理契约

`FrozenEncoder.encode(enu_m)` 一次处理一条已经采样为 5 秒间隔的轨迹：

- 输入有限实数 `(T,3)`，为 ENU 米制坐标；不接受经纬高、NaN padding 或 Inf。
- 推理接口不做重采样；轨迹必须至少 30 点。
- 内部构造 `[east,north,up,direction_e,direction_n,direction_u,radius,sin(theta),cos(theta)]`，使用 checkpoint 中训练集均值/标准差，不重新拟合。方向为前向差分，末点重复前一步方向。
- 返回字典含 `tokens: (T,16)`、`embedding: (16,)`、`n_points`、`pooling`、`preprocessor_id`。支持 pooling `sum`、`mean`、`gem2`（带符号 GeM-p2）。
- 权重按 strict state_dict 加载，模型设为 eval 并冻结参数。当前加载器使用 `torch.load(..., weights_only=False)`；只加载可信 checkpoint，不提供旧裸 state_dict 自动适配。


## 从轨迹接入复杂度

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
