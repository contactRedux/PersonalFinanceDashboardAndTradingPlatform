"""
MLflow Experiment Tracking module.

Provides a thin, opinionated wrapper around MLflow that:
  - Auto-creates experiments by name
  - Starts / ends runs and logs params, metrics, artefacts
  - Stores artefacts in the local filesystem under data/mlruns (or MLflow
    tracking server when MLFLOW_TRACKING_URI is set)

Usage::

    from ml.experiments.tracker import ExperimentTracker

    tracker = ExperimentTracker("LSTM-SPY")
    with tracker.start_run(run_name="run-001", tags={"model": "lstm", "ticker": "SPY"}) as run_id:
        tracker.log_params({"hidden_size": 64, "seq_len": 30, "epochs": 20})
        tracker.log_metrics({"train_loss": 0.42, "val_loss": 0.38}, step=0)
        tracker.log_artifact("/path/to/model.pt")
"""

from __future__ import annotations

import contextlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# MLflow tracking URI — defaults to local filesystem directory
_DEFAULT_TRACKING_URI = str(
    Path(__file__).resolve().parents[2] / "data" / "mlruns"
)
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", _DEFAULT_TRACKING_URI)


def _get_mlflow():
    """Lazy import so modules that don't need MLflow don't pay the import cost."""
    try:
        import mlflow  # noqa: PLC0415

        # MLflow ≥3.13 requires MLFLOW_ALLOW_FILE_STORE=true for filesystem
        # backends. Set it automatically when using the default local path.
        if MLFLOW_TRACKING_URI and not MLFLOW_TRACKING_URI.startswith(("sqlite", "postgresql", "mysql", "http")):
            os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        return mlflow
    except ImportError:
        return None


class ExperimentTracker:
    """
    Thin MLflow wrapper for QuantNexus model training runs.

    Falls back gracefully (no-op) when MLflow is not installed.
    """

    def __init__(self, experiment_name: str) -> None:
        self.experiment_name = experiment_name
        self._active_run_id: str | None = None

    def _setup_experiment(self, mlflow) -> None:  # type: ignore[no-untyped-def]
        """Create the experiment if it does not already exist."""
        try:
            exp = mlflow.get_experiment_by_name(self.experiment_name)
            if exp is None:
                mlflow.create_experiment(self.experiment_name)
            mlflow.set_experiment(self.experiment_name)
        except Exception:  # noqa: BLE001
            logger.warning("mlflow.experiment_setup_failed", name=self.experiment_name)

    @contextmanager
    def start_run(
        self,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ):
        """
        Context manager that starts an MLflow run and yields the run_id.

        On exit it ends the run automatically (even if an exception is raised).
        If MLflow is not installed, yields None and is a no-op.
        """
        mlflow = _get_mlflow()
        if mlflow is None:
            logger.warning("mlflow.not_installed.skipping_tracking")
            yield None
            return

        self._setup_experiment(mlflow)
        run = mlflow.start_run(run_name=run_name, tags=tags or {})
        self._active_run_id = run.info.run_id
        logger.info(
            "mlflow.run.started",
            experiment=self.experiment_name,
            run_id=self._active_run_id,
            run_name=run_name,
        )
        try:
            yield self._active_run_id
        except Exception:
            mlflow.end_run(status="FAILED")
            raise
        else:
            mlflow.end_run(status="FINISHED")
            logger.info("mlflow.run.finished", run_id=self._active_run_id)
        finally:
            self._active_run_id = None

    def log_params(self, params: dict[str, Any]) -> None:
        """Log a dict of hyperparameters to the active run."""
        mlflow = _get_mlflow()
        if mlflow is None:
            return
        with contextlib.suppress(Exception):
            mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log a dict of scalar metrics to the active run."""
        mlflow = _get_mlflow()
        if mlflow is None:
            return
        with contextlib.suppress(Exception):
            mlflow.log_metrics(metrics, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        """Log a file or directory as an MLflow artefact."""
        mlflow = _get_mlflow()
        if mlflow is None:
            return
        with contextlib.suppress(Exception):
            mlflow.log_artifact(local_path, artifact_path=artifact_path)

    def log_model_artifact(self, model, flavor: str = "pytorch", artifact_path: str = "model") -> None:  # type: ignore[no-untyped-def]
        """
        Log a trained model via the appropriate MLflow model flavour.

        Supported flavours: 'pytorch', 'sklearn' (xgboost uses sklearn flavour).
        """
        mlflow = _get_mlflow()
        if mlflow is None:
            return
        try:
            if flavor == "pytorch":
                mlflow.pytorch.log_model(model, artifact_path=artifact_path)
            elif flavor == "sklearn":
                mlflow.sklearn.log_model(model, artifact_path=artifact_path)
            else:
                logger.warning("mlflow.unknown_flavor", flavor=flavor)
        except Exception:  # noqa: BLE001
            logger.warning("mlflow.log_model_failed", flavor=flavor)

    def get_best_run(self, metric: str, mode: str = "min") -> dict[str, Any] | None:
        """
        Retrieve the best run for this experiment by a given metric.

        Args:
            metric: The metric name to optimise.
            mode:   'min' for loss-type metrics, 'max' for accuracy-type metrics.

        Returns:
            A dict with run_id, params, and metrics, or None if no runs exist.
        """
        mlflow = _get_mlflow()
        if mlflow is None:
            return None

        try:
            client = mlflow.tracking.MlflowClient()
            exp = client.get_experiment_by_name(self.experiment_name)
            if exp is None:
                return None

            order = "ASC" if mode == "min" else "DESC"
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=[f"metrics.{metric} {order}"],
                max_results=1,
            )
            if not runs:
                return None

            best = runs[0]
            return {
                "run_id": best.info.run_id,
                "run_name": best.info.run_name,
                "params": best.data.params,
                "metrics": best.data.metrics,
            }
        except Exception:  # noqa: BLE001
            logger.warning("mlflow.get_best_run_failed", experiment=self.experiment_name)
            return None
