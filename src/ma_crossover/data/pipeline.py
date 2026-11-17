"""Fetch (or read from cache) -> normalise -> trim -> validate -> store processed Parquet."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from ma_crossover.config import AssetConfig, Config
from ma_crossover.data.cache import Manifest, RawStore, write_parquet_atomic
from ma_crossover.data.schema import normalize
from ma_crossover.data.sources import PriceSource
from ma_crossover.data.validation import ValidationReport, validate_prices

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadedAsset:
    asset: AssetConfig
    prices: pd.DataFrame
    report: ValidationReport
    manifest: Manifest
    from_cache: bool
    processed_path: Path


def last_complete_date(end: date, today: date) -> date:
    """Last date whose daily bar is closed: never today (crypto closes at 24:00 UTC, equities
    at 16:00 NY), so a run during the day cannot ingest a partial bar."""
    return min(end, today - timedelta(days=1))


def load_asset(
    asset: AssetConfig,
    cfg: Config,
    source: PriceSource,
    *,
    refresh: bool = False,
    strict: bool = True,
    today: date | None = None,
) -> LoadedAsset:
    today = today or datetime.now(UTC).date()
    store = RawStore(cfg.data.raw_dir)
    start, end = asset.start, cfg.data.end

    from_cache = store.exists(asset.ticker, start, end) and not refresh
    if from_cache:
        raw, manifest = store.read(asset.ticker, start, end)
        log.info(
            "%s: cache hit (%s, downloaded %s)", asset.name, asset.ticker, manifest.downloaded_at
        )
    else:
        log.info(
            "%s: downloading %s [%s, %s] from %s", asset.name, asset.ticker, start, end, source.name
        )
        raw = source.fetch(asset.ticker, start, end)
        manifest = store.write(
            raw,
            ticker=asset.ticker,
            start=start,
            end=end,
            source=source.name,
            source_version=source.version(),
        )

    effective_end = last_complete_date(end, today)
    prices = normalize(raw)
    prices = prices.loc[pd.Timestamp(start, tz="UTC") : pd.Timestamp(effective_end, tz="UTC")]

    report = validate_prices(
        prices,
        name=asset.name,
        calendar=asset.calendar,
        kind=asset.kind,
        start=start,
        end=effective_end,
        cfg=cfg.validation,
    )
    log.info("%s", report.summary())
    if strict:
        report.raise_if_errors()

    out = cfg.data.processed_dir / f"{asset.name}.parquet"
    write_parquet_atomic(prices, out)
    out.with_suffix(".json").write_text(
        json.dumps(
            {
                "asset": asset.name,
                "ticker": asset.ticker,
                "calendar": asset.calendar,
                "kind": asset.kind,
                "raw_sha256": manifest.sha256,
                "rows": len(prices),
                "first": f"{report.first:%Y-%m-%d}" if report.first is not None else None,
                "last": f"{report.last:%Y-%m-%d}" if report.last is not None else None,
                "errors": len(report.errors),
                "warnings": len(report.warnings),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return LoadedAsset(asset, prices, report, manifest, from_cache, out)


def load_all(
    cfg: Config,
    source: PriceSource,
    *,
    names: list[str] | None = None,
    refresh: bool = False,
    strict: bool = True,
    today: date | None = None,
) -> dict[str, LoadedAsset]:
    selected = names or list(cfg.data.assets)
    unknown = set(selected) - set(cfg.data.assets)
    if unknown:
        raise KeyError(f"unknown assets {sorted(unknown)}; known: {sorted(cfg.data.assets)}")
    return {
        n: load_asset(cfg.data.assets[n], cfg, source, refresh=refresh, strict=strict, today=today)
        for n in selected
    }


def read_processed(cfg: Config, name: str) -> pd.DataFrame:
    """Read a validated processed frame (what signals/backtests should consume)."""
    return pd.read_parquet(cfg.data.processed_dir / f"{name}.parquet", engine="pyarrow")
