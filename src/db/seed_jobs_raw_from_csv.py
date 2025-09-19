from __future__ import annotations
import os
import csv
from typing import Optional
import psycopg

DDL_JOBS_RAW = """
CREATE TABLE IF NOT EXISTS public.linkedin_jobs_raw (
  id BIGSERIAL PRIMARY KEY,
  link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
  job_url TEXT,
  html_object_key TEXT,
  snapshot_object_key TEXT,
  raw_json JSONB,
  scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  scrape_status text NOT NULL DEFAULT 'done',
  -- denormalized fields aligned with CSV
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
CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_raw_link ON public.linkedin_jobs_raw(link_id);
"""


def upsert_jobs_raw_from_csv(database_url: str, csv_path: str) -> int:
    count = 0
    with psycopg.connect(database_url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute(DDL_JOBS_RAW)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = (row.get("url") or "").strip()
                if not url:
                    continue
                role_title = (row.get("role_title") or "").strip()
                company_name = (row.get("company_name") or "").strip()
                location = (row.get("location") or "").strip()
                posted_time = (row.get("posted_time") or "").strip()
                status_txt = (row.get("status") or "").strip()
                desc_text = (row.get("description_text") or "").strip()
                html_path = (row.get("html_path") or "").strip()
                shot_path = (row.get("screenshot_path") or "").strip()
                # find or create link
                rec = conn.execute(
                    "SELECT id FROM public.linkedin_links WHERE url_canonical = lower(%s)",
                    (url,),
                ).fetchone()
                link_id: Optional[int] = rec[0] if rec else None
                if link_id is None:
                    # minimal insert
                    rec = conn.execute(
                        """
                        INSERT INTO public.linkedin_links (url, source, category, status)
                        VALUES (%s, 'google_sheet', 'jobs', 'queued')
                        ON CONFLICT (url_canonical) DO UPDATE SET url = EXCLUDED.url
                        RETURNING id
                        """,
                        (url,),
                    ).fetchone()
                    link_id = rec[0]
                # upsert raw with denormalized fields
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
                        location,
                        posted_time,
                        status_txt,
                        desc_text,
                        html_path,
                        shot_path,
                    ),
                )
                # transition to scraped
                conn.execute(
                    "UPDATE public.linkedin_links SET status='scraped' WHERE id=%s",
                    (link_id,),
                )
                count += 1
        conn.commit()
    return count


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Seed linkedin_jobs_raw from a scraper CSV")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--db", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.db:
        raise SystemExit("DATABASE_URL is required (env or --db)")
    n = upsert_jobs_raw_from_csv(args.db, args.csv)
    print(json.dumps({"ok": True, "inserted": n, "csv": args.csv}, indent=2))
