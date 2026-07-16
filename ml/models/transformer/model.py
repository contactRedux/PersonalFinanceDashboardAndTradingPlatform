"""
Temporal Fusion Transformer (TFT) — Attention-based multi-horizon forecaster.

Architecture
============

This is a simplified TFT inspired by the paper:
  "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series
  Forecasting" — Bryan Lim et al., 2019 (https://arxiv.org/abs/1912.09363)

Simplifications vs full TFT:
  - Uses standard multi-head self-attention (no separate temporal self-attention)
  - No static covariate encoders (could be added when metadata is available)
  - Single output head for 3-class signal classification (bullish/neutral/bearish)

Input shape: (batch, seq_len, n_features)
Output shape: (batch, 3)  ← class logits [bullish, neutral, bearish]

Usage::

    from ml.models.transformer.model import TFTModel

    model = TFTModel(n_features=12, d_model=64, n_heads=4, n_layers=2, dropout=0.1)
    logits = model(x)           # x: (B, T, n_features)
    probs = torch.softmax(logits, dim=-1)
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn


class _GatedResidualNetwork(nn.Module):
    """
    Gated Residual Network (GRN) — the key building block of TFT.

    GRN(a) = LayerNorm(a + GLU(ELU(Linear(a)) · Linear(a)))

    The gate is computed from a separate linear projection so the network
    can suppress irrelevant information paths.
    """

    def __init__(self, d_model: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.fc1 = nn.Linear(d_model, d_model)
        self.fc2 = nn.Linear(d_model, d_model * 2)  # output for GLU
        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(d_model)
        self.elu = nn.ELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, D)
        h = self.elu(self.fc1(x))
        h = self.dropout(h)
        h = self.fc2(h)
        # GLU: split into two halves, gate the first by sigmoid of the second
        h1, h2 = h.chunk(2, dim=-1)
        h = h1 * torch.sigmoid(h2)
        return self.norm(x + h)


class _VariableSelectionNetwork(nn.Module):
    """
    Variable Selection Network — learns per-feature importance weights.

    Outputs a weighted sum of per-feature projections.
    """

    def __init__(self, n_features: int, d_model: int, dropout: float = 0.1) -> None:
        super().__init__()
        # Project each input feature to d_model
        self.feature_projections = nn.ModuleList(
            [nn.Linear(1, d_model) for _ in range(n_features)]
        )
        # GRN that produces selection weights
        self.grn = _GatedResidualNetwork(d_model, dropout=dropout)
        self.weight_fc = nn.Linear(d_model, n_features)
        self.n_features = n_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, n_features)
        # Project each feature independently
        projections = torch.stack(
            [self.feature_projections[i](x[..., i : i + 1]) for i in range(self.n_features)],
            dim=-2,
        )  # (B, T, n_features, d_model)

        # Compute selection weights using the aggregated representation
        agg = projections.mean(dim=-2)  # (B, T, d_model)
        agg = self.grn(agg)
        weights = torch.softmax(self.weight_fc(agg), dim=-1)  # (B, T, n_features)

        # Weighted sum
        out = (projections * weights.unsqueeze(-1)).sum(dim=-2)  # (B, T, d_model)
        return out


class _TemporalSelfAttention(nn.Module):
    """
    Multi-head self-attention over the temporal dimension with a causal mask.

    The causal mask ensures each timestep can only attend to itself and
    previous steps (auto-regressive property).
    """

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.size(1)
        # Causal mask: positions can attend to i <= j only
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        attn_out, _ = self.attn(x, x, x, attn_mask=mask)
        return self.norm(x + self.dropout(attn_out))


class _PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding (fixed, not learned)."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float) * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]  # type: ignore[index]
        return self.dropout(x)


class TFTModel(nn.Module):
    """
    Temporal Fusion Transformer for 3-class signal classification.

    Parameters
    ----------
    n_features:
        Number of input features per timestep.
    d_model:
        Internal model dimension (embedding size).
    n_heads:
        Number of attention heads (must divide d_model evenly).
    n_layers:
        Number of Transformer encoder layers (each with self-attention + GRN).
    dropout:
        Dropout probability for regularisation.
    num_classes:
        Output classes (3 = bullish / neutral / bearish).
    """

    def __init__(
        self,
        n_features: int,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.1,
        num_classes: int = 3,
    ) -> None:
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.n_features = n_features
        self.d_model = d_model

        # Variable selection
        self.vsn = _VariableSelectionNetwork(n_features, d_model, dropout=dropout)

        # Positional encoding
        self.pos_enc = _PositionalEncoding(d_model, dropout=dropout)

        # Temporal self-attention layers, each followed by a GRN
        self.temporal_layers = nn.ModuleList(
            [
                nn.ModuleList(
                    [
                        _TemporalSelfAttention(d_model, n_heads, dropout=dropout),
                        _GatedResidualNetwork(d_model, dropout=dropout),
                    ]
                )
                for _ in range(n_layers)
            ]
        )

        # Final decoder head
        self.decoder = nn.Sequential(
            _GatedResidualNetwork(d_model, dropout=dropout),
            nn.Linear(d_model, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, n_features).

        Returns:
            Class logits of shape (batch, num_classes).
        """
        # Variable selection: (B, T, d_model)
        h = self.vsn(x)
        h = self.pos_enc(h)

        # Temporal self-attention + GRN blocks
        for attn_layer, grn_layer in self.temporal_layers:
            h = attn_layer(h)
            h = grn_layer(h)

        # Pool over time dimension (mean) → (B, d_model)
        h = h.mean(dim=1)

        # Output logits → (B, num_classes)
        return self.decoder(h)
