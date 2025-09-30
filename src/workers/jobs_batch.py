#!/usr/bin/env python3
"""
LinkedIn Jobs Batch Runner

Purpose:
- Pull a batch of queued job links from public.linkedin_links
- Invoke the existing login-enabled job scraper (apps.orchestration.scrapers.scrape_job)
- Persist results into public.linkedin_jobs_raw (handled by the task)
- Update link statuses (handled by the task)

Usage:
  # Process a batch of queued jobs (default batch size: 5)
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/data_lake \
  python -m src.workers.jobs_batch run-batch --batch-size 5

  # Scrape a single job by existing link_id
  DATABASE_URL=... python -m src.workers.jobs_batch scrape-single --link-id 123

  # Scrape a single job by URL (creates a link if not present)
  DATABASE_URL=... python -m src.workers.jobs_batch scrape-single --url "https://www.linkedin.com/jobs/view/..."

Notes:
- The underlying task performs login using config.json (linkedin_credentials).
- Ensure config.json has email/password and optional chrome profile user_data_dir.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple, Optional

try:
    import psycopg
except ImportError:
    print("❌ psycopg is required. Install with: pip install 'psycopg[binary]'")
    sys.exit(1)


def _db_url() -> str:
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise SystemExit("DATABASE_URL environment variable is required")
    return db_url


def _fetch_queued_jobs(db_url: str, limit: int) -> List[Tuple[int, str]]:
    """Select eligible job links for scraping."""
    sql = """
        SELECT id, url
        FROM public.linkedin_links
        WHERE classification = 'job'
          AND (
                status = 'queued'
             OR (status = 'error' AND now() >= COALESCE(next_attempt_at, now()))
          )
        ORDER BY id ASC
        LIMIT %s
    """
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [(r[0], r[1]) for r in rows]


def _ensure_link_for_url(db_url: str, url: str) -> int:
    """Ensure a link row exists for a given URL; create if missing."""
    with psycopg.connect(db_url) as conn:
        with conn.transaction():
            row = conn.execute(
                "SELECT id FROM public.linkedin_links WHERE url = %s",
                (url,)
            ).fetchone()
            if row:
                return int(row[0])
            # Insert new job-classified queued link
            new_id = conn.execute(
                """
                INSERT INTO public.linkedin_links (url, classification, status)
                VALUES (%s, 'job', 'queued')
                RETURNING id
                """,
                (url,)
            ).fetchone()[0]
            return int(new_id)


def run_batch(batch_size: int) -> int:
    """Process a batch of queued job links using the existing scraper task."""
    from apps.orchestration.scrapers import scrape_job  # Celery task callable

    db_url = _db_url()
    jobs = _fetch_queued_jobs(db_url, batch_size)

    if not jobs:
        print("✅ No eligible queued job links found")
        return 0

    print(f"🧵 Processing {len(jobs)} job link(s)...")
    ok = 0
    failed = 0

    for link_id, url in jobs:
        msg = {
            "link_id": link_id,
            "url": url,
            "type": "job",
            "trace_id": f"jobs-batch-{link_id}",
            "attempt": 1,
        }
        try:
            # Call task synchronously without a broker
            result = scrape_job.run(msg)
            if result.get("ok"):
                ok += 1
                print(f"  ✅ link_id={link_id} scraped")
            else:
                failed += 1
                print(f"  ❌ link_id={link_id} failed: {result.get('error') or result}")
        except Exception as e:
            failed += 1
            print(f"  ❌ link_id={link_id} exception: {e}")

    print(f"\n📊 Batch summary: ok={ok}, failed={failed}, total={len(jobs)}")
    return 0 if failed == 0 else 1


def run_single(link_id: Optional[int], url: Optional[str]) -> int:
    """Scrape a single job either by existing link_id or by URL (creating link if needed)."""
    from apps.orchestration.scrapers import scrape_job

    if not link_id and not url:
        print("Provide --link-id or --url")
        return 2

    db_url = _db_url()
    if not link_id and url:
        link_id = _ensure_link_for_url(db_url, url)
    elif link_id and not url:
        with psycopg.connect(db_url) as conn:
            row = conn.execute("SELECT url FROM public.linkedin_links WHERE id=%s", (link_id,)).fetchone()
            if not row:
                print(f"Link id {link_id} not found")
                return 3
            url = row[0]

    msg = {
        "link_id": int(link_id),
        "url": str(url),
        "type": "job",
        "trace_id": f"jobs-single-{link_id}",
        "attempt": 1,
    }
    print(f"🕷️  Scraping single job: link_id={link_id}")
    result = scrape_job.run(msg)
    print(result)
    return 0 if result.get("ok") else 1


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Jobs Batch Runner")
    sub = parser.add_subparsers(dest="cmd")

    p_batch = sub.add_parser("run-batch", help="Process a batch of queued job links")
    p_batch.add_argument("--batch-size", type=int, default=5, help="Number of links to process")

    p_single = sub.add_parser("scrape-single", help="Scrape a single job by link_id or URL")
    p_single.add_argument("--link-id", type=int, help="Existing link_id in linkedin_links")
    p_single.add_argument("--url", type=str, help="LinkedIn job URL (creates link if missing)")

    args = parser.parse_args()
    if args.cmd == "run-batch":
        raise SystemExit(run_batch(args.batch_size))
    elif args.cmd == "scrape-single":
        raise SystemExit(run_single(args.link_id, args.url))
    else:
        parser.print_help()
        raise SystemExit(1)


if __name__ == "__main__":
    main()

