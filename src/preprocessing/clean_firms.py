"""
FIRMS raw-CSV cleaning / preprocessing pipeline.

Reads every raw FIRMS CSV under data/raw/ (auto-discovered — no filenames
need to be listed by hand), combines NOAA-20 + NOAA-21 detections into one
dataset, validates/cleans it, and writes data/interim/firms_clean.csv.

This module does NOT do India boundary filtering or OSM enrichment —
those are later phases. It only cleans what FIRMS itself returned.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("preprocessing.clean_firms")

# Matches the downloader's naming convention:
# firms_<product_key>_<source>_<start>_to_<end>.csv
RAW_FILENAME_GLOB = "firms_*.csv"

REQUIRED_COLUMNS = [
    "latitude", "longitude", "bright_ti4", "scan", "track",
    "acq_date", "acq_time", "satellite", "instrument", "confidence",
]


@dataclass
class CleaningReport:
    raw_files_found: int = 0
    raw_files_loaded: int = 0
    raw_files_skipped: list[str] = field(default_factory=list)
    raw_record_count: int = 0
    duplicate_rows_removed: int = 0
    invalid_coordinate_rows_removed: int = 0
    final_record_count: int = 0
    date_range: tuple[str, str] | None = None
    satellite_counts: dict[str, int] = field(default_factory=dict)
    missing_value_counts: dict[str, int] = field(default_factory=dict)


def discover_raw_files(raw_dir: Path) -> list[Path]:
    """Auto-discover FIRMS raw CSVs by naming pattern, so nothing needs to
    be listed manually. Sorted for reproducible load order."""
    files = sorted(Path(raw_dir).glob(RAW_FILENAME_GLOB))
    logger.info("Discovered %d raw FIRMS CSV file(s) in %s", len(files), raw_dir)
    return files


def _infer_source_satellite(filename: str) -> str:
    """
    Derive satellite label from the filename rather than FIRMS's own
    'satellite' column, whose values are terse codes (e.g. '1', 'N') that
    are easy to misread. Our downloader already encodes the product in
    the filename (firms_viirs_noaa20_..., firms_viirs_noaa21_...), which
    is unambiguous.
    """
    name = filename.lower()
    if "noaa20" in name:
        return "NOAA-20"
    if "noaa21" in name:
        return "NOAA-21"
    if "snpp" in name:
        return "SUOMI-NPP"
    return "UNKNOWN"


def load_raw_files(files: list[Path]) -> tuple[pd.DataFrame, list[str]]:
    """Load + concatenate raw FIRMS CSVs. A file that fails to parse or is
    missing a required column is skipped (logged) rather than crashing
    the whole run."""
    frames = []
    skipped: list[str] = []

    for path in files:
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logger.warning("Skipping unreadable file %s: %s", path.name, exc)
            skipped.append(path.name)
            continue

        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            logger.warning("Skipping %s: missing required columns %s", path.name, missing_cols)
            skipped.append(path.name)
            continue

        df["source_satellite"] = _infer_source_satellite(path.name)
        df["source_file"] = path.name
        frames.append(df)

    if not frames:
        raise ValueError("No valid FIRMS raw files could be loaded from data/raw/.")

    return pd.concat(frames, ignore_index=True, sort=False), skipped


def _convert_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ["latitude", "longitude", "bright_ti4", "scan", "track"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Optional columns that may or may not be present depending on product.
    for col in ["bright_ti5", "frp"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # acq_time is HHMM, sometimes without leading zeros (e.g. "830" -> "0830").
    df["acq_time"] = df["acq_time"].astype(str).str.zfill(4)
    df["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce").dt.date

    # VIIRS confidence is categorical (l/n/h), NOT numeric like MODIS
    # confidence (0-100). Coercing it to float would silently turn all of
    # it into NaN, so it's kept as a normalized string category instead.
    df["confidence"] = df["confidence"].astype(str).str.strip().str.lower()

    df["satellite"] = df["satellite"].astype(str)
    df["instrument"] = df["instrument"].astype(str)

    return df


def _build_acquisition_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    dt_strings = df["acq_date"].astype(str) + " " + df["acq_time"]
    df["acquisition_datetime"] = pd.to_datetime(
        dt_strings, format="%Y-%m-%d %H%M", errors="coerce", utc=True
    )
    return df


def clean_coordinates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)]
    return df, before - len(df)


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    # Sort first so which copy of a duplicate is kept is deterministic
    # across runs, regardless of file-discovery order.
    df = df.sort_values(["acq_date", "acq_time", "latitude", "longitude"], kind="mergesort")
    df = df.drop_duplicates(
        subset=["latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument"],
        keep="first",
    )
    return df, before - len(df)


def _build_detection_id(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def make_id(row) -> str:
        key = f"{row['latitude']:.5f}|{row['longitude']:.5f}|{row['acq_date']}|{row['acq_time']}|{row['source_satellite']}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]

    df["detection_id"] = df.apply(make_id, axis=1)
    return df


def _missing_value_summary(df: pd.DataFrame) -> dict[str, int]:
    cols = [c for c in REQUIRED_COLUMNS + ["acquisition_datetime"] if c in df.columns]
    return {c: int(df[c].isna().sum()) for c in cols}


def run_cleaning_pipeline() -> tuple[pd.DataFrame, CleaningReport]:
    """Runs the full clean and returns (cleaned_df, report). Raises
    FileNotFoundError/ValueError on unrecoverable input problems — callers
    (the CLI script) are expected to catch and report these clearly."""
    cfg = get_config()
    report = CleaningReport()

    raw_files = discover_raw_files(cfg.raw_data_dir)
    report.raw_files_found = len(raw_files)
    if not raw_files:
        raise FileNotFoundError(
            f"No FIRMS raw CSV files found in {cfg.raw_data_dir} "
            f"(expected files matching '{RAW_FILENAME_GLOB}'). Run the downloader first."
        )

    combined, skipped = load_raw_files(raw_files)
    report.raw_files_loaded = len(raw_files) - len(skipped)
    report.raw_files_skipped = skipped
    report.raw_record_count = len(combined)

    combined = _convert_types(combined)
    combined = _build_acquisition_datetime(combined)

    combined, invalid_coord_removed = clean_coordinates(combined)
    report.invalid_coordinate_rows_removed = invalid_coord_removed

    combined, dup_removed = remove_duplicates(combined)
    report.duplicate_rows_removed = dup_removed

    combined = _build_detection_id(combined)

    report.final_record_count = len(combined)
    if not combined.empty:
        report.date_range = (str(combined["acq_date"].min()), str(combined["acq_date"].max()))
    report.satellite_counts = combined["source_satellite"].value_counts().to_dict()
    report.missing_value_counts = _missing_value_summary(combined)

    return combined, report


def save_cleaned_dataset(df: pd.DataFrame) -> Path:
    cfg = get_config()
    out_path = cfg.interim_data_dir / "firms_clean.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved cleaned dataset: %s (%d rows)", out_path, len(df))
    return out_path


def print_summary(report: CleaningReport) -> None:
    print("\n=== FIRMS Cleaning Summary ===")
    print(f"Raw files found:              {report.raw_files_found}")
    print(f"Raw files loaded:             {report.raw_files_loaded}")
    if report.raw_files_skipped:
        print(f"Raw files skipped:            {report.raw_files_skipped}")
    print(f"Raw records (combined):       {report.raw_record_count}")
    print(f"Invalid coordinates removed:  {report.invalid_coordinate_rows_removed}")
    print(f"Duplicate rows removed:       {report.duplicate_rows_removed}")
    print(f"Final cleaned records:        {report.final_record_count}")
    print(f"Date range:                   {report.date_range}")
    print("Satellite counts:")
    for sat, count in report.satellite_counts.items():
        print(f"  {sat:12s} {count}")
    print("Missing values (key fields):")
    for col, count in report.missing_value_counts.items():
        print(f"  {col:24s} {count}")
    print("================================\n")