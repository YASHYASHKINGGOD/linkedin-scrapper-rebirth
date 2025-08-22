from __future__ import annotations
from typing import Optional, Dict, Any


def select_tab_by_month(sheets: list[dict], month_filter: str) -> Optional[Dict[str, Any]]:
    """Select the tab whose title contains the month_filter (case-insensitive).

    If multiple tabs match, choose the one with the highest 'index'.
    sheets: list of {'properties': {'title': str, 'index': int, 'sheetId': int, ...}}
    Returns the matching sheet dict or None.
    """
    month = (month_filter or "").lower()
    if not month:
        return None
    matches = [s for s in sheets if month in str(s.get("properties", {}).get("title", "")).lower()]
    if not matches:
        return None
    # Choose the one with the highest index (most recent/last)
    matches.sort(key=lambda s: int(s.get("properties", {}).get("index", -1)))
    return matches[-1]


def resolve_tab_gid(sheet_props: Dict[str, Any]) -> Optional[str]:
    try:
        return str(sheet_props.get("properties", {}).get("sheetId"))
    except Exception:
        return None

