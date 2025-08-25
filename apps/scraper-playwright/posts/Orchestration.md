# Orchestration — LinkedIn Posts Scraper (Playwright)

Scope (M1/M2)
- No queue integration yet; direct CLI for single URL and batch-of-5.
- Authenticated session supported via env; still respect strict rate limits.

State machine (per URL)
- pending → navigating → extracting → artifacts_saved → succeeded | failed
- On error: backoff (2s, 6s, 18s) then fail for that URL; continue batch.

Rate limiting & hygiene
- Concurrency=1; QPS≈0.2 with jitter.
- Human-like scroll; expand “See more”; load max 20 top-level comments.

Outputs
- CSV (single file): post_url, poster_name, post_text, posted_at, external_urls_json, image_urls_json, image_file_paths_json, comments_json, comment_count, snapshot_paths_json, scraped_at.
- Artifacts: ./storage/scrape/<post_id>/{raw.html,snapshot.png,img_*.ext}

Future (M3+)
- Consume scrape.post queue; transition queued → scraping → scraped.
- Upsert to linkedin_posts_raw (raw_json + artifact paths).
