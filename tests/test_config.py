from datetime import date
from pathlib import Path

import pytest

from ma_crossover.config import load_config, parse_config

ROOT = Path(__file__).resolve().parents[1]


def test_default_config_loads() -> None:
    cfg = load_config(ROOT / "config" / "default.yaml")
    assert set(cfg.data.assets) == {"btc", "spy", "spx"}
    assert cfg.data.assets["btc"].calendar == "crypto"
    assert cfg.data.assets["spy"].calendar == "XNYS"
    assert cfg.data.raw_dir == ROOT / "data" / "raw"
    assert isinstance(cfg.data.end, date)


def test_start_after_end_rejected() -> None:
    raw = {
        "data": {
            "source": "yfinance",
            "end": "2020-01-01",
            "raw_dir": "r",
            "processed_dir": "p",
            "assets": {
                "x": {"ticker": "X", "calendar": "XNYS", "kind": "etf", "start": "2021-01-01"}
            },
        }
    }
    with pytest.raises(ValueError, match="after end"):
        parse_config(raw)


def test_unknown_calendar_rejected() -> None:
    raw = {
        "data": {
            "source": "yfinance",
            "end": "2020-01-01",
            "raw_dir": "r",
            "processed_dir": "p",
            "assets": {
                "x": {"ticker": "X", "calendar": "LSE", "kind": "etf", "start": "2019-01-01"}
            },
        }
    }
    with pytest.raises(ValueError, match="calendar"):
        parse_config(raw)
