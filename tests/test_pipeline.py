from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from ma_crossover.config import Config
from ma_crossover.data.pipeline import last_complete_date, load_all, load_asset, read_processed
from ma_crossover.data.validation import DataValidationError
from tests.conftest import FakeSource, make_raw

TODAY = date(2026, 11, 16)


def test_fetch_then_cache(cfg: Config, source: FakeSource) -> None:
    first = load_all(cfg, source, today=TODAY)
    assert len(source.calls) == 2 and not first["btc"].from_cache
    second = load_all(cfg, source, today=TODAY)
    assert len(source.calls) == 2 and second["btc"].from_cache
    pd.testing.assert_frame_equal(first["spy"].prices, second["spy"].prices)
    load_all(cfg, source, names=["spy"], refresh=True, today=TODAY)
    assert len(source.calls) == 3


def test_processed_output(cfg: Config, source: FakeSource) -> None:
    loaded = load_all(cfg, source, today=TODAY)
    for name, item in loaded.items():
        assert item.report.ok, item.report.summary()
        stored = read_processed(cfg, name)
        pd.testing.assert_frame_equal(stored, item.prices, check_freq=False)
        assert item.processed_path.with_suffix(".json").exists()
    assert loaded["btc"].prices.index[-1] == pd.Timestamp("2024-06-28", tz="UTC")


def test_incomplete_bar_of_today_is_dropped(cfg: Config, source: FakeSource) -> None:
    today = date(2024, 6, 20)
    item = load_asset(cfg.data.assets["btc"], cfg, source, today=today)
    assert item.prices.index[-1] == pd.Timestamp("2024-06-19", tz="UTC")
    assert item.report.ok
    assert last_complete_date(date(2024, 6, 28), today) == date(2024, 6, 19)


def test_unknown_asset(cfg: Config, source: FakeSource) -> None:
    with pytest.raises(KeyError):
        load_all(cfg, source, names=["eth"], today=TODAY)


class _HoleySource(FakeSource):
    def fetch(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        raw = make_raw("XNYS", start, end, dividend_yield=0.01)
        return raw.drop(raw.index[50:53])


def test_strict_mode_blocks_bad_data(cfg: Config) -> None:
    src = _HoleySource()
    with pytest.raises(DataValidationError, match="missing_sessions"):
        load_asset(cfg.data.assets["spy"], cfg, src, today=TODAY)
    item = load_asset(cfg.data.assets["spy"], cfg, src, strict=False, today=TODAY)
    assert not item.report.ok


def test_tolerance_from_config(cfg: Config) -> None:
    lenient = replace(cfg, validation=replace(cfg.validation, max_missing_sessions=3))
    item = load_asset(lenient.data.assets["spy"], lenient, _HoleySource(), today=TODAY)
    assert item.report.ok and item.report.warnings
