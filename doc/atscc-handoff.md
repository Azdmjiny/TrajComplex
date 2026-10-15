# ATSCC → complexity 框架与调参交接

## 1. 当前实现与边界

参数以 `encoder-training-plan.md` 为当前实验依据；点云文档中的 128 维是方法示例，**本次初始输出为 8 维**，后续比较 4/8/16，不预设 8 维最优。

- 因果 Transformer：9 维输入、256 主干、4 层、4 头、FFN 512、dropout 0.35，不加显式位置编码。
- 训练时按 20% 概率遮挡 token；原始实现的 `rand > 0.2` 实际约遮挡 80%，本次已修正为 `< p`。旧权重的 eval 推理不受该训练 masking 修正影响；继续训练不再等价于旧 masking 方案。
- 保留原始 token 级 L2 normalization、attention 计算和 flat SNNL；没有更换损失定义。保留 `final_proj` 辅助头以兼容旧权重，但**场景 embedding 使用 `forward()` 的 `output_dims`，不调用会再减半的 `final_projection()`**。
- 默认时间聚合 **sum**；mean 和文档定义的**带符号 GeM-p2**为对照，旧 first/last/max 仍可显式使用。
- 不做 pooled embedding 的额外 L2 normalization。需要时在 `ComplexityConfig(normalize=True)` 显式开启，并固定整组实验规则。
- 本次搭建训练/推理/保存/加载框架，未做真实数据训练、GPU 显存测试、调参、多种子质量评估或分形结构研究验证。
- 未实现 AMP、梯度累积、跨微批次负样本、optimizer/RNG 断点恢复、小时切窗、飞机 ID 去重、坐标转换和代理回归评估。这些不能作为已完成成果报告。

## 2. 代码入口

| 文件 | 职责 |
|---|---|
| `ATSCC/config.py` | `EncoderConfig`、`TrainingConfig`、`EmbeddingConfig`；调参点以 `TUNE` 注释标记 |
| `ATSCC/configs/encoder-default.json` | 可复制的初始实验配置；JSON 不支持注释，对照 config.py 和本表修改 |
| `ATSCC/model/GPT.py` | 缩小版默认参数、20% masking、逐 token 输出；保留旧层名/权重键 |
| `ATSCC/pooling.py` | sum/mean/带符号 GeM/first/last/max，只统计有效 token |
| `ATSCC/inference.py` | `build_model`、`save_model`、`load_model`、`encode_scene`、`EmbeddingResult` |
| `ATSCC/train.py` | 无 W&B 登录副作用的训练 CLI、`make_dataset` 特征/RDP 适配、`fit_encoder` |
| `ATSCC/atscc.py` | 原始聚类/绘图接口仍在；encode 保留五项返回值，默认改为 sum |
| `complexity/calculator.py` | 独立关联维数算法，未改变其计算逻辑或强制维度 |
| `ATSCC/tests/test_encoder_pipeline.py` | 配置、pooling、padding、masking、重载、训练与 complexity 对接测试 |

推荐在仓库根目录 `from ATSCC import ...`，仅推理不引入绘图、UMAP、W&B。旧 `from atscc import ...` 在 `ATSCC/` 目录下使用，仍依赖原绘图/评估环境。`ablation.py` 是上游旧实验脚本，未迁移，不是本框架入口。

## 3. 数据先决条件：先审计，再运行

1. 按日期/航班分组准备训练、验证、测试，保存 split manifest，禁止同一航班/高度重叠轨迹跨集合泄漏。CLI 不会自动切分或判断集合中的航班重叠。
2. 训练 CLI 输入为实数 `.npy`，形状 `(N,T,3)`，坐标应已经转换成以机场为原点、单位已确认的 ENU xyz。**不能直接把经纬高或其他坐标命名为 ENU 后送入。**
3. 全 NaN 行代表 padding；部分维度 NaN、Inf、空飞机轨迹会报错。去掉 padding 后降采样，每架轨迹至少留 2 步，才能计算方向和 RDP。
4. 现有特征顺序固定为 `[x,y,z, dx_unit,dy_unit,dz_unit, r,sin(theta),cos(theta)]`，`theta=atan2(y,x)`，方向来自相邻位置差，最后一步方向沿用前一步；r 为 xy 平面的模长。
5. `make_dataset` 沿用 `ATPCCDataset`，生成这 9 维及 RDP 自监督段标签；不做坐标转换、重采样插值、scaler 拟合或归一化。`downsample` 是按观测索引抽样，不等价于固定秒数采样。
6. 如需新归一化，必须新定义并冻结预处理版本，只在训练集拟合；当前 checkpoint 没有一个可自动恢复的 scaler。新旧预处理不可混用。
7. 推理前按半开区间 `[t_s,t_s+1h)` 切窗，同一小时一架飞机只提供一个片段；ID 与片段一一对应由上游保证。模型 batch 不是场景边界。

