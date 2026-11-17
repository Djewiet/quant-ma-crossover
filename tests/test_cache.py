from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ma_crossover.data.cache import CacheIntegrityError, RawStore
from tests.conftest import make_raw


def test_roundtrip_preserves_tz_and_values(tmp_path: Path) -> None:
    raw = make_raw("XNYS", date(2024, 1, 2), date(2024, 2, 29))
    store = RawStore(tmp_path)
    m = store.write(
        raw,
        ticker="^GSPC",
        start=date(2024, 1, 2),
        end=date(2024, 2, 29),
        source="fake",
        source_version="1",
    )
    assert store.path("^GSPC", date(2024, 1, 2), date(2024, 2, 29)).parent.name == "GSPC"
    back, m2 = store.read("^GSPC", date(2024, 1, 2), date(2024, 2, 29))
    pd.testing.assert_frame_equal(back, raw, check_freq=False)
    assert m == m2 and m.n_rows == len(raw)
    assert str(back.index.tz) == "America/New_York"


def test_tampered_file_detected(tmp_path: Path) -> None:
    raw = make_raw("crypto", date(2024, 1, 1), date(2024, 1, 31))
    store = RawStore(tmp_path)
    store.write(
        raw,
        ticker="BTC-USD",
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
        source="fake",
        source_version="1",
    )
    p = store.path("BTC-USD", date(2024, 1, 1), date(2024, 1, 31))
    (raw * 2).to_parquet(p)
    with pytest.raises(CacheIntegrityError):
        store.read("BTC-USD", date(2024, 1, 1), date(2024, 1, 31))
