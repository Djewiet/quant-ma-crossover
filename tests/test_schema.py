import random
from datetime import date

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from ma_crossover.data.schema import COLUMNS, SchemaError, normalize, to_trading_dates
from tests.conftest import make_raw


def test_exchange_midnight_maps_to_same_trading_date() -> None:
    # 00:00 New York == 04:00/05:00 UTC; a naive tz_convert would keep the date here but
    # would shift a Asia/Tokyo stamp to the previous day. We read the local date instead.
    for tz in ("America/New_York", "Asia/Tokyo", "UTC"):
        idx = pd.DatetimeIndex(["2024-03-15", "2024-03-18"]).tz_localize(tz)
        out = to_trading_dates(idx)
        assert str(out.tz) == "UTC"
        assert list(out.strftime("%Y-%m-%d")) == ["2024-03-15", "2024-03-18"]
        assert (out == out.normalize()).all()


def test_intraday_stamp_rejected() -> None:
    idx = pd.DatetimeIndex(["2024-03-15 09:30"]).tz_localize("America/New_York")
    with pytest.raises(SchemaError, match="midnight"):
        to_trading_dates(idx)


def test_missing_adj_close_rejected() -> None:
    raw = make_raw("XNYS", date(2024, 1, 2), date(2024, 1, 31)).drop(columns="Adj Close")
    with pytest.raises(SchemaError, match="auto_adjust"):
        normalize(raw)


def test_normalize_schema() -> None:
    df = normalize(make_raw("XNYS", date(2024, 1, 2), date(2024, 3, 28)))
    assert tuple(df.columns) == COLUMNS
    assert (df.dtypes == "float64").all()
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing


@given(st.randoms(use_true_random=False))
def test_normalize_is_order_invariant(rnd: random.Random) -> None:
    raw = make_raw("crypto", date(2024, 1, 1), date(2024, 2, 15))
    positions = list(range(len(raw)))
    rnd.shuffle(positions)
    pd.testing.assert_frame_equal(normalize(raw), normalize(raw.iloc[positions]))
