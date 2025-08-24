from __future__ import annotations
import os
import psycopg
from celery import shared_task
from src.scraper.dev import scrape_single_job


def _db() -> str:
    db = os.environ.get("DATABASE_URL", "")
    if not db:
        raise RuntimeError("DATABASE_URL is required")
    return db


@shared_task(name="src.scraper.tasks.scrape_job")
def scrape_job(msg: dict) -> dict:
    link_id = int(msg.get("link_id"))
    url = str(msg.get("url"))
    attempt = int(msg.get("attempt", 1))
    db = _db()
    claimed = False
    with psycopg.connect(db) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        # claim if queued/error and due
        r = conn.execute(
            """
            UPDATE public.linkedin_links
            SET status='scraping'
            WHERE id=%s AND COALESCE(status,'new') IN ('queued','error') AND now() >= COALESCE(next_attempt_at, now())
            RETURNING id
            """,
            (link_id,),
        ).fetchone()
        if not r:
            return {"ok": False, "skipped": True, "reason": "not eligible", "link_id": link_id}
        claimed = True
        conn.commit()
    try:
        res = scrape_single_job(url, headed=False)
        html_path = res.get("html_path")
        shot_path = res.get("screenshot_path")
        with psycopg.connect(db) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            # ensure table and desired columns exist
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS public.linkedin_jobs_raw (
                  id BIGSERIAL PRIMARY KEY,
                  link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
                  job_url TEXT,
                  html_object_key TEXT,
                  snapshot_object_key TEXT,
                  raw_json JSONB,
                  scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  scrape_status text NOT NULL DEFAULT 'done'
                );
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_raw_link ON public.linkedin_jobs_raw(link_id)")
            # new, denormalized columns to mirror CSV output
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS url TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS role_title TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS company_name TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS location TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS posted_time TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS status TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS description_text TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS html_path TEXT")
            conn.execute("ALTER TABLE public.linkedin_jobs_raw ADD COLUMN IF NOT EXISTS screenshot_path TEXT")
            # map fields from scraper result
            role_title = res.get("role_title")
            company_name = res.get("company_name")
            loc = res.get("location")
            posted_time = res.get("posted_time")
            status_txt = res.get("status")
            desc_text = res.get("description_text")
            conn.execute(
                """
                INSERT INTO public.linkedin_jobs_raw (
                  link_id, job_url, html_object_key, snapshot_object_key, scrape_status,
                  url, role_title, company_name, location, posted_time, status, description_text, html_path, screenshot_path
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
                """,
                (
                    link_id,
                    url,
                    html_path,
                    shot_path,
                    url,
                    role_title,
                    company_name,
                    loc,
                    posted_time,
                    status_txt,
                    desc_text,
                    html_path,
                    shot_path,
                ),
            )
            conn.execute(
                "UPDATE public.linkedin_links SET status='scraped' WHERE id=%s",
                (link_id,),
            )
            conn.commit()
        return {"ok": True, "link_id": link_id, "html_path": html_path, "screenshot_path": shot_path}
    except Exception as e:
        with psycopg.connect(db) as conn:
            conn.execute(
                """
                UPDATE public.linkedin_links
                SET status='error', attempt_count=COALESCE(attempt_count,0)+1, last_error=%s, next_attempt_at=now() + interval '30 minutes'
                WHERE id=%s
                """,
                (str(e), link_id),
            )
            conn.commit()
        return {"ok": False, "link_id": link_id, "error": str(e)}


@shared_task(name="src.scraper.tasks.scrape_post")
def scrape_post(msg: dict) -> dict:
    # Placeholder: implement posts later
    return {"ok": False, "skipped": True, "reason": "post scraper not implemented", "link_id": msg.get("link_id")}

