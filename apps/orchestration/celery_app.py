"""
Unified Celery App for LinkedIn Pipeline Orchestration

Single broker, single beat, clear queue separation:
- ingest: Google Sheets → CSV
- route: classify and enqueue per-link tasks  
- scrape.job: LinkedIn jobs scraping
- scrape.post: LinkedIn posts scraping
"""
from __future__ import annotations
import os
from celery import Celery
from celery.schedules import crontab

# Environment-driven configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")

# Pipeline schedule (default: every 2 hours)
PIPELINE_CRON = os.environ.get("PIPELINE_CRON", "0 */2 * * *")

# Create unified Celery app
app = Celery(
    "linkedin_pipeline",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Configuration
app.conf.update(
    timezone=CELERY_TIMEZONE,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    
    # Queue routing
    task_routes={
        "apps.orchestration.tasks.ingest_links": {"queue": "ingest"},
        "apps.orchestration.tasks.import_csv": {"queue": "ingest"},  
        "apps.orchestration.tasks.classify_links": {"queue": "route"},
        "apps.orchestration.tasks.route_links": {"queue": "route"},
        "apps.orchestration.scrapers.scrape_job": {"queue": "scrape.job"},
        "apps.orchestration.scrapers.scrape_post": {"queue": "scrape.post"},
        "apps.orchestration.tasks.pipeline_chain": {"queue": "default"},
    },
    
    # Queue definitions
    task_create_missing_queues=True,
    task_default_exchange="linkedin_pipeline",
    task_default_exchange_type="direct",
)

# Auto-discover tasks from orchestration modules
app.autodiscover_tasks([
    "apps.orchestration"
], force=True)

# Beat schedule - single pipeline chain every 2 hours
try:
    # Parse PIPELINE_CRON (format: "minute hour day_of_month month day_of_week")
    cron_fields = PIPELINE_CRON.strip().split()
    if len(cron_fields) == 5:
        minute, hour, day_of_month, month_of_year, day_of_week = cron_fields
        
        app.conf.beat_schedule = {
            "linkedin-pipeline": {
                "task": "apps.orchestration.tasks.pipeline_chain",
                "schedule": crontab(
                    minute=minute,
                    hour=hour,
                    day_of_month=day_of_month,
                    month_of_year=month_of_year,
                    day_of_week=day_of_week,
                ),
                "args": [],
            }
        }
    else:
        # Fallback to default every 2 hours
        app.conf.beat_schedule = {
            "linkedin-pipeline": {
                "task": "apps.orchestration.tasks.pipeline_chain",
                "schedule": crontab(minute=0, hour="*/2"),
                "args": [],
            }
        }
except Exception:
    # Fallback to default schedule on parse error
    app.conf.beat_schedule = {
        "linkedin-pipeline": {
            "task": "apps.orchestration.tasks.pipeline_chain", 
            "schedule": crontab(minute=0, hour="*/2"),
            "args": [],
        }
    }

# Export the app
__all__ = ["app"]