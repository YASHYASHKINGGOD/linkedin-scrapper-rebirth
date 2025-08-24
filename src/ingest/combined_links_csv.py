from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.clients.google_sheets import GoogleSheetsClient
from src.extractor.google_sheets.urls import parse_sheet_id_and_gid
from src.extractor.google_sheets.select import select_tab_by_month
from src.extractor.common.io import write_csv

# Date header patterns across sheets
DATE_PATTERNS = [
    re.compile(r"(?i)(?:opportunit(?:y|ies)|openings).*?(?:posted)?\s*(?:on)?\s*(\d{1,2})(?:st|nd|rd|th)?\s+(?:aug|august)(?:\s+\d{4})?"),
    re.compile(r"(?i)^\s*(\d{1,2})(?:st|nd|rd|th)?\s+(aug|august)(?:\s+\d{4})?\s*$"),
    re.compile(r"(?i)^\s*(aug|august)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+\d{4})?\s*$"),
    re.compile(r"(?i)jobs\s+updated\s+on\s+(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?"),
]

HEADER_KEYS = {
    "company": ["company"],
    "role": ["role", "title", "position"],
    "location": ["location", "city"],
    "link": ["link", "post link", "job link", "url", "application link"],
}


def _detect_header_indices(row: List[str]) -> Dict[str, int]:
    idx: Dict[str, int] = {}
    lower = [str(c).strip().lower() for c in row]
    for key, aliases in HEADER_KEYS.items():
        for i, cell in enumerate(lower):
            if any(alias in cell for alias in aliases):
                idx[key] = i
                break
    # Require at least link column to proceed
    return idx if "link" in idx else {}


def _match_date(text: str) -> Optional[str]:
    t = text.strip()
    if not t:
        return None
    for pat in DATE_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        if pat.pattern.startswith("(?i)jobs"):
            mon, day, year = m.group(1), m.group(2), m.group(3)
            if mon:
                mon_map = {
                    "january":"Jan","february":"Feb","march":"Mar","april":"Apr","may":"May","june":"Jun","july":"Jul","august":"Aug","september":"Sep","october":"Oct","november":"Nov","december":"Dec",
                    "jan":"Jan","feb":"Feb","mar":"Mar","apr":"Apr","jun":"Jun","jul":"Jul","aug":"Aug","sep":"Sep","sept":"Sep","oct":"Oct","nov":"Nov","dec":"Dec",
                }
                mon_norm = mon_map.get(mon.lower(), mon.title())
                return f"{mon_norm} {day}{',' if year else ''} {year}".strip().strip(',')
            return day if not year else f"{day}, {year}"
        # normalize outputs for the other patterns
        gs = m.groups()
        if len(gs) == 1:
            day = m.group(1)
            return f"{day} August"
        if len(gs) == 2:
            g1, g2 = gs
            if g1 and g1.lower().startswith("aug"):
                return f"{g2} August"
            return f"{g1} August"
    return None


def parse_generic(values: List[List[str]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    header_idx: Dict[str, int] = {}
    current_date: Optional[str] = None

    for ridx, row in enumerate(values, start=1):
        # Detect header
        if not header_idx:
            hdr = _detect_header_indices([str(c) if c is not None else "" for c in row])
            if hdr:
                header_idx = hdr
                continue
        # Date header line
        text = " ".join([str(c) for c in row if c]).strip()
        d = _match_date(text)
        if d:
            current_date = d
            continue
        # Data row
        if header_idx and current_date:
            def cell(i: Optional[int]) -> str:
                return str(row[i]).strip() if i is not None and i < len(row) and row[i] is not None else ""
            comp = cell(header_idx.get("company"))
            role = cell(header_idx.get("role"))
            loc = cell(header_idx.get("location"))
            link = cell(header_idx.get("link"))
            if link:
                rows.append({
                    "date": current_date,
                    "company": comp,
                    "role": role,
                    "location": loc,
                    "url": link,
                    "row_number": ridx,
                })
    return rows


def run_combined_csv(urls: List[str], month_filter: str = "aug", output_csv: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    client = GoogleSheetsClient()

    combined: List[Dict[str, Any]] = []

    for sheet_url in urls:
        sheet_id, gid = parse_sheet_id_and_gid(sheet_url)
        meta = client.get_spreadsheet(sheet_id)
        sheet_title = (meta.get("properties", {}) or {}).get("title")
        sheets = meta.get("sheets", []) or []

        # If this spreadsheet has the three known tabs, parse all of them
        tab_names = [s.get("properties", {}).get("title") for s in sheets]
        tab_names_lc = { (t or "").lower(): (t or "") for t in tab_names }
        desired_order = ["The FinTech PM", "Top 1% PM", "The Remote PM"]
        desired_lc = [d.lower() for d in desired_order]
        if any(d in tab_names_lc for d in desired_lc):
            for d in desired_lc:
                if d in tab_names_lc:
                    tab = tab_names_lc[d]
                else:
                    continue
                values = client.get_values(sheet_id, tab)
                rows = parse_generic(values)
                for r in rows:
                    r.setdefault("sheet_name", sheet_title)
                    r.setdefault("tab_title", tab)
                combined.extend(rows)
            continue

        # Otherwise, select tab by month
        selected = select_tab_by_month(sheets, month_filter)
        if not selected and gid:
            for s in sheets:
                pr = s.get("properties", {})
                if str(pr.get("sheetId")) == str(gid):
                    selected = s
                    break
        if not selected:
            continue
        tab_title = selected.get("properties", {}).get("title")
        values = client.get_values(sheet_id, tab_title)
        rows = parse_generic(values)
        for r in rows:
            r.setdefault("sheet_name", sheet_title)
            r.setdefault("tab_title", tab_title)
        combined.extend(rows)

    # Dedupe by url preserving first
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for r in combined:
        u = r.get("url", "")
        if u and u not in seen:
            seen.add(u)
            uniq.append(r)

    if not output_csv:
        ts = now.strftime("%Y%m%d-%H%M%S")
        output_csv = f"./storage/ingest/google_sheets/{ts}/combined_august.csv"

    write_csv(output_csv, uniq, ["date","company","role","location","url","sheet_name","tab_title","row_number"])
    return {"total": len(combined), "unique": len(uniq), "output_csv": output_csv}

