from __future__ import annotations
import argparse
import csv
import os
import time
from typing import List
from .dev import scrape_single_job


def write_csv(rows: List[dict], path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Normalize lists to semicolon-joined strings
    def norm(v):
        if isinstance(v, list):
            return "; ".join([str(x) for x in v])
        return v
    fields = [
        "url",
        "role_title",
        "company_name",
        "location",
        "posted_time",
        "description_text",
        "key_responsibilities",
        "requirements",
        "html_path",
        "screenshot_path",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: norm(r.get(k, "")) for k in fields})
    return path


def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job URL(s) and save artifacts; optionally write CSV")
    parser.add_argument("--url", help="Single URL to scrape")
    parser.add_argument("--urls", help="Comma-separated list of URLs to scrape")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode for debugging (single URL mode)")
    parser.add_argument("--output-csv", help="Write results to this CSV (batch mode)")
    args = parser.parse_args()

    import json

    if args.urls:
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
        results = []
        for i, u in enumerate(urls, start=1):
            res = scrape_single_job(u, headed=False)
            results.append(res)
            time.sleep(1.0)
        if args.output_csv:
            path = write_csv(results, args.output_csv)
            print(json.dumps({"ok": True, "count": len(results), "output_csv": path}, indent=2))
        else:
            print(json.dumps(results, indent=2))
        return

    if not args.url:
        parser.error("Provide --url or --urls")

    res = scrape_single_job(args.url, headed=args.headed)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

