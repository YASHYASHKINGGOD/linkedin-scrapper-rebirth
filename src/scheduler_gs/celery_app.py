from __future__ import annotations
import os
from celery import Celery
from celery.schedules import crontab

# Celery app for Google Sheets → DB scheduler
# Broker/backend configured via env (Redis by default in local dev)

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")

# Default schedule: every 2 hours (can override with CELERY_CRON)
DEFAULT_CRON = os.environ.get("CELERY_CRON", "0 */2 * * *")

app = Celery(
    "scheduler_gs",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Basic config
app.conf.update(
    timezone=CELERY_TIMEZONE,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Import tasks module for autodiscovery
app.autodiscover_tasks(["src.scheduler_gs"], force=True)

# Beat schedule: pipeline every 2 hours by default
# If CELERY_CRON provided, it will be used; otherwise defaults to 0 */2 * * *
app.conf.beat_schedule = {
    "pipeline-every-2h": {
        "task": "src.scheduler_gs.tasks.pipeline",
        # crontab expects minute, hour, day_of_week, etc.
        # Parse DEFAULT_CRON by splitting fields
        "schedule": crontab(minute=0, hour="*/2"),
        "args": [],
    }
}

# If a custom cron string is provided, override the schedule (best-effort simple parser)
cron_str = DEFAULT_CRON.strip()
try:
    if cron_str and cron_str != "0 */2 * * *":
        fields = cron_str.split()
        if len(fields) == 5:
            minute, hour, day_of_month, month_of_year, day_of_week = fields
            app.conf.beat_schedule["pipeline-every-2h"]["schedule"] = crontab(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
            )
except Exception:
    # Fall back to default schedule on parse error
    pass

