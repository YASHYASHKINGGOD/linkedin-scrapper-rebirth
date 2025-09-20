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
    import argparse
    from datetime import datetime, timezone
    from src.ingest.google_sheets_run import run_google_sheets_ingest

    parser = argparse.ArgumentParser(description="Utilities for Google Sheets link extraction")
    sub = parser.add_subparsers(dest="cmd")

    p_ingest = sub.add_parser("ingest-google-sheets", help="Extract links from multiple Google Sheets into CSV (Google API client)")
    p_ingest.add_argument("--urls", type=str, default=os.environ.get("GOOGLE_SHEETS_URLS", ""), help="Comma-separated Google Sheets URLs")
    p_ingest.add_argument("--month-filter", type=str, default=os.environ.get("MONTH_FILTER", "aug"), help="Month substring to match tab titles (case-insensitive)")
    p_ingest.add_argument("--output-csv", type=str, default=os.environ.get("OUTPUT_CSV", ""), help="Output CSV path (optional)")

    p_gspread = sub.add_parser("ingest-google-sheets-gspread", help="Extract links using gspread OAuth (as per your reference)")
    p_gspread.add_argument("--urls", type=str, default=os.environ.get("GOOGLE_SHEETS_URLS", ""), help="Comma-separated Google Sheets URLs")
    p_gspread.add_argument("--month-filter", type=str, default=os.environ.get("MONTH_FILTER", "aug"), help="Month substring to match tab titles (case-insensitive)")
    p_gspread.add_argument("--output-csv", type=str, default=os.environ.get("OUTPUT_CSV", ""), help="Output CSV path (optional)")

    p_aug = sub.add_parser("ingest-august-links", help="Extract last N LinkedIn links (date + link) from August tab (column F)")
    p_aug.add_argument("--url", type=str, required=True, help="Single Google Sheet URL")
    p_aug.add_argument("--month-filter", type=str, default=os.environ.get("MONTH_FILTER", "aug"))
    p_aug.add_argument("--count", type=int, default=20, help="How many from the bottom to return")
    p_aug.add_argument("--output-csv", type=str, default=os.environ.get("OUTPUT_CSV", ""))

    p_s3 = sub.add_parser("ingest-sheet3-links", help="Extract links from all three Sheet 3 tabs (The Fintech PM, Top 1% PM, The Remote PM) from column D; recent-first per tab")
    p_s3.add_argument("--url", type=str, required=True)
    p_s3.add_argument("--count", type=int, default=20, help="If >0, limit to first N across tabs; set to 0 with --all to fetch all")
    p_s3.add_argument("--all", action="store_true", help="Fetch all rows across all three tabs (ignores --count)")
    p_s3.add_argument("--output-csv", type=str, default=os.environ.get("OUTPUT_CSV", ""))

    p_comb = sub.add_parser("ingest-combined-csv", help="Create one CSV with date, company, role, location, url from all three sheets")
    p_comb.add_argument("--urls", type=str, required=True, help="Comma-separated 3 Google Sheets URLs")
    p_comb.add_argument("--month-filter", type=str, default=os.environ.get("MONTH_FILTER", "aug"))
    p_comb.add_argument("--output-csv", type=str, default=os.environ.get("OUTPUT_CSV", ""))

    p_import = sub.add_parser("import-and-backup", help="Migrate DB (url TEXT + canonical), upsert CSV via ON CONFLICT, and write backup CSV of inserted/updated rows")
    p_import.add_argument("--csv", type=str, required=True)
    p_import.add_argument("--backup-dir", type=str, default="./storage/backups")
    p_import.add_argument("--minutes", type=int, default=10, help="Backup rows with extracted_at within last N minutes")

    p_class = sub.add_parser("classify-and-queue", help="Classify links (job|post|unknown) and set status='queued'; emits link.new and link.classified events")

    args = parser.parse_args()

    if args.cmd == "ingest-google-sheets":
        urls = [u.strip() for u in (args.urls or "").split(",") if u.strip()]
        if not urls:
            urls = load_urls_from_env_and_config()
        if not urls:
            raise SystemExit("Provide at least one Sheets URL via --urls or GOOGLE_SHEETS_URLS / SHEETS_CONFIG.")
        stats = run_google_sheets_ingest(urls=urls, month_filter=args.month_filter, output_csv=(args.output_csv or None))
        print(json.dumps(stats, indent=2))
    elif args.cmd == "ingest-google-sheets-gspread":
        from src.ingest.google_sheets_gspread import run_google_sheets_ingest_gspread
        urls = [u.strip() for u in (args.urls or "").split(",") if u.strip()]
        if not urls:
            urls = load_urls_from_env_and_config()
        if not urls:
            raise SystemExit("Provide at least one Sheets URL via --urls or GOOGLE_SHEETS_URLS / SHEETS_CONFIG.")
        stats = run_google_sheets_ingest_gspread(urls=urls, month_filter=args.month_filter, output_csv=(args.output_csv or None))
        print(json.dumps(stats, indent=2))
    elif args.cmd == "ingest-august-links":
        from src.ingest.august_sheet_links import run_ingest_august_links
        stats = run_ingest_august_links(url=args.url, month_filter=args.month_filter, count=args.count, output_csv=(args.output_csv or None))
        print(json.dumps(stats, indent=2))
    elif args.cmd == "ingest-sheet3-links":
        from src.ingest.sheet3_links import run_ingest_sheet3_links
        eff_count = None if getattr(args, "all", False) else args.count
        stats = run_ingest_sheet3_links(url=args.url, count=eff_count, output_csv=(args.output_csv or None))
        print(json.dumps(stats, indent=2))
    elif args.cmd == "ingest-combined-csv":
        from src.ingest.combined_links_csv import run_combined_csv
        urls = [u.strip() for u in (args.urls or "").split(",") if u.strip()]
        stats = run_combined_csv(urls=urls, month_filter=args.month_filter, output_csv=(args.output_csv or None))
        print(json.dumps(stats, indent=2))
    elif args.cmd == "import-and-backup":
        from src.db.import_and_backup import import_and_backup
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise SystemExit("DATABASE_URL is required")
        backup = import_and_backup(database_url=db_url, csv_path=args.csv, backup_dir=args.backup_dir, insert_window_minutes=args.minutes)
        print(json.dumps({"backup_csv": backup}, indent=2))
    elif args.cmd == "classify-and-queue":
        from src.db.classify_and_queue import migrate_and_classify
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise SystemExit("DATABASE_URL is required")
        out = migrate_and_classify(db_url)
        print(json.dumps(out, indent=2))
    else:
        # Backward-compatible default: JSONL writer using all tabs (legacy path)
        urls = load_urls_from_env_and_config()
        if not urls:
            raise SystemExit("Provide at least one Sheets URL via GOOGLE_SHEETS_URLS or SHEETS_CONFIG.")
        result = extract_from_urls(urls)
        out_path = os.environ.get("OUTPUT_JSONL", "./storage/linkedin_links.jsonl")
        written = save_links_jsonl(result, urls, out_path)
        print(json.dumps({"count": len(result), "written": written, "output": out_path}, indent=2))
