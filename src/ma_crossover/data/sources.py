"""Price providers. Every provider returns *raw* output; normalisation happens in schema.py."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

import pandas as pd


class DataSourceError(RuntimeError):
    """The provider could not deliver data (network, rate limit, unknown ticker...)."""


class PriceSource(Protocol):
    """A daily OHLCV provider. `end` is inclusive."""

    name: str

    def fetch(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...

    def version(self) -> str: ...


class YFinanceSource:
    """Yahoo Finance via yfinance. Free, unofficial, fine for research, not for production.

    We request auto_adjust=False so that both the raw `Close` and `Adj Close` are kept,
    plus the dividend and split events (actions=True) for auditability.
    """

    name = "yfinance"

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def fetch(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        import yfinance as yf

        try:
            df: pd.DataFrame = yf.Ticker(ticker).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),  # yfinance `end` is exclusive
                interval="1d",
                auto_adjust=False,
                back_adjust=False,
                actions=True,
                repair=False,
                timeout=self._timeout,
                raise_errors=True,
            )
        except Exception as exc:  # yfinance raises many unrelated types
            raise DataSourceError(f"yfinance failed for {ticker}: {exc}") from exc
        if df.empty:
            raise DataSourceError(f"yfinance returned no rows for {ticker} [{start}, {end}]")
        return df

    def version(self) -> str:
        import yfinance as yf

        return str(yf.__version__)
