from __future__ import annotations
from src.extractor.google_sheets.select import select_tab_by_month, resolve_tab_gid


def test_select_tab_by_month_basic():
    sheets = [
        {"properties": {"title": "July Data", "index": 0, "sheetId": 111}},
        {"properties": {"title": "Aug Leads", "index": 1, "sheetId": 222}},
        {"properties": {"title": "Aug Final", "index": 2, "sheetId": 333}},
    ]
    sel = select_tab_by_month(sheets, "aug")
    assert sel["properties"]["sheetId"] == 333
    assert resolve_tab_gid(sel) == "333"


def test_select_tab_by_month_no_match():
    sheets = [
        {"properties": {"title": "June", "index": 0, "sheetId": 1}},
        {"properties": {"title": "July", "index": 1, "sheetId": 2}},
    ]
    assert select_tab_by_month(sheets, "aug") is None

