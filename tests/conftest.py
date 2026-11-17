"""Shared fixtures: a deterministic fake provider producing yfinance-shaped output."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ma_crossover.config import AssetConfig, Config, DataConfig, ValidationConfig
from ma_crossover.data.calendars import expected_sessions

SEED = 42


def make_raw(
    calendar: str,
    start: date,
    end: date,
    *,
    dividend_yield: float = 0.0,
    seed: int = SEED,
) -> pd.DataFrame:
    """Synthetic daily bars in the exact shape yfinance returns (auto_adjust=False)."""
    sessions = expected_sessions("crypto" if calendar == "crypto" else "XNYS", start, end)
    tz = "UTC" if calendar == "crypto" else "America/New_York"
    index = pd.DatetimeIndex(sessions.tz_localize(None), name="Date").tz_localize(tz)
    rng = np.random.default_rng(seed)
    n = len(index)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    open_ = close * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    # Back-adjustment: factor grows towards 1 at the end (past scaled down).
    factor = np.exp(-dividend_yield / 252 * np.arange(n)[::-1])
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Adj Close": close * factor,
            "Volume": rng.integers(1_000, 10_000, n).astype("float64"),
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=index,
    )


@dataclass
class FakeSource:
    name: str = "fake"
    calls: list[tuple[str, date, date]] = field(default_factory=list)
    calendars: dict[str, str] = field(default_factory=dict)

    def fetch(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        self.calls.append((ticker, start, end))
        cal = self.calendars.get(ticker, "XNYS")
        return make_raw(cal, start, end, dividend_yield=0.0 if cal == "crypto" else 0.015)

    def version(self) -> str:
        return "0.0-test"


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    assets = {
        "btc": AssetConfig("btc", "BTC-USD", "crypto", "crypto", date(2023, 1, 1)),
        "spy": AssetConfig("spy", "SPY", "XNYS", "etf", date(2023, 1, 3)),
    }
    data = DataConfig(
        source="fake",
        end=date(2024, 6, 28),
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        assets=assets,
    )
    return Config(data=data, validation=ValidationConfig())


@pytest.fixture
def source() -> FakeSource:
    return FakeSource(calendars={"BTC-USD": "crypto", "SPY": "XNYS"})
