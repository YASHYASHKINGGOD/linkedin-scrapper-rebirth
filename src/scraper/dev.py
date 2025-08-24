from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager
from typing import Optional
import random

from playwright.sync_api import sync_playwright

OUT_DIR = os.environ.get("SCRAPER_OUT_DIR", "./storage/scrape")
HEADLESS_DEFAULT = os.environ.get("SCRAPER_HEADLESS", "true").lower() == "true"
RATE_QPS = float(os.environ.get("SCRAPER_RATE_QPS", "0.2"))  # ~1 req / 5s by default

_last_req_ts: float = 0.0


def _rate_limit_sleep():
    global _last_req_ts
    if RATE_QPS <= 0:
        return
    min_interval = 1.0 / RATE_QPS
    now = time.monotonic()
    elapsed = now - _last_req_ts
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_req_ts = time.monotonic()


def ensure_dirs(ts: str) -> tuple[str, str]:
    html_dir = os.path.join(OUT_DIR, "html", ts)
    shot_dir = os.path.join(OUT_DIR, "shots", ts)
    os.makedirs(html_dir, exist_ok=True)
    os.makedirs(shot_dir, exist_ok=True)
    return html_dir, shot_dir


def save_artifacts(html: str, html_path: str, png_path: str) -> None:
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def _txt(page, selector: str) -> str:
    el = page.query_selector(selector)
    return el.inner_text().strip() if el else ""


def _first_text(page, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                txt = el.inner_text().strip()
                if txt:
                    return txt
        except Exception:
            continue
    return ""


def _desc_text(page) -> str:
    # Try the rich description container first
    el = page.query_selector(".description__text .show-more-less-html__markup")
    if not el:
        el = page.query_selector(".description__text")
    return el.inner_text().strip() if el else ""


def _parse_sections(desc: str) -> tuple[list[str], list[str]]:
    # Naive split based on headings in provided HTML: "Key Responsibilities:" and "Requirements:"
    lower = desc
    resp: list[str] = []
    reqs: list[str] = []
    try:
        if "Key Responsibilities:" in desc and "Requirements:" in desc:
            a, b = desc.split("Key Responsibilities:", 1)
            resp_block, rest = b.split("Requirements:", 1)
            # Split bullet-ish lines
            resp = [line.strip("•- \t\n").strip() for line in resp_block.splitlines() if line.strip()]
            reqs = [line.strip("•- \t\n").strip() for line in rest.splitlines() if line.strip()]
    except Exception:
        pass
    return resp, reqs


def scrape_single_job(url: str, headed: bool = False) -> dict:
    ts = time.strftime("%Y%m%d")
    html_dir, shot_dir = ensure_dirs(ts)
    headless = not headed if HEADLESS_DEFAULT else headed is False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # Slightly vary viewport to reduce fingerprints
        vw = random.randint(1280, 1440)
        vh = random.randint(800, 950)
        context = browser.new_context(
            user_agent=os.environ.get(
                "SCRAPER_USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
            ),
            viewport={"width": vw, "height": vh},
            locale="en-US",
            timezone_id="UTC",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = context.new_page()
        # global token-bucket rate limit + small jitter before navigating
        _rate_limit_sleep()
        time.sleep(random.uniform(0.8, 1.6))
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        # human-like waiting and scroll
        page.wait_for_timeout(int(random.uniform(1500, 3000)))
        for _ in range(random.randint(2, 4)):
            page.mouse.wheel(0, random.randint(600, 1000))
            page.wait_for_timeout(int(random.uniform(400, 900)))

        # Try to expand description if collapsed
        try:
            btn = page.query_selector(".show-more-less-html__button--more")
            if btn:
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Extract core fields against provided classes/selectors with robust fallbacks
        role = _first_text(page, [
            "h1.top-card-layout__title",
            "h1.topcard__title",
            ".topcard__title",
            ".sub-nav-cta__header",
            "section.top-card-layout h1",
        ])
        if not role:
            # fall back to document title heuristic
            try:
                t = page.title().strip()
                # common patterns: "<role> - <Company> - LinkedIn" or "<role> | LinkedIn"
                for sep in [" - ", " | ", " • "]:
                    if sep in t:
                        role = t.split(sep)[0].strip()
                        break
            except Exception:
                pass

        company = _first_text(page, [
            "a.topcard__org-name-link",
            ".sub-nav-cta__optional-url",
            ".top-card-layout__second-subline a",
        ])
        location = _txt(page, ".topcard__flavor-row .topcard__flavor--bullet") or _txt(page, ".sub-nav-cta__meta-text")
        posted = _txt(page, ".posted-time-ago__text")
        # Job status (e.g., No longer accepting applications)
        status = _txt(page, "figure.closed-job .closed-job__flavor--closed")
        desc_text = _desc_text(page)
        key_resp, requirements = _parse_sections(desc_text)

        html = page.content()
        link_id = int(time.time())  # placeholder until DB wiring; return path only
        html_path = os.path.join(html_dir, f"{link_id}.html")
        png_path = os.path.join(shot_dir, f"{link_id}.png")
        save_artifacts(html, html_path, png_path)
        page.screenshot(path=png_path, full_page=True)
        context.close()
        browser.close()
        return {
            "ok": True,
            "url": url,
            "role_title": role,
            "company_name": company,
            "location": location,
            "posted_time": posted,
            "description_text": desc_text,
            "key_responsibilities": key_resp,
            "requirements": requirements,
            "status": status,
            "html_path": html_path,
            "screenshot_path": png_path,
        }

