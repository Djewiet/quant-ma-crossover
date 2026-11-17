"""Typed loading of the YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

CalendarName = Literal["crypto", "XNYS"]
AssetKind = Literal["crypto", "etf", "index", "equity"]
_CALENDARS: frozenset[str] = frozenset({"crypto", "XNYS"})
_KINDS: frozenset[str] = frozenset({"crypto", "etf", "index", "equity"})


@dataclass(frozen=True, slots=True)
class AssetConfig:
    name: str
    ticker: str
    calendar: CalendarName
    kind: AssetKind
    start: date


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    max_missing_sessions: int = 0
    extreme_return_threshold: float = 0.25
    max_stale_days: int = 5
    price_rel_tol: float = 1e-6


@dataclass(frozen=True, slots=True)
class DataConfig:
    source: str
    end: date
    raw_dir: Path
    processed_dir: Path
    assets: dict[str, AssetConfig]


@dataclass(frozen=True, slots=True)
class Config:
    data: DataConfig
    validation: ValidationConfig


def _to_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field}: expected ISO date, got {value!r}")


def _parse_asset(name: str, raw: dict[str, Any]) -> AssetConfig:
    calendar = raw["calendar"]
    kind = raw["kind"]
    if calendar not in _CALENDARS:
        raise ValueError(f"asset {name}: unknown calendar {calendar!r}")
    if kind not in _KINDS:
        raise ValueError(f"asset {name}: unknown kind {kind!r}")
    return AssetConfig(
        name=name,
        ticker=str(raw["ticker"]),
        calendar=calendar,
        kind=kind,
        start=_to_date(raw["start"], f"{name}.start"),
    )


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> Config:
    """Build a Config from a parsed YAML mapping. Relative paths resolve against base_dir."""
    base = base_dir or Path.cwd()
    d = raw["data"]
    assets = {name: _parse_asset(name, a) for name, a in d["assets"].items()}
    end = _to_date(d["end"], "data.end")
    for a in assets.values():
        if a.start > end:
            raise ValueError(f"asset {a.name}: start {a.start} is after end {end}")
    data = DataConfig(
        source=str(d["source"]),
        end=end,
        raw_dir=base / d["raw_dir"],
        processed_dir=base / d["processed_dir"],
        assets=assets,
    )
    validation = ValidationConfig(**raw.get("validation", {}))
    return Config(data=data, validation=validation)


def load_config(path: str | Path) -> Config:
    """Load a YAML config. Relative data paths resolve against the repo root (config/..)."""
    p = Path(path).resolve()
    with p.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return parse_config(raw, base_dir=p.parent.parent)