## 4. 如何训练

环境沿用 `ATSCC/.venv`（当前 Torch 2.4.1）；加载使用 `torch.load(weights_only=True)`，不反序列化整个模型对象。

复制默认 JSON 为每个实验的独立配置，修改下节所列字段。`rdp_epsilon=0.1` 只是占位起点，**必须先按坐标单位与 RDP 段分布校准**，不是适用于任何机场的推荐值。

在仓库根目录运行，例如：

```bash
ATSCC/.venv/bin/python -m ATSCC.train \
  --train-data data/enu_train.npy \
  --validation-data data/enu_validation.npy \
  --config ATSCC/configs/encoder-default.json \
  --output-dir artifacts/d8_tau001_seed0 \
  --data-version enu_preproc_v1 \
  --split-id flight_date_split_v1 \
  --device cuda:0
```

本机没有 CUDA 时用 `--device cpu`；MPS 可显式指定 `mps`，但尚未验证。默认 CPU，无自动选择 `cuda:1`。

- 所有字段均可通过 JSON 对应 section 覆盖，未提供字段沿用 dataclass 默认值，未知字段报错。
- 最多 30 epochs，或达到 `max_steps` 后停止。AdamW lr/weight_decay 均为 `1e-5`。
- `last.pt`：最近一次训练后的推理 checkpoint；`best.pt`：有验证集时按最小验证 flat SNNL 暂选；`history.json`：逐 epoch 的训练/验证 loss 与累计步数。
- 不提供验证集时只生成 last，不把训练 loss 的最小值称为 best。真实项目仍需留出代理评估，验证 loss 只是框架暂用的选择准则。
- 每次运行使用新的输出目录；已有 last/best/history 时拒绝覆写。不支持训练断点恢复。
- checkpoint 记录模型结构、pooling、训练配置、种子、数据版本、split ID、预处理说明和 epoch/损失。没有保存 optimizer/RNG，不能宣称精确续训。
- 如从 Python 使用 `fit_encoder`，在 `build_model` **之前**调用 `seed_everything(seed)`；fit 内再固定训练随机数。自建 loader 时实际 batch、数据转换和 split 必须与记录的配置一致，API 不会代做这些转换。
- 当前使用全部有效 token 的 flat SNNL，距离/相似度矩阵内存随 batch 内 token 总量平方增长；不保证 batch 16 在所有轨迹长度下都适合 8 GB。

## 5. 调哪里、怎么调

优先修改实验 JSON，不直接散改多个脚本。Python 接口使用 dataclass 或 `dataclasses.replace`。涉及训练参数或输出维度的实验必须重训，pooling/复杂度规则可在固定权重上重新导出。

