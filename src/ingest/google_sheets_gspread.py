from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import gspread  # type: ignore

from src.extractor.google_sheets.links import extract_linkedin_links_from_sheet
from src.extractor.google_sheets.urls import parse_sheet_id_and_gid
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


def _select_tab_by_month_gspread(worksheets: List[Any], month_filter: str):
    month = (month_filter or "").lower()
    matches = [ws for ws in worksheets if month in ws.title.lower()]
    if not matches:
        return None
    # Prefer the worksheet with the highest index property
    def _idx(ws):
        try:
            return int(ws._properties.get("index", -1))
        except Exception:
            return -1
    matches.sort(key=_idx)
    return matches[-1]


def run_google_sheets_ingest_gspread(
    urls: List[str],
    month_filter: str,
    output_csv: Optional[str] = None,
    now_utc: Optional[datetime] = None,
    credentials_file: Optional[str] = None,
    token_file: Optional[str] = None,
) -> Dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    credentials_file = credentials_file or os.environ.get("GOOGLE_OAUTH_CLIENT_JSON", "./.secrets/google_client.json")
    token_file = token_file or os.environ.get("GOOGLE_OAUTH_TOKEN_JSON", "./.secrets/google_token.json")

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    port = int(os.environ.get("GOOGLE_OAUTH_REDIRECT_PORT", "8765"))
    gc = gspread.oauth(credentials_filename=credentials_file, authorized_user_filename=token_file, scopes=scopes, port=port)

    rows: List[Dict[str, Any]] = []
    per_sheet_counts: Dict[str, int] = {}

    for sheet_url in urls:
        # gspread can open by URL directly; also capture spreadsheet_id
        spreadsheet_id, _ = parse_sheet_id_and_gid(sheet_url)
        sh = gc.open_by_url(sheet_url)
        worksheets = sh.worksheets()
        selected = _select_tab_by_month_gspread(worksheets, month_filter)
        if not selected:
            per_sheet_counts[spreadsheet_id] = 0
            continue
        values = selected.get_all_values()
        links = extract_linkedin_links_from_sheet(values)
        per_sheet_counts[spreadsheet_id] = len(links)
        for link in links:
            rows.append(
                {
                    "url": link,
                    "source": "google_sheet",
                    "spreadsheet_id": sh.id,
                    "spreadsheet_title": sh.title,
                    "spreadsheet_url": sheet_url,
                    "sheet_name": selected.title,
                    "tab_title": selected.title,
                    "tab_gid": str(selected.id),
                    "discovered_at": now.isoformat(),
                }
            )

    # Deduplicate by url preserving first occurrence
    seen: Dict[str, Dict[str, Any]] = {}
    ordered: List[str] = []
    for r in rows:
        u = r["url"]
        if u not in seen:
            seen[u] = r
            ordered.append(u)
    deduped = [seen[u] for u in ordered]

    output_csv = output_csv or os.environ.get("OUTPUT_CSV", "")
    if not output_csv:
        ts = now.strftime("%Y%m%d-%H%M%S")
        output_csv = f"./storage/ingest/google_sheets/{ts}/links.csv"

    write_csv(output_csv, deduped, CSV_COLUMNS)

    return {
        "total_links_raw": len(rows),
        "total_links_unique": len(deduped),
        "per_sheet_counts": per_sheet_counts,
        "output_csv": output_csv,
    }
