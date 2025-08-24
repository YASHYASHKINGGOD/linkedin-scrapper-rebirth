#!/usr/bin/env python3
"""
notion_table_scraper.py
Scrape ALL rows from a public Notion database (table view) with virtual scrolling.

Usage:
  python notion_table_scraper.py "https://foccommunity.notion.site/14d2955ab7ed80569735c3061cffa884?v=14d2955ab7ed8194aef0000c929e4422" --out data/foc_full.csv --json data/foc_full.json

Notes:
- Works best with Playwright >= 1.45
- Does NOT use Notion's private API. It simulates correct scrolling on the internal grid container.
- If the database is huge, increase --max_idle and --max_scrolls.
"""
import asyncio
import csv
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, Page, Locator

LINK_PATTERNS = [
    re.compile(r"https?://(www\.)?linkedin\.com/[^\s\"]+", re.I),
]

def textify(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

async def find_grid_container(page: Page) -> Optional[Locator]:
    # 1) Try Notion's custom table view class (most common for Notion DB)
    notion_table = page.locator('.notion-table-view').first
    if await notion_table.count() > 0:
        print("Found .notion-table-view")
        return notion_table

    # 2) Try ARIA role grid (standard approach)
    grid = page.locator('[role="grid"]').first
    if await grid.count() > 0:
        print("Found [role='grid']")
        return grid

    # 3) Fallback: common Notion collection container hints
    candidates = page.locator('div:has([role="columnheader"])')
    if await candidates.count() > 0:
        print("Found div with columnheader")
        return candidates.first

    return None

async def find_scrollable_parent(page: Page, element: Locator) -> Optional[Locator]:
    # For Notion, try specific known scrollable containers first
    notion_scrollers = [
        '.notion-scroller',
        '.notion-collection-view-body', 
        '.notion-table-view',
        'body'
    ]
    
    for selector in notion_scrollers:
        scroller = page.locator(selector).first
        if await scroller.count() > 0:
            # Check if it's actually scrollable
            is_scrollable = await scroller.evaluate('''el => {
                const style = getComputedStyle(el);
                const oy = style.overflowY;
                return (oy === 'auto' || oy === 'scroll' || oy === 'overlay') && (el.scrollHeight > el.clientHeight);
            }''')
            if is_scrollable:
                print(f"Found scrollable container: {selector}")
                return scroller
    
    # Fallback to body
    return page.locator('body')

async def click_load_more_buttons(page: Page) -> int:
    # Click any "Load more" / "Show more" / "Next" type button that Notion might expose
    # Returns the number of clicks performed.
    btn = page.locator("button:has-text('Load more'), button:has-text('Show more'), button:has-text('Next')").first
    clicks = 0
    while await btn.count() > 0 and await btn.is_enabled():
        try:
            await btn.scroll_into_view_if_needed()
            await btn.click()
            clicks += 1
            await page.wait_for_timeout(500)
        except Exception:
            break
        btn = page.locator("button:has-text('Load more'), button:has-text('Show more'), button:has-text('Next')").first
    return clicks

async def scroll_until_stable(page: Page, grid: Locator, scrollable: Locator, max_idle: int = 6, max_scrolls: int = 120) -> None:
    """
    Scrolls the *correct* container to the bottom until row count stops increasing.
    - max_idle: how many consecutive iterations with no growth before we stop
    - max_scrolls: hard cap to avoid infinite loops
    """
    # Zoom out to load more rows per viewport (helps virtualized lists)
    try:
        await page.evaluate("document.body.style.zoom = '0.80'")
    except Exception:
        pass

    rows = grid.locator('[role="row"]')
    seen = 0
    idle = 0
    total_scrolls = 0

    while idle < max_idle and total_scrolls < max_scrolls:
        # Try clicking "Load more" if it exists
        clicked = await click_load_more_buttons(page)
        if clicked:
            idle = 0

        # Scroll the scrollable container to bottom
        try:
            await page.evaluate("el => el.scrollTop = el.scrollHeight", await scrollable.element_handle())
        except Exception:
            # Fallback: Arrow/PageDown on grid
            await grid.press("PageDown")

        await page.wait_for_timeout(600)

        # Nudge: hover last row to encourage rendering
        try:
            count = await rows.count()
            if count > 0:
                await rows.nth(count - 1).scroll_into_view_if_needed()
        except Exception:
            pass

        # Check if count increased
        try:
            count = await rows.count()
        except Exception:
            count = seen

        if count > seen:
            seen = count
            idle = 0
        else:
            idle += 1
        total_scrolls += 1

async def extract_table(page: Page, grid: Locator) -> List[Dict[str, Any]]:
    # Try Notion-specific structure first
    notion_headers = grid.locator('.notion-table-view-header-cell')
    notion_rows = grid.locator('.notion-table-view-row')
    
    if await notion_headers.count() > 0:
        print(f"Using Notion-specific extraction - found {await notion_headers.count()} headers")
        return await extract_notion_table(page, grid, notion_headers, notion_rows)
    
    # Fallback to standard ARIA table structure
    print("Using standard ARIA table extraction")
    header_cells = grid.locator('[role="columnheader"]')
    n_headers = await header_cells.count()
    headers = []
    for i in range(n_headers):
        htxt = textify(await header_cells.nth(i).inner_text())
        headers.append(htxt or f"col_{i+1}")

    # Rows
    rows = grid.locator('[role="row"]')
    n_rows = await rows.count()
    data = []

    for r in range(n_rows):
        row = rows.nth(r)
        cells = row.locator('[role="gridcell"], [role="cell"]')
        n_cells = await cells.count()
        record = {}

        for c in range(min(n_cells, n_headers)):
            cell = cells.nth(c)
            text = textify(await cell.inner_text())

            # collect all links in this cell (esp. LinkedIn)
            anchors = cell.locator("a[href]")
            links = []
            for aidx in range(await anchors.count()):
                href = await anchors.nth(aidx).get_attribute("href")
                if href:
                    links.append(href)

            # pick first linkedin link if present
            linkedin = next((l for l in links if 'linkedin.com' in l.lower()), '')

            record[headers[c]] = text
            if linkedin:
                record[f"{headers[c]}__linkedin"] = linkedin

        # also include a combined list of all links in the row
        all_as = row.locator("a[href]")
        all_links = []
        for aidx in range(await all_as.count()):
            href = await all_as.nth(aidx).get_attribute("href")
            if href:
                all_links.append(href)
        record["all_links"] = ", ".join(sorted(set(all_links)))

        data.append(record)

    return data

async def extract_notion_table(page: Page, grid: Locator, header_cells: Locator, rows: Locator) -> List[Dict[str, Any]]:
    """Extract data from Notion's custom table structure."""
    # Extract headers
    n_headers = await header_cells.count()
    headers = []
    print(f"Extracting {n_headers} headers...")
    for i in range(n_headers):
        htxt = textify(await header_cells.nth(i).inner_text())
        headers.append(htxt or f"col_{i+1}")
        print(f"  Header {i+1}: {htxt}")

    # Wait for rows to load and try to get all of them
    await page.wait_for_timeout(2000)  # Give time for rows to render
    
    # Try multiple selectors for Notion rows
    row_selectors = [
        '.notion-table-view-row',
        'div[data-block-id]:has(.notion-table-view-cell)',
        '.notion-collection-view-item'
    ]
    
    data_rows = None
    for selector in row_selectors:
        test_rows = grid.locator(selector)
        count = await test_rows.count()
        print(f"Trying selector '{selector}': found {count} rows")
        if count > 0:
            data_rows = test_rows
            break
    
    if not data_rows:
        # Last resort: look for any div that contains links
        data_rows = grid.locator('div:has(a[href*="linkedin.com"])')
        print(f"Fallback selector found {await data_rows.count()} rows with LinkedIn links")
    
    n_rows = await data_rows.count()
    print(f"Processing {n_rows} data rows...")
    
    data = []
    for r in range(n_rows):
        row = data_rows.nth(r)
        
        # Try to find cells in this row - Notion uses different structures
        cell_selectors = [
            '.notion-table-view-cell',
            'div[style*="width"]',  # Notion often uses width styling for columns
            'div:has(a)',  # Divs containing links
        ]
        
        cells = None
        for cell_selector in cell_selectors:
            test_cells = row.locator(cell_selector)
            if await test_cells.count() > 0:
                cells = test_cells
                break
        
        if not cells:
            # If we can't find specific cells, treat the whole row as one cell
            cells = row
            n_cells = 1
        else:
            n_cells = await cells.count()
        
        record = {}
        
        # Get all text and links from the row
        row_text = textify(await row.inner_text())
        all_as = row.locator("a[href]")
        all_links = []
        linkedin_links = []
        
        for aidx in range(await all_as.count()):
            href = await all_as.nth(aidx).get_attribute("href")
            if href:
                all_links.append(href)
                if 'linkedin.com' in href.lower():
                    linkedin_links.append(href)
        
        # Try to map data to headers if possible
        if n_cells > 1 and len(headers) > 0:
            for c in range(min(n_cells, len(headers))):
                if cells == row:
                    cell_text = row_text
                else:
                    cell = cells.nth(c)
                    cell_text = textify(await cell.inner_text())
                
                record[headers[c]] = cell_text
                
                # Check for LinkedIn links in this cell
                if cells != row:
                    cell_links = cell.locator("a[href*='linkedin.com']")
                    for link_idx in range(await cell_links.count()):
                        href = await cell_links.nth(link_idx).get_attribute("href")
                        if href:
                            record[f"{headers[c]}__linkedin"] = href
                            break
        else:
            # If we can't parse cells, just put everything in the first column
            if headers:
                record[headers[0]] = row_text
            else:
                record["content"] = row_text
        
        # Add metadata
        record["all_links"] = ", ".join(sorted(set(all_links)))
        record["linkedin_links"] = ", ".join(linkedin_links)
        record["row_text"] = row_text
        
        if linkedin_links:  # Only include rows with LinkedIn links
            data.append(record)
    
    print(f"Extracted {len(data)} rows with LinkedIn links")
    return data

async def run(url: str, out_csv: str, out_json: Optional[str], headless: bool, timeout_ms: int, max_idle: int, max_scrolls: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1400, "height": 1000})
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        await page.goto(url, wait_until="domcontentloaded")
        # Skip networkidle for Notion as it often doesn't reach true idle state
        print("Waiting for page content to load...")
        await asyncio.sleep(8)  # Longer wait for Notion to load table content

        print("Looking for Notion database grid...")
        grid = await find_grid_container(page)
        if not grid or await grid.count() == 0:
            # Debug: see what's actually on the page
            title = await page.title()
            print(f"Page title: {title}")
            
            # Look for any grids or tables
            all_grids = await page.locator('[role="grid"]').count()
            all_tables = await page.locator('table').count()
            all_columnheaders = await page.locator('[role="columnheader"]').count()
            
            print(f"Found {all_grids} grids, {all_tables} tables, {all_columnheaders} column headers")
            
            # Save page for debugging
            html = await page.content()
            with open('debug_page.html', 'w') as f:
                f.write(html)
            print("Saved page HTML to debug_page.html")
            
            raise RuntimeError("Could not find Notion database grid on the page.")

        scrollable = await find_scrollable_parent(page, grid)
        if not scrollable:
            # As a fallback, try to use the main page scroll — less reliable for Notion
            scrollable = page.locator('body')

        # Scroll until we've loaded all rows (or stabilized)
        await scroll_until_stable(page, grid, scrollable, max_idle=max_idle, max_scrolls=max_scrolls)

        # Extract
        data = await extract_table(page, grid)

        # Persist
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        if data:
            # union headers
            fieldnames = sorted({k for row in data for k in row.keys()})
            with open(out_csv, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for row in data:
                    w.writerow(row)

        if out_json:
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        await context.close()
        await browser.close()

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('url', help='Public Notion database URL (table view)')
    ap.add_argument('--out', dest='out_csv', default='notion_export.csv', help='CSV output path')
    ap.add_argument('--json', dest='out_json', default=None, help='Optional JSON output path')
    ap.add_argument('--headless', action='store_true', help='Run headless (default: headed for easier debug)')
    ap.add_argument('--timeout', type=int, default=30000, help='Playwright default timeout in ms (per action)')
    ap.add_argument('--max-idle', type=int, default=6, help='Stop after N consecutive no-growth cycles')
    ap.add_argument('--max-scrolls', type=int, default=150, help='Hard cap on scroll iterations')
    return ap.parse_args()

if __name__ == '__main__':
    args = parse_args()
    asyncio.run(run(
        url=args.url,
        out_csv=args.out_csv,
        out_json=args.out_json,
        headless=args.headless,
        timeout_ms=args.timeout,
        max_idle=args.max_idle,
        max_scrolls=args.max_scrolls,
    ))