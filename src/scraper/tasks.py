from __future__ import annotations
from celery import shared_task

# Minimal stub so Flower shows task registry; real implementation comes in M2
@shared_task(name="src.scraper.tasks.scrape_job")
def scrape_job(msg: dict) -> dict:
    return {"ok": True, "received": msg}

@shared_task(name="src.scraper.tasks.scrape_post")
def scrape_post(msg: dict) -> dict:
    return {"ok": True, "received": msg}

