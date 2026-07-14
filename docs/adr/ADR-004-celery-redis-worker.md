# ADR-004 — Celery + Redis for Background Task Execution

**Date:** 2025-01-10  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Several platform operations must run asynchronously without blocking the API request lifecycle:
ML model training (LSTM and XGBoost jobs lasting minutes to hours), periodic OHLCV data refresh
(every 5 minutes per symbol), alert condition evaluation (every 60 seconds across all active
user alerts), and on-demand PDF report generation. These workloads vary from sub-second
(alert evaluation) to long-running (ML training), and some must be triggered on a schedule
rather than by an HTTP request.

Alternatives considered: Python's built-in `asyncio` background tasks (`BackgroundTask` in
FastAPI), APScheduler, and a full message queue (RabbitMQ with Celery). FastAPI's
`BackgroundTask` runs in the same process as the API server; a crash or OOM in a training job
would take down the API. APScheduler provides scheduling but not distributed task queues or
result persistence. RabbitMQ + Celery offers maximum durability but introduces another
infrastructure component (RabbitMQ) that the team does not already operate.

## Decision

Use **Celery** with **Redis as both the broker and the result backend**.

Redis is already in the stack as the quote cache and pub/sub relay. Using it as the Celery
broker (database index 1) and result backend (database index 2) means no new infrastructure
component is required. Celery Beat is used as the periodic task scheduler, replacing APScheduler
with a solution that integrates naturally with the Celery worker fleet. Task definitions live in
`backend/app/tasks/` and are registered via the Celery app's `autodiscover_tasks()` mechanism.
The FastAPI application dispatches tasks via `.delay()` and returns a `task_id` to the caller
for polling.

## Consequences

### Positive
- Workers are horizontally scalable: additional Celery worker containers can be added without
  changing the API or broker configuration
- Celery Beat provides cron-like scheduling for periodic tasks (data refresh, alert evaluation)
  in a single, unified system
- Redis is already operated for caching and pub/sub — no new infrastructure dependency
- Task results and status are queryable via the Celery result backend; the API exposes a
  `GET /celery/tasks/{task_id}` endpoint for polling
- Long-running ML training jobs are isolated from the API process; a training crash does not
  affect API availability

### Negative
- Redis is not a durable message broker: if Redis loses data (no AOF/RDB persistence), in-flight
  tasks are lost; this is acceptable for periodic refresh tasks but is a known limitation
- Celery's serialisation default (pickle) must be changed to JSON to avoid security
  vulnerabilities when accepting user-controlled task arguments
- `celery beat` is a single-process scheduler and is not inherently highly available; a second
  beat instance would submit duplicate tasks without a distributed lock

### Neutral
- Celery worker and beat processes are separate Docker Compose services
  (`celery_worker`, `celery_beat`) sharing the backend codebase via the same Docker image
- Task concurrency per worker is configured via `CELERY_WORKER_CONCURRENCY` environment
  variable (default: number of CPU cores)
