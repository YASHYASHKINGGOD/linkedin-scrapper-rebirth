# Operating Manual — LinkedIn Posts Scraper

Prereqs
- make setup; python -m pip install -r requirements.txt (if present)
- python -m playwright install

Environment variables (local only)
- POSTS_SCRAPER_CONCURRENCY=1
- POSTS_SCRAPER_RATE_QPS=0.2
- POSTS_SCRAPER_OUT_DIR=./storage/scrape
- POSTS_OUTPUT_CSV=./storage/outputs/linkedin_posts/posts.csv
- POSTS_SESSION_DIR=<absolute path to your local user-data-dir>  # optional, recommended if you log in manually once
- LI_EMAIL={{LI_EMAIL}}
- LI_PASSWORD={{LI_PASSWORD}}

Run (single URL, headed)
- make posts.dev URL="https://www.linkedin.com/posts/..."

Run (batch first 5, headless)
- make posts.batch INPUT=./links.txt

Login strategies
- Preferred: user-data-dir session. Manually log in once (headed), then reuse session via POSTS_SESSION_DIR.
- Env login: provide LI_EMAIL and LI_PASSWORD via your shell (do not commit). The scraper will perform a cautious login flow once per context.

Anti-bot hygiene
- Concurrency=1; QPS≈0.2; jitter between actions.
- Human-like scroll; expand “See more”; cap 20 top-level comments.

Artifacts
- HTML: ./storage/scrape/<post_id>/raw.html
- Screenshot: ./storage/scrape/<post_id>/snapshot.png
- Images: ./storage/scrape/<post_id>/img_*.ext

Troubleshooting
- Stuck behind authwall: ensure session-dir contains a valid signed-in profile; otherwise export LI_EMAIL/LI_PASSWORD and retry.
- 429s: lower QPS, add sleep; retry later.
- Elements not found: run headed mode and enable --verbose to inspect selectors.

