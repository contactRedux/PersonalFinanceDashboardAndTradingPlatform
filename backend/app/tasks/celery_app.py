"""
Celery application factory.

Workers: uv run celery -A app.tasks.celery_app worker --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "quantnexus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sentiment_tasks",
        "app.tasks.data_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.order_tasks",
        "app.tasks.ml_tasks",
        "app.tasks.fundamentals_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "sync-open-orders-every-10s": {
            "task": "order_tasks.sync_open_orders",
            "schedule": 10.0,
        },
        "record-ticks-every-60s": {
            "task": "tasks.record_ticks",
            "schedule": 60.0,
        },
        "evaluate-alerts-every-30s": {
            "task": "tasks.evaluate_alerts",
            "schedule": 30.0,
        },
    },
)
