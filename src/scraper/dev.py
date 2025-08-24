from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from playwright.sync_api import sync_playwright

OUT_DIR = os.environ.get("SCRAPER_OUT_DIR", "./storage/scrape")
HEADLESS_DEFAULT = os.environ.get("SCRAPER_HEADLESS", "true").lower() == "true"


def ensure_dirs(ts: str) -> tuple[str, str]:
    html_dir = os.path.join(OUT_DIR, "html", ts)
    shot_dir = os.path.join(OUT_DIR, "shots", ts)
    os.makedirs(html_dir, exist_ok=True)
    os.makedirs(shot_dir, exist_ok=True)
    return html_dir, shot_dir


def save_artifacts(html: str, html_path: str, png_path: str) -> None:
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def scrape_single_job(url: str, headed: bool = False) -> dict:
    ts = time.strftime("%Y%m%d")
    html_dir, shot_dir = ensure_dirs(ts)
    headless = not headed if HEADLESS_DEFAULT else headed is False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=os.environ.get("SCRAPER_USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        # polite delay to allow dynamic content
        page.wait_for_timeout(2000)
        html = page.content()
        link_id = int(time.time())  # placeholder until DB wiring; return path only
        html_path = os.path.join(html_dir, f"{link_id}.html")
        png_path = os.path.join(shot_dir, f"{link_id}.png")
        save_artifacts(html, html_path, png_path)
        page.screenshot(path=png_path, full_page=True)
        context.close()
        browser.close()
        return {"ok": True, "url": url, "html_path": html_path, "screenshot_path": png_path}

