"""
Unified LinkedIn Pipeline Tasks

Data Flow:
ingest_links → import_csv → classify_links → route_links → scrape_{job|post}

Message Schema:
{
    "link_id": int,
    "url": str, 
    "type": "job" | "post",
    "trace_id": str,
    "attempt": int
}
"""
from __future__ import annotations
import os
import time
import uuid
from typing import List, Dict, Any
from celery import shared_task, chain

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import existing functionality
from src.ingest.combined_links_csv import run_combined_csv
from src.db.import_and_backup import import_and_backup
from src.db.classify_and_queue import migrate_and_classify
from src.app import load_urls_from_env_and_config


def _get_database_url() -> str:
    """Get DATABASE_URL with validation."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return db_url


def _resolve_urls_and_month() -> tuple[List[str], str]:
    """Resolve Google Sheets URLs and month filter from environment."""
    urls = load_urls_from_env_and_config()
    month = os.environ.get("MONTH_FILTER", "aug")
    return urls, month


@shared_task(name="apps.orchestration.tasks.pipeline_chain")
def pipeline_chain() -> Dict[str, Any]:
    """
    Master pipeline task that chains all stages.
    
    Flow: ingest → import → classify → route
    Returns chain ID for monitoring.
    """
    trace_id = str(uuid.uuid4())[:8]
    
    # Create task chain with proper error handling
    async_result = chain(
        ingest_links.si(trace_id=trace_id),
        import_csv.s(),
        classify_links.s(), 
        route_links.s(),
    ).apply_async()
    
    return {
        "ok": True,
        "chain_id": async_result.id,
        "trace_id": trace_id,
        "message": "Pipeline chain initiated"
    }


@shared_task(name="apps.orchestration.tasks.ingest_links")
def ingest_links(trace_id: str = None) -> Dict[str, Any]:
    """
    Stage 1: Ingest Google Sheets → CSV
    
    Returns: {"ok": bool, "output_csv": str, "stats": dict}
    """
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]
    
    try:
        urls, month = _resolve_urls_and_month()
        if not urls:
            return {
                "ok": False, 
                "error": "No Google Sheets URLs configured",
                "trace_id": trace_id
            }
        
        # Create timestamped output path
        timestamp = int(time.time())
        output_csv = f"./storage/ingest/google_sheets/{timestamp}/combined.csv"
        
        # Run ingestion
        stats = run_combined_csv(
            urls=urls, 
            month_filter=month, 
            output_csv=output_csv
        )
        
        return {
            "ok": True,
            "output_csv": stats.get("output_csv", output_csv),
            "stats": stats,
            "trace_id": trace_id,
            "stage": "ingest"
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
            "stage": "ingest"
        }


@shared_task(name="apps.orchestration.tasks.import_csv")
def import_csv(ingest_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 2: Import CSV → linkedin_links table
    
    Input: Result from ingest_links
    Returns: {"ok": bool, "backup_csv": str, "trace_id": str}
    """
    # Extract trace_id and validate input
    trace_id = ingest_result.get("trace_id", str(uuid.uuid4())[:8])
    
    if not isinstance(ingest_result, dict) or not ingest_result.get("ok"):
        return {
            "ok": False,
            "error": f"Ingest stage failed: {ingest_result.get('error', 'Unknown error')}",
            "trace_id": trace_id,
            "stage": "import"
        }
    
    try:
        csv_path = ingest_result.get("output_csv")
        if not csv_path:
            return {
                "ok": False,
                "error": "No CSV path provided from ingest stage",
                "trace_id": trace_id,
                "stage": "import"
            }
        
        db_url = _get_database_url()
        
        # Import with backup
        backup_csv = import_and_backup(
            database_url=db_url,
            csv_path=csv_path,
            backup_dir="./storage/backups",
            insert_window_minutes=10
        )
        
        return {
            "ok": True,
            "backup_csv": backup_csv,
            "csv_path": csv_path,
            "trace_id": trace_id,
            "stage": "import"
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
            "stage": "import"
        }


@shared_task(name="apps.orchestration.tasks.classify_links")
def classify_links(import_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 3: Classify links and set status='queued'
    
    Input: Result from import_csv 
    Returns: {"ok": bool, "summary": dict, "trace_id": str}
    """
    # Extract trace_id and validate input
    trace_id = import_result.get("trace_id", str(uuid.uuid4())[:8])
    
    if not isinstance(import_result, dict) or not import_result.get("ok"):
        return {
            "ok": False,
            "error": f"Import stage failed: {import_result.get('error', 'Unknown error')}",
            "trace_id": trace_id,
            "stage": "classify"
        }
    
    try:
        db_url = _get_database_url()
        
        # Run classification
        classification_result = migrate_and_classify(db_url)
        
        return {
            "ok": True,
            "summary": classification_result,
            "trace_id": trace_id,
            "stage": "classify"
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
            "stage": "classify"
        }


@shared_task(name="apps.orchestration.tasks.route_links")
def route_links(classify_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 4: Route queued links to per-link scraping tasks
    
    Finds links with status='queued' and enqueues individual scraping tasks.
    
    Input: Result from classify_links
    Returns: {"ok": bool, "routed": {"jobs": int, "posts": int}, "trace_id": str}
    """
    from apps.orchestration.scrapers import scrape_job, scrape_post
    import psycopg
    
    # Extract trace_id and validate input
    trace_id = classify_result.get("trace_id", str(uuid.uuid4())[:8])
    
    if not isinstance(classify_result, dict) or not classify_result.get("ok"):
        return {
            "ok": False,
            "error": f"Classify stage failed: {classify_result.get('error', 'Unknown error')}",
            "trace_id": trace_id,
            "stage": "route"
        }
    
    try:
        db_url = _get_database_url()
        routed_jobs = 0
        routed_posts = 0
        
        with psycopg.connect(db_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            
            # Find all links ready for scraping
            cursor = conn.execute("""
                SELECT id, url, classification 
                FROM public.linkedin_links 
                WHERE COALESCE(status, 'new') = 'queued'
                AND COALESCE(classification, '') IN ('job', 'post')
                AND now() >= COALESCE(next_attempt_at, now())
                ORDER BY id
            """)
            
            queued_links = cursor.fetchall()
            
            for link_id, url, classification in queued_links:
                # Create standardized message
                message = {
                    "link_id": link_id,
                    "url": url,
                    "type": classification,
                    "trace_id": trace_id,
                    "attempt": 1
                }
                
                # Route to appropriate scraper
                if classification == "job":
                    scrape_job.apply_async(args=[message])
                    routed_jobs += 1
                elif classification == "post":
                    scrape_post.apply_async(args=[message])  
                    routed_posts += 1
        
        return {
            "ok": True,
            "routed": {
                "jobs": routed_jobs,
                "posts": routed_posts,
                "total": routed_jobs + routed_posts
            },
            "trace_id": trace_id,
            "stage": "route"
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
            "stage": "route"
        }