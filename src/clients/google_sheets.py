from __future__ import annotations
import os
from typing import Any, Dict, List
from src.extractor.google_sheets.client import ensure_credentials, get_sheets_service


class GoogleSheetsClient:
    def __init__(self):
        self._svc = get_sheets_service(ensure_credentials())

    def get_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        req = self._svc.get(spreadsheetId=spreadsheet_id)
        return req.execute()

    def get_values(self, spreadsheet_id: str, sheet_title: str) -> List[List[str]]:
        a1 = f"{sheet_title}!A:Z"
        resp = (
            self._svc.values()
            .get(spreadsheetId=spreadsheet_id, range=a1, majorDimension="ROWS")
            .execute()
        )
        return resp.get("values", [])

