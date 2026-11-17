"""Trading calendars and cross-asset alignment."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

import pandas as pd

from ma_crossover.config import CalendarName

# Annualisation factors: number of bars per year for each calendar.
PERIODS_PER_YEAR: dict[str, int] = {"crypto": 365, "XNYS": 252}


@lru_cache(maxsize=8)
def _exchange_calendar(name: str) -> Any:
    import exchange_calendars as xcals

    return xcals.get_calendar(name, start="1990-01-01")


def expected_sessions(calendar: CalendarName, start: date, end: date) -> pd.DatetimeIndex:
    """Trading dates in [start, end] as UTC midnights.

    crypto -> every calendar day; XNYS -> NYSE sessions (holidays and special closures such as
    2001-09-11..14, 2012-10-29..30 and national days of mourning are excluded).
    """
    if start > end:
        return pd.DatetimeIndex([], tz="UTC", name="date")
    if calendar == "crypto":
        return pd.date_range(start, end, freq="D", tz="UTC", name="date")
    sessions = _exchange_calendar(calendar).sessions_in_range(
        pd.Timestamp(start), pd.Timestamp(end)
    )
    idx = pd.DatetimeIndex(sessions, name="date")
    return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")


def align_on_sessions(
    series: dict[str, pd.Series], sessions: pd.DatetimeIndex, *, dropna: bool = True
) -> pd.DataFrame:
    """Put several price series on a common set of trading dates, WITHOUT forward-filling.

    Typical use: BTC (7/7) next to SPY (5/7) -> pass the NYSE sessions. BTC is sampled on those
    dates, so a Friday->Monday BTC return correctly includes the weekend move. Forward-filling
    equities onto weekends instead would fabricate zero returns and bias volatility down.
    """
    frame = pd.DataFrame({name: s.reindex(sessions) for name, s in series.items()})
    frame.index.name = "date"
    return frame.dropna(how="any") if dropna else frame
