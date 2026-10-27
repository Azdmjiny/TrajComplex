# Encoder 10 秒模型训练结果

当前导出的 Encoder 是 **10 秒采样、固定 epoch-90、16 维、sum pooling、seed 43** 的模型。权重在 `encoder/encoder.pt`，SHA-256 为 `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`，与 evaluation 代码要求的 checkpoint 一致。

## 训练与数据

- 采样：严格 10 秒，不追加 off-grid 端点。
- 轨迹：6,877 train / 1,214 validation / 8,092 held-out test。
- 训练：90 epoch，batch 16，bf16，seed 43，固定 epoch 90，不按验证损失挑选。
- 最终 epoch：train loss **4.0134**，validation loss **3.9758**。
- 数据划分沿用原 5 秒 split manifest，不在 10 秒形状上重新划分。

## 导出与验证

- `encoder.pt`：冻结权重，`FrozenEncoder` 可直接加载。
- `preprocess.json`：`stride_s=10`、`include_endpoint=false`、preprocessor `52fabdb8…`。
- `example_input_output.npz`：真实 10 秒轨迹的输入与输出。
- `export_verification.json`：严格 state-dict 加载、冻结参数、重复 CPU 推理一致、token 单位范数与 sum pooling 校验通过。
- `selection_10s.json`：记录固定 epoch-90 的选择规则与哈希。

## 与旧 5 秒模型的关系

`checkpoints/` 中仍保留旧的 5 秒候选 checkpoint（`d8/d4/d16_e120_t0p01_*`）和对应的 `RESULTS_5s_ZH.md`，它们只作为历史敏感性记录，不是当前导出。旧的 `embeddings.npz` 已重命名为 `encoder/embeddings-5s-old.npz`，避免被误认为当前模型的输出。

## 限制

本次 10 秒训练只报告训练/验证损失与导出完整性；没有用 TEST 集重新评分，也没有把几何代理 R² 当作复杂度真值。Encoder 的几何代理表现与 evaluation 的 D 结果是两件事，不能互相替代。
