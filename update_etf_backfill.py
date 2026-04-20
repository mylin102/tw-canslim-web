#!/usr/bin/env python3
"""
ETF-only backfill publisher.
"""

from __future__ import annotations

import argparse
import sys

from update_single_stock import SingleStockUpdater


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill ETF entries into the publish bundle.")
    parser.add_argument(
        "--tickers",
        help="Comma-separated ETF tickers to backfill. Defaults to all known ETFs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap for how many ETF tickers to process.",
    )
    return parser.parse_args(argv)


def resolve_etf_tickers(updater: SingleStockUpdater, tickers_arg: str | None, limit: int) -> list[str]:
    if tickers_arg:
        requested = [ticker.strip().upper() for ticker in tickers_arg.split(",") if ticker.strip()]
        etf_tickers = [ticker for ticker in requested if updater.is_etf_ticker(ticker)]
    else:
        etf_tickers = sorted(
            ticker
            for ticker in updater.ticker_info
            if updater.is_etf_ticker(ticker)
        )

    if limit and limit > 0:
        etf_tickers = etf_tickers[:limit]
    return etf_tickers


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    updater = SingleStockUpdater()
    tickers = resolve_etf_tickers(updater, args.tickers, args.limit)
    if not tickers:
        print("No ETF tickers selected for backfill.")
        return 1

    description = f"ETF-only backfill for {len(tickers)} tickers"
    success = updater.update_stocks(
        tickers,
        update_type="ETF backfill",
        description=description,
        next_action="Review ETF coverage and freshness in GitHub Pages after the backfill run.",
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
