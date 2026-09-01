"""Tests for src/preprocessing/clean_firms.py — pure DataFrame logic,
no real FIRMS files or network access needed."""

from __future__ import annotations

import os

import pandas as pd

os.environ.setdefault("FIRMS_MAP_KEY", "test_key_1234567890")

from src.preprocessing.clean_firms import (  # noqa: E402
    clean_coordinates,
    discover_raw_files,
    remove_duplicates,
)

COLS = [
    "latitude", "longitude", "bright_ti4", "scan", "track",
    "acq_date", "acq_time", "satellite", "instrument", "confidence",
]


def _row(lat, lon, date="2026-08-20", time="0530", sat="1", inst="VIIRS", conf="n"):
    return [lat, lon, 320.0, 0.4, 0.4, date, time, sat, inst, conf]


def test_clean_coordinates_drops_out_of_range_and_missing():
    df = pd.DataFrame(
        [_row(28.6, 77.2), _row(999, 77.2), _row(None, 72.8), _row(19.0, -200)],
        columns=COLS,
    )
    cleaned, removed = clean_coordinates(df)
    assert removed == 3
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["latitude"] == 28.6


def test_remove_duplicates_drops_exact_repeats_only():
    df = pd.DataFrame(
        [_row(28.6, 77.2), _row(28.6, 77.2), _row(19.0, 72.8)],
        columns=COLS,
    )
    cleaned, removed = remove_duplicates(df)
    assert removed == 1
    assert len(cleaned) == 2


def test_discover_raw_files_matches_naming_pattern(tmp_path):
    (tmp_path / "firms_viirs_noaa20_VIIRS_NOAA20_NRT_2026-08-20_to_2026-08-22.csv").write_text("x")
    (tmp_path / "not_a_firms_file.csv").write_text("x")
    found = discover_raw_files(tmp_path)
    assert len(found) == 1
    assert found[0].name.startswith("firms_")