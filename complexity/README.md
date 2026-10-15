# 场景复杂度组件

独立于 `ATSCC/` 的 Python 组件，按 `doc/trajectory-embedding-point-cloud-complexity.md` 的定义计算 **trajectory embedding 点云的经验关联维数**。

## 边界与输入约定

- 输入：实数数组 `(N, D)`；一行是一架飞机在一个小时窗口内的 **pooled trajectory embedding**。
- `N` 是该小时飞机数，`D` 不固定，可为 8、128、320 等。
- 不接受 `(N, T, D)` 的逐时间步输出，不自动 flatten、pooling、切时间窗口或混合不同场景。
- **不加载 Encoder、不训练、不修改 ATSCC。** checkpoint 加载、特征转换及 pooling 由上游提供。
- 上游必须保证同一场景中每架飞机只有一个点；组件不接收飞机 ID，无法判断重复 ID。不同飞机出现相同 embedding 时保留两行，不擅自去重。
- 输入必须有限，不接受 NaN padding、Inf、复数或字符串；非法输入抛出 `ValueError`，不悄悄删除飞机。
- 默认不对点云标准化、不做 PCA、不做 L2 归一化。可显式选择逐点 L2 归一化，零向量会报错。它会改变点云几何；整个实验应固定同一种规则。

## 安装与运行

Python 3.9+，只依赖 NumPy、SciPy；不依赖 Torch、W&B、sklearn。

```bash
python -m pip install -r complexity/requirements.txt
```

在仓库根目录使用。当前也可复用已有环境：

```bash
ATSCC/.venv/bin/python -m complexity --help
```

## Python 接口

```python
import numpy as np
from complexity import ComplexityConfig, estimate_complexity, correlation_integral

# 替换为 Encoder 上游提供的某一小时 embedding，不能把所有小时混成一个点云。
scene_embeddings = np.load("hour_01.npy", allow_pickle=False)  # (N, D)

result = estimate_complexity(
    scene_embeddings,
    scene_id="2026-01-01T08:00:00Z",
    config=ComplexityConfig(normalize=False),
)
if result.status == "ok":
    print(result.dimension, result.r_squared)
else:
    print("无法估计：", result.reason)

# 预先确定尺度区间时，使用显式拟合区间。
# 不同 checkpoint/pooling 的尺度不同，这里只是接口示例，不是推荐值。
result = estimate_complexity(scene_embeddings, fit_range=(0.05, 0.5))

# 也可以只计算关联积分，供外部研究/作图，最少需要两个点。
radii = np.geomspace(0.01, 1.0, 64)
curve = correlation_integral(scene_embeddings, radii)
```

主函数签名：

```python
estimate_complexity(embeddings, *, config=None, radii=None, fit_range=None, scene_id=None)
correlation_integral(embeddings, radii, *, normalize=False, max_pairs=5_000_000)
```

`result.to_dict()` 可直接 JSON 序列化，包含：

- `status`：`ok` / `unestimable`；只有 `ok` 才提供 `dimension`。
- `reason`：不可估计原因；正常时为 `None`。
- `scene_id`、`n_samples`、`embedding_dim`、`n_unique`、`n_pairs`、`zero_distance_pairs`（提前拒绝、未计算距离时为 `None`）。
- `radii`、`correlation`、`pair_counts`：用于复核和绘图的完整离散曲线；提前拒绝的场景可能没有曲线。
- `fit_indices`、`fit_radius_range`、`fit_slope`、`intercept`、`r_squared`：候选拟合诊断。拟合不合格时仍可保留候选斜率，但它不是有效的 `dimension`。
- `selection`、`requested_fit_range`、`config`、`warnings`：所用规则和警告。

组件不会返回没有定义的 NaN/Inf 结果；不可估计值为 `None`（JSON `null`），**不能当成复杂度 0**。

## 数学规则与默认质量门槛

精确计算所有无序点对的欧氏距离，只统计 `i < j`，不包含自身配对：

```text
C(r) = count(distance(i,j) < r, i < j) / [N(N-1)/2]
log C(r) = D2 * log r + intercept
```

使用严格小于 `< r`，距离正好等于半径的点对不计入。

自动模式规则（本组件的初始工程默认值，并非文档/论文保证的最优值）：

1. 至少 30 个点；这个下限可配置，但不保证 30 架飞机足以可靠估计。
2. 从最小正距离到最大距离，生成 64 个对数等距半径。
3. 选择 **全部** 满足 `0.02 <= C(r) <= 0.3` 且至少计入 10 个点对的半径。
4. 至少 8 个拟合半径，最大/最小半径比至少为 2。
5. 对 `log(r), log(C(r))` 做带截距的普通最小二乘回归；正斜率且 `R² >= 0.98` 才输出维数。

不通过寻找最高 R² 的短窗口挑选结果。显式 `fit_range=(r_min, r_max)` 时，未指定 `radii` 就在该区间生成半径；指定了 `radii` 就选其中落入闭区间的半径。显式模式不使用 `0.02..0.3` 过滤，但仍排除 `C=0/1`，并保留点对数、拟合点数、跨度、R² 等门槛。