| 阶段 | 修改位置（JSON / Python） | 初始值 → 建议实验 | 是否重训 / 判据 |
|---|---|---|---|
| 数据审计 | `training.downsample`、预处理适配层 | 5；按真实采样率确定后先冻结 | 是；记录采样间隔、长度分布及坐标/缺失规则 |
| RDP 校准 | `training.rdp_epsilon` / `TrainingConfig` | 0.1 占位；按实际坐标尺度选量级，检查每架轨迹段数/段长 | 是；避免全段合并或几乎每点独立；不要直接照搬不同单位数据的阈值 |
| 首轮核心比较 | `training.temperature` | **0.01、0.05**，其余固定 | 是；损失/梯度有限、验证表现与表示非坍塌，不单看训练 loss |
| 显存/负样本 | `training.batch_size` | **8、16**，资源允许再参考 64 | 是；记录实际 batch 与轨迹长度；梯度累积不是更大的负样本池 |
| 低维消融 | `encoder.output_dims` / `EncoderConfig` | **4、8、16**；主干保持 256/4 层不变 | 是；留出行为信号与经验维数稳定性共同选型，不仅看是否容易拟合 |
| 多种子 | `training.seed` | 至少 **0、1、2** | 是；相同 split，报告均值/离散程度，不只报最好种子 |
| pooling 对照 | `embedding.pooling`、`embedding.gem_p` / `EmbeddingConfig` | **sum、mean、gem(p=2)** | 否；固定 checkpoint、飞机集合及窗口，比较长度与 embedding 模长/距离的关系 |
| 后续优化 | `training.learning_rate/weight_decay/epochs/max_steps` | `1e-5/1e-5/30/500000` 起步，一次改一组 | 是；记录训练预算与选择准则，避免用测试集调参 |
| 后续容量/正则 | `encoder.embed_dim/num_layers/hidden_dim/num_heads/dropout/mask_probability` | `256/4/512/4/0.35/0.2` 先冻结 | 是；embed_dim 必须能被 num_heads 整除；不要和低维消融同时改主干 |
| 推理资源 | `embedding.batch_size` | 16，可按设备调整 | 否；它只分推理批次，不分割小时点云；浮点容差内结果应一致 |
| 几何规则 | `ComplexityConfig(normalize=...)` | 默认 False；显式 L2 仅作为预先定义的对照 | 否；改变点云几何，整组实验固定，零向量归一化报错 |
| 经验维数尺度/质量 | `estimate_complexity(..., radii=..., fit_range=...)`、`ComplexityConfig` | 见下文 | 否；用验证场景研究敏感性，冻结后评估测试场景，不能逐窗追最高 R² |

complexity 当前工程门槛：`n_radii=64`、`min_samples=30`、`min_fit_points=8`、`min_pairs=10`、`correlation_bounds=(0.02,0.3)`、`min_radius_ratio=2`、`min_r_squared=0.98`。它们不是文献保证的最优值。`max_pairs=5_000_000` 是资源保护，不是估计超参；需要时显式提高，不静默采样/拆窗绕过。

可按每次只改一个轴的顺序执行：数据/RDP 校准 → 温度 → 固定 batch 下 4/8/16 × 至少 3 seeds → 固定权重上的 sum/mean/GeM → 固定归一化/尺度后的场景质量检查。正式运行前再决定是否进行完整组合；不默认跑大网格。

建议每次记录：配置 JSON、checkpoint、数据版本/划分、实际 batch/长度/显存、训练日志、留出代理指标、embedding 方差/有效秩/距离分布、长度与模长偏差、每小时 N/重复点、C(r) 曲线/拟合区间/R²/拒绝原因。当前框架**没有自动生成所有这些研究指标**。

## 6. 加载模型、导出并接入 complexity

### 新 checkpoint：包含配置，可直接加载

```python
import json
from pathlib import Path
import numpy as np
from ATSCC import load_model, encode_scene
from ATSCC.config import TrainingConfig
from ATSCC.train import make_dataset
from complexity import ComplexityConfig, estimate_complexity

model = load_model("artifacts/d8_tau001_seed0/best.pt", device="cpu")

# 必须已按一小时、每架飞机一个片段组织；与训练保持同一 ENU/特征规则。
positions = np.load("data/hour_01_enu.npy", allow_pickle=False)  # (N,T,3)
training = TrainingConfig(**model.checkpoint_metadata["training_config"])
features = make_dataset(positions, config=training).features  # (N,T',9)，同时计算 RDP
encoded = encode_scene(model, features, scene_id="hour_01")
# encode_scene 本身只接受已处理的 9 维特征或变长 (T_i,9) 列表，绝不偷偷做转换。
# 空小时可直接 encode_scene(model, [])，无需 make_dataset。
assert encoded.embeddings.shape[1] == model.output_dims

np.save("artifacts/hour_01.npy", encoded.embeddings)
Path("artifacts/hour_01.embedding.json").write_text(
    json.dumps(encoded.to_dict(), ensure_ascii=False, allow_nan=False), encoding="utf-8")
result = estimate_complexity(encoded.embeddings, scene_id=encoded.scene_id,
                             config=ComplexityConfig(normalize=False))
print(result.status, result.dimension, result.reason)
```

`EmbeddingResult` 与 complexity 的配置/结果风格一致：保留 `scene_id`、配置、长度，`to_dict()` 可 JSON 序列化。实际传给 complexity 的仍是 **`encoded.embeddings` NumPy `(N,D)`**，不能传逐 token `(N,T,D)` 或整个结果对象。输入顺序保留，不去重，默认不归一化；只全 NaN 行为 padding，空片段/部分 NaN/Inf 会报错，不静默删飞机。

