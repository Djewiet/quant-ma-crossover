"""Canonical daily-bar schema and normalisation of provider output.

Canonical frame:
    index   : DatetimeIndex named "date", tz=UTC, at 00:00 -> the *trading date* of the bar
    columns : open, high, low, close, adj_close, volume, dividends, splits (float64)

Note on the timestamp: for an equity the bar of date D closes at 16:00 New York on D; for
BTC on Yahoo the bar of date D covers [D 00:00 UTC, D+1 00:00 UTC). Same label, different
closing instants (~4-5h apart). See calendars.align_on_sessions.
"""

from __future__ import annotations

import pandas as pd

PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "adj_close")
COLUMNS: tuple[str, ...] = (*PRICE_COLUMNS, "volume", "dividends", "splits")

_RENAME: dict[str, str] = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}


class SchemaError(ValueError):
    """Provider output cannot be mapped to the canonical schema."""


def to_trading_dates(index: pd.Index) -> pd.DatetimeIndex:
    """Map provider timestamps to tz-aware UTC midnights of the local trading date.

    A tz-aware stamp is first read in its own (exchange) timezone: 2024-03-15 00:00 America/New_York
    is the 2024-03-15 session, not 2024-03-15 04:00 UTC.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise SchemaError(f"expected a DatetimeIndex, got {type(index).__name__}")
    local = index.tz_localize(None) if index.tz is not None else index
    if not (local == local.normalize()).all():
        bad = local[local != local.normalize()][:3]
        raise SchemaError(f"daily bars must be stamped at local midnight, got e.g. {list(bad)}")
    # freq=None: the trading-date index is irregular by nature; never carry an inferred freq.
    # Canonical: ns resolution, no inferred freq (trading dates are irregular by nature).
    values = local.as_unit("ns").to_numpy()
    return pd.DatetimeIndex(values, name="date").tz_localize("UTC")


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename columns, coerce dtypes, convert the index. Never drops or fills rows."""
    df = raw.rename(columns=_RENAME)
    missing = [c for c in ("open", "high", "low", "close", "adj_close") if c not in df.columns]
    if missing:
        raise SchemaError(
            f"missing columns {missing}; was the download made with auto_adjust=False?"
        )
    for col in ("volume", "dividends", "splits"):
        if col not in df.columns:
            df[col] = 0.0
    out = df.loc[:, list(COLUMNS)].astype("float64")
    out.index = to_trading_dates(df.index)
    return out.sort_index(kind="stable")
