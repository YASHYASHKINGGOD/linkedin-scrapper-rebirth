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

from playwright.sync_api import Browser, Playwright, sync_playwright
import requests

# Env config with sensible defaults
POSTS_QPS = float(os.getenv("POSTS_SCRAPER_RATE_QPS", "0.2"))
POSTS_OUT_DIR = Path(os.getenv("POSTS_SCRAPER_OUT_DIR", "./storage/scrape")).resolve()
POSTS_CSV = Path(os.getenv("POSTS_OUTPUT_CSV", "./storage/outputs/linkedin_posts/posts.csv")).resolve()
SESSION_DIR = os.getenv("POSTS_SESSION_DIR", "").strip() or None
LI_EMAIL = os.getenv("LI_EMAIL", "").strip() or None
LI_PASSWORD = os.getenv("LI_PASSWORD", "").strip() or None

HEADERS_DL = {"Referer": "https://www.linkedin.com", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

VIEWPORTS = [(1366, 768), (1440, 900), (1536, 864)]
TIMEZONES = ["America/Los_Angeles", "America/New_York", "Europe/London", "Europe/Berlin"]

CSV_HEADERS = [
    "post_url",
    "poster_name",
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


def ensure_dirs():
    POSTS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_CSV.parent.mkdir(parents=True, exist_ok=True)


def rate_sleep(base_ms: Tuple[int, int] = (200, 800)):
    # Token bucket-ish: sleep at least 1/QPS between important actions
    min_gap = 1.0 / max(POSTS_QPS, 0.05)
    time.sleep(min_gap)
    time.sleep(random.uniform(base_ms[0] / 1000.0, base_ms[1] / 1000.0))


@dataclass
class ScrapeResult:
    ok: bool
    reason: str = ""


def csv_append_row(row: Dict[str, Any]):
    file_exists = POSTS_CSV.exists()
    with POSTS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)


def normalize_post_id(url: str) -> str:
    m = re.search(r"activity-(\d+)", url)
    if m:
        return m.group(1)
    return f"post_{int(time.time()*1000)}"


# --- Playwright helpers ---

def launch(playwright: Playwright, headed: bool) -> Browser:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
    ]
    return playwright.chromium.launch(headless=not headed, args=args, slow_mo=0)


def new_context(browser: Browser):
    ua = random.choice(UA_POOL)
    vp = random.choice(VIEWPORTS)
    tz = random.choice(TIMEZONES)

    kw = {
        "user_agent": ua,
        "locale": "en-US",
        "timezone_id": tz,
        "viewport": {"width": vp[0], "height": vp[1]},
    }
    if SESSION_DIR:
        # Use persistent context when session dir provided
        # Note: with persistent context we must create it from playwright.chromium.launch_persistent_context
        pass
    return browser.new_context(**kw)


def login_if_needed(page, email: Optional[str], password: Optional[str]) -> None:
    if not email or not password:
        return
    # If an authwall or sign-in required flow is visible, try logging in
    try:
        if page.locator("text=Sign in").first.is_visible() or page.url.startswith("https://www.linkedin.com/login"):
            page.goto("https://www.linkedin.com/login", timeout=45000)
            rate_sleep()
            page.fill("input#username", email)
            rate_sleep()
            page.fill("input#password", password)
            rate_sleep()
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle", timeout=45000)
            rate_sleep((500, 1200))
    except Exception:
        # Best-effort only
        pass


