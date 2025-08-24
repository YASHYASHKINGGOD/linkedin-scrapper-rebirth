#!/usr/bin/env python3
"""
notion_table_scraper_cssaware.py

Virtualized Notion TABLE view scraper using CSS hooks.
- Scrolls the *internal* table container by manipulating scrollTop.
- Aggregates rows across viewports by their stable data-block-id to bypass virtualization.
- Extracts headers and maps cell text/links to those headers.

Usage:
  pip install playwright bs4
  python -m playwright install

  python notion_table_scraper_cssaware.py "NOTION_TABLE_URL" \
      --out foc_full.csv --json foc_full.json
"""

import asyncio
import csv
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

from playwright.async_api import async_playwright, Page, Locator
from bs4 import BeautifulSoup


def textify(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


async def get_scrollable_container(page: Page) -> Locator:
    # Try known Notion scrollable containers first
    containers = [
        ".notion-scroller",
        ".notion-collection-view-body",
        ".notion-table-view",
        "body"
    ]
    
    for selector in containers:
        container = page.locator(selector).first
        if await container.count() > 0:
            try:
                is_scrollable = await container.evaluate("""el => {
                    const style = getComputedStyle(el);
                    return ['auto','scroll','overlay'].includes(style.overflowY) && el.scrollHeight > el.clientHeight;
                }""")
                if is_scrollable:
                    return container
            except:
                continue
    
    # Fallback to body
    return page.locator("body")


async def extract_headers(page: Page) -> List[str]:
    header_cells = page.locator(".notion-table-view-header-cell")
    n = await header_cells.count()
    headers = []
    for i in range(n):
        txt = textify(await header_cells.nth(i).inner_text())
        headers.append(txt or f"col_{i+1}")
    return headers


async def extract_visible_rows(page: Page, headers: List[str]) -> Dict[str, Dict[str, Any]]:
    # Return mapping: row_id -> record
    rows = page.locator(".notion-collection-item")
    out: Dict[str, Dict[str, Any]] = {}
    count = await rows.count()
    for i in range(count):
        r = rows.nth(i)
        row_id = await r.get_attribute("data-block-id") or f"row_{i}"
        record: Dict[str, Any] = {"__row_id": row_id}

        cells = r.locator(".notion-table-view-cell")
        ccount = await cells.count()
        for c in range(ccount):
            cell = cells.nth(c)
            idx_attr = await cell.get_attribute("data-col-index")
            try:
                idx = int(idx_attr) if idx_attr is not None else c
            except:
                idx = c
            header = headers[idx] if idx < len(headers) else f"col_{idx+1}"
            html = await cell.inner_html()
            txt = textify(BeautifulSoup(html, "html.parser").get_text(" "))

            # collect links (esp. LinkedIn)
            anchors = await cell.locator("a[href]").all()
            links: List[str] = []
            for a in anchors:
                href = await a.get_attribute("href")
                if href:
                    links.append(href)

            record[header] = txt
            if links:
                record[f"{header}__links"] = ", ".join(sorted(set(links)))
                li = next((l for l in links if "linkedin.com" in l.lower()), "")
                if li:
                    record[f"{header}__linkedin"] = li

        out[row_id] = record
    return out


async def scroll_to_bottom_collect(page: Page, container: Locator, headers: List[str],
                                   max_steps: int = 400, settle: int = 8):
    """
    Scrolls the container in chunks until bottom is reached (scrollTop stops increasing)
    while collecting rows per viewport. Uses a 'settle' counter to verify we've reached
    bottom (no change in scrollTop & no new rows) across multiple checks.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    prev_top = -1
    stale = 0

    try:
        await page.evaluate("document.body.style.zoom='0.9'")
    except:
        pass

    for step in range(max_steps):
        batch = await extract_visible_rows(page, headers)
        before = len(seen)
        seen.update(batch)

        try:
            el = await container.element_handle()
            top, sh, ch = await page.evaluate("""(el)=>[el.scrollTop, el.scrollHeight, el.clientHeight]""", el)
            new_top = min(sh - ch, top + int(ch * 0.85))
            await page.evaluate("(el, y)=>{ el.scrollTop = y }", el, new_top)
        except Exception:
            await page.keyboard.press("PageDown")

        await page.wait_for_timeout(450)

        try:
            el = await container.element_handle()
            cur_top = await page.evaluate("(el)=>el.scrollTop", el)
        except:
            cur_top = prev_top

        grew = (cur_top > prev_top)
        new_rows = (len(seen) > before)

        if not grew and not new_rows:
            stale += 1
        else:
            stale = 0

        prev_top = cur_top
        if stale >= settle:
            break

    return list(seen.values())


async def run(url: str, out_csv: str, out_json: Optional[str],
              headless: bool, timeout_ms: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        await page.goto(url, wait_until="domcontentloaded")
        # Skip networkidle as Notion pages often don't reach true idle
        await asyncio.sleep(5)

        container = await get_scrollable_container(page)
        headers = await extract_headers(page)
        data = await scroll_to_bottom_collect(page, container, headers)

        fieldnames = sorted({k for r in data for k in r.keys()})
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in data:
                w.writerow(r)

        if out_json:
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        await context.close()
        await browser.close()


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", dest="out_csv", default="notion_export_full.csv")
    ap.add_argument("--json", dest="out_json", default="notion_export_full.json")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--timeout", type=int, default=30000)
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args.url, args.out_csv, args.out_json, args.headless, args.timeout))