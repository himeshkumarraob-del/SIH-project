"""
Tests for the FIRMS ingestion layer.

These tests avoid real network calls (no FIRMS_MAP_KEY required for most
of them) by testing URL construction, date chunking, and result handling
against mocked responses.
"""

from __future__ import annotations

import datetime as dt
import os

import pytest

os.environ.setdefault("FIRMS_MAP_KEY", "test_key_1234567890")

from src.config import get_config  # noqa: E402
from src.ingestion.downloader import _chunk_date_range, _raw_filename  # noqa: E402
from src.ingestion.firms_client import FirmsClient  # noqa: E402


def test_config_loads_study_area():
    cfg = get_config()
    area = cfg.study_area
    assert area.west == 68
    assert area.south == 6
    assert area.east == 97
    assert area.north == 36
    assert area.as_firms_bbox_str() == "68.0,6.0,97.0,36.0"


def test_config_lists_default_products():
    cfg = get_config()
    keys = cfg.firms_default_product_keys
    assert "viirs_noaa20" in keys
    assert "viirs_noaa21" in keys


def test_firms_client_builds_expected_url():
    client = FirmsClient()
    url = client.build_url("viirs_noaa20_sp", dt.date(2026, 8, 1), 10)
    assert "VIIRS_NOAA20_SP" in url
    assert "68.0,6.0,97.0,36.0" in url
    assert "/10/2026-08-01" in url


def test_firms_client_rejects_unknown_product():
    client = FirmsClient()
    with pytest.raises(ValueError):
        client.build_url("not_a_real_product", dt.date(2026, 8, 1), 1)


def test_chunk_date_range_splits_on_max_days():
    chunks = _chunk_date_range(dt.date(2026, 8, 1), dt.date(2026, 8, 30), max_days=10)
    assert chunks == [
        (dt.date(2026, 8, 1), 10),
        (dt.date(2026, 8, 11), 10),
        (dt.date(2026, 8, 21), 10),
    ]


def test_chunk_date_range_handles_remainder():
    chunks = _chunk_date_range(dt.date(2026, 8, 1), dt.date(2026, 8, 23), max_days=10)
    assert chunks == [
        (dt.date(2026, 8, 1), 10),
        (dt.date(2026, 8, 11), 10),
        (dt.date(2026, 8, 21), 3),
    ]


def test_chunk_date_range_single_day():
    chunks = _chunk_date_range(dt.date(2026, 8, 5), dt.date(2026, 8, 5), max_days=10)
    assert chunks == [(dt.date(2026, 8, 5), 1)]


def test_chunk_date_range_rejects_inverted_range():
    with pytest.raises(ValueError):
        _chunk_date_range(dt.date(2026, 8, 10), dt.date(2026, 8, 1), max_days=10)


def test_raw_filename_is_deterministic_and_descriptive():
    name = _raw_filename("viirs_noaa20_sp", "VIIRS_NOAA20_SP", dt.date(2026, 8, 1), 10)
    assert name == "firms_viirs_noaa20_sp_VIIRS_NOAA20_SP_2026-08-01_to_2026-08-10.csv"