`make_dataset` 需要至少两步，且会计算用于训练的 RDP，作为共用预处理配方先保证一致；若后续单独实现高效纯推理特征转换，应逐元素对照该版本，并升级预处理版本。若飞机不足两步，应由上游显式记录排除规则或定义新特征规则，不偷偷丢弃。

### 固定 checkpoint 比较 pooling

```python
from ATSCC import EmbeddingConfig, encode_scene
for pooling in ("sum", "mean", "gem"):
    points = encode_scene(model, features, scene_id="hour_01",
                          config=EmbeddingConfig(pooling=pooling, gem_p=2.0))
    # 各规则分别保存并送入相同 complexity 配置；不得混合到同一场景点云。
```

多小时可分别编码，再 `np.savez("artifacts/hours.npz", hour_01=z1, hour_02=z2)`；不能把所有小时拼成一个 `(N,D)` 点云。得到 NumPy 文件后可独立运行：

```bash
ATSCC/.venv/bin/python -m complexity artifacts/hour_01.npy -o artifacts/hour_01.complexity.json
```

### 旧裸 state_dict：必须提供原始配置

```python
from ATSCC import EncoderConfig, load_model
legacy = EncoderConfig(input_dims=9, output_dims=320, embed_dim=768,
                       num_heads=12, num_layers=12, hidden_dim=3072,
                       dropout=0.35, mask_probability=0.2)
model = load_model("old_encoder.pt", config=legacy, device="cpu")
```

裸权重无法恢复注意力头数、dropout、训练 masking 等语义，不能只从矩阵尺寸猜配置；这里的示例必须替换为该权重的真实设置。还支持 `state_dict`、`model_state_dict`、`model` 键包装的权重字典。不支持序列化整个模型对象、自动修补 DDP 前缀、忽略缺失层或自动截断 320→8 维。

`load_model` 使用 CPU map_location、strict=True 校验后再迁移设备，返回 eval 模式，暴露 `embedding_config`、`checkpoint_metadata`、`checkpoint_path`。新 checkpoint 自带配置，显式传入不同配置会拒绝；旧权重默认 sum 只是本框架策略，不代表旧实验采用 sum。复现旧实验时显式使用其 pooling（例如 last）。

## 7. 验证与交接完成条件

在根目录：

```bash
ATSCC/.venv/bin/python -m unittest discover -s ATSCC/tests -v
ATSCC/.venv/bin/python -m unittest discover -s complexity/tests -v
ATSCC/.venv/bin/python -m ATSCC.train --help
```

这些检查验证工程接口与小型合成数据执行，不验证真实场景的表示质量。最终验收还需在真实数据/目标 GPU 上：损失与梯度有限；重载后固定输入一致；留出行为信号非坍塌；多种子稳定；足够飞机的小时点云有可复核的尺度拟合区间。`unestimable` 是有效的不可估计状态，不是复杂度 0，更不能靠降低门槛强行得到结论。

仓库注意：ATSCC 是嵌套 Git 项目；根 `.gitignore` 当前忽略整个 `/doc/`。本交接文档已写入该目录，但提交交接时需要明确处理忽略规则（例如仅针对本文件 `git add -f doc/atscc-handoff.md`），不要误把文档未被跟踪当成文件不存在。

### 本次实际验证记录

- 当前环境 Torch 2.4.1 / CPU：ATSCC 23 项测试、complexity 21 项测试全部通过。
- 实际默认 256 维 / 4 层主干的 `(2,6,9) -> (2,6,8)` 前向、flat SNNL 与反向传播通过，损失及梯度有限。
- 小型合成数据训练 CLI 已跑通 train → validation → best/last checkpoint → 重载 → 共用特征转换 → encode_scene → complexity；不代表真实训练完成。
- 4/8/16 维与旧 320 维输出的保存/重载检查、非法 padding/非有限值拒绝、旧五项返回接口与输出防覆盖检查通过。
- 改动 Python 文件语法检查及保留原 CRLF 换行的差异检查通过；一次只读复核未报告范围内具体缺陷。
- 未进行 CUDA/MPS、真实数据训练、多种子质量实验；目标 GPU 显存/速度、表示非坍塌与研究指标有效性仍需实测。
