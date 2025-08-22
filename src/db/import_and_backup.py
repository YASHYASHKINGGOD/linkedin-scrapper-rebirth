from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional
import psycopg

SQL_MIGRATE = """
-- Ensure url is TEXT and url_canonical (lower(url)) exists with unique index
DO $$
BEGIN
  -- Drop dependent generated column if present to allow type change
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='linkedin_links' AND column_name='url_canonical'
  ) THEN
    -- drop index if exists first
    IF EXISTS (
      SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_linkedin_links_canonical'
    ) THEN
      EXECUTE 'DROP INDEX IF EXISTS ux_linkedin_links_canonical';
    END IF;
    ALTER TABLE public.linkedin_links DROP COLUMN url_canonical;
  END IF;
  -- Alter url type to TEXT (no-op if already TEXT)
  ALTER TABLE public.linkedin_links ALTER COLUMN url TYPE text;
  -- Recreate generated column
  ALTER TABLE public.linkedin_links
    ADD COLUMN IF NOT EXISTS url_canonical text GENERATED ALWAYS AS (lower(url)) STORED;
END$$;
-- Recreate unique index safely
CREATE UNIQUE INDEX IF NOT EXISTS ux_linkedin_links_canonical ON public.linkedin_links (url_canonical);
-- Additional supportive columns (idempotent)
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS sheet_name text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS tab text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS row_number int;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS date_in_source text;
ALTER TABLE public.linkedin_links ADD COLUMN IF NOT EXISTS extracted_at timestamptz DEFAULT now();
"""

SQL_CREATE_PROVENANCE = """
CREATE TABLE IF NOT EXISTS public.link_provenance (
  id BIGSERIAL PRIMARY KEY,
  link_url TEXT NOT NULL REFERENCES public.linkedin_links(url) ON DELETE CASCADE,
  sheet_name TEXT,
  tab TEXT,
  row_number INT,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_link_provenance_url ON public.link_provenance(link_url);
"""


def import_and_backup(
    database_url: str,
    csv_path: str,
    backup_dir: str = "./storage/backups",
    insert_window_minutes: int = 10,
    create_provenance: bool = True,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"links_inserted_{ts}.csv")
    with psycopg.connect(database_url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        with conn.transaction():
            conn.execute(SQL_MIGRATE)
            if create_provenance:
                conn.execute(SQL_CREATE_PROVENANCE)
            # staging load
            conn.execute("DROP TABLE IF EXISTS tmp_links")
            conn.execute(
                """
                CREATE TEMP TABLE tmp_links (
                  date text, company text, role text, location text, url text, sheet_name text, tab_title text, row_number int
                )
                """
            )
            with conn.cursor() as cur:
                with open(csv_path, "r", encoding="utf-8") as f:
                    cur.copy(
                        "COPY tmp_links (date,company,role,location,url,sheet_name,tab_title,row_number) FROM STDIN WITH (FORMAT csv, HEADER true)",
                        f,
                    )
            # upsert
            conn.execute(
                """
                INSERT INTO public.linkedin_links (url, sheet_name, row_number, extracted_at, source, tab, date_in_source, category)
                SELECT url, sheet_name, row_number, now(), CONCAT('google_sheet:',COALESCE(sheet_name,'')), tab_title, date,
                       CASE WHEN url LIKE 'https://www.linkedin.com/posts%' THEN 'posts'
                            WHEN url LIKE 'https://www.linkedin.com/jobs%'  THEN 'jobs'
                            WHEN url LIKE 'https://www.linkedin.com/%'      THEN 'other'
                            ELSE 'external' END
                FROM tmp_links t
                ON CONFLICT (url_canonical) DO UPDATE
                  SET sheet_name=EXCLUDED.sheet_name,
                      row_number=EXCLUDED.row_number,
                      extracted_at=now(),
                      source=EXCLUDED.source,
                      tab=EXCLUDED.tab,
                      date_in_source=EXCLUDED.date_in_source,
                      category=EXCLUDED.category
                """
            )
            # provenance: write one row per staging record (idempotent via unique not enforced here)
            if create_provenance:
                conn.execute(
                    """
                    INSERT INTO public.link_provenance (link_url, sheet_name, tab, row_number, discovered_at)
                    SELECT t.url, t.sheet_name, t.tab_title, t.row_number, now()
                    FROM tmp_links t
                    ON CONFLICT DO NOTHING
                    """
                )
            # backup: rows touched recently
            with conn.cursor() as cur:
                # psycopg3 doesn't parameterize interval expression easily; inline minutes safely as integer
                minutes = int(insert_window_minutes)
                with open(backup_path, "w", encoding="utf-8") as out:
                    cur.copy(
                        f"""
                        COPY (
                          SELECT id,url,sheet_name,row_number,extracted_at,source,tab,date_in_source,category
                          FROM public.linkedin_links
                          WHERE extracted_at > now() - interval '{minutes} minutes'
                          ORDER BY id
                        ) TO STDOUT WITH (FORMAT csv, HEADER true)
                        """,
                        out,
                    )
        conn.commit()
    return backup_path
