"""Deterministic inference for the current frozen trajectory checkpoint.

Reference: petchthwr/ATSCC, commit 789ccd72b7496b52e03df7d8599d8c9e6659bdb9.
Preserves upstream projection L2 norms, bias-free attention and
normalization/residual order. No extra final LayerNorm or positional encoding.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F


class Attention(nn.Module):
    def __init__(self, model_dim, heads):
        super().__init__()
        self.dim, self.heads = model_dim, heads
        self.q_proj = nn.Linear(model_dim, model_dim, bias=False)
        self.k_proj = nn.Linear(model_dim, model_dim, bias=False)
        self.v_proj = nn.Linear(model_dim, model_dim, bias=False)
        self.out_proj = nn.Linear(model_dim, model_dim, bias=False)

    def forward(self, x, allowed):
        b, t, d = x.shape
        def heads(projection):
            return projection(x).reshape(b, t, self.heads, d // self.heads).transpose(1, 2)
        q, k, v = [heads(p) for p in (self.q_proj, self.k_proj, self.v_proj)]
        # The upstream implementation scales by sqrt(model_dim), not sqrt(head_dim).
        # SDPA gives zero attention for a fully masked causal prefix, avoiding
        # upstream's uniform softmax over disallowed future keys in that case.
        result = F.scaled_dot_product_attention(q, k, v, attn_mask=allowed,
                    dropout_p=0.0,
                    scale=1.0 / math.sqrt(self.dim))
        result = result.transpose(1, 2).reshape(b, t, d)
        return self.out_proj(result)


class Block(nn.Module):
    def __init__(self, model_dim, ffn_dim, heads):
        super().__init__()
        self.attn_norm, self.ff_norm = nn.LayerNorm(model_dim), nn.LayerNorm(model_dim)
        self.attn = Attention(model_dim, heads)
        # Parameter names are those stored in the current frozen checkpoint.
        self.ff = nn.ModuleDict({"0": nn.Linear(model_dim, ffn_dim),
                                 "3": nn.Linear(ffn_dim, model_dim)})

    def forward(self, x, allowed):
        x = self.attn_norm(x)
        x = x + self.attn(x, allowed)
        x = self.ff_norm(x)
        return x + self.ff["3"](F.gelu(self.ff["0"](x)))


class TrajectoryEncoder(nn.Module):
    def __init__(self, output_dim, input_dim=9, model_dim=256, ffn_dim=512,
                 heads=4, layers=4):
        super().__init__()
        if model_dim % heads:
            raise ValueError("model_dim must be divisible by heads")
        self.pre_proj = nn.Linear(input_dim, model_dim)
        self.layers = nn.ModuleList([Block(model_dim, ffn_dim, heads) for _ in range(layers)])
        self.post_proj = nn.Linear(model_dim, output_dim)

    def forward(self, x, valid):
        hidden = ~valid
        h = F.normalize(self.pre_proj(x.masked_fill(hidden[..., None], 0)).float(), dim=-1)
        causal = torch.ones((x.shape[1], x.shape[1]), device=x.device, dtype=torch.bool).tril()
        allowed = causal[None, None] & (~hidden[:, None, None, :])
        for layer in self.layers:
            h = layer(h, allowed)
        z = F.normalize(self.post_proj(h).float(), dim=-1)
        return z.masked_fill(~valid[..., None], 0)


def pool(tokens, mode):
    if mode == "sum":
        return tokens.sum(0)
    if mode == "mean":
        return tokens.mean(0)
    if mode == "gem2":
        # ITSC equation on page 3: signed generalized mean, p=2.
        value = (tokens.sign() * tokens.abs().square()).mean(0)
        return value.sign() * value.abs().sqrt()
    raise ValueError(mode)
