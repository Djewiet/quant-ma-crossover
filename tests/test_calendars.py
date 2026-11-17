from datetime import date

import pandas as pd

from ma_crossover.data.calendars import align_on_sessions, expected_sessions


def test_crypto_calendar_is_every_day() -> None:
    assert len(expected_sessions("crypto", date(2024, 1, 1), date(2024, 12, 31))) == 366


def test_nyse_2024_has_252_sessions() -> None:
    assert len(expected_sessions("XNYS", date(2024, 1, 1), date(2024, 12, 31))) == 252


def test_nyse_special_closures() -> None:
    s = expected_sessions("XNYS", date(2001, 9, 1), date(2025, 1, 31))
    for closed in ("2001-09-11", "2012-10-29", "2018-12-05", "2025-01-09", "2024-07-04"):
        assert pd.Timestamp(closed, tz="UTC") not in s
    assert pd.Timestamp("2001-09-17", tz="UTC") in s


def test_empty_range() -> None:
    assert len(expected_sessions("XNYS", date(2024, 1, 2), date(2024, 1, 1))) == 0


def test_align_samples_crypto_on_equity_sessions_without_ffill() -> None:
    days = expected_sessions("crypto", date(2024, 3, 1), date(2024, 3, 11))  # Fri..Mon+
    btc = pd.Series(range(len(days)), index=days, dtype="float64")
    nyse = expected_sessions("XNYS", date(2024, 3, 1), date(2024, 3, 11))
    spy = pd.Series(1.0, index=nyse)
    out = align_on_sessions({"btc": btc, "spy": spy}, nyse)
    assert out.index.equals(nyse)
    # Friday 03-01 -> Monday 03-04: BTC return spans the weekend (3 calendar days).
    assert out.loc["2024-03-04", "btc"] - out.loc["2024-03-01", "btc"] == 3
    assert not out.isna().any().any()
