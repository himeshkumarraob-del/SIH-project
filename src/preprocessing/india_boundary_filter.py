"""
India national-boundary filtering.

Filters the cleaned FIRMS dataset (data/interim/firms_clean.csv) down to
detections that fall inside India's actual national boundary polygon —
replacing the coarse bounding-box filter used during ingestion, which
also covers parts of Pakistan, Nepal, Bangladesh, Myanmar, Sri Lanka,
and ocean.

Boundary source: https://github.com/datasets/geo-countries (Natural
Earth country polygons, public domain). The full world file is
downloaded once, India's polygon (ISO3166-1-Alpha-3 == "IND") is
extracted, and only that polygon is cached to
data/external/india_boundary.geojson — no coordinates are hardcoded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("preprocessing.india_boundary_filter")

# Natural Earth country polygons via datasets/geo-countries (public domain,
# stable URL). We filter this down to India only and cache the result —
# we do not hardcode any polygon coordinates ourselves.
BOUNDARY_SOURCE_URL = "https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson"
BOUNDARY_ISO3_FIELD = "ISO3166-1-Alpha-3"
BOUNDARY_ISO3_VALUE = "IND"
BOUNDARY_FILENAME = "india_boundary.geojson"

WGS84 = "EPSG:4326"  # FIRMS latitude/longitude are WGS84 by definition.


@dataclass
class BoundaryFilterReport:
    input_records: int = 0
    records_inside_india: int = 0
    records_excluded: int = 0
    percentage_retained: float = 0.0
    date_range: tuple[str, str] | None = None
    noaa20_count: int = 0
    noaa21_count: int = 0


def ensure_india_boundary(external_dir: Path) -> Path:
    """
    Return the path to the cached India boundary GeoJSON, downloading and
    extracting it from the source dataset if it isn't already cached.
    Safe to call repeatedly: if the cached file exists, no network
    request is made, so re-running the pipeline is fully reproducible
    and does not depend on the source staying online after first use.
    """
    external_dir = Path(external_dir)
    boundary_path = external_dir / BOUNDARY_FILENAME

    if boundary_path.exists():
        logger.info("Using cached India boundary: %s", boundary_path)
        return boundary_path

    logger.info("India boundary not cached yet, downloading from %s", BOUNDARY_SOURCE_URL)
    try:
        resp = requests.get(BOUNDARY_SOURCE_URL, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to download country boundaries from {BOUNDARY_SOURCE_URL}: {exc}"
        ) from exc

    world = json.loads(resp.text)
    india_features = [
        f for f in world["features"]
        if f["properties"].get(BOUNDARY_ISO3_FIELD) == BOUNDARY_ISO3_VALUE
    ]
    if not india_features:
        raise RuntimeError(
            f"Could not find a feature with {BOUNDARY_ISO3_FIELD}={BOUNDARY_ISO3_VALUE} "
            f"in the downloaded boundary source."
        )

    india_gdf = gpd.GeoDataFrame.from_features(india_features, crs=WGS84)
    external_dir.mkdir(parents=True, exist_ok=True)
    india_gdf.to_file(boundary_path, driver="GeoJSON")
    logger.info("Cached India boundary to %s", boundary_path)
    return boundary_path


def load_india_boundary(boundary_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(boundary_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    elif gdf.crs.to_string() != WGS84:
        gdf = gdf.to_crs(WGS84)
    return gdf


def filter_to_india(df: pd.DataFrame, boundary: gpd.GeoDataFrame) -> tuple[pd.DataFrame, int]:
    """
    Point-in-polygon filter: keeps only rows whose latitude/longitude
    fall inside the India boundary polygon. Returns (filtered_df,
    excluded_count). All original columns are preserved; no geometry
    column is added to the output.
    """
    if "latitude" not in df.columns or "longitude" not in df.columns:
        raise ValueError("Input dataframe must have 'latitude' and 'longitude' columns.")

    before = len(df)
    points = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs=WGS84,
    )

    joined = gpd.sjoin(points, boundary[["geometry"]], predicate="within", how="inner")
    # sjoin adds an 'index_right' column and keeps the geometry column;
    # drop both to return a plain DataFrame with only the original +
    # already-derived FIRMS columns.
    result = joined.drop(columns=["geometry", "index_right"], errors="ignore")
    result = pd.DataFrame(result)

    excluded = before - len(result)
    return result, excluded


def run_india_filter_pipeline() -> tuple[pd.DataFrame, BoundaryFilterReport]:
    cfg = get_config()
    report = BoundaryFilterReport()

    input_path = cfg.interim_data_dir / "firms_clean.csv"
    if not input_path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at {input_path}. Run the cleaning pipeline first."
        )

    df = pd.read_csv(input_path)
    report.input_records = len(df)

    boundary_path = ensure_india_boundary(cfg.external_data_dir)
    boundary = load_india_boundary(boundary_path)

    filtered, excluded = filter_to_india(df, boundary)

    report.records_inside_india = len(filtered)
    report.records_excluded = excluded
    report.percentage_retained = (
        round(100 * len(filtered) / report.input_records, 2) if report.input_records else 0.0
    )

    if "acq_date" in filtered.columns and not filtered.empty:
        report.date_range = (str(filtered["acq_date"].min()), str(filtered["acq_date"].max()))

    if "source_satellite" in filtered.columns:
        counts = filtered["source_satellite"].value_counts().to_dict()
        report.noaa20_count = int(counts.get("NOAA-20", 0))
        report.noaa21_count = int(counts.get("NOAA-21", 0))

    return filtered, report


def save_india_dataset(df: pd.DataFrame) -> Path:
    cfg = get_config()
    out_path = cfg.processed_data_dir / "firms_india.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved India-filtered dataset: %s (%d rows)", out_path, len(df))
    return out_path


def print_summary(report: BoundaryFilterReport) -> None:
    print("\n=== India Boundary Filtering Summary ===")
    print(f"Input records:            {report.input_records}")
    print(f"Records inside India:     {report.records_inside_india}")
    print(f"Records excluded:         {report.records_excluded}")
    print(f"Percentage retained:      {report.percentage_retained}%")
    print(f"Date range:               {report.date_range}")
    print(f"NOAA-20 count:            {report.noaa20_count}")
    print(f"NOAA-21 count:            {report.noaa21_count}")
    print("==========================================\n")