"""
Thin client for the NASA FIRMS "area" CSV API.

Reference: https://firms.modaps.eosdis.nasa.gov/api/area/

This module ONLY talks to the FIRMS API and returns raw CSV text plus
request metadata. It does not parse, clean, or interpret the data —
that happens in src/preprocessing. Keeping this separation means the
ingestion module can be tested/mocked independently of parsing logic.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

from src.config import Config, FirmsProduct, get_config
from src.logging_setup import get_logger

logger = get_logger("ingestion.firms_client")

# FIRMS area API historical limit: requests further back than this are
# rejected by NASA's service (subject to change; kept as a named
# constant so it's easy to find/update, not silently baked into logic).
FIRMS_AREA_API_MAX_LOOKBACK_DAYS = 365


@dataclass
class FirmsRequestResult:
    """Outcome of a single FIRMS API call, success or failure."""

    product_key: str
    source: str
    start_date: dt.date
    day_range: int
    url: str
    status_code: int | None
    success: bool
    csv_text: str | None
    record_count: int | None
    error: str | None


class FirmsClient:
    """
    Wraps NASA FIRMS area-API requests.

    Example:
        client = FirmsClient()
        result = client.fetch(
            product_key="viirs_noaa20_sp",
            start_date=date(2026, 8, 1),
            day_range=10,
        )
    """

    def __init__(self, config: Config | None = None, session: requests.Session | None = None):
        self.config = config or get_config()
        self.session = session or requests.Session()

    def _product(self, product_key: str) -> FirmsProduct:
        products = self.config.firms_products
        if product_key not in products:
            valid = ", ".join(products.keys())
            raise ValueError(f"Unknown FIRMS product_key '{product_key}'. Valid keys: {valid}")
        return products[product_key]

    def build_url(self, product_key: str, start_date: dt.date, day_range: int) -> str:
        """
        Build a FIRMS area-API URL.

        URL shape:
        {base_url}/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{day_range}/{start_date}
        """
        product = self._product(product_key)
        bbox = self.config.study_area.as_firms_bbox_str()
        map_key = self.config.firms_map_key
        return (
            f"{self.config.firms_base_url}/{map_key}/{product.source}/"
            f"{bbox}/{day_range}/{start_date.isoformat()}"
        )

    def fetch(
        self,
        product_key: str,
        start_date: dt.date,
        day_range: int = 1,
        timeout: int = 60,
    ) -> FirmsRequestResult:
        """
        Fetch one window of FIRMS data for a single product.

        day_range: number of days of data to fetch, counting forward from
        start_date. FIRMS caps this per request (see
        config.firms_max_days_per_request) — callers should respect that
        cap; this method does not silently clamp it, so an out-of-range
        value produces a visible API error rather than silently wrong data.
        """
        product = self._product(product_key)
        url = self.build_url(product_key, start_date, day_range)
        # Don't log the URL as-is: it embeds the MAP_KEY secret.
        safe_url = url.replace(self.config.firms_map_key, "***REDACTED***")

        logger.info(
            "FIRMS request: product=%s start_date=%s day_range=%s",
            product_key, start_date, day_range,
        )

        try:
            resp = self.session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            logger.error("FIRMS request failed (network error): %s | url=%s", exc, safe_url)
            return FirmsRequestResult(
                product_key=product_key,
                source=product.source,
                start_date=start_date,
                day_range=day_range,
                url=safe_url,
                status_code=None,
                success=False,
                csv_text=None,
                record_count=None,
                error=str(exc),
            )

        if resp.status_code != 200:
            logger.error(
                "FIRMS request failed: status=%s url=%s body=%.200s",
                resp.status_code, safe_url, resp.text,
            )
            return FirmsRequestResult(
                product_key=product_key,
                source=product.source,
                start_date=start_date,
                day_range=day_range,
                url=safe_url,
                status_code=resp.status_code,
                success=False,
                csv_text=None,
                record_count=None,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        csv_text = resp.text

        # FIRMS returns a plain-text error message (still HTTP 200) for
        # bad map keys, invalid params, etc. Detect the common cases
        # rather than silently treating an error string as a 0-row CSV.
        first_line = csv_text.strip().splitlines()[0] if csv_text.strip() else ""
        if "Invalid" in first_line or "invalid" in first_line.lower() or "error" in first_line.lower():
            logger.error("FIRMS returned an error payload: %s | url=%s", first_line, safe_url)
            return FirmsRequestResult(
                product_key=product_key,
                source=product.source,
                start_date=start_date,
                day_range=day_range,
                url=safe_url,
                status_code=resp.status_code,
                success=False,
                csv_text=csv_text,
                record_count=None,
                error=f"FIRMS API error payload: {first_line}",
            )

        lines = csv_text.strip().splitlines()
        record_count = max(len(lines) - 1, 0)  # minus header row

        logger.info(
            "FIRMS request succeeded: product=%s start_date=%s day_range=%s records=%d",
            product_key, start_date, day_range, record_count,
        )

        return FirmsRequestResult(
            product_key=product_key,
            source=product.source,
            start_date=start_date,
            day_range=day_range,
            url=safe_url,
            status_code=resp.status_code,
            success=True,
            csv_text=csv_text,
            record_count=record_count,
            error=None,
        )
