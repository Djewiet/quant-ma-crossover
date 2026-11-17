"""Immutable on-disk cache for raw downloads, with a provenance manifest per file.

Layout: <raw_dir>/<ticker-slug>/<start>_<end>.parquet + .json sidecar
The parquet is written once (atomic rename) and never modified; the sidecar records when
and how it was obtained, plus a sha256 checked on every read.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd


class CacheIntegrityError(RuntimeError):
    """The cached file does not match its manifest checksum."""


@dataclass(frozen=True, slots=True)
class Manifest:
    ticker: str
    source: str
    source_version: str
    start: str
    end: str
    downloaded_at: str
    n_rows: int
    sha256: str


def _slug(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", ticker).strip("_") or "ticker"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp, engine="pyarrow")
    os.replace(tmp, path)


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, ticker: str, start: date, end: date) -> Path:
        return self.root / _slug(ticker) / f"{start.isoformat()}_{end.isoformat()}.parquet"

    def exists(self, ticker: str, start: date, end: date) -> bool:
        p = self.path(ticker, start, end)
        return p.exists() and p.with_suffix(".json").exists()

    def read(self, ticker: str, start: date, end: date) -> tuple[pd.DataFrame, Manifest]:
        p = self.path(ticker, start, end)
        manifest = Manifest(**json.loads(p.with_suffix(".json").read_text(encoding="utf-8")))
        if _sha256(p) != manifest.sha256:
            raise CacheIntegrityError(f"{p} was modified after download; refetch with --refresh")
        return pd.read_parquet(p, engine="pyarrow"), manifest

    def write(
        self,
        df: pd.DataFrame,
        *,
        ticker: str,
        start: date,
        end: date,
        source: str,
        source_version: str,
        now: datetime | None = None,
    ) -> Manifest:
        p = self.path(ticker, start, end)
        write_parquet_atomic(df, p)
        manifest = Manifest(
            ticker=ticker,
            source=source,
            source_version=source_version,
            start=start.isoformat(),
            end=end.isoformat(),
            downloaded_at=(now or datetime.now(UTC)).isoformat(timespec="seconds"),
            n_rows=len(df),
            sha256=_sha256(p),
        )
        p.with_suffix(".json").write_text(
            json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8"
        )
        return manifest
