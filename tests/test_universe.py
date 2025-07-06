import pandas as pd
from pathlib import Path
from scrapers import universe as uni


def test_load_sp1500(tmp_path):
    path = tmp_path / "sp1500.csv"
    pd.DataFrame({"symbol": ["AAA", "BBB"]}).to_csv(path, index=False)
    old = uni.DATA_DIR
    uni.DATA_DIR = tmp_path
    try:
        assert uni.load_sp1500() == ["AAA", "BBB"]
    finally:
        uni.DATA_DIR = old


def test_load_russell2000(tmp_path):
    path = tmp_path / "russell2000.csv"
    pd.DataFrame({"symbol": ["CCC", "DDD"]}).to_csv(path, index=False)
    old = uni.DATA_DIR
    uni.DATA_DIR = tmp_path
    try:
        assert uni.load_russell2000() == ["CCC", "DDD"]
    finally:
        uni.DATA_DIR = old
