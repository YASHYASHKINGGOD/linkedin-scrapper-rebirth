from __future__ import annotations
import os
import json
import time
from typing import List
from celery import shared_task, chain

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


@shared_task(name="src.scheduler_gs.tasks.upsert_db_from_ingest")
def upsert_db_from_ingest(res_ing: dict) -> dict:
    """Glue step to feed ingest's result into upsert_db.
    Accepts the previous task's dict and extracts csv_path.
    """
    if not isinstance(res_ing, dict) or not res_ing.get("ok"):
        return {"ok": False, "stage": "ingest", "error": (res_ing.get("error") if isinstance(res_ing, dict) else "ingest failed"), "result": res_ing}
    csv_path = res_ing.get("output_csv")
    return upsert_db.run(csv_path)


@shared_task(name="src.scheduler_gs.tasks.classify_queue_step")
def classify_queue_step(_: dict | None = None) -> dict:
    """Glue step to ignore prior result and call classification."""
    return classify_queue.run()


@shared_task(name="src.scheduler_gs.tasks.classify_queue")
def classify_queue() -> dict:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL is required"}
    out = migrate_and_classify(db_url)
    return {"ok": True, "summary": out}


@shared_task(name="src.scheduler_gs.tasks.pipeline")
def pipeline() -> dict:
    """Kick off the pipeline as a Celery chain without blocking inside the task."""
    async_res = chain(
        ingest.s(),
        upsert_db_from_ingest.s(),
        classify_queue_step.s(),
    ).apply_async()
    return {"ok": True, "chain_id": async_res.id}