全部门槛可通过 `ComplexityConfig` 调整：

| 参数 | 默认值 |
|---|---:|
| `normalize` | `False` |
| `n_radii` | 64 |
| `min_samples` | 30 |
| `min_fit_points` | 8 |
| `min_pairs` | 10 |
| `correlation_bounds` | `(0.02, 0.3)` |
| `min_radius_ratio` | 2.0 |
| `min_r_squared` | 0.98 |
| `max_pairs` | 5,000,000 |

常见拒绝原因：

| `reason` | 含义 |
|---|---|
| `insufficient_samples` | 飞机数不足 |
| `collapsed_point_cloud` | 所有距离为零，点云坍塌 |
| `no_distance_scale_range` | 所有正距离相等，无法自动生成尺度范围 |
| `insufficient_fit_scales` | 有效拟合尺度不足，可能过稀疏或已饱和 |
| `insufficient_scale_span` | 尺度范围太窄 |
| `flat_correlation_curve` | 关联积分没有可辨别的增长 |
| `poor_linear_fit` | R² 未达到门槛 |
| `nonpositive_slope` / `nonfinite_fit` | 无效斜率或数值拟合失败 |

重复 embedding/零距离会在结果中提示，但保留在点对统计中。近重复点可通过曲线在小尺度的行为检查，组件不自动合并或添加噪声。

**R² 高不证明存在真实分形结构；这里是有限样本经验斜率。** 当前不提供统计置信区间（不同半径的 C(r) 共享点对，不应将普通 OLS 标准误误当成可靠不确定度）。应使用真实场景验证固定尺度、样本量和配置的敏感性，不能把本组件的 `ok` 当作研究结论验证。

距离计算为精确 `O(N²D)`，距离排序为 `O(P log P)`，内存为 `O(P + ND)`，`P=N(N-1)/2`。默认最多 500 万点对，距离数组约 40 MB，处理还需额外临时内存。超过上限直接报错，不静默随机采样。可显式提高上限，但不要为绕过上限随意拆散一个小时场景，否则改变了指标定义。

## 文件/命令行接口

单场景 `.npy`：存储一个 `(N,D)` 数组。多场景 `.npz`：每个键为场景 ID，每个值为该场景的 `(N_s,D)` 数组，允许不同场景飞机数不同。

```python
np.save("hour_01.npy", embeddings_hour_01)
np.savez("hours.npz", hour_01=embeddings_hour_01, hour_02=embeddings_hour_02)
```

```bash
# 单小时
python -m complexity hour_01.npy -o result.json

# 多小时，逐场景计算并保留 ID
python -m complexity hours.npz -o results.json

# 明确指定尺度区间；可选 L2 归一化
python -m complexity hours.npz --fit-range 0.05 0.5 --normalize -o results.json
```

JSON 顶层包含 `schema_version`、`method`、`metric`、`input` 和 `results` 列表。不指定 `-o` 时写标准输出。不支持 pickle；NumPy 文件以 `allow_pickle=False` 加载。

成功处理的文件返回退出码 0（包括包含 `unestimable` 场景的文件，调用者必须检查各场景状态）；格式/参数/资源上限错误返回 2。批量中有非法输入时整个命令失败，不输出不完整结果。输出目录需预先存在；禁止输出覆盖输入文件。

## 和 ATSCC 对接

推荐在仓库根目录使用 ATSCC 的轻量加载/场景编码入口：

```python
from ATSCC import load_model, encode_scene

model = load_model("artifacts/run/best.pt", device="cpu")
# features 已切成一个小时、每架飞机一段，并按训练规则预处理成 9 维。
encoded = encode_scene(model, features, scene_id="hour_01")
result = estimate_complexity(encoded.embeddings, scene_id=encoded.scene_id)
```

ATSCC 当前训练计划初始输出是 8 维，主干 256 维 / 4 层，默认 **sum pooling**；mean 与带符号 GeM-p2 为对照。模型逐时间步输出 `(B,T,D)`，编码入口仅对有效时间步 pooling，返回有限 `(N,D)` 点云。`encoded` 本身是结果对象，传入本组件的是 `encoded.embeddings`。旧 `atscc.encode()` 的第一个返回值也为 `(N,D)`，默认同样改为 sum；复现旧实验的 last pooling 请显式指定。

checkpoint 加载、预处理与 pooling 均由 ATSCC 侧负责；本组件仍不依赖 Torch。上游必须确认这些行属于同一个小时、每架飞机只有一行。同一实验固定 checkpoint、预处理、pooling、归一化和距离规则，不强制沿用旧 320 维，也不把逐时间步编码当成飞机点。完整调参及模型加载交接见 [`doc/atscc-handoff.md`](../doc/atscc-handoff.md)。

## 测试

在仓库根目录：

```bash
ATSCC/.venv/bin/python -m unittest discover -s complexity/tests -v
```

测试覆盖：手算点对和严格边界、暴力计算对照、直线/平面经验维数、平移/整体缩放/置换、显式尺度和 OLS 对照、重复点/坍塌/空场景、NaN/Inf/非法格式、L2 归一化、质量拒绝、资源上限、单/多场景 CLI 和 JSON 输出。
