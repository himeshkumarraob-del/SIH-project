"""
Automated FIRMS downloader.

Given a date range and a list of products, this module:
  1. Splits the range into chunks that respect FIRMS's per-request day cap.
  2. Calls FirmsClient for each chunk.
  3. Saves each successful response as its own raw CSV file (never
     overwriting an existing file for the same request).
  4. Writes a structured JSONL request log (one line per request) with
     date, satellite, record count, filename, status, and errors —
     so every download attempt (including failures) is auditable.

This is the module referenced in PHASE 3 ("automated downloader",
"do not manually download dozens of files").
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from src.config import Config, get_config
from src.ingestion.firms_client import FirmsClient, FirmsRequestResult
from src.logging_setup import get_logger

logger = get_logger("ingestion.downloader")


def _chunk_date_range(start_date: dt.date, end_date: dt.date, max_days: int) -> list[tuple[dt.date, int]]:
    """
    Split [start_date, end_date] (inclusive) into (chunk_start, day_range)
    pairs, each covering at most max_days days, so ingestion never issues
    a request that exceeds FIRMS's per-request limit.
    """
    if start_date > end_date:
        raise ValueError(f"start_date {start_date} is after end_date {end_date}")

    chunks: list[tuple[dt.date, int]] = []
    cursor = start_date
    while cursor <= end_date:
        remaining_days = (end_date - cursor).days + 1
        day_range = min(max_days, remaining_days)
        chunks.append((cursor, day_range))
        cursor = cursor + dt.timedelta(days=day_range)
    return chunks


def _raw_filename(product_key: str, source: str, start_date: dt.date, day_range: int) -> str:
    end_date = start_date + dt.timedelta(days=day_range - 1)
    return f"firms_{product_key}_{source}_{start_date.isoformat()}_to_{end_date.isoformat()}.csv"


class FirmsDownloader:
    def __init__(self, config: Config | None = None, client: FirmsClient | None = None):
        self.config = config or get_config()
        self.client = client or FirmsClient(config=self.config)
        self._log_path = self.config.reports_dir / "logs" / "firms_download_log.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_log_entry(self, result: FirmsRequestResult, saved_path: str | None) -> None:
        entry = asdict(result)
        # dataclass asdict() keeps date objects; make them JSON-serializable.
        entry["start_date"] = result.start_date.isoformat()
        entry["downloaded_at"] = dt.datetime.utcnow().isoformat() + "Z"
        entry["saved_path"] = saved_path
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def download_range(
        self,
        start_date: dt.date,
        end_date: dt.date,
        product_keys: list[str] | None = None,
    ) -> list[dict]:
        """
        Download FIRMS data for every product in product_keys (defaults to
        config's default_products) across [start_date, end_date], chunked
        to respect the per-request day cap.

        Returns a list of summary dicts (one per request made), so a
        caller/script can print or inspect results without re-parsing the
        JSONL log.
        """
        product_keys = product_keys or self.config.firms_default_product_keys
        max_days = self.config.firms_max_days_per_request
        chunks = _chunk_date_range(start_date, end_date, max_days)

        summaries: list[dict] = []

        for product_key in product_keys:
            for chunk_start, day_range in chunks:
                result = self.client.fetch(product_key, chunk_start, day_range)

                saved_path: str | None = None
                if result.success and result.csv_text is not None:
                    filename = _raw_filename(
                        product_key, result.source, chunk_start, day_range
                    )
                    target = self.config.raw_data_dir / filename

                    if target.exists():
                        # PHASE 3 requirement: never overwrite raw source
                        # files silently.
                        logger.warning(
                            "Raw file already exists, skipping write (not overwriting): %s",
                            target,
                        )
                        saved_path = str(target)
                    else:
                        target.write_text(result.csv_text)
                        saved_path = str(target)
                        logger.info("Saved raw FIRMS file: %s (%d records)", target, result.record_count)

                self._write_log_entry(result, saved_path)

                summaries.append(
                    {
                        "product_key": product_key,
                        "source": result.source,
                        "start_date": chunk_start.isoformat(),
                        "day_range": day_range,
                        "success": result.success,
                        "record_count": result.record_count,
                        "saved_path": saved_path,
                        "error": result.error,
                    }
                )

        return summaries

    def download_lookback(
        self,
        lookback_days: int | None = None,
        product_keys: list[str] | None = None,
        end_date: dt.date | None = None,
    ) -> list[dict]:
        """
        Convenience wrapper for PHASE 3's "~30 days of VIIRS over India"
        initial collection. FIRMS end_date semantics: start_date + day_range
        covers dates up to and including end_date, so we anchor on
        end_date - (lookback_days - 1).
        """
        lookback_days = lookback_days or self.config.initial_collection_lookback_days
        end_date = end_date or dt.date.today()
        start_date = end_date - dt.timedelta(days=lookback_days - 1)
        return self.download_range(start_date, end_date, product_keys)

    @property
    def log_path(self) -> Path:
        return self._log_path
