from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.extractor.google_sheets.urls import parse_sheet_id_and_gid
from src.clients.google_sheets import GoogleSheetsClient
from src.extractor.google_sheets.select import select_tab_by_month
from src.extractor.google_sheets.links import extract_linkedin_links_from_sheet
from src.extractor.common.dedupe import dedupe_preserve_order
from src.extractor.common.io import write_csv


CSV_COLUMNS = [
    "url",
    "source",
    "spreadsheet_id",
    "spreadsheet_title",
    "spreadsheet_url",
    "sheet_name",
    "tab_title",
    "tab_gid",
    "discovered_at",
]


def run_google_sheets_ingest(
    urls: List[str],
    month_filter: str,
    output_csv: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    client = GoogleSheetsClient()

    rows: List[Dict[str, Any]] = []
    per_sheet_counts: Dict[str, int] = {}

    for sheet_url in urls:
        spreadsheet_id, _ = parse_sheet_id_and_gid(sheet_url)
        meta = client.get_spreadsheet(spreadsheet_id)
        spreadsheet_title = (meta.get("properties", {}) or {}).get("title")
        sheets = meta.get("sheets", []) or []

        selected = select_tab_by_month(sheets, month_filter)
        if not selected:
            per_sheet_counts[spreadsheet_id] = 0
            continue
        sel_title = (selected.get("properties", {}) or {}).get("title")
        sel_gid = str((selected.get("properties", {}) or {}).get("sheetId"))

        values = client.get_values(spreadsheet_id, sel_title)
        links = extract_linkedin_links_from_sheet(values)
        per_sheet_counts[spreadsheet_id] = len(links)

        for link in links:
            rows.append(
                {
                    "url": link,
                    "source": "google_sheet",
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_title": spreadsheet_title,
                    "spreadsheet_url": sheet_url,
                    "sheet_name": sel_title,
                    "tab_title": sel_title,
                    "tab_gid": sel_gid,
                    "discovered_at": now.isoformat(),
                }
            )

    # Deduplicate by url preserving first occurrence
    first_seen: Dict[str, Dict[str, Any]] = {}
    ordered_urls: List[str] = []
    for r in rows:
        u = r["url"]
        if u not in first_seen:
            first_seen[u] = r
            ordered_urls.append(u)
    deduped_rows = [first_seen[u] for u in ordered_urls]

    # Determine output path
    output_csv = output_csv or os.environ.get("OUTPUT_CSV", "")
    if not output_csv:
        ts = now.strftime("%Y%m%d-%H%M%S")
        output_csv = f"./storage/ingest/google_sheets/{ts}/links.csv"

    write_csv(output_csv, deduped_rows, CSV_COLUMNS)

    return {
        "total_links_raw": len(rows),
        "total_links_unique": len(deduped_rows),
        "per_sheet_counts": per_sheet_counts,
        "output_csv": output_csv,
    }

