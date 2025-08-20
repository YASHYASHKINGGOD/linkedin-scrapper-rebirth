from __future__ import annotations
import re
from typing import Iterable, List

LINK_RE = re.compile(r"https?://(www\.)?linkedin\.com/[^\s]+", re.IGNORECASE)


def extract_linkedin_links_from_sheet(sheet_values: Iterable[Iterable[str | None]]) -> List[str]:
    """Scan a 2D array (rows x columns) of strings for LinkedIn URLs.

    - sheet_values: result of a Sheets API values.get(...).get('values', [])
    - returns list of unique links (preserving first-seen order)
    """
    seen = set()
    out: List[str] = []
    for row in sheet_values:
        for cell in row:
            if not cell:
                continue
            for match in LINK_RE.findall(str(cell)):
                if match not in seen:
                    seen.add(match)
                    out.append(match)
    return out
