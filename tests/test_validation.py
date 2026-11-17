from datetime import date

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from ma_crossover.config import ValidationConfig
from ma_crossover.data.schema import normalize
from ma_crossover.data.validation import Severity, ValidationReport, validate_prices
from tests.conftest import make_raw

START, END = date(2023, 1, 3), date(2023, 12, 29)
CFG = ValidationConfig()


def _spy() -> pd.DataFrame:
    return normalize(make_raw("XNYS", START, END, dividend_yield=0.015))


def _check(df: pd.DataFrame, cfg: ValidationConfig = CFG, kind: str = "etf") -> ValidationReport:
    return validate_prices(
        df,
        name="t",
        calendar="XNYS",
        kind=kind,
        start=START,
        end=END,
        cfg=cfg,  # type: ignore[arg-type]
    )


def test_clean_data_passes() -> None:
    report = _check(_spy())
    assert report.ok, report.summary()
    assert report.issues == []


def test_clean_crypto_passes() -> None:
    df = normalize(make_raw("crypto", START, END))
    r = validate_prices(
        df, name="btc", calendar="crypto", kind="crypto", start=START, end=END, cfg=CFG
    )
    assert r.ok and not r.issues, r.summary()


def test_duplicates_are_errors() -> None:
    df = _spy()
    r = _check(pd.concat([df, df.iloc[[10]]]).sort_index())
    assert "duplicates" in r.checks(Severity.ERROR)


def test_unsorted_is_error() -> None:
    assert "index_sorted" in _check(_spy().iloc[::-1]).checks(Severity.ERROR)


def test_missing_session_error_then_tolerated() -> None:
    df = _spy().drop(index=pd.Timestamp("2023-06-15", tz="UTC"))
    r = _check(df)
    assert "missing_sessions" in r.checks(Severity.ERROR)
    assert r.errors[0].dates == (pd.Timestamp("2023-06-15", tz="UTC"),)
    r2 = _check(df, ValidationConfig(max_missing_sessions=1))
    assert r2.ok and "missing_sessions" in r2.checks(Severity.WARNING)


def test_truncated_tail_is_detected() -> None:
    assert "missing_sessions" in _check(_spy().iloc[:-5]).checks(Severity.ERROR)


def test_weekend_bar_on_equity_is_error() -> None:
    df = _spy()
    sat = df.iloc[[5]].copy()
    sat.index = pd.DatetimeIndex([pd.Timestamp("2023-01-14", tz="UTC")], name="date")
    assert "extra_sessions" in _check(pd.concat([df, sat]).sort_index()).checks(Severity.ERROR)


def test_nan_and_nonpositive_close() -> None:
    df = _spy()
    df.iloc[3, df.columns.get_loc("close")] = np.nan
    df.iloc[4, df.columns.get_loc("adj_close")] = 0.0
    errs = _check(df).checks(Severity.ERROR)
    assert {"nan_close", "nonpositive_adj_close"} <= errs


def test_non_utc_index_is_error() -> None:
    df = _spy()
    df.index = df.index.tz_convert("America/New_York")
    assert "index_tz" in _check(df).checks(Severity.ERROR)


def test_adj_ratio_above_one_is_error() -> None:
    df = _spy()
    df["adj_close"] = df["close"] * 1.01
    assert "adj_ratio_range" in _check(df).checks(Severity.ERROR)


def test_unadjusted_etf_warns() -> None:
    df = normalize(make_raw("XNYS", date(2022, 1, 3), END, dividend_yield=0.0))
    r = validate_prices(
        df, name="t", calendar="XNYS", kind="etf", start=date(2022, 1, 3), end=END, cfg=CFG
    )
    assert "adj_ratio_missing" in r.checks(Severity.WARNING)


def test_index_with_adjustment_warns() -> None:
    assert "adj_ratio_unexpected" in _check(_spy(), kind="index").checks(Severity.WARNING)


def test_extreme_return_and_stale_are_warnings() -> None:
    df = _spy()
    df.iloc[100:, df.columns.get_loc("adj_close")] *= 0.6
    df.iloc[150:157, df.columns.get_loc("close")] = 123.0
    r = _check(df)
    assert {"extreme_returns", "stale_prices"} <= r.checks(Severity.WARNING)


def test_late_start_warns() -> None:
    df = _spy().loc["2023-03-01":]
    r = _check(df)
    assert "late_start" in r.checks(Severity.WARNING)
    assert "missing_sessions" not in r.checks()


@settings(max_examples=30, deadline=None)
@given(
    seed=st.integers(0, 2**32 - 1),
    yield_=st.floats(0.0, 0.05),
    cal=st.sampled_from(["crypto", "XNYS"]),
)
def test_any_wellformed_series_validates(seed: int, yield_: float, cal: str) -> None:
    kind = "crypto" if cal == "crypto" else "etf"
    y = 0.0 if cal == "crypto" else yield_
    df = normalize(make_raw(cal, START, END, dividend_yield=y, seed=seed))
    cfg = ValidationConfig(extreme_return_threshold=1.0, max_stale_days=1000)
    r = validate_prices(
        df,
        name="p",
        calendar=cal,
        kind=kind,
        start=START,
        end=END,  # type: ignore[arg-type]
        cfg=cfg,
    )
    assert r.ok, r.summary()
