"""Command-line entry point: `uv run ma-crossover fetch [--refresh] [--assets btc spy]`."""

from __future__ import annotations

import argparse
import logging
import sys

from ma_crossover.config import load_config
from ma_crossover.data.pipeline import load_all
from ma_crossover.data.sources import DataSourceError, YFinanceSource
from ma_crossover.data.validation import DataValidationError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ma-crossover")
    p.add_argument("--config", default="config/default.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="download (or read cache), validate and store daily bars")
    f.add_argument("--assets", nargs="*", help="subset of config assets (default: all)")
    f.add_argument("--refresh", action="store_true", help="ignore the raw cache")
    f.add_argument("--no-strict", action="store_true", help="store data even with errors")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config(args.config)
    if cfg.data.source != "yfinance":
        print(f"unsupported source {cfg.data.source!r}", file=sys.stderr)
        return 2
    try:
        loaded = load_all(
            cfg,
            YFinanceSource(),
            names=args.assets,
            refresh=args.refresh,
            strict=not args.no_strict,
        )
    except DataValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    except DataSourceError as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 3
    for item in loaded.values():
        origin = "cache" if item.from_cache else "download"
        print(f"{item.report.summary()}\n  -> {item.processed_path} ({origin})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
