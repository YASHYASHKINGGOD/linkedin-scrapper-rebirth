from __future__ import annotations
import re
from typing import Tuple

SHEET_URL_RE = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/(?P<id>[^/]+)/edit(?:.*?gid=(?P<gid>\d+))?",
    re.IGNORECASE,
)


def parse_sheet_id_and_gid(url: str) -> Tuple[str, str | None]:
    m = SHEET_URL_RE.match(url)
    if not m:
        raise ValueError(f"Unrecognized Google Sheet URL: {url}")
    return m.group("id"), m.group("gid")
