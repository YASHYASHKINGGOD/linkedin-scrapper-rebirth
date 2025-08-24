from __future__ import annotations
import os
from celery import Celery

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

app = Celery(
    "scraper",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Autodiscover scraper and router tasks
app.autodiscover_tasks(["src.scraper", "src.router"], force=True)

# Beat schedule for router sweep (every minute)
from celery.schedules import crontab  # type: ignore
app.conf.beat_schedule = {
    "router-every-minute": {
        "task": "src.router.tasks.route_once",
        "schedule": crontab(minute="*"),
        "args": [],
    },
}

