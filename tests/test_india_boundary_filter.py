"""Tests for src/preprocessing/india_boundary_filter.py.

Uses a small synthetic square polygon around Delhi as a stand-in India
boundary (fast, no network) to verify the point-in-polygon logic and
column preservation, independent of the real downloaded boundary file.
"""

from __future__ import annotations

import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

os.environ.setdefault("FIRMS_MAP_KEY", "test_key_1234567890")

from src.preprocessing.india_boundary_filter import filter_to_india, WGS84  # noqa: E402

# A simple bounding box standing in for "India" for test purposes only:
# roughly covers Delhi but not Beijing.
_TEST_BOUNDARY = gpd.GeoDataFrame(
    {"name": ["TestIndia"]},
    geometry=[box(68, 6, 97, 36)],
    crs=WGS84,
)

COLS = [
    "latitude", "longitude", "acq_date", "satellite", "detection_id",
]


def test_point_inside_boundary_is_retained():
    df = pd.DataFrame(
        [[28.6139, 77.2090, "2026-08-20", "1", "id1"]],  # Delhi
        columns=COLS,
    )
    result, excluded = filter_to_india(df, _TEST_BOUNDARY)
    assert excluded == 0
    assert len(result) == 1
    assert result.iloc[0]["detection_id"] == "id1"


def test_point_outside_boundary_is_removed():
    df = pd.DataFrame(
        [[39.9042, 116.4074, "2026-08-21", "1", "id2"]],  # Beijing
        columns=COLS,
    )
    result, excluded = filter_to_india(df, _TEST_BOUNDARY)
    assert excluded == 1
    assert len(result) == 0


def test_original_columns_are_preserved_and_no_geometry_leaks():
    df = pd.DataFrame(
        [
            [28.6139, 77.2090, "2026-08-20", "1", "id1"],  # inside
            [39.9042, 116.4074, "2026-08-21", "1", "id2"],  # outside
        ],
        columns=COLS,
    )
    result, excluded = filter_to_india(df, _TEST_BOUNDARY)
    assert excluded == 1
    assert list(result.columns) == COLS
    assert "geometry" not in result.columns
    assert "index_right" not in result.columns