"""
Model Registry — filesystem + MLflow model versioning.

The registry provides:
  1. File-system registry:  weights stored under data/ml_weights/<model>/<ticker>.pt
     with a JSON manifest tracking version, metrics, and metadata.
  2. MLflow model registry (optional): when MLFLOW_TRACKING_URI is configured,
     each save() also registers the model in the MLflow Model Registry.

Registry manifest schema (data/ml_weights/<model>/registry.json):
  {
    "models": {
      "<ticker>": {
        "version": 3,
        "path": "data/ml_weights/lstm/SPY.pt",
        "ticker": "SPY",
        "model_type": "lstm",
        "train_start": "2023-01-01",
        "train_end": "2024-01-01",
        "val_loss": 0.382,
        "created_at": "2024-03-01T12:00:00Z",
        "mlflow_run_id": "abc123",
        "mlflow_model_uri": "models:/lstm_SPY/3"
      }
    }
  }

Usage::

    from ml.training.registry import ModelRegistry

    reg = ModelRegistry("lstm")
    reg.save(
        ticker="SPY",
        weight_path=Path("data/ml_weights/lstm/SPY.pt"),
        metrics={"val_loss": 0.382},
        metadata={"train_start": "2023-01-01", "epochs": 20},
    )
    entry = reg.get("SPY")
    best = reg.get_best("val_loss", mode="min")
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_WEIGHTS_ROOT = Path(os.environ.get("ML_WEIGHTS_DIR", "data/ml_weights"))


class ModelRegistry:
    """
    Filesystem-backed model registry with optional MLflow integration.

    Parameters
    ----------
    model_type:
        One of 'lstm', 'xgboost', 'hmm', 'transformer'.
    weights_root:
        Root directory where weight files and the manifest are stored.
        Defaults to the ML_WEIGHTS_DIR env var or 'data/ml_weights'.
    """

    def __init__(
        self,
        model_type: str,
        weights_root: Path | str | None = None,
    ) -> None:
        self.model_type = model_type
        self._root = Path(weights_root or _WEIGHTS_ROOT) / model_type
        self._root.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._root / "registry.json"
        self._manifest: dict[str, Any] = self._load_manifest()

    # ── Manifest I/O ──────────────────────────────────────────────────────────

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"models": {}}

    def _save_manifest(self) -> None:
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2))

    # ── Public API ────────────────────────────────────────────────────────────

    def save(
        self,
        ticker: str,
        weight_path: Path,
        metrics: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
        mlflow_run_id: str | None = None,
    ) -> int:
        """
        Register a newly trained model version.

        Returns the new version number.
        """
        ticker = ticker.upper()
        existing = self._manifest["models"].get(ticker, {})
        version = int(existing.get("version", 0)) + 1

        entry: dict[str, Any] = {
            "version": version,
            "path": str(weight_path),
            "ticker": ticker,
            "model_type": self.model_type,
            "created_at": datetime.now(UTC).isoformat(),
            **(metrics or {}),
            **(metadata or {}),
        }
        if mlflow_run_id:
            entry["mlflow_run_id"] = mlflow_run_id

        self._manifest["models"][ticker] = entry
        self._save_manifest()

        logger.info(
            "model_registry.saved",
            model_type=self.model_type,
            ticker=ticker,
            version=version,
            path=str(weight_path),
        )
        return version

    def get(self, ticker: str) -> dict[str, Any] | None:
        """Return the latest registered entry for a ticker, or None."""
        return self._manifest["models"].get(ticker.upper())

    def get_best(self, metric: str, mode: str = "min") -> dict[str, Any] | None:
        """
        Return the model entry with the best value for ``metric``.

        Args:
            metric: Key in the registry entry (e.g. 'val_loss').
            mode:   'min' for loss metrics, 'max' for accuracy metrics.
        """
        entries = [
            e for e in self._manifest["models"].values() if metric in e
        ]
        if not entries:
            return None
        reverse = mode == "max"
        return sorted(entries, key=lambda e: e[metric], reverse=reverse)[0]

    def list_models(self) -> list[dict[str, Any]]:
        """Return all registered model entries as a list."""
        return list(self._manifest["models"].values())

    def delete(self, ticker: str) -> bool:
        """Remove the registry entry for a ticker. Does not delete the weight file."""
        ticker = ticker.upper()
        if ticker in self._manifest["models"]:
            del self._manifest["models"][ticker]
            self._save_manifest()
            return True
        return False

    def promote_to_mlflow(self, ticker: str, model, flavor: str = "pytorch") -> str | None:  # type: ignore[no-untyped-def]
        """
        Register a model with the MLflow Model Registry if MLflow is available.

        Returns the MLflow model URI (e.g. 'models:/lstm_SPY/1') or None.
        """
        try:
            import mlflow  # noqa: PLC0415

            model_name = f"{self.model_type}_{ticker.upper()}"
            if flavor == "pytorch":
                result = mlflow.pytorch.log_model(
                    model,
                    artifact_path="model",
                    registered_model_name=model_name,
                )
            elif flavor == "sklearn":
                result = mlflow.sklearn.log_model(
                    model,
                    artifact_path="model",
                    registered_model_name=model_name,
                )
            else:
                return None

            uri = result.model_uri
            entry = self._manifest["models"].get(ticker.upper(), {})
            entry["mlflow_model_uri"] = uri
            self._manifest["models"][ticker.upper()] = entry
            self._save_manifest()
            return uri
        except Exception:  # noqa: BLE001
            logger.warning("model_registry.mlflow_promote_failed", ticker=ticker)
            return None
