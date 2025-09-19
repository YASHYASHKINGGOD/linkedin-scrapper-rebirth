from __future__ import annotations
import os
import psycopg
from celery import Celery

BROKER = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
app = Celery("router", broker=BROKER)

SQL_CANDIDATES = """
WITH cand AS (
  SELECT l.id, l.url, COALESCE(l.classification,'unknown') AS classification
  FROM public.linkedin_links l
  LEFT JOIN public.events e
    ON e.link_id = l.id AND e.kind = 'link.routed'
  WHERE e.id IS NULL
    AND COALESCE(l.status,'new') = 'queued'
    AND COALESCE(l.classification,'unknown') IN ('job','post')
    AND now() >= COALESCE(l.next_attempt_at, now())
  ORDER BY l.id
  LIMIT 100
),
mark AS (
  INSERT INTO public.events(kind, link_id, payload)
  SELECT 'link.routed', c.id, jsonb_build_object('url', (SELECT url FROM public.linkedin_links WHERE id=c.id), 'classification', c.classification)
  FROM cand c
  ON CONFLICT (kind, link_id) DO NOTHING
  RETURNING link_id
)
SELECT l.id, l.url, COALESCE(l.classification,'unknown') AS classification
FROM public.linkedin_links l
JOIN mark m ON m.link_id = l.id;
"""


def route_new_links() -> dict:
    db = os.environ.get("DATABASE_URL", "")
    if not db:
        return {"ok": False, "error": "DATABASE_URL is required"}
    routed = 0
    with psycopg.connect(db) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        rows = conn.execute(SQL_CANDIDATES).fetchall()
        for link_id, url, classification in rows:
            task = "src.scraper.tasks.scrape_job" if classification == "job" else "src.scraper.tasks.scrape_post"
            queue = "scrape.job" if classification == "job" else "scrape.post"
            app.send_task(task, args=[{"link_id": link_id, "url": url, "attempt": 1}], queue=queue)
            routed += 1
    return {"ok": True, "routed": routed}

if __name__ == "__main__":
    import json
    print(json.dumps(route_new_links(), indent=2))
