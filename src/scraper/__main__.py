from __future__ import annotations
import argparse
from .dev import scrape_single_job


def main():
    parser = argparse.ArgumentParser(description="Scrape a single LinkedIn job URL and save artifacts")
    parser.add_argument("--url", required=True)
    parser.add_argument("--headed", action="store_true", help="Run in headed mode for debugging")
    args = parser.parse_args()
    res = scrape_single_job(args.url, headed=args.headed)
    import json
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

