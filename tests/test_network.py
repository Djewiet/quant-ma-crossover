"""Live provider smoke test. Excluded by default; run with `uv run pytest -m network`."""

from datetime import date

import pytest

from ma_crossover.config import ValidationConfig
from ma_crossover.data.schema import normalize
from ma_crossover.data.sources import YFinanceSource
from ma_crossover.data.validation import validate_prices


@pytest.mark.network
@pytest.mark.parametrize(
    ("ticker", "calendar", "kind"),
    [("SPY", "XNYS", "etf"), ("^GSPC", "XNYS", "index"), ("BTC-USD", "crypto", "crypto")],
)
def test_yfinance_2023(ticker: str, calendar: str, kind: str) -> None:
    start, end = date(2023, 1, 3), date(2023, 12, 29)
    df = normalize(YFinanceSource().fetch(ticker, start, end))
    report = validate_prices(
        df,
        name=ticker,
        calendar=calendar,
        kind=kind,  # type: ignore[arg-type]
        start=start,
        end=end,
        cfg=ValidationConfig(),
    )
    assert report.ok, report.summary()
