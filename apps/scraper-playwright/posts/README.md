# README — LinkedIn Posts Scraper

Quickstart
1) Install browsers: `python -m playwright install`
2) Set env (local only):
   - export POSTS_OUTPUT_CSV=./storage/outputs/linkedin_posts/posts.csv
   - export POSTS_SCRAPER_OUT_DIR=./storage/scrape
   - export POSTS_SCRAPER_RATE_QPS=0.2
   - export POSTS_SCRAPER_CONCURRENCY=1
   - Optional login:
     - export POSTS_SESSION_DIR=/abs/path/to/linkedinsession  # preferred
     - or export LI_EMAIL={{LI_EMAIL}} && export LI_PASSWORD={{LI_PASSWORD}}
3) Single URL (headed):
   - make posts.dev URL="https://www.linkedin.com/posts/..."
4) Batch of 5 (headless):
   - echo "<url1>\n<url2>\n..." > links.txt
   - make posts.batch INPUT=./links.txt

CSV schema (one row per post)
- post_url
- poster_name
- post_text
- posted_at
- external_urls_json
- image_urls_json
- image_file_paths_json
- comments_json   # list of {commenter_name, comment_text, commented_at?}
- comment_count
- snapshot_paths_json  # {html_path, screenshot_path}
- scraped_at

Artifacts
- ./storage/scrape/<post_id>/: raw.html, snapshot.png, img_*.ext

