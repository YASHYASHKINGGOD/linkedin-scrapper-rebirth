from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Iterable, Dict, Any


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_jsonl(path: str, records: Iterable[Dict[str, Any]]) -> int:
    ensure_dir(os.path.dirname(path) or ".")
    count = 0
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            if "discovered_at" not in rec:
                rec["discovered_at"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count
