from __future__ import annotations
import os
import json
import time
from typing import List
from celery import shared_task

from src.ingest.combined_links_csv import run_combined_csv
from src.db.import_and_backup import import_and_backup
from src.db.classify_and_queue import migrate_and_classify
from src.app import load_urls_from_env_and_config


def _resolve_urls_and_month() -> tuple[List[str], str]:
    urls = load_urls_from_env_and_config()
    month = os.environ.get("MONTH_FILTER", "aug")
    return urls, month


@shared_task(name="src.scheduler_gs.tasks.ingest")
def ingest() -> dict:
    urls, month = _resolve_urls_and_month()
    if not urls:
        return {"ok": False, "error": "No Google Sheets URLs configured"}
    ts = int(time.time())
    out_csv = f"./storage/ingest/google_sheets/{ts}/combined.csv"
    stats = run_combined_csv(urls=urls, month_filter=month, output_csv=out_csv)
    return {"ok": True, "output_csv": stats.get("output_csv"), "stats": stats}


@shared_task(name="src.scheduler_gs.tasks.upsert_db")
def upsert_db(csv_path: str | None = None, minutes: int = 10) -> dict:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL is required"}
    if not csv_path:
        # Try to infer the last CSV path from storage (best-effort)
        return {"ok": False, "error": "csv_path is required for upsert_db in this version"}
    backup = import_and_backup(database_url=db_url, csv_path=csv_path, backup_dir="./storage/backups", insert_window_minutes=minutes)
    return {"ok": True, "backup_csv": backup}


@shared_task(name="src.scheduler_gs.tasks.classify_queue")
def classify_queue() -> dict:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL is required"}
    out = migrate_and_classify(db_url)
    return {"ok": True, "summary": out}


@shared_task(name="src.scheduler_gs.tasks.pipeline")
def pipeline() -> dict:
    # 1) ingest → CSV
    res_ing = ingest.apply().get()
    if not res_ing.get("ok"):
        return {"ok": False, "stage": "ingest", "error": res_ing.get("error"), "result": res_ing}
    csv_path = res_ing.get("output_csv")

    # 2) import_and_backup → DB
    res_db = upsert_db.apply(args=[csv_path]).get()
    if not res_db.get("ok"):
        return {"ok": False, "stage": "upsert_db", "error": res_db.get("error"), "result": res_db}

    # 3) classify_and_queue
    res_cl = classify_queue.apply().get()
    if not res_cl.get("ok"):
        return {"ok": False, "stage": "classify_queue", "error": res_cl.get("error"), "result": res_cl}

    return {"ok": True, "ingest": res_ing, "upsert": res_db, "classify": res_cl}

