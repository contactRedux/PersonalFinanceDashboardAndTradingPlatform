"""
Regime Detection using a Gaussian Hidden Markov Model.

Requires hmmlearn >= 0.3.3. Install with:
    pip install hmmlearn
or add to pyproject.toml dependencies.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

try:
    from hmmlearn import hmm as _hmm

    _HMMLEARN_AVAILABLE = True
except ImportError:
    _HMMLEARN_AVAILABLE = False

# Stable mapping: HMM state index → human-readable regime label.
# Assignment is done after fitting by ranking states on mean volatility
# (features[:, 0] is assumed to be the volatility proxy).
_REGIME_LABELS = [
    "low_volatility",
    "mean_reverting",
    "trending",
    "high_volatility",
]


class RegimeDetector:
    """
    4-state Gaussian HMM that classifies market regimes.

    States are labelled after fitting by ranking on the mean of the first
    feature dimension (volatility proxy): lowest → 'low_volatility',
    highest → 'high_volatility'. The two middle states are labelled
    'mean_reverting' and 'trending' by mean momentum (feature[:, 2]).
    """

    def __init__(
        self,
        n_components: int = 4,
        n_iter: int = 100,
        random_state: int = 42,
    ) -> None:
        if not _HMMLEARN_AVAILABLE:
            raise ImportError(
                "hmmlearn is required for RegimeDetector. "
                "Install it with: pip install 'hmmlearn>=0.3.3'"
            )
        self.n_components = n_components
        self.n_iter = n_iter
        self.random_state = random_state
        self._model: object | None = None
        # Maps fitted HMM state index → _REGIME_LABELS index
        self._state_to_label: dict[int, int] = {}

    def fit(self, features: np.ndarray) -> "RegimeDetector":
        """
        Fit the HMM on a (T, n_features) array.

        Features should be columns: [volatility, yield_spread, momentum].
        """
        model = _hmm.GaussianHMM(
            n_components=self.n_components,
            covariance_type="full",
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        model.fit(features)
        self._model = model
        self._build_label_map(features)
        return self

    def _build_label_map(self, features: np.ndarray) -> None:
        """
        After fitting, sort HMM states by mean volatility (col 0) and
        assign regime labels.
        """
        means = self._model.means_  # type: ignore[union-attr]
        # Sort state indices by mean volatility ascending
        vol_order = np.argsort(means[:, 0])
        # Lowest vol → low_volatility, highest → high_volatility
        # Middle two sorted by momentum (col 2): lower → mean_reverting, higher → trending
        mid_states = vol_order[1:3]
        if features.shape[1] > 2:
            mom_vals = means[mid_states, 2]
        else:
            mom_vals = means[mid_states, 0]
        mid_sorted = mid_states[np.argsort(mom_vals)]  # ascending momentum

        ordered = [int(vol_order[0]), int(mid_sorted[0]), int(mid_sorted[1]), int(vol_order[3])]
        # ordered[i] is the HMM state index that corresponds to _REGIME_LABELS[i]
        self._state_to_label = {state_idx: label_idx for label_idx, state_idx in enumerate(ordered)}

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Return regime label indices (0-3) for each time step."""
        if self._model is None:
            raise RuntimeError("Call fit() before predict().")
        raw_states = self._model.predict(features)  # type: ignore[union-attr]
        return np.array([self._state_to_label.get(int(s), 0) for s in raw_states])

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """
        Return per-step posterior probabilities, shape (T, n_components).
        Columns are reordered to match _REGIME_LABELS ordering.
        """
        if self._model is None:
            raise RuntimeError("Call fit() before predict().")
        _, posteriors = self._model.score_samples(features)  # type: ignore[union-attr]
        n_labels = self.n_components
        reordered = np.zeros_like(posteriors)
        for state_idx, label_idx in self._state_to_label.items():
            if label_idx < n_labels and state_idx < posteriors.shape[1]:
                reordered[:, label_idx] = posteriors[:, state_idx]
        return reordered

    def regime_label(self, state_idx: int) -> str:
        """Map a label index (0-3) to a human-readable regime string."""
        if state_idx < 0 or state_idx >= len(_REGIME_LABELS):
            raise ValueError(f"state_idx must be 0–{len(_REGIME_LABELS) - 1}, got {state_idx}")
        return _REGIME_LABELS[state_idx]

    def save(self, path: str | Path) -> None:
        """Persist the fitted model to a pickle file."""
        with open(path, "wb") as fh:
            pickle.dump(self, fh)

    @classmethod
    def load(cls, path: str | Path) -> "RegimeDetector":
        """Load a previously saved RegimeDetector."""
        with open(path, "rb") as fh:
            return pickle.load(fh)  # noqa: S301
