# quant-ma-crossover

Does the classic **50/200-day moving-average crossover** ("golden cross / death cross") beat
**buy & hold** on **Bitcoin** and the **S&P 500** once trading costs are included?

This repo answers that question with production-grade data hygiene: versioned raw downloads,
explicit trading calendars, automated data-quality checks and tests that guard against
look-ahead bias.

> Status: **step 1/5, data pipeline.** Signals, backtest and results come next.

## Data

| Asset | Ticker | Calendar | Price used | Why |
|---|---|---|---|---|
| Bitcoin | `BTC-USD` | 24/7, 365 bars/year (UTC days) | `adj_close` (= close) | Yahoo aggregate quote, from 2014-09-17 |
| S&P 500 ETF | `SPY` | NYSE, ~252 sessions/year | `adj_close` (dividends reinvested) | investable, total-return proxy |
| S&P 500 index | `^GSPC` | NYSE | `close` (price only) | long history, reference only |

Source: Yahoo Finance via `yfinance` (free, unofficial: good for research, not for production).
Equity prices are **adjusted for splits and dividends**. Details and pitfalls (in French):
[`docs/donnees-de-marche.md`](docs/donnees-de-marche.md).

### Pipeline

```
yfinance ──> data/raw/<ticker>/<start>_<end>.parquet  (+ .json manifest: date, version, sha256)
         ──> normalise (UTC trading dates, canonical columns)
         ──> drop today's unfinished bar
         ──> validate (calendar gaps, duplicates, OHLC, adjustment factor, outliers)
         ──> data/processed/<asset>.parquet
```

Checks run on every load; any error stops the pipeline (`--no-strict` to override):

- index: UTC, midnight-stamped, sorted, no duplicates
- calendar: every NYSE session (via `exchange_calendars`) or every calendar day for crypto is
  present, and nothing falls on a non-trading day
- values: no NaN / non-positive close, coherent OHLC
- adjustment factor `adj_close / close` in (0, 1], non-decreasing, equal to 1 for BTC and `^GSPC`
- warnings: daily moves above 25 %, runs of stale prices, history starting later than requested

## Reproduce

```bash
uv sync
uv run ma-crossover fetch                 # downloads once, then reads the cache
uv run ma-crossover fetch --refresh       # force a new download
uv run ruff check . && uv run mypy && uv run pytest
uv run pytest -m network                  # live smoke test against Yahoo
```

All parameters (tickers, dates, tolerances) live in [`config/default.yaml`](config/default.yaml).
The end date is fixed for reproducibility. `data/` is git-ignored: anyone can rebuild it.

## Layout

```
config/default.yaml        all parameters
src/ma_crossover/
  config.py                typed YAML config
  cli.py                   `ma-crossover` entry point
  data/
    sources.py             provider protocol + yfinance implementation
    cache.py               immutable raw store with sha256 manifest
    schema.py              canonical daily-bar schema
    calendars.py           NYSE / crypto calendars, cross-asset alignment (no forward-fill)
    validation.py          data-quality report
    pipeline.py            fetch -> normalise -> validate -> store
tests/                     offline tests (fake provider) + hypothesis property tests
```

## Roadmap

1. ✅ Data: repo, download, cache, validation
2. Concepts: returns, volatility, moving averages
3. Backtest: signal (executed at t+1), positions, equity curve vs buy & hold
4. Pitfalls: costs, slippage, look-ahead test, parameter sensitivity, out-of-sample
5. Results and write-up

## Limitations

- Yahoo data is unofficial and can be revised; raw downloads are kept immutable with a checksum.
- `BTC-USD` is an aggregated quote, not a tradable venue; its history starts in Sept 2014.
- Picking BTC and the S&P 500 today is itself a survivorship choice (see docs).