def dismiss_modals(page):
    # Common overlays
    selectors = [
        "button[aria-label=Close]",
        "button[aria-label=Dismiss]",
        "button:has-text('Maybe later')",
        "button:has-text('Not now')",
        "button:has-text('X')",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible():
                el.click()
                rate_sleep()
        except Exception:
            pass
    # Fallback: remove authwall via JS if it blocks clicks
    try:
        page.evaluate(
            """
            const blocks = Array.from(document.querySelectorAll('#authwall, .base-authwall, .sign-in-modal, .artdeco-modal__overlay'));
            blocks.forEach(n => n.remove());
            """
        )
    except Exception:
        pass


def expand_post(page):
    try:
        # Expand “see more” in post body
        btns = page.locator("button:has-text('see more'), button:has-text('See more')")
        if btns.count() > 0:
            btns.first.click()
            rate_sleep()
    except Exception:
        pass


def open_comments_and_collect(page, max_comments: int = 20) -> List[Dict[str, Any]]:
    comments: List[Dict[str, Any]] = []
    try:
        # Open comments if there is a button
        btn = page.locator("button:has-text('comments'), button:has-text('Comment'), a:has-text('comments')").first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass

    # Attempt to load more comments until cap
    for _ in range(15):  # cap attempts
        try:
            items = page.locator("article, li").filter(has_text=re.compile("\n"))  # broad sweep
            # This is heuristic. For reliability, we may focus on known comment container classes
        except Exception:
            break
        if len(comments) >= max_comments:
            break
        # Try clicking a generic "load more" comments
        try:
            more = page.locator("button:has-text('Load more'), button:has-text('more comments')").first
            if more.is_visible():
                more.click()
                rate_sleep()
        except Exception:
            pass
        # Collect visible comment blocks by common selectors
        try:
            blocks = page.locator(".comments-comment-item, .feed-shared-comments-list__comment-item, [data-test-reply-parent-urn]")
            count = blocks.count()
            for i in range(count):
                if len(comments) >= max_comments:
                    break
                b = blocks.nth(i)
                try:
                    name = b.locator("a[href*='/in/']").first.inner_text(timeout=2000).strip()
                except Exception:
                    name = ""
                try:
                    # Get comment text and expand if needed
                    see_more = b.locator("button:has-text('See more')").first
                    if see_more.is_visible():
                        see_more.click()
                        rate_sleep()
                except Exception:
                    pass
                try:
                    text = b.locator("span[dir='ltr'], div[dir='ltr'], p").first.inner_text(timeout=2000).strip()
                except Exception:
                    text = ""
                try:
                    ts = b.locator("time").first.inner_text(timeout=1000).strip()
                except Exception:
                    ts = ""
                if name or text:
                    comments.append({"commenter_name": name, "comment_text": text, "commented_at": ts})
            if count == 0:
                break
        except Exception:
            break
    return comments[:max_comments]


def extract_post_fields(page) -> Tuple[str, str, str, str, List[str], List[str]]:
    post_url = page.url
    poster_name = ""
    post_text = ""
    posted_at = ""
    external_urls: List[str] = []
    image_urls: List[str] = []

    # Poster name
    try:
        poster_name = page.locator("header a[href*='/in/'], .feed-shared-actor__container a[href*='/in/']").first.inner_text(timeout=5000).strip()
    except Exception:
        pass

    # Expand body then read
    expand_post(page)
    try:
        post_text = page.locator("div[dir='ltr'], span[dir='ltr'], p").first.inner_text(timeout=6000).strip()
    except Exception:
        pass

    try:
        posted_at = page.locator("time").first.inner_text(timeout=4000).strip()
    except Exception:
        pass

    # External URLs: anchors not linkedin domains
    try:
        anchors = page.locator("a").all()
        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                if "linkedin.com" in href or "lnkd.in" in href:
                    continue
                if href.startswith("javascript:"):
                    continue
                external_urls.append(href)
            except Exception:
                continue
    except Exception:
        pass
    external_urls = sorted(list({u for u in external_urls}))

    # Images
    try:
        imgs = page.locator("img").all()
        for im in imgs:
            try:
                src = im.get_attribute("src") or im.get_attribute("data-delayed-url") or ""
                if src and src.startswith("http"):
                    image_urls.append(src)
            except Exception:
                continue
    except Exception:
        pass
    image_urls = sorted(list({u for u in image_urls}))

    return post_url, poster_name, post_text, posted_at, external_urls, image_urls


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
            else:
                continue
            rate_sleep((50, 150))
        except Exception:
            continue
    return files


def scrape_one(playwright: Playwright, url: str, headed: bool) -> ScrapeResult:
    ensure_dirs()
    t0 = time.time()
    browser = launch(playwright, headed=headed)

    # Persistent session if provided
    context = None
    page = None
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_navigation_timeout(45000)
        page.set_default_timeout(8000)

        # Navigate and attempt login/modal handling
        page.goto(url, timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        dismiss_modals(page)
        rate_sleep()
        login_if_needed(page, LI_EMAIL, LI_PASSWORD)
        dismiss_modals(page)
        rate_sleep()

        # Heuristic: if content area still obscured, try reloading once
        try:
            main_sel = "article, main, div[data-urn*='urn:li:activity']"
            if not page.locator(main_sel).first.is_visible():
                page.reload()
                page.wait_for_load_state("domcontentloaded")
                dismiss_modals(page)
                rate_sleep()
        except Exception:
            pass

        # Scroll to load content and comments
        for _ in range(4):
            page.mouse.wheel(0, random.randint(400, 900))
            rate_sleep()
        for _ in range(2):
            page.mouse.wheel(0, -random.randint(200, 500))
            rate_sleep()

        post_url, poster_name, post_text, posted_at, external_urls, image_urls = extract_post_fields(page)
        comments = open_comments_and_collect(page, max_comments=20)

        # Artifacts
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
            "post_text": post_text,
            "posted_at": posted_at,
            "external_urls_json": json.dumps(external_urls, ensure_ascii=False),
            "image_urls_json": json.dumps(image_urls, ensure_ascii=False),
            "image_file_paths_json": json.dumps(image_files, ensure_ascii=False),
            "comments_json": json.dumps(comments, ensure_ascii=False),
            "comment_count": len(comments),
            "snapshot_paths_json": json.dumps({"html_path": str(html_path), "screenshot_path": str(png_path)}, ensure_ascii=False),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        csv_append_row(row)

        dt = int((time.time() - t0) * 1000)
        print(f"Scraped OK: {post_url} in {dt} ms; images={len(image_files)} comments={len(comments)}")
        return ScrapeResult(ok=True)
    except Exception as e:
        print(f"ERROR scraping {url}: {e}", file=sys.stderr)
        return ScrapeResult(ok=False, reason=str(e))
    finally:
        try:
            if page:
                page.close()
        except Exception:
            pass
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


# --- CLI ---

def cmd_single(args):
    url: str = args.url
    headed: bool = args.headed
    with sync_playwright() as p:
        res = scrape_one(p, url, headed=headed)
    sys.exit(0 if res.ok else 1)


def cmd_batch(args):
    limit = int(args.limit)
    headed = bool(args.headed)
    with open(args.input, "r", encoding="utf-8") as f:
        urls = [ln.strip() for ln in f if ln.strip()]
    urls = urls[:limit]
    if not urls:
        print("No URLs to process", file=sys.stderr)
        sys.exit(1)

    ok_any = False
    with sync_playwright() as p:
        for u in urls:
            res = scrape_one(p, u, headed=headed)
            ok_any = ok_any or res.ok
            time.sleep(random.uniform(2.0, 5.0))
    sys.exit(0 if ok_any else 1)


def main():
    ap = argparse.ArgumentParser(description="LinkedIn Posts Scraper (Playwright)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    s1 = sp.add_parser("single", help="Scrape a single post URL")
    s1.add_argument("--url", required=True)
    s1.add_argument("--headed", action="store_true")
    s1.set_defaults(func=cmd_single)

    s2 = sp.add_parser("batch", help="Scrape first N post URLs from a file")
    s2.add_argument("--input", required=True)
    s2.add_argument("--limit", default="5")
    s2.add_argument("--headed", action="store_true")
    s2.set_defaults(func=cmd_batch)

    args = ap.parse_args()
    main_env_warning()
    args.func(args)


def main_env_warning():
    # Never echo secrets; only warn if not set and session_dir not provided
    if not SESSION_DIR and not (LI_EMAIL and LI_PASSWORD):
        print("Note: no session_dir or credentials provided. If authwall blocks content, export LI_EMAIL and LI_PASSWORD or set POSTS_SESSION_DIR.")


if __name__ == "__main__":
    main()

