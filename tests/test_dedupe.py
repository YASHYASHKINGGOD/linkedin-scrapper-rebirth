from __future__ import annotations
from src.extractor.common.dedupe import dedupe_preserve_order


def test_dedupe_preserve_order():
    data = ["a", "b", "a", "c", "b", "d"]
    assert dedupe_preserve_order(data) == ["a", "b", "c", "d"]

