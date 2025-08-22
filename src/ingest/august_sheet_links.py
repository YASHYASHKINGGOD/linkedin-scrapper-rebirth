from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.clients.google_sheets import GoogleSheetsClient
from src.extractor.google_sheets.urls import parse_sheet_id_and_gid
from src.extractor.google_sheets.select import select_tab_by_month
from src.extractor.common.io import write_csv

# Accept rich headers like 'Opportunities Posted on 20th August'
DATE_HEADER_RE = re.compile(r"(?i)(?:opportunit(?:y|ies)|openings).*?(?:posted)?\s*(?:on)?\s*(\d{1,2})(?:st|nd|rd|th)?\s+(?:aug|august)(?:\s+\d{4})?")
# Also accept bare date lines like '21st August' or '21 Aug' or 'August 21'
DATE_ONLY_RE_1 = re.compile(r"(?i)^\s*(\d{1,2})(?:st|nd|rd|th)?\s+(aug|august)(?:\s+\d{4})?\s*$")
DATE_ONLY_RE_2 = re.compile(r"(?i)^\s*(aug|august)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+\d{4})?\s*$")


def parse_august_links(values: List[List[str]], link_col_index: int | None = 5) -> List[Dict[str, str]]:
    """Parse a values matrix and return rows with date and linkedin_link.

    - Expects date section headers like 'Opportunities Posted on 20th August'
    - Only extracts LinkedIn links from the given column index (default F = 5)
    - Scans top-to-bottom, then caller can take last-N for bottom-most items
    """
    results: List[Dict[str, str]] = []
    current_date: Optional[str] = None

    for row in values:
        # Detect date header anywhere in the row
        header_text = " ".join([c for c in row if c]).strip()
        if header_text:
            m = DATE_HEADER_RE.search(header_text)
            if m:
                day = m.group(1)
                current_date = f"{day} August"
                continue
            m1 = DATE_ONLY_RE_1.match(header_text)
            if m1:
                day = m1.group(1)
                current_date = f"{day} August"
                continue
            m2 = DATE_ONLY_RE_2.match(header_text)
            if m2:
                day = m2.group(2)
                current_date = f"{day} August"
                continue
        # Extract link from column F (index 5) by default; when link_col_index is None, scan entire row
        if link_col_index is None:
            candidates = [c for c in row if isinstance(c, str) and "linkedin.com" in c]
            for cell in candidates:
                if current_date is None:
                    continue
                results.append({"date": current_date, "linkedin_link": cell.strip()})
        else:
            if len(row) > link_col_index:
                cell = row[link_col_index]
                if isinstance(cell, str) and "linkedin.com" in cell:
                    if current_date is None:
                        # If we haven't seen a header yet, skip until a date header appears
                        continue
                    results.append({
                        "date": current_date,
                        "linkedin_link": cell.strip(),
                    })
    return results


def run_ingest_august_links(url: str, month_filter: str = "aug", count: int = 20, output_csv: Optional[str] = None) -> Dict[str, Any]:
    sheet_id, gid = parse_sheet_id_and_gid(url)
    client = GoogleSheetsClient()
    meta = client.get_spreadsheet(sheet_id)
    sheets = meta.get("sheets", []) or []
    selected = select_tab_by_month(sheets, month_filter)
    if not selected and gid:
        # Fallback: use the gid from URL if month tab not found
        for s in sheets:
            props = s.get("properties", {})
            if str(props.get("sheetId")) == str(gid):
                selected = s
                break
    if not selected:
        raise SystemExit(f"Could not find a tab containing '{month_filter}' in this spreadsheet")
    tab_title = selected.get("properties", {}).get("title")
    values = client.get_values(sheet_id, tab_title)

    all_rows = parse_august_links(values, link_col_index=5)
    if not all_rows:
        # Fallback: scan all columns for LinkedIn links if column F is not used in this sheet
        all_rows = parse_august_links(values, link_col_index=None)
    # Take the last N entries (bottom-most)
    last_n = all_rows[-count:] if count > 0 else all_rows

    # Determine output path
    if not output_csv:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_csv = f"./storage/ingest/google_sheets/{ts}/august_links.csv"

    write_csv(output_csv, last_n, ["date", "linkedin_link"])

    return {
        "tab_title": tab_title,
        "total_found": len(all_rows),
        "returned": len(last_n),
        "output_csv": output_csv,
    }
