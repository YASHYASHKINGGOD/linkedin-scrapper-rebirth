from __future__ import annotations
import io
import os
from typing import List
import csv

from src.extractor.common.io import write_csv


def test_write_csv_tmp(tmp_path):
    rows = [
        {"a": 1, "b": "x", "c": "ignore"},
        {"a": 2, "b": "y"},
    ]
    cols = ["a", "b"]
    out = tmp_path / "foo" / "bar.csv"
    write_csv(str(out), rows, cols)
    assert out.exists()
    content = out.read_text(encoding="utf-8").splitlines()
    assert content[0] == "a,b"
    assert content[1] == "1,x"
    assert content[2] == "2,y"

