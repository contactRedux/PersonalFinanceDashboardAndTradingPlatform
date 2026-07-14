"""
LSTM price prediction model — PyTorch implementation.

Architecture:
  - Input: (batch, seq_len, n_features) — OHLCV + technical indicators
  - LSTM encoder: 2 layers, hidden_size configurable
  - Linear classifier head → 3 output classes
  - Output: softmax probabilities (up >1%, flat ±1%, down >1%)

Classes:
  - LSTMPricePredictor: PyTorch nn.Module
"""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


def _require_torch() -> None:
    if not _TORCH_AVAILABLE:
        raise ImportError("PyTorch is required. Install with: pip install torch>=2.6.0")


if _TORCH_AVAILABLE:
    import torch
    import torch.nn as nn

    class LSTMPricePredictor(nn.Module):
        """
        2-layer LSTM classifier for 3-class next-bar return prediction.

        Labels:
          0 = down (return < -1%)
          1 = flat (-1% ≤ return ≤ +1%)
          2 = up   (return > +1%)

        Parameters
        ----------
        n_features : int
            Number of input features per time step.
        hidden_size : int
            LSTM hidden dimension (default 64).
        num_layers : int
            Number of stacked LSTM layers (default 2).
        dropout : float
            Dropout between LSTM layers (default 0.2).
        """

        def __init__(
            self,
            n_features: int,
            hidden_size: int = 64,
            num_layers: int = 2,
            dropout: float = 0.2,
        ) -> None:
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=n_features,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.classifier = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 3),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            """
            Forward pass.

            Parameters
            ----------
            x : Tensor of shape (batch, seq_len, n_features)

            Returns
            -------
            Tensor of shape (batch, 3) — raw logits
            """
            # Use only the last hidden state
            lstm_out, _ = self.lstm(x)
            last_hidden = lstm_out[:, -1, :]  # (batch, hidden_size)
            logits = self.classifier(last_hidden)  # (batch, 3)
            return logits

        def predict_proba(self, x: "torch.Tensor") -> "torch.Tensor":
            """Return softmax probabilities."""
            self.eval()
            with torch.no_grad():
                logits = self.forward(x)
                return torch.softmax(logits, dim=-1)

else:
    # Stub class when PyTorch is not installed
    class LSTMPricePredictor:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            _require_torch()
