#!/usr/bin/env python3
"""
CLI entry point for downloading FIRMS data.

Examples:
    # Default: ~30 days lookback, default products (VIIRS NOAA-20/21 SP), ending today
    python scripts/download_firms_data.py

    # Small test range (PHASE 3 step 3: "test the downloader with a small date range")
    python scripts/download_firms_data.py --start 2026-08-20 --end 2026-08-22

    # Specific products only
    python scripts/download_firms_data.py --start 2026-08-01 --end 2026-08-30 \
        --products viirs_noaa20_sp
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# When this file is run directly (`python scripts/download_firms_data.py`),
# Python puts this script's own directory (scripts/) on sys.path[0], NOT
# the project root — so the sibling `src` package is not importable on its
# own. Explicitly add the project root (this file's parent's parent) to
# sys.path before importing from `src`, so the command works from any cwd
# without requiring PYTHONPATH to be set manually or the package to be
# pip-installed.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.downloader import FirmsDownloader  # noqa: E402
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger("scripts.download_firms_data")


def _parse_date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download NASA FIRMS thermal data.")
    parser.add_argument("--start", type=_parse_date, default=None, help="YYYY-MM-DD")
    parser.add_argument("--end", type=_parse_date, default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="If --start/--end omitted, download this many days ending today (default from config.yaml).",
    )
    parser.add_argument(
        "--products",
        nargs="+",
        default=None,
        help="FIRMS product keys to fetch (default: config.yaml firms.default_products).",
    )
    args = parser.parse_args()

    downloader = FirmsDownloader()

    if args.start and args.end:
        summaries = downloader.download_range(args.start, args.end, args.products)
    elif args.start or args.end:
        parser.error("--start and --end must be provided together.")
        return 2
    else:
        summaries = downloader.download_lookback(args.lookback_days, args.products)

    total = len(summaries)
    succeeded = sum(1 for s in summaries if s["success"])
    failed = total - succeeded
    total_records = sum(s["record_count"] or 0 for s in summaries if s["success"])

    print(f"\nRequests made: {total} | succeeded: {succeeded} | failed: {failed}")
    print(f"Total records downloaded: {total_records}")
    print(f"Full request log: {downloader.log_path}\n")

    for s in summaries:
        status = "OK" if s["success"] else "FAILED"
        print(
            f"[{status}] {s['product_key']:16s} {s['start_date']} "
            f"(+{s['day_range']}d) records={s['record_count']} "
            f"{'error=' + s['error'] if s['error'] else ''}"
        )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
