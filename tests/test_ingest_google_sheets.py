from __future__ import annotations
from typing import List, Dict, Any, Optional

from src.ingest.google_sheets_run import run_google_sheets_ingest


class StubSheetsClient:
    def __init__(self, spreadsheets: Dict[str, Dict[str, Any]], values: Dict[tuple, list[list[str]]]):
        self._spreadsheets = spreadsheets
        self._values = values

    def get_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        return self._spreadsheets[spreadsheet_id]

    def get_values(self, spreadsheet_id: str, sheet_title: str):
        return self._values[(spreadsheet_id, sheet_title)]


def test_run_google_sheets_ingest_stub(monkeypatch, tmp_path):
    # Prepare stub data: two spreadsheets, Aug tabs selected; overlapping links across sheets
    ss1 = {
        "properties": {"title": "Sheet One"},
        "sheets": [
            {"properties": {"title": "July", "index": 0, "sheetId": 11}},
            {"properties": {"title": "Aug Data", "index": 1, "sheetId": 12}},
        ],
    }
    ss2 = {
        "properties": {"title": "Sheet Two"},
        "sheets": [
            {"properties": {"title": "Aug Recent", "index": 2, "sheetId": 21}},
        ],
    }

    values = {
        ("AAA", "Aug Data"): [["https://www.linkedin.com/jobs/view/1"], ["https://www.linkedin.com/company/x"], ["n/a"]],
        ("BBB", "Aug Recent"): [["https://www.linkedin.com/jobs/view/1"], ["https://www.linkedin.com/in/y"]],
    }

    stub = StubSheetsClient({"AAA": ss1, "BBB": ss2}, values)

    # Monkeypatch GoogleSheetsClient used inside run_google_sheets_ingest
    import src.ingest.google_sheets_run as mod

    class _FakeClient:
        def get_spreadsheet(self, spreadsheet_id: str):
            return stub.get_spreadsheet(spreadsheet_id)

        def get_values(self, spreadsheet_id: str, sheet_title: str):
            return stub.get_values(spreadsheet_id, sheet_title)

    mod.GoogleSheetsClient = _FakeClient  # type: ignore

    out = tmp_path / "out.csv"
    stats = run_google_sheets_ingest(
        urls=[
            "https://docs.google.com/spreadsheets/d/AAA/edit#gid=12",
            "https://docs.google.com/spreadsheets/d/BBB/edit#gid=21",
        ],
        month_filter="aug",
        output_csv=str(out),
    )

    assert stats["total_links_raw"] == 4
    assert stats["total_links_unique"] == 3  # deduped 'jobs/view/1'
    assert out.exists()
    content = out.read_text(encoding="utf-8").splitlines()
    assert content[0].split(",") == [
        "url",
        "source",
        "spreadsheet_id",
        "spreadsheet_title",
        "spreadsheet_url",
        "sheet_name",
        "tab_title",
        "tab_gid",
        "discovered_at",
    ]

