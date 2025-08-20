from src.extractor.google_sheets.urls import parse_sheet_id_and_gid


def test_parse_sheet_with_gid():
    url = "https://docs.google.com/spreadsheets/d/14OmQuYyreTa_ehui2vGXbydNpMsJCrCTArolMozuPG0/edit?gid=1790709853#gid=1790709853"
    sheet_id, gid = parse_sheet_id_and_gid(url)
    assert sheet_id == "14OmQuYyreTa_ehui2vGXbydNpMsJCrCTArolMozuPG0"
    assert gid == "1790709853"


def test_parse_sheet_without_gid():
    url = "https://docs.google.com/spreadsheets/d/AAAABBBBCCCC/edit"
    sheet_id, gid = parse_sheet_id_and_gid(url)
    assert sheet_id == "AAAABBBBCCCC"
    assert gid is None
