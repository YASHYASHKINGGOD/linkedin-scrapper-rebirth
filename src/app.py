from __future__ import annotations
import os
import json
from typing import List, Iterable
import yaml  # type: ignore
from src.extractor.common.io import write_jsonl

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


def load_urls_from_env_and_config() -> List[str]:
    urls: List[str] = []
    # From env list
    url_env = os.environ.get("GOOGLE_SHEETS_URLS", "").strip()
    if url_env:
        urls.extend([u.strip() for u in url_env.split(",") if u.strip()])
    # From YAML config
    cfg_path = os.environ.get("SHEETS_CONFIG", "").strip()
    if cfg_path and os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            urls.extend(list(data.get("sheets", []) or []))
    # Unique preserve order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def save_links_jsonl(links: Iterable[str], source_urls: List[str], out_path: str) -> int:
    records = (
        {"url": link, "source": "google_sheets", "source_urls": source_urls}
        for link in links
    )
    return write_jsonl(out_path, records)


if __name__ == "__main__":
    urls = load_urls_from_env_and_config()
    if not urls:
        raise SystemExit("Provide at least one Sheets URL via GOOGLE_SHEETS_URLS or SHEETS_CONFIG.")
    result = extract_from_urls(urls)
    out_path = os.environ.get("OUTPUT_JSONL", "./storage/linkedin_links.jsonl")
    written = save_links_jsonl(result, urls, out_path)
    print(json.dumps({"count": len(result), "written": written, "output": out_path}, indent=2))
