"""
Unified LinkedIn Scrapers

Per-link scraping tasks for jobs and posts with:
- Link claiming (status='scraping')
- Artifact storage (./storage/{jobs|posts}/{link_id}/)
- Database persistence (*_raw tables)
- Error handling with exponential backoff
- Idempotent upserts
"""
from __future__ import annotations
import os
import uuid
from typing import Dict, Any
from celery import shared_task
import psycopg


def _get_database_url() -> str:
    """Get DATABASE_URL with validation."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return db_url


@shared_task(name="apps.orchestration.scrapers.scrape_job", 
             bind=True, 
             autoretry_for=(Exception,),
             retry_backoff=True,
             retry_kwargs={'max_retries': 3})
def scrape_job(self, message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape a LinkedIn job posting.
    
    Input message: {
        "link_id": int,
        "url": str,
        "type": "job", 
        "trace_id": str,
        "attempt": int
    }
    
    Returns: {"ok": bool, "link_id": int, "artifacts": dict}
    """
    from src.scraper.dev import scrape_single_job
    
    link_id = int(message.get("link_id"))
    url = str(message.get("url"))
    trace_id = message.get("trace_id", str(uuid.uuid4())[:8])
    attempt = int(message.get("attempt", 1))
    
    db_url = _get_database_url()
    
    # Step 1: Claim the link
    try:
        with psycopg.connect(db_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            
            # Claim link if eligible
            result = conn.execute("""
                UPDATE public.linkedin_links
                SET status = 'scraping',
                    last_scraped_at = now()
                WHERE id = %s 
                AND COALESCE(status, 'new') IN ('queued', 'error')
                AND now() >= COALESCE(next_attempt_at, now())
                RETURNING id
            """, (link_id,))
            
            if not result.fetchone():
                return {
                    "ok": False,
                    "skipped": True, 
                    "reason": "Link not eligible for scraping",
                    "link_id": link_id,
                    "trace_id": trace_id
                }
            
            conn.commit()
            
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to claim link: {str(e)}",
            "link_id": link_id,
            "trace_id": trace_id
        }
    
    # Step 2: Scrape the job
    try:
        # Use existing scraper logic
        scrape_result = scrape_single_job(url, headed=False)
        
        # Step 3: Persist to linkedin_jobs_raw
        with psycopg.connect(db_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            
            # Ensure table exists with all columns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS public.linkedin_jobs_raw (
                    id BIGSERIAL PRIMARY KEY,
                    link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
                    job_url TEXT,
                    html_object_key TEXT,
                    snapshot_object_key TEXT,
                    raw_json JSONB,
                    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    scrape_status TEXT NOT NULL DEFAULT 'done',
                    
                    -- Denormalized fields from scraper
                    url TEXT,
                    role_title TEXT,
                    company_name TEXT,
                    location TEXT,
                    posted_time TEXT,
                    status TEXT,
                    description_text TEXT,
                    html_path TEXT,
                    screenshot_path TEXT
                );
            """)
            
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_raw_link 
                ON public.linkedin_jobs_raw(link_id);
            """)
            
            # Extract scraper results
            html_path = scrape_result.get("html_path")
            screenshot_path = scrape_result.get("screenshot_path")
            role_title = scrape_result.get("role_title")
            company_name = scrape_result.get("company_name")
            location = scrape_result.get("location")
            posted_time = scrape_result.get("posted_time")
            status_text = scrape_result.get("status")
            description_text = scrape_result.get("description_text")
            
            # Upsert job record
            conn.execute("""
                INSERT INTO public.linkedin_jobs_raw (
                    link_id, job_url, html_object_key, snapshot_object_key, 
                    scrape_status, url, role_title, company_name, location,
                    posted_time, status, description_text, html_path, screenshot_path
                ) VALUES (
                    %s, %s, %s, %s, 'done',
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (link_id) DO UPDATE SET
                    job_url = EXCLUDED.job_url,
                    html_object_key = EXCLUDED.html_object_key,
                    snapshot_object_key = EXCLUDED.snapshot_object_key,
                    scraped_at = now(),
                    scrape_status = 'done',
                    url = EXCLUDED.url,
                    role_title = EXCLUDED.role_title,
                    company_name = EXCLUDED.company_name,
                    location = EXCLUDED.location,
                    posted_time = EXCLUDED.posted_time,
                    status = EXCLUDED.status,
                    description_text = EXCLUDED.description_text,
                    html_path = EXCLUDED.html_path,
                    screenshot_path = EXCLUDED.screenshot_path
            """, (
                link_id, url, html_path, screenshot_path,
                url, role_title, company_name, location,
                posted_time, status_text, description_text, html_path, screenshot_path
            ))
            
            # Mark link as scraped
            conn.execute("""
                UPDATE public.linkedin_links 
                SET status = 'scraped',
                    last_scraped_at = now()
                WHERE id = %s
            """, (link_id,))
            
            conn.commit()
        
        return {
            "ok": True,
            "link_id": link_id,
            "url": url,
            "artifacts": {
                "html_path": html_path,
                "screenshot_path": screenshot_path
            },
            "trace_id": trace_id,
            "scraper": "job"
        }
        
    except Exception as e:
        # Step 4: Handle errors with backoff
        try:
            with psycopg.connect(db_url) as conn:
                conn.execute("""
                    UPDATE public.linkedin_links
                    SET status = 'error',
                        attempt_count = COALESCE(attempt_count, 0) + 1,
                        last_error = %s,
                        next_attempt_at = now() + interval '30 minutes'
                    WHERE id = %s
                """, (str(e), link_id))
                conn.commit()
        except Exception:
            pass  # Don't fail the task if we can't update error state
        
        return {
            "ok": False,
            "error": str(e),
            "link_id": link_id,
            "url": url,
            "trace_id": trace_id,
            "scraper": "job"
        }


