"""
Persistence analysis: groups India-filtered FIRMS detections into
candidate thermal-event clusters based on spatial proximity and temporal
proximity, then computes per-cluster persistence features.

IMPORTANT — what this module does and does not claim:
- It identifies detections that are spatially close and temporally
  chained (i.e. recurring activity at roughly the same location).
- The resulting "persistence_score" and "persistence_category" are
  DERIVED FEATURES for later risk assessment — they are NOT a claim
  that any cluster is an industrial fire, or any other confirmed
  cause. A persistent thermal source could be industrial, agricultural,
  a landfill, a natural fire, or something else; this module makes no
  attempt to classify cause.

Clustering method: two detections are linked (same cluster) if they are
both within `spatial_distance_km` of each other (great-circle distance)
AND within `temporal_window_days` of each other (by acquisition date).
Clusters are the connected components of this link graph, found via a
union-find over spatially-blocked candidate pairs (grid blocking keeps
this from degrading to O(n^2) on the full dataset).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import PersistenceConfig, get_config
from src.logging_setup import get_logger

logger = get_logger("persistence.persistence_analysis")

EARTH_RADIUS_KM = 6371.0088

REQUIRED_COLUMNS = ["latitude", "longitude", "acq_date"]

# Ordinal mapping used only when confidence is categorical (VIIRS: l/n/h).
# This is a documented ordinal scale for averaging purposes, not a
# reconstruction of a numeric confidence percentage.
_CATEGORICAL_CONFIDENCE_MAP = {"l": 1, "n": 2, "h": 3}


@dataclass
class PersistenceRunReport:
    input_records: int = 0
    cluster_count: int = 0
    isolated_count: int = 0
    short_lived_repeated_count: int = 0
    persistent_count: int = 0
    date_range: tuple[str, str] | None = None
    category_counts: dict[str, int] = field(default_factory=dict)


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorized great-circle distance in km."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _grid_candidate_pairs(lats: np.ndarray, lons: np.ndarray, spatial_distance_km: float):
    """
    Bucket points into a coarse lat/lon grid (cell size ~= threshold
    distance) and yield candidate index pairs from the same or adjacent
    cells only. This avoids computing a full O(n^2) distance matrix while
    still guaranteeing every true within-threshold pair is checked
    (any two points within spatial_distance_km fall in the same or a
    neighboring cell for this cell size).
    """
    # ~111 km per degree of latitude; conservative approximation used only
    # for bucketing candidates, not for the actual distance calculation
    # (that uses proper haversine below).
    cell_size_deg = max(spatial_distance_km / 111.0, 1e-6)

    cells: dict[tuple[int, int], list[int]] = {}
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        key = (int(math.floor(lat / cell_size_deg)), int(math.floor(lon / cell_size_deg)))
        cells.setdefault(key, []).append(i)

    seen_pairs = set()
    for (cx, cy), indices in cells.items():
        neighbor_indices: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbor_indices.extend(cells.get((cx + dx, cy + dy), []))
        neighbor_indices = sorted(set(neighbor_indices))
        for a_idx, i in enumerate(indices):
            for j in neighbor_indices:
                if j <= i:
                    continue
                pair = (i, j)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                yield i, j


def cluster_detections(df: pd.DataFrame, cfg: PersistenceConfig) -> np.ndarray:
    """
    Returns an array of cluster ids (one per row of df, aligned by
    position) using spatial + temporal linkage as described in the
    module docstring.
    """
    n = len(df)
    if n == 0:
        return np.array([], dtype=int)

    lats = df["latitude"].to_numpy()
    lons = df["longitude"].to_numpy()
    dates = pd.to_datetime(df["acq_date"]).to_numpy()

    uf = _UnionFind(n)
    temporal_window = np.timedelta64(cfg.temporal_window_days, "D")

    for i, j in _grid_candidate_pairs(lats, lons, cfg.spatial_distance_km):
        if abs(dates[i] - dates[j]) > temporal_window:
            continue
        dist = _haversine_km(lats[i], lons[i], lats[j], lons[j])
        if dist <= cfg.spatial_distance_km:
            uf.union(i, j)

    roots = [uf.find(i) for i in range(n)]
    # Renumber roots to consecutive 0..k-1 cluster ids for readability.
    root_to_id: dict[int, int] = {}
    cluster_ids = np.empty(n, dtype=int)
    for i, r in enumerate(roots):
        if r not in root_to_id:
            root_to_id[r] = len(root_to_id)
        cluster_ids[i] = root_to_id[r]

    return cluster_ids


def _confidence_to_numeric(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.5:
        return numeric
    # Mostly non-numeric (categorical VIIRS l/n/h) -> ordinal mapping.
    return series.astype(str).str.strip().str.lower().map(_CATEGORICAL_CONFIDENCE_MAP)


def _categorize(active_days: int, cfg: PersistenceConfig) -> str:
    if active_days < cfg.repeated_min_active_days:
        return "isolated"
    if active_days < cfg.persistent_min_active_days:
        return "short_lived_repeated"
    return "persistent"


def compute_cluster_features(df: pd.DataFrame, cluster_ids: np.ndarray, cfg: PersistenceConfig) -> pd.DataFrame:
    """
    Builds one row per cluster with the persistence features. persistence_score
    is defined as:

        active_days_in_cluster / total_days_in_dataset_window

    i.e. the fraction of the ENTIRE monitored period (across the whole
    input dataset, not just the cluster's own span) during which this
    cluster was actively detected. This rewards clusters that recur
    across a large share of the observed window, and avoids a single
    one-off detection trivially scoring 1.0 (which a "cluster's own
    span" formula would do).
    """
    work = df.copy()
    work["_cluster_id"] = cluster_ids
    work["acq_date"] = pd.to_datetime(work["acq_date"])
    work["_confidence_numeric"] = _confidence_to_numeric(work["confidence"]) if "confidence" in work.columns else np.nan

    dataset_start = work["acq_date"].min()
    dataset_end = work["acq_date"].max()
    total_dataset_days = max((dataset_end - dataset_start).days + 1, 1)

    rows = []
    for cluster_id, g in work.groupby("_cluster_id"):
        active_days = g["acq_date"].dt.date.nunique()
        first_detection = g["acq_date"].min()
        last_detection = g["acq_date"].max()
        duration_days = (last_detection - first_detection).days + 1
        persistence_score = round(active_days / total_dataset_days, 4)

        row = {
            "cluster_id": int(cluster_id),
            "observation_count": len(g),
            "active_days": active_days,
            "first_detection": first_detection.date().isoformat(),
            "last_detection": last_detection.date().isoformat(),
            "duration_days": duration_days,
            "mean_bright_ti4": round(g["bright_ti4"].mean(), 3) if "bright_ti4" in g else None,
            "max_bright_ti4": round(g["bright_ti4"].max(), 3) if "bright_ti4" in g else None,
            "mean_bright_ti5": round(g["bright_ti5"].mean(), 3) if "bright_ti5" in g.columns else None,
            "max_bright_ti5": round(g["bright_ti5"].max(), 3) if "bright_ti5" in g.columns else None,
            "mean_frp": round(g["frp"].mean(), 3) if "frp" in g.columns else None,
            "max_frp": round(g["frp"].max(), 3) if "frp" in g.columns else None,
            "mean_confidence": round(g["_confidence_numeric"].mean(), 3) if g["_confidence_numeric"].notna().any() else None,
            "persistence_score": persistence_score,
            "persistence_category": _categorize(active_days, cfg),
        }
        rows.append(row)

    result = pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)
    return result


def run_persistence_pipeline() -> tuple[pd.DataFrame, PersistenceRunReport]:
    cfg_obj = get_config()
    pcfg = cfg_obj.persistence

    input_path = cfg_obj.processed_data_dir / "firms_india.csv"
    if not input_path.exists():
        raise FileNotFoundError(
            f"India-filtered dataset not found at {input_path}. "
            "Run the India boundary filtering stage first."
        )

    df = pd.read_csv(input_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input dataset is missing required columns: {missing}")

    report = PersistenceRunReport(input_records=len(df))

    cluster_ids = cluster_detections(df, pcfg)
    clusters = compute_cluster_features(df, cluster_ids, pcfg)

    report.cluster_count = len(clusters)
    counts = clusters["persistence_category"].value_counts().to_dict()
    report.category_counts = counts
    report.isolated_count = int(counts.get("isolated", 0))
    report.short_lived_repeated_count = int(counts.get("short_lived_repeated", 0))
    report.persistent_count = int(counts.get("persistent", 0))

    if not df.empty:
        dates = pd.to_datetime(df["acq_date"])
        report.date_range = (str(dates.min().date()), str(dates.max().date()))

    return clusters, report


def save_persistence_dataset(df: pd.DataFrame) -> Path:
    cfg = get_config()
    out_path: Path = cfg.processed_data_dir / "firms_persistence.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved persistence dataset: %s (%d clusters)", out_path, len(df))
    return out_path


def print_summary(report: PersistenceRunReport) -> None:
    print("\n=== Persistence Analysis Summary ===")
    print(f"Input records:              {report.input_records}")
    print(f"Number of clusters:         {report.cluster_count}")
    print(f"Isolated detections:        {report.isolated_count}")
    print(f"Short-lived/repeated:       {report.short_lived_repeated_count}")
    print(f"Persistent candidates:      {report.persistent_count}")
    print(f"Date range:                 {report.date_range}")
    print("Persistence-category counts:")
    for cat, count in report.category_counts.items():
        print(f"  {cat:24s} {count}")
    print("=====================================\n")