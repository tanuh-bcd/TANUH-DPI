"""
Celery application for the forgensic (Forgery Detection) service.

Runs on a dedicated 'forgensic' queue — completely isolated from the
nhcx and abdm worker pools so CV workloads never starve insurance/clinical jobs.

Worker startup (docker-compose override):
    celery -A forgensic.celery_app worker --loglevel=info --concurrency=2 -Q forgensic
"""
import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "forgensic_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["forgensic.tasks"],
)

celery_app.conf.update(
    # ── Serialisation ─────────────────────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ── Time zone ─────────────────────────────────────────────────────────────
    timezone="UTC",
    enable_utc=True,

    # ── Reliability ───────────────────────────────────────────────────────────
    task_track_started=True,
    task_acks_late=True,           # Ack only after task completes — never lose a job on worker crash
    worker_prefetch_multiplier=1,  # Each worker only takes 1 task at a time (CV tasks are heavy)
    task_reject_on_worker_lost=True,  # Re-queue the task if a worker dies mid-execution

    # ── Timeouts ──────────────────────────────────────────────────────────────
    task_time_limit=3600,          # 1 h hard kill
    task_soft_time_limit=3300,     # 55 min soft — raises SoftTimeLimitExceeded, lets task clean up

    # ── Result backend ────────────────────────────────────────────────────────
    result_expires=3600,           # Keep Celery result entries for 1 h (matches JOB_TTL_SECONDS)

    # ── Routing ───────────────────────────────────────────────────────────────
    task_routes={
        "forgensic.tasks.process_forgensic_job": {"queue": "forgensic"},
    },
    task_default_queue="forgensic",
)
