"""Data-quality checks on canonical daily bars.

Errors make the data unusable for a backtest (duplicates, unsorted index, NaN or non-positive
closes, missing sessions beyond tolerance). Warnings need a human look but are often genuine
market events (e.g. 2020-03-16 S&P -12%, BTC -37% on 2020-03-12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd

from ma_crossover.config import AssetKind, CalendarName, ValidationConfig
from ma_crossover.data.calendars import expected_sessions
from ma_crossover.data.schema import COLUMNS


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Issue:
    check: str
    severity: Severity
    message: str
    dates: tuple[pd.Timestamp, ...] = ()


class DataValidationError(ValueError):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__(report.summary())
        self.report = report


@dataclass(slots=True)
class ValidationReport:
    name: str
    n_rows: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def checks(self, severity: Severity | None = None) -> set[str]:
        return {i.check for i in self.issues if severity is None or i.severity is severity}

    def summary(self) -> str:
        span = f"{self.first:%Y-%m-%d} -> {self.last:%Y-%m-%d}" if self.first is not None else "-"
        lines = [
            f"[{self.name}] {self.n_rows} rows, {span}: "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        ]
        lines += [f"  {i.severity.upper():7} {i.check}: {i.message}" for i in self.issues]
        return "\n".join(lines)

    def raise_if_errors(self) -> None:
        if self.errors:
            raise DataValidationError(self)


def _dates(idx: pd.Index, limit: int = 10) -> tuple[pd.Timestamp, ...]:
    return tuple(pd.Timestamp(t) for t in idx[:limit])


def _fmt(dates: tuple[pd.Timestamp, ...]) -> str:
    return ", ".join(f"{d:%Y-%m-%d}" for d in dates)


def _longest_constant_runs(s: pd.Series, min_len: int) -> list[tuple[pd.Timestamp, int]]:
    """Start date and length of runs of identical consecutive values with length >= min_len."""
    run_id = (s != s.shift()).cumsum()
    lengths = s.groupby(run_id).transform("size")
    starts = s.index[(lengths >= min_len) & (run_id != run_id.shift())]
    return [(pd.Timestamp(t), int(lengths.loc[t])) for t in starts]


def validate_prices(
    df: pd.DataFrame,
    *,
    name: str,
    calendar: CalendarName,
    kind: AssetKind,
    start: date,
    end: date,
    cfg: ValidationConfig,
) -> ValidationReport:
    """Run every check on a canonical frame (see schema.py). Never mutates df."""
    idx = df.index
    report = ValidationReport(
        name=name,
        n_rows=len(df),
        first=pd.Timestamp(idx.min()) if len(df) else None,
        last=pd.Timestamp(idx.max()) if len(df) else None,
    )
    add = report.issues.append
    err, warn = Severity.ERROR, Severity.WARNING
    tol = cfg.price_rel_tol

    if df.empty:
        add(Issue("empty", err, "no rows"))
        return report

    # --- index ---------------------------------------------------------------------------
    if not isinstance(idx, pd.DatetimeIndex) or str(idx.tz) != "UTC":
        add(Issue("index_tz", err, f"index must be a UTC DatetimeIndex, got {idx.dtype}"))
        return report
    if not (idx == idx.normalize()).all():
        add(Issue("index_midnight", err, "timestamps must be at 00:00 UTC (trading dates)"))
    if not idx.is_monotonic_increasing:
        add(Issue("index_sorted", err, "index is not sorted ascending"))
    dup = idx[idx.duplicated()]
    if len(dup):
        add(
            Issue(
                "duplicates", err, f"{len(dup)} duplicated dates: {_fmt(_dates(dup))}", _dates(dup)
            )
        )

    missing_cols = [c for c in COLUMNS if c not in df.columns]
    if missing_cols:
        add(Issue("columns", err, f"missing columns {missing_cols}"))
        return report

    # --- values ----------------------------------------------------------------------------
    for col in ("close", "adj_close"):
        nan_idx = idx[df[col].isna().to_numpy()]
        if len(nan_idx):
            add(
                Issue(
                    f"nan_{col}",
                    err,
                    f"{len(nan_idx)} NaN in {col}: {_fmt(_dates(nan_idx))}",
                    _dates(nan_idx),
                )
            )
        nonpos = idx[(df[col] <= 0).to_numpy()]
        if len(nonpos):
            add(
                Issue(
                    f"nonpositive_{col}", err, f"{len(nonpos)} values <= 0 in {col}", _dates(nonpos)
                )
            )

    # OHLC coherence. Warning only: old index data often has open=high=low=close or open=0.
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    with np.errstate(invalid="ignore"):
        bad = (h < np.fmax(o, c) * (1 - tol)) | (lo > np.fmin(o, c) * (1 + tol)) | (h < lo)
    if bad.any():
        bad_idx = idx[bad]
        add(
            Issue(
                "ohlc_consistency",
                warn,
                f"{int(bad.sum())} bars with high/low outside open/close: "
                f"{_fmt(_dates(bad_idx, 5))}",
                _dates(bad_idx),
            )
        )

    # Adjustment factor adj_close / close: in (0, 1], non-decreasing in time (dividends and
    # splits only ever scale the *past* down), and == 1 when nothing is paid (crypto, price index).
    ratio = (df["adj_close"] / df["close"]).dropna()
    if len(ratio):
        if (ratio > 1 + tol).any() or (ratio <= 0).any():
            add(Issue("adj_ratio_range", err, "adj_close / close outside (0, 1]"))
        drops = ratio.index[(ratio.diff() < -tol).to_numpy()]
        if len(drops):
            add(
                Issue(
                    "adj_ratio_monotonic",
                    warn,
                    f"adjustment factor decreases on {len(drops)} dates: {_fmt(_dates(drops, 5))}",
                    _dates(drops),
                )
            )
        if kind in ("crypto", "index") and (abs(ratio - 1) > tol).any():
            add(
                Issue(
                    "adj_ratio_unexpected",
                    warn,
                    f"{kind} should have adj_close == close (no distributions)",
                )
            )
        if kind in ("etf", "equity") and (abs(ratio - 1) <= tol).all() and len(ratio) > 252:
            add(
                Issue(
                    "adj_ratio_missing",
                    warn,
                    "adj_close == close over >1y for a distributing asset: adjusted data?",
                )
            )

    # --- calendar ------------------------------------------------------------------------------
    first_date = report.first.date() if report.first is not None else start
    if (first_date - start) > timedelta(days=7):
        add(
            Issue(
                "late_start",
                warn,
                f"history starts {first_date}, {(first_date - start).days} days after "
                f"requested start {start} (provider history limit?)",
            )
        )
    expected = expected_sessions(calendar, max(start, first_date), end)
    present = idx.unique()
    missing = expected.difference(present)
    extra = present.difference(expected_sessions(calendar, start, end))
    if len(missing):
        sev = err if len(missing) > cfg.max_missing_sessions else warn
        add(
            Issue(
                "missing_sessions",
                sev,
                f"{len(missing)} {calendar} sessions missing: {_fmt(_dates(missing))}",
                _dates(missing),
            )
        )
    if len(extra):
        add(
            Issue(
                "extra_sessions",
                err,
                f"{len(extra)} bars on non-{calendar} dates: {_fmt(_dates(extra))}",
                _dates(extra),
            )
        )

    # --- returns sanity ------------------------------------------------------------------------
    rets = df["adj_close"].pct_change(fill_method=None)
    jumps = rets.index[(rets.abs() > cfg.extreme_return_threshold).to_numpy()]
    if len(jumps):
        detail = ", ".join(f"{t:%Y-%m-%d} ({rets.loc[t]:+.1%})" for t in jumps[:5])
        add(
            Issue(
                "extreme_returns",
                warn,
                f"{len(jumps)} |return| > {cfg.extreme_return_threshold:.0%}: {detail}",
                _dates(jumps),
            )
        )
    runs = _longest_constant_runs(df["close"], cfg.max_stale_days)
    if runs:
        detail = ", ".join(f"{t:%Y-%m-%d} x{n}" for t, n in runs[:5])
        add(
            Issue(
                "stale_prices",
                warn,
                f"{len(runs)} runs of >= {cfg.max_stale_days} identical closes: {detail}",
                tuple(t for t, _ in runs),
            )
        )
    return report