@shared_task(name="apps.orchestration.scrapers.scrape_post",
             bind=True,
             autoretry_for=(Exception,),
             retry_backoff=True,
             retry_kwargs={'max_retries': 3})
def scrape_post(self, message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape a LinkedIn post.
    
    Input message: {
        "link_id": int,
        "url": str, 
        "type": "post",
        "trace_id": str,
        "attempt": int
    }
    
    Returns: {"ok": bool, "link_id": int, "artifacts": dict}
    """
    from src.routers.posts_router import LinkedInPostsRouter
    from async_database_scraper import AsyncDatabaseLinkedInScraper
    import asyncio
    
    link_id = int(message.get("link_id"))
    url = str(message.get("url"))
    trace_id = message.get("trace_id", str(uuid.uuid4())[:8])
    attempt = int(message.get("attempt", 1))
    
    db_url = _get_database_url()
    
    # Step 1: Claim the link
    try:
        with psycopg.connect(db_url) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            
            # Claim link if eligible
            result = conn.execute("""
                UPDATE public.linkedin_links
                SET status = 'scraping',
                    last_scraped_at = now()
                WHERE id = %s
                AND COALESCE(status, 'new') IN ('queued', 'error')
                AND now() >= COALESCE(next_attempt_at, now())
                RETURNING id
            """, (link_id,))
            
            if not result.fetchone():
                return {
                    "ok": False,
                    "skipped": True,
                    "reason": "Link not eligible for scraping", 
                    "link_id": link_id,
                    "trace_id": trace_id
                }
            
            conn.commit()
            
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to claim link: {str(e)}",
            "link_id": link_id,
            "trace_id": trace_id
        }
    
    # Step 2: Scrape the post
    try:
        # Use existing posts pipeline
        router = LinkedInPostsRouter(db_url, "./storage")
        
        # Create or get raw entry
        raw_id = None
        try:
            def run_async(coro):
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            
            raw_id = run_async(router.create_or_update_raw_entry(link_id, url, trace_id))
            
            # Scrape using async database scraper
            async def _scrape():
                async with AsyncDatabaseLinkedInScraper(
                    database_url=db_url,
                    config_path="config.json", 
                    storage_base="./storage"
                ) as scraper:
                    return await scraper.scrape_post(url, link_id, trace_id)
            
            scrape_result = run_async(_scrape())
            
            if scrape_result.get("success"):
                # Update raw entry and link status
                run_async(router.update_scraping_status(raw_id, 'completed', result=scrape_result))
                run_async(router.update_link_status(link_id, 'scraped'))
                
                return {
                    "ok": True,
                    "link_id": link_id,
                    "url": url,
                    "raw_id": raw_id,
                    "artifacts": {
                        "raw_html_path": scrape_result.get("raw_html_path"),
                        "screenshot_path": scrape_result.get("screenshot_path")
                    },
                    "trace_id": trace_id,
                    "scraper": "post"
                }
            else:
                # Update raw entry with error
                run_async(router.update_scraping_status(raw_id, 'retry', error_message=scrape_result.get("error_message")))
                raise Exception(scrape_result.get("error_message", "Post scraping failed"))
                
        except Exception as scrape_error:
            raise scrape_error
            
    except Exception as e:
        # Step 3: Handle errors with backoff
        try:
            with psycopg.connect(db_url) as conn:
                conn.execute("""
                    UPDATE public.linkedin_links
                    SET status = 'error',
                        attempt_count = COALESCE(attempt_count, 0) + 1,
                        last_error = %s,
                        next_attempt_at = now() + interval '30 minutes'
                    WHERE id = %s
                """, (str(e), link_id))
                conn.commit()
        except Exception:
            pass  # Don't fail the task if we can't update error state
        
        return {
            "ok": False,
            "error": str(e),
            "link_id": link_id,
            "url": url,
            "trace_id": trace_id,
            "scraper": "post"
        }