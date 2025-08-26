#!/usr/bin/env python3
import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Playwright, sync_playwright
import requests

# --- Config ---
POSTS_QPS = float(os.getenv("POSTS_SCRAPER_RATE_QPS", "0.5"))
POSTS_OUT_DIR = Path(os.getenv("POSTS_SCRAPER_OUT_DIR", "./storage/scrape_v2")).resolve()
POSTS_CSV = Path(os.getenv("POSTS_OUTPUT_CSV", "./storage/outputs/linkedin_posts/posts_v2.csv")).resolve()
SESSION_DIR = os.getenv("POSTS_SESSION_DIR", "").strip() or None

CSV_HEADERS = [
    "post_url",
    "poster_name",
    "author_title",
    "post_text",
    "posted_at",
    "external_urls_json",
    "image_urls_json",
    "image_file_paths_json",
    "comments_json",
    "comment_count",
    "snapshot_paths_json",
    "scraped_at",
]

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
VIEWPORTS = [(1366, 768), (1440, 900), (1536, 864)]
TIMEZONES = ["America/Los_Angeles", "America/New_York", "Europe/London", "Europe/Berlin"]

HEADERS_DL = {"Referer": "https://www.linkedin.com", "User-Agent": UA_POOL[0]}

# --- Helpers ---

def ensure_dirs():
    POSTS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_CSV.parent.mkdir(parents=True, exist_ok=True)


def rate_sleep(base_ms: Tuple[int, int] = (200, 600)):
    min_gap = 1.0 / max(POSTS_QPS, 0.1)
    time.sleep(min_gap)
    time.sleep(random.uniform(base_ms[0]/1000.0, base_ms[1]/1000.0))


def normalize_post_id(url: str) -> str:
    m = re.search(r"activity-(\d+)", url)
    if m:
        return m.group(1)
    m2 = re.search(r"urn:li:activity:(\d+)", url)
    if m2:
        return m2.group(1)
    return f"post_{int(time.time()*1000)}"


def canonicalize_post_url(url: str) -> str:
    m = re.search(r"activity-(\d+)", url) or re.search(r"urn:li:activity:(\d+)", url)
    if m:
        act = m.group(1)
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{act}/"
    return url


def csv_append_row(row: Dict[str, Any]):
    file_exists = POSTS_CSV.exists()
    with POSTS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)

# --- UI helpers ---

def dismiss_light_overlays(page):
    selectors = [
        "button[aria-label=Close]",
        "button[aria-label=Dismiss]",
        "button:has-text('Not now')",
        "button:has-text('Maybe later')",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el and el.is_visible():
                el.click()
                rate_sleep()
        except Exception:
            pass


def try_open_login_from_modal(page) -> bool:
    try:
        dlg = page.locator("div[role='dialog']").filter(has_text="Sign in").first
        if dlg and dlg.is_visible():
            variants = [
                "button.sign-in-modal__outlet-btn",
                "button[data-tracking-control-name='public_post_contextual-sign-in-modal_sign-in-modal_outlet-button']",
                "button[data-modal*='sign-in-modal']",
                "button[data-tracking-control-name*='outlet-button']",
                "button:has-text('Sign in')",
                "a:has-text('Sign in')",
            ]
            for sel in variants:
                try:
                    btn = dlg.locator(sel).first
                    if btn and btn.is_visible():
                        btn.scroll_into_view_if_needed(timeout=3000)
                        btn.click()
                        page.wait_for_load_state("domcontentloaded", timeout=45000)
                        rate_sleep()
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def expand_within(node):
    try:
        btns = node.locator("button:has-text('See more'), button:has-text('see more')")
        if btns.count() > 0:
            btns.first.click()
            rate_sleep()
    except Exception:
        pass


def extract_post_fields(page, container):
    poster_name = ""
    author_title = ""
    post_text = ""
    posted_at = ""
    external_urls: List[str] = []
    image_urls: List[str] = []

    try:
        poster_name = container.locator(
            ".update-components-actor__title span[aria-hidden='true']"
        ).first.inner_text(timeout=6000).strip()
    except Exception:
        try:
            poster_name = container.locator(".update-components-actor__title").first.inner_text(timeout=6000).strip()
        except Exception:
            pass
    try:
        author_title = container.locator(".update-components-actor__description").first.inner_text(timeout=5000).strip()
    except Exception:
        pass

    expand_within(container)
    try:
        post_text = container.locator("div.update-components-text").first.inner_text(timeout=7000).strip()
    except Exception:
        try:
            post_text = container.locator("div[dir='ltr'], span[dir='ltr']").first.inner_text(timeout=6000).strip()
        except Exception:
            pass

    try:
        ts_full = container.locator(".update-components-actor__sub-description").first.inner_text(timeout=4000).strip()
        posted_at = ts_full.split("•")[0].strip()
    except Exception:
        try:
            posted_at = container.locator("time").first.inner_text(timeout=4000).strip()
        except Exception:
            pass

    try:
        for a in container.locator("a").all():
            try:
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                if href.startswith("javascript:"):
                    continue
                if ("linkedin.com" in href or "lnkd.in" in href) and not href.startswith("mailto:"):
                    continue
                external_urls.append(href)
            except Exception:
                continue
    except Exception:
        pass
    external_urls = sorted(list(set(external_urls)))

    try:
        for im in container.locator("img").all():
            try:
                src = im.get_attribute("src") or im.get_attribute("data-delayed-url") or ""
                if src and src.startswith("http"):
                    image_urls.append(src)
            except Exception:
                continue
    except Exception:
        pass
    image_urls = sorted(list(set(image_urls)))

    return page.url, poster_name, author_title, post_text, posted_at, external_urls, image_urls


def download_images(image_urls: List[str], dest_dir: Path) -> List[str]:
    files: List[str] = []
    for idx, url in enumerate(image_urls, start=1):
        try:
            ext = ".jpg"
            m = re.search(r"\.([a-zA-Z0-9]{2,4})(?:$|\?)", url)
            if m:
                ext = f".{m.group(1)}"
            fp = dest_dir / f"img_{idx}{ext}"
            r = requests.get(url, headers=HEADERS_DL, timeout=20)
            if r.status_code == 200:
                fp.write_bytes(r.content)
                files.append(str(fp))
            rate_sleep((60, 140))
        except Exception:
            continue
    return files

# --- Core ---

def launch_persistent(playwright: Playwright, headed: bool):
    if not SESSION_DIR:
        raise SystemExit("POSTS_SESSION_DIR is required for scraper_v2 (persistent context). Set env and retry.")
    Path(SESSION_DIR).mkdir(parents=True, exist_ok=True)
    ua = random.choice(UA_POOL)
    vp = random.choice(VIEWPORTS)
    tz = random.choice(TIMEZONES)

    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--password-store=basic",
        "--use-mock-keychain",
    ]
    return playwright.chromium.launch_persistent_context(
        SESSION_DIR,
        headless=not headed,
        args=args,
        user_agent=ua,
        locale="en-US",
        timezone_id=tz,
        viewport={"width": vp[0], "height": vp[1]},
    )


