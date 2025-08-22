from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Dict, Any, Set

from playwright.async_api import async_playwright

RUN_TS_FMT = "%Y%m%d-%H%M%S"


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def load_seeds(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        urls = data.get("urls") or data.get("seeds") or []
    else:
        urls = data
    return [u for u in urls if isinstance(u, str) and u.strip()]


async def scrape_one(page, url: str, out_dir: Path, take_snapshots: bool = True) -> Dict[str, Any]:
    started = time.time()
    # Be lenient with Notion load; some workspaces take longer and may stream content
    last_err = None
    for attempt in range(2):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            # Wait for a likely container to appear, but don't fail the run if it doesn't
            try:
                await page.wait_for_selector(
                    ".notion-scroller.notion-collection-view-body, .notion-table-view, [role='grid'], [role='table']",
                    timeout=30000,
                )
            except Exception:
                pass
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                # Small backoff then retry once
                await asyncio.sleep(2.0)
                continue
            raise

    # Try to auto-scroll database/table containers if present
    scroll_js = """
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const candidates = Array.from(document.querySelectorAll('.notion-scroller.notion-collection-view-body, .notion-table-view, [role="grid"], [role="table"]'));
  let scroller = candidates.find(el => el.scrollHeight > el.clientHeight) || document.scrollingElement || document.body;
  let lastHeight = 0;
  let stableCount = 0;
  for (let i = 0; i < 40; i++) {
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: 'instant' });
    await sleep(400);
    const h = scroller.scrollHeight;
    if (h <= lastHeight) {
      stableCount += 1;
    } else {
      stableCount = 0;
      lastHeight = h;
    }
    if (stableCount >= 3) break;
  }
  return true;
})()
    """
    try:
        await page.evaluate(scroll_js)
    except Exception:
        pass

    # Extract LinkedIn links with light context
    extract_js = """
(() => {
  const anchors = Array.from(document.querySelectorAll('a[href*="linkedin.com"]'));
  const rows = [];
  for (const a of anchors) {
    const href = a.getAttribute('href');
    if (!href) continue;
    const rowNode = a.closest('.notion-collection-item') || a.closest('[data-block-id]') || a.parentElement;
    let context = '';
    if (rowNode) {
      const text = rowNode.innerText || '';
      context = text.replace(/\s+/g,' ').trim().slice(0, 300);
    }
    rows.push({ href, text: (a.innerText||'').trim().slice(0,200), context });
  }
  return rows;
})()
    """
    items: List[Dict[str, str]] = await page.evaluate(extract_js)

    # Deduplicate by href order-preserving
    seen: Set[str] = set()
    links: List[Dict[str, str]] = []
    for it in items:
        h = it.get("href") or ""
        if not h:
            continue
        if h not in seen:
            seen.add(h)
            links.append(it)

    # Snapshots per source
    snapshots_rel = None
    if take_snapshots:
        slug = _short_hash(url)
        snap_dir = out_dir / "snapshots" / slug
        _ensure_dir(snap_dir)
        try:
            await page.screenshot(path=str(snap_dir / "page.png"), full_page=True)
        except Exception:
            pass
        try:
            html = await page.content()
            (snap_dir / "page.html").write_text(html, encoding="utf-8")
        except Exception:
            pass
        snapshots_rel = str(Path("snapshots") / slug)

    return {
        "source_url": url,
        "found": links,
        "snapshot": snapshots_rel,
        "elapsed_sec": round(time.time() - started, 2),
    }


async def run(urls: List[str], base_output: Path, no_snapshots: bool = False) -> Dict[str, Any]:
    ts = datetime.utcnow().strftime(RUN_TS_FMT)
    run_dir = base_output / ts
    _ensure_dir(run_dir)

    out_links = run_dir / "links.jsonl"
    manifest_path = run_dir / "run.json"

    results_summary: Dict[str, Any] = {
        "run_id": ts,
        "started_at": _now_ts(),
        "notion_source_urls": urls,
        "output_dir": str(run_dir),
        "count_found": 0,
        "count_unique": 0,
    }

    unique_seen: Set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        with out_links.open("w", encoding="utf-8") as out:
            for u in urls:
                res = await scrape_one(page, u, run_dir, take_snapshots=not no_snapshots)
                for it in res["found"]:
                    href = it.get("href") or ""
                    rec = {
                        "url": href,
                        "source": "notion",
                        "source_page_url": u,
                        "anchor_text": it.get("text") or "",
                        "row_context": it.get("context") or "",
                        "captured_at": _now_ts(),
                    }
                    results_summary["count_found"] += 1
                    if href not in unique_seen:
                        unique_seen.add(href)
                        out.write(json.dumps(rec) + "\n")
                # write per-source snapshot marker
                # (no-op; already saved in scrape_one)

        await context.close()
        await browser.close()

    results_summary["count_unique"] = len(unique_seen)
    results_summary["finished_at"] = _now_ts()

    manifest_path.write_text(json.dumps(results_summary, indent=2), encoding="utf-8")

    return results_summary


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Notion pages for LinkedIn links")
    p.add_argument("--url", action="append", dest="urls", help="Notion page/database URL (repeatable)")
    p.add_argument("--seeds", type=str, help="Path to JSON file with array of URLs or {urls: [...]} ", default="")
    p.add_argument("--output", type=str, help="Base output directory", default="./storage/ingest/notion")
    p.add_argument("--no-snapshots", action="store_true", help="Do not save HTML/screenshot snapshots")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    ns = parse_args(argv or sys.argv[1:])
    urls: List[str] = []
    if ns.urls:
        urls.extend(ns.urls)
    if ns.seeds:
        try:
            urls.extend(load_seeds(Path(ns.seeds)))
        except Exception as e:
            print(json.dumps({"error": f"Failed to load seeds: {e}"}))
            return 2
    # de-dupe preserve order
    seen: Set[str] = set()
    final_urls: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            final_urls.append(u)
    if not final_urls:
        print("No URLs provided. Use --url or --seeds.")
        return 1

    output = Path(ns.output)
    _ensure_dir(output)

    summary = asyncio.run(run(final_urls, output, no_snapshots=ns.no_snapshots))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
