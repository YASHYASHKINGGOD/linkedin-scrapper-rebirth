from src.extractor.google_sheets.links import extract_linkedin_links_from_sheet


def test_extract_links_matrix():
    matrix = [
        ["Check this: https://www.linkedin.com/jobs/view/123"],
        ["No link here"],
        ["Two: https://linkedin.com/in/someone https://www.linkedin.com/company/foo"],
        [None],
    ]
    links = extract_linkedin_links_from_sheet(matrix)
    assert links == [
        "https://www.linkedin.com/jobs/view/123",
        "https://linkedin.com/in/someone",
        "https://www.linkedin.com/company/foo",
    ]
