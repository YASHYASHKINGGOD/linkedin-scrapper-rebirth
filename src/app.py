from __future__ import annotations
import os
import json
from typing import List

from src.extractor.google_sheets import (
    ensure_credentials,
    get_sheets_service,
    parse_sheet_id_and_gid,
    extract_linkedin_links_from_sheet,
)


def fetch_sheet_values(spreadsheet_id: str, gid: str | None, range_a1: str | None = None):
    service = get_sheets_service(ensure_credentials())
    # If gid is provided, map it to a sheet name via metadata; otherwise default to first sheet
    meta = service.get(spreadsheetId=spreadsheet_id).get().execute()
    sheets = meta.get("sheets", [])
    title = None
    if gid:
        for s in sheets:
            pg = s.get("properties", {})
            if str(pg.get("sheetId")) == str(gid):
                title = pg.get("title")
                break
    if not title and sheets:
        title = sheets[0].get("properties", {}).get("title")
    if not title:
        raise RuntimeError("Could not determine sheet/tab title")

    a1 = f"{title}!A:Z" if not range_a1 else f"{title}!{range_a1}"
    resp = (
        service.values()
        .get(spreadsheetId=spreadsheet_id, range=a1, majorDimension="ROWS")
        .execute()
    )
    return resp.get("values", [])


def extract_from_urls(urls: List[str]) -> List[str]:
    all_links: List[str] = []
    for url in urls:
        sheet_id, gid = parse_sheet_id_and_gid(url)
        values = fetch_sheet_values(sheet_id, gid)
        links = extract_linkedin_links_from_sheet(values)
        all_links.extend(links)
    # make unique preserving order
    seen = set()
    unique = []
    for l in all_links:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique


if __name__ == "__main__":
    url_env = os.environ.get("GOOGLE_SHEETS_URLS", "").strip()
    if not url_env:
        raise SystemExit("Set GOOGLE_SHEETS_URLS to a comma-separated list of Google Sheet URLs.")
    urls = [u.strip() for u in url_env.split(",") if u.strip()]
    result = extract_from_urls(urls)
    print(json.dumps({"count": len(result), "links": result}, indent=2))