def process_url(page, url: str):
    ensure_dirs()
    target = canonicalize_post_url(url)

    # Navigate with minimal interference — keep auth dialogs intact
    page.goto(target, timeout=45000)
    page.wait_for_load_state("domcontentloaded", timeout=45000)
    rate_sleep()

    # If a sign-in modal is present, click-through to login page (so user can auth once per session)
    try_open_login_from_modal(page)

    # Light overlays only (keep authwall if any so user can log in when headed)
    dismiss_light_overlays(page)

    # Heuristic to find main post container
    activity_id = normalize_post_id(target)
    container = None
    try:
        container = page.locator(f"[data-urn*='urn:li:activity:{activity_id}']").first
        if not container or not container.is_visible():
            container = None
    except Exception:
        container = None
    if container is None:
        try:
            container = page.locator("div.feed-shared-update-v2:has(div.update-components-text)").first
        except Exception:
            container = page

    # Gentle scroll to load content/comments
    for _ in range(3):
        page.mouse.wheel(0, random.randint(350, 850))
        rate_sleep()

    post_url, poster_name, author_title, post_text, posted_at, external_urls, image_urls = extract_post_fields(page, container)

    # Save artifacts
    post_id = normalize_post_id(post_url)
    dest = POSTS_OUT_DIR / post_id
    dest.mkdir(parents=True, exist_ok=True)
    html_path = dest / "raw.html"
    png_path = dest / "snapshot.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path), full_page=True)
    image_files = download_images(image_urls, dest)

    row = {
        "post_url": post_url,
        "poster_name": poster_name,
        "author_title": author_title,
        "post_text": post_text,
        "posted_at": posted_at,
        "external_urls_json": json.dumps(external_urls, ensure_ascii=False),
        "image_urls_json": json.dumps(image_urls, ensure_ascii=False),
        "image_file_paths_json": json.dumps(image_files, ensure_ascii=False),
        "comments_json": json.dumps([], ensure_ascii=False),  # v2: focus on stable context first
        "comment_count": 0,
        "snapshot_paths_json": json.dumps({"html_path": str(html_path), "screenshot_path": str(png_path)}, ensure_ascii=False),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    csv_append_row(row)

# --- CLI ---

def cmd_single(args):
    headed: bool = bool(args.headed)
    url: str = args.url
    with sync_playwright() as p:
        ctx = launch_persistent(p, headed=headed)
        page = ctx.new_page()
        page.set_default_navigation_timeout(45000)
        page.set_default_timeout(8000)
        try:
            process_url(page, url)
        finally:
            try:
                page.close()
            except Exception:
                pass
            # Do not delete the persistent session; just close context
            try:
                ctx.close()
            except Exception:
                pass


def cmd_batch(args):
    headed: bool = bool(args.headed)
    limit = int(args.limit)
    with open(args.input, "r", encoding="utf-8") as f:
        urls = [ln.strip() for ln in f if ln.strip()]
    urls = urls[:limit]
    if not urls:
        print("No URLs to process", file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        ctx = launch_persistent(p, headed=headed)
        page = ctx.new_page()
        page.set_default_navigation_timeout(45000)
        page.set_default_timeout(8000)
        try:
            for u in urls:
                process_url(page, u)
                time.sleep(random.uniform(1.5, 3.0))
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                ctx.close()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="LinkedIn Posts Scraper v2 (persistent session)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    s1 = sp.add_parser("single", help="Scrape a single post URL (requires POSTS_SESSION_DIR)")
    s1.add_argument("--url", required=True)
    s1.add_argument("--headed", action="store_true")
    s1.set_defaults(func=cmd_single)

    s2 = sp.add_parser("batch", help="Scrape first N post URLs from a file (requires POSTS_SESSION_DIR)")
    s2.add_argument("--input", required=True)
    s2.add_argument("--limit", default="5")
    s2.add_argument("--headed", action="store_true")
    s2.set_defaults(func=cmd_batch)

    args = ap.parse_args()
    if not SESSION_DIR:
        print("Error: POSTS_SESSION_DIR is required. Example: POSTS_SESSION_DIR=$HOME/.cache/linkedin-session", file=sys.stderr)
        sys.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()

