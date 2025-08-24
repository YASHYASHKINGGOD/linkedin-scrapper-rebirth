from __future__ import annotations
import psycopg

MIGRATE_SQL = """
-- 1) Add orchestration columns to linkedin_links (idempotent)
ALTER TABLE public.linkedin_links
  ADD COLUMN IF NOT EXISTS classification text CHECK (classification IN ('job','post','unknown')) DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS status text CHECK (status IN ('new','queued','scraping','scraped','staged','extracted','error','dead')) DEFAULT 'new',
  ADD COLUMN IF NOT EXISTS attempt_count int DEFAULT 0,
  ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS last_error text;

-- 2) Events table for idempotent audit of transitions
CREATE TABLE IF NOT EXISTS public.events (
  id BIGSERIAL PRIMARY KEY,
  kind text NOT NULL,
  link_id BIGINT NOT NULL REFERENCES public.linkedin_links(id) ON DELETE CASCADE,
  payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kind, link_id)
);
CREATE INDEX IF NOT EXISTS ix_events_link ON public.events(link_id, created_at DESC);
"""

CLASSIFY_SQL = """
WITH new_links AS (
  SELECT id, url, category
  FROM public.linkedin_links
  WHERE COALESCE(status,'new') = 'new'
)
-- emit link.new (idempotent)
INSERT INTO public.events(kind, link_id, payload)
SELECT 'link.new', nl.id, jsonb_build_object('url', l.url, 'sheet_name', l.sheet_name, 'tab', l.tab)
FROM new_links nl
JOIN public.linkedin_links l ON l.id = nl.id
ON CONFLICT (kind, link_id) DO NOTHING;

-- classify
UPDATE public.linkedin_links l
SET classification = CASE
                        WHEN l.category = 'jobs' THEN 'job'
                        WHEN l.category = 'posts' THEN 'post'
                        ELSE 'unknown'
                     END
WHERE COALESCE(l.status,'new') = 'new';

-- emit link.classified (idempotent)
WITH classified AS (
  SELECT id, classification, category
  FROM public.linkedin_links
  WHERE COALESCE(status,'new') = 'new'
)
INSERT INTO public.events(kind, link_id, payload)
SELECT 'link.classified', c.id, jsonb_build_object('classification', c.classification, 'category', c.category)
FROM classified c
ON CONFLICT (kind, link_id) DO NOTHING;

-- transition to queued
UPDATE public.linkedin_links
SET status='queued', attempt_count=0, next_attempt_at=now()
WHERE COALESCE(status,'new') = 'new';
"""


def migrate_and_classify(database_url: str) -> dict:
    with psycopg.connect(database_url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        with conn.transaction():
            conn.execute(MIGRATE_SQL)
            # Count pre
            pre_new = conn.execute("SELECT COUNT(*) FROM public.linkedin_links WHERE COALESCE(status,'new')='new'").fetchone()[0]
            conn.execute(CLASSIFY_SQL)
            post_queued = conn.execute("SELECT COUNT(*) FROM public.linkedin_links WHERE status='queued'").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM public.events").fetchone()[0]
        conn.commit()
    return {"new_classified": pre_new, "queued_total": post_queued, "events_total": events}
