"""Alert condition evaluation sweep — full implementation in ST-10."""
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.evaluate_alerts")
def evaluate_alerts() -> dict:
    """Scan all active alerts and publish triggered ones to Redis."""
    # Implemented in ST-10
    return {"status": "pending_st10"}
