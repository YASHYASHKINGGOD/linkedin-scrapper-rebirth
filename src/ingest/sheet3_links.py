from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.clients.google_sheets import GoogleSheetsClient
from src.extractor.google_sheets.urls import parse_sheet_id_and_gid
from src.extractor.common.io import write_csv

# Example header: "Jobs Updated on Aug 19, 2025" (allow variations)
DATE_HEADER_RE = re.compile(
    r"(?i)jobs\s+updated\s+on\s+(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?"
)


def parse_sheet3_tab(values: List[List[str]], link_col_index: int = 3) -> List[Dict[str, str]]:
    """Parse a tab with headers like 'Jobs Updated on Aug 19, 2025'.

    - values: 2D array of strings
    - link_col_index: column index where LinkedIn links reside (default D=3)
    Returns rows in reading order (top to bottom): [{date, linkedin_link}, ...]
    """
    out: List[Dict[str, str]] = []
    current_date: Optional[str] = None

    for row in values:
        header_text = " ".join([c for c in row if c]).strip()
        if header_text:
            m = DATE_HEADER_RE.search(header_text)
            if m:
                mon, day, year = m.group(1), m.group(2), m.group(3)
                # Normalize date string for CSV; keep month token as-is if present
                if mon:
                    mon_token = mon.capitalize()
                    # Normalize abbreviations
                    mon_map = {
                        "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "May",
                        "Jun": "Jun", "Jul": "Jul", "Aug": "Aug", "Sep": "Sep", "Sept": "Sep",
                        "Oct": "Oct", "Nov": "Nov", "Dec": "Dec",
                        "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
                        "June": "Jun", "July": "Jul", "August": "Aug", "September": "Sep",
                        "October": "Oct", "November": "Nov", "December": "Dec",
                    }
                    mon_norm = mon_map.get(mon_token, mon_token)
                    date_label = f"{mon_norm} {day}{',' if year else ''} {year}".strip()
                else:
                    # If month missing, keep as just day; caller context implies current month
                    date_label = day if not year else f"{day}, {year}"
                current_date = date_label.replace("  ", " ").strip().strip(",")
                continue
        # Data row: collect link from column D
        if len(row) > link_col_index and current_date:
            cell = row[link_col_index]
            if isinstance(cell, str) and "linkedin.com" in cell:
                out.append({"date": current_date, "linkedin_link": cell.strip()})
    return out


def run_ingest_sheet3_links(
    url: str,
    tabs: Optional[List[str]] = None,
    count: Optional[int] = 20,
    output_csv: Optional[str] = None,
) -> Dict[str, Any]:
    sheet_id, _ = parse_sheet_id_and_gid(url)
    client = GoogleSheetsClient()
    # Tabs to scan (order matters). Accept both 'The Fintech PM' and 'The FinTech PM'.
    desired_order = tabs or ["The FinTech PM", "Top 1% PM", "The Remote PM"]
    # Map available tab titles by lowercase for robust matching
    meta_tabs = client.get_spreadsheet(sheet_id).get("sheets", [])
    available = { (s.get("properties", {}) or {}).get("title"): (s.get("properties", {}) or {}).get("title") for s in meta_tabs }
    available_lc = { name.lower(): name for name in available.keys() }

    resolved_tabs: List[str] = []
    for wanted in desired_order:
        key = wanted.lower()
        # also normalize 'fintech' capitalization variants
        if key == "the fintech pm":
            key_variants = ["the fintech pm", "the fintech pm"]
        else:
            key_variants = [key]
        found = None
        for kv in key_variants:
            if kv in available_lc:
                found = available_lc[kv]
                break
        if found:
            resolved_tabs.append(found)

    rows_accum: List[Dict[str, str]] = []
    per_tab_counts: Dict[str, int] = {}

    for tab in resolved_tabs:
        values = client.get_values(sheet_id, tab)
        parsed = parse_sheet3_tab(values, link_col_index=3)
        per_tab_counts[tab] = len(parsed)
        if count is None or count <= 0:
            rows_accum.extend(parsed)
        else:
            for r in parsed:
                if len(rows_accum) < count:
                    rows_accum.append(r)
                else:
                    break
            if len(rows_accum) >= count:
                break

    if not output_csv:
        ts = datetime.now(timezone.utc).strftime("%YMMDD-%H%M%S")
        output_csv = f"./storage/ingest/google_sheets/{ts}/sheet3_links.csv"

    write_csv(output_csv, rows_accum, ["date", "linkedin_link"])

    return {
        "tabs": tabs,
        "returned": len(rows_accum),
        "per_tab_counts": per_tab_counts,
        "output_csv": output_csv,
    }
