"""
Stable thermal-event identity layer.

WHY THIS EXISTS
---------------
The persistence stage re-clusters the full dataset on every pipeline run and
renumbers clusters 0..k-1. Those sequential ids are *grouping* results, not
identities: adding one new FIRMS observation can shift every downstream
cluster_id. Thermal alerts are keyed TAL-{cluster_id}, so raw sequential ids
must never be used as long-term event identity — an operator ACKNOWLEDGED /
RESOLVED state could silently attach to a different physical source.

WHAT THIS MODULE DOES
---------------------
After each fresh clustering pass, it resolves a STABLE identity for every
cluster and remaps cluster_id to a canonical value before any per-cluster
intelligence is generated:

1. event_key (physical identity, deterministic):
       sha1_16("EVK1|{source_satellite}|{lat:.3f}|{lon:.3f}")
   derived from the cluster's ANCHOR observation = earliest-dated detection,
   ties broken by (latitude, longitude, detection_id). Rounding at 3 decimals
   (~111 m at the equator) is coarser than the 1.0 km clustering threshold, so
   any anchor inside one cluster yields the same key, and finer than typical
   cluster diameter, so distinct sources rarely collide. The satellite is part
   of the key so a collocated anchor from another sensor never merges keys.

2. Continuity matching (the identity AUTHORITY, not the hash):
   every run, current clusters are matched one-to-one against the previous
   run's registry entries by centroid distance (<= match_radius_km, default
   1.5x the clustering spatial threshold). A matched cluster INHERITS the
   previous event_key and canonical cluster_id regardless of sequential
   renumbering. Matching is greedy in a deterministic order (entries by most
   recent last_seen, then event_key; clusters by observation_count desc, then
   fresh id) so identical inputs always produce identical output. Entries not
   seen for more than REGISTRY_EXPIRY_DAYS are no longer matched (a source
   silent that long that reactivates is treated as a new episode with a new
   alert id).

3. Canonical cluster_id assignment:
   - matched clusters keep their previous canonical id;
   - genuinely new events get ids above MAX EVER RECORDED (bootstrapped from
     the deployed alert snapshot), so the id of a retired event is never
     reused while its TAL-{id} row may still exist in history files.

4. Bootstrap alignment (one-time, legacy -> stable):
   when no registry exists, the previous identity state is reconstructed from
   the deployed gis_thermal_events.csv (one row per detection with the legacy
   cluster_id it was clustered under). Because that artifact was produced by
   the same deterministic cluster_detections() on the same firms_india.csv,
   a fresh clustering of the same input reproduces the legacy membership
   exactly, so legacy ids (e.g. 1105 / TAL-01105) are preserved bit-for-bit.

WHAT THIS MODULE DOES NOT CLAIM
-------------------------------
Identity here means "the same monitored thermal source location (per
satellite) within the match radius and registry expiry window". It is a
monitoring bookkeeping construct for decision support — not a claim that two
linked observations are the same physical combustion process.

All writes performed by this module are atomic (temp file + os.replace).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import PersistenceConfig
from src.logging_setup import get_logger

logger = get_logger("persistence.event_identity")

EARTH_RADIUS_KM = 6371.0088

# Versioned key payload: bump EVENT_KEY_VERSION if the derivation ever changes.
EVENT_KEY_VERSION = "EVK1"

# Registry semantic constants (documented defaults; overridable per call).
DEFAULT_MATCH_RADIUS_FACTOR = 1.5   # match_radius = factor * spatial_distance_km
DEFAULT_REGISTRY_EXPIRY_DAYS = 14   # entries unseen this long are not re-matched
REGISTRY_PRUNE_DAYS = 90            # hard-prune entries unseen this long
REGISTRY_VERSION = 1

# Per-detection identity columns added to firms_india.csv.
IDENTITY_COLUMNS = ("event_key", "identity_status", "legacy_cluster_id")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points (scalar)."""
    phi1, lam1, phi2, lam2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def _haversine_km_vec(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Vectorized great-circle distance (km) from one point to arrays of points."""
    phi1, lam1 = math.radians(lat), math.radians(lon)
    phi2 = np.radians(lats)
    lam2 = np.radians(lons)
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = np.sin(dphi / 2) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON atomically: temp file in the same directory, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def _iso_date(value: Any) -> Optional[str]:
    """Best-effort ISO date string (YYYY-MM-DD) from date/datetime/str/NaN."""
    if value is None:
        return None
    try:
        if isinstance(value, (datetime, pd.Timestamp)):
            if pd.isna(value):
                return None
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        return pd.to_datetime(s).date().isoformat()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Event key (anchor hash)
# ---------------------------------------------------------------------------

def build_event_key(anchor_lat: float, anchor_lon: float, anchor_satellite: str) -> str:
    """
    Deterministic physical-identity key for a thermal event.

    Derived from the ANCHOR observation (earliest detection of the cluster):
      * source_satellite (e.g. 'NOAA-20'): sensor is part of the identity so a
        collocated anchor from another satellite never silently merges keys;
      * coordinates rounded to 3 decimals (~111 m): coarser than the 1 km
        clustering threshold, finer than typical cluster extent.

    NOTE: the key alone is NOT the continuity authority. A delayed/backfilled
    observation can shift the anchor between runs; in that case the registry
    centroid match (resolve_event_identity) preserves identity and the key is
    simply re-pointed in the registry. The key's job is to give first-time
    events a stable, collision-resistant default identifier.
    """
    payload = (
        f"{EVENT_KEY_VERSION}|"
        f"{str(anchor_satellite).strip().upper()}|"
        f"{float(anchor_lat):.3f}|"
        f"{float(anchor_lon):.3f}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _anchor_observation(cluster_rows: pd.DataFrame) -> pd.Series:
    """
    Pick the anchor row of a cluster: earliest acq_date; ties broken by
    (latitude, longitude, detection_id) lexicographic order. Deterministic
    regardless of row order in the input frame.
    """
    rows = cluster_rows.copy()
    rows["_lat"] = pd.to_numeric(rows["latitude"], errors="coerce")
    rows["_lon"] = pd.to_numeric(rows["longitude"], errors="coerce")
    rows["_date"] = pd.to_datetime(rows["acq_date"], errors="coerce")
    rows["_det"] = rows["detection_id"].astype(str) if "detection_id" in rows.columns else ""
    rows = rows.sort_values(
        ["_date", "_lat", "_lon", "_det"], kind="mergesort", na_position="last"
    )
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Registry (persistent identity state)
# ---------------------------------------------------------------------------

def empty_registry() -> Dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "last_run_utc": None,
        "max_ever_cluster_id": -1,
        "events": {},
        "bootstrap": False,
    }


def load_registry(path: Path) -> Optional[Dict[str, Any]]:
    """Load the identity registry; None when absent/corrupt (caller bootstraps)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "events" not in data:
            logger.warning("Identity registry at %s is malformed; will re-bootstrap.", path)
            return None
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read identity registry %s: %s; will re-bootstrap.", path, exc)
        return None


def save_registry(path: Path, registry: Dict[str, Any], run_utc: Optional[str] = None) -> None:
    """Persist the registry atomically."""
    registry = dict(registry)
    registry["version"] = REGISTRY_VERSION
    registry["last_run_utc"] = run_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _atomic_write_json(path, registry)


def bootstrap_registry_from_legacy(
    gis_events_df: Optional[pd.DataFrame],
    max_known_cluster_id: int,
) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    """
    Reconstruct the previous identity state from deployed legacy artifacts.

    gis_events_df: per-detection rows from data/processed/gis_thermal_events.csv
      (must contain cluster_id, latitude, longitude, acq_date).
    max_known_cluster_id: highest cluster id ever issued (e.g. max cluster_id
      in thermal_alerts.csv / firms_persistence.csv) — new events start above it.

    Returns (registry, bootstrap_entries) where bootstrap_entries maps
    legacy cluster_id -> {centroid_lat, centroid_lon, last_seen, observation_count}.
    Bootstrap entries carry no event_key yet; the first identity run assigns
    real keys to the clusters that match them.
    """
    registry = empty_registry()
    registry["max_ever_cluster_id"] = int(max_known_cluster_id)
    registry["bootstrap"] = True

    entries: Dict[int, Dict[str, Any]] = {}
    if gis_events_df is None or gis_events_df.empty:
        logger.warning(
            "Identity bootstrap: no legacy gis_thermal_events data available; "
            "first run will treat all clusters as new events."
        )
        return registry, entries

    required = {"cluster_id", "latitude", "longitude"}
    missing = required - set(gis_events_df.columns)
    if missing:
        logger.warning(
            "Identity bootstrap: legacy gis frame missing columns %s; "
            "treating all clusters as new events.", sorted(missing),
        )
        return registry, entries

    gis = gis_events_df.copy()
    gis["latitude"] = pd.to_numeric(gis["latitude"], errors="coerce")
    gis["longitude"] = pd.to_numeric(gis["longitude"], errors="coerce")
    gis = gis.dropna(subset=["latitude", "longitude"])
    gis["cluster_id"] = pd.to_numeric(gis["cluster_id"], errors="coerce").astype("Int64")
    gis = gis.dropna(subset=["cluster_id"])

    for legacy_cid, group in gis.groupby("cluster_id"):
        last_seen = None
        if "acq_date" in group.columns:
            dates = pd.to_datetime(group["acq_date"], errors="coerce").dropna()
            last_seen = dates.max().date().isoformat() if len(dates) else None
        entries[int(legacy_cid)] = {
            "centroid_lat": float(group["latitude"].mean()),
            "centroid_lon": float(group["longitude"].mean()),
            "last_seen": last_seen,
            "observation_count": int(len(group)),
        }

    logger.info(
        "Identity bootstrap reconstructed %d legacy event(s) from gis_thermal_events "
        "(max known cluster id: %d).",
        len(entries), registry["max_ever_cluster_id"],
    )
    return registry, entries


def _max_known_cluster_id_from_artifacts(data_dir: Path) -> int:
    """Highest cluster id ever issued, from deployed alert/intelligence artifacts."""
    best = -1
    for name in ("thermal_alerts.csv", "firms_persistence.csv", "firms_ai_results.csv"):
        p = Path(data_dir) / name
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p, usecols=lambda c: c == "cluster_id")
        except (ValueError, OSError, pd.errors.ParserError):
            # usecols raises ValueError if the file has no cluster_id column.
            continue
        if df.empty or "cluster_id" not in df.columns:
            continue
        try:
            mx = pd.to_numeric(df["cluster_id"], errors="coerce").max()
            if pd.notna(mx):
                best = max(best, int(mx))
        except (TypeError, ValueError):
            continue
    return best


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------

@dataclass
class IdentityReport:
    run_utc: str = ""
    clusters_total: int = 0
    continued: int = 0
    reassociated: int = 0
    new_events: int = 0
    registry_expired: int = 0
    bootstrap_matched: int = 0
    bootstrap_unmatched: int = 0
    max_ever_cluster_id: int = -1
    new_cluster_ids: List[int] = field(default_factory=list)
    preserved_alert_ids: List[int] = field(default_factory=list)


def _cluster_summaries(
    clustered_df: pd.DataFrame, fresh_ids: np.ndarray
) -> List[Dict[str, Any]]:
    """One summary per fresh cluster: centroid, dates, anchor key, sizes."""
    work = clustered_df.copy()
    work["_fresh"] = fresh_ids
    work["latitude"] = pd.to_numeric(work["latitude"], errors="coerce")
    work["longitude"] = pd.to_numeric(work["longitude"], errors="coerce")
    work = work.dropna(subset=["latitude", "longitude"])

    summaries: List[Dict[str, Any]] = []
    for fresh_id, group in work.groupby("_fresh"):
        anchor = _anchor_observation(group)
        first_detection = pd.to_datetime(group["acq_date"], errors="coerce").min()
        summaries.append(
            {
                "fresh_id": int(fresh_id),
                "centroid_lat": float(group["latitude"].mean()),
                "centroid_lon": float(group["longitude"].mean()),
                "observation_count": int(len(group)),
                "first_detection": _iso_date(first_detection),
                "last_seen": _iso_date(pd.to_datetime(group["acq_date"], errors="coerce").max()),
                "anchor_lat": float(anchor["latitude"]),
                "anchor_lon": float(anchor["longitude"]),
                "anchor_satellite": str(
                    anchor.get("source_satellite", anchor.get("satellite", "UNKNOWN"))
                ),
                "event_key": build_event_key(
                    float(anchor["latitude"]),
                    float(anchor["longitude"]),
                    str(anchor.get("source_satellite", anchor.get("satellite", "UNKNOWN"))),
                ),
            }
        )

    # Deterministic processing order: largest clusters first, then fresh id.
    summaries.sort(key=lambda s: (-s["observation_count"], s["fresh_id"]))
    return summaries


def resolve_event_identity(
    clustered_df: pd.DataFrame,
    fresh_cluster_ids: np.ndarray,
    registry: Dict[str, Any],
    bootstrap_entries: Optional[Dict[int, Dict[str, Any]]] = None,
    spatial_distance_km: float = 1.0,
    match_radius_factor: float = DEFAULT_MATCH_RADIUS_FACTOR,
    registry_expiry_days: int = DEFAULT_REGISTRY_EXPIRY_DAYS,
    run_utc: Optional[str] = None,
) -> Tuple[np.ndarray, List[str], List[str], IdentityReport]:
    """
    Resolve stable identity for every fresh cluster and produce the canonical
    cluster_id mapping.

    Parameters
    ----------
    clustered_df : per-detection frame (needs latitude, longitude, acq_date;
                   detection_id and source_satellite recommended).
    fresh_cluster_ids : output of cluster_detections(), aligned by row position.
    registry : loaded registry dict (see load_registry / bootstrap helpers).
    bootstrap_entries : legacy {cluster_id: {centroid_lat, centroid_lon,
                        last_seen, observation_count}} when bootstrapping.
    spatial_distance_km : the clustering spatial threshold (match radius scales
                          from it).

    Returns
    -------
    (canonical_ids, event_keys, identity_statuses, report)
        canonical_ids : np.ndarray of int, aligned by row position — the
            remapped cluster_id column to persist.
        event_keys : list[str] aligned by row position.
        identity_statuses : list[str] aligned by row position
            ("continued" | "reassociated" | "new" | "bootstrap_continued").
        report : IdentityReport summary of the run.
    """
    run_utc = run_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = IdentityReport(run_utc=run_utc, max_ever_cluster_id=int(registry.get("max_ever_cluster_id", -1)))
    bootstrap_entries = bootstrap_entries or {}

    match_radius_km = max(float(spatial_distance_km) * float(match_radius_factor), 0.05)
    now_dt = datetime.now(timezone.utc)

    summaries = _cluster_summaries(clustered_df, fresh_cluster_ids)
    report.clusters_total = len(summaries)

    events: Dict[str, Dict[str, Any]] = dict(registry.get("events", {}))

    # -- Prune + expire -----------------------------------------------------
    active_entries: List[Tuple[str, Dict[str, Any]]] = []
    for key, entry in events.items():
        last_run = entry.get("last_run_utc")
        days_idle = REGISTRY_PRUNE_DAYS + 1.0
        if last_run:
            try:
                days_idle = (now_dt - datetime.fromisoformat(str(last_run))).total_seconds() / 86400.0
            except ValueError:
                days_idle = REGISTRY_PRUNE_DAYS + 1.0
        if days_idle > REGISTRY_PRUNE_DAYS:
            report.registry_expired += 1
            continue  # hard-pruned
        if days_idle > float(registry_expiry_days):
            report.registry_expired += 1
            continue  # expired: not matchable this run (but kept in registry)
        active_entries.append((key, entry))

    # Deterministic match order: most recently seen first, then key.
    active_entries.sort(
        key=lambda kv: (
            str(kv[1].get("last_seen") or ""),
            str(kv[0]),
        ),
        reverse=True,
    )

    # Bootstrap entries participate once (they have no event_key yet) and use
    # legacy ids directly. Order: most recently seen first.
    boot_items: List[Tuple[int, Dict[str, Any]]] = sorted(
        bootstrap_entries.items(),
        key=lambda kv: (str(kv[1].get("last_seen") or ""), -kv[0]),
        reverse=True,
    )

    matched_summary_idx: Dict[int, str] = {}      # summary index -> event_key
    matched_canonical: Dict[int, int] = {}        # summary index -> canonical id
    matched_status: Dict[int, str] = {}
    consumed_entries: set = set()
    used_bootstrap: set = set()

    cluster_lats = np.array([s["centroid_lat"] for s in summaries], dtype=float)
    cluster_lons = np.array([s["centroid_lon"] for s in summaries], dtype=float)

    def _nearest_free(entry_lat: float, entry_lon: float) -> Optional[int]:
        """Index of the nearest unmatched cluster within the match radius."""
        if len(summaries) == 0:
            return None
        dists = _haversine_km_vec(entry_lat, entry_lon, cluster_lats, cluster_lons)
        order = np.argsort(dists, kind="mergesort")
        for idx in order:
            idx = int(idx)
            if idx in matched_summary_idx:
                continue
            if dists[idx] <= match_radius_km:
                return idx
            break  # sorted: first out-of-radius ends the search
        return None

    # -- 1. Registry continuity (authoritative for known events) ------------
    for key, entry in active_entries:
        if key in consumed_entries:
            continue
        idx = _nearest_free(float(entry["centroid_lat"]), float(entry["centroid_lon"]))
        if idx is None:
            continue
        matched_summary_idx[idx] = key
        matched_canonical[idx] = int(entry["cluster_id"])
        matched_status[idx] = "continued"
        consumed_entries.add(key)
        report.continued += 1
        cid = int(entry["cluster_id"])
        if cid not in report.preserved_alert_ids:
            report.preserved_alert_ids.append(cid)

    # -- 2. Bootstrap alignment (first run only) ----------------------------
    for legacy_cid, entry in boot_items:
        if legacy_cid in used_bootstrap:
            continue
        idx = _nearest_free(float(entry["centroid_lat"]), float(entry["centroid_lon"]))
        if idx is None:
            report.bootstrap_unmatched += 1
            continue
        used_bootstrap.add(legacy_cid)
        matched_summary_idx[idx] = summaries[idx]["event_key"]
        matched_canonical[idx] = int(legacy_cid)
        matched_status[idx] = "bootstrap_continued"
        report.bootstrap_matched += 1
        if int(legacy_cid) not in report.preserved_alert_ids:
            report.preserved_alert_ids.append(int(legacy_cid))

    # -- 3. Remaining clusters = new events ---------------------------------
    next_id = int(registry.get("max_ever_cluster_id", -1)) + 1
    for idx, summary in enumerate(summaries):
        if idx in matched_summary_idx:
            continue
        event_key = summary["event_key"]
        # Same anchor cell + satellite re-appearing in one run is a distinct
        # episode only if the key is already taken by a live registry entry;
        # suffix with the episode start date to keep keys unique.
        if event_key in events or event_key in {matched_summary_idx[i] for i in matched_summary_idx}:
            event_key = f"{event_key}-{(summary['first_detection'] or 'unknown').replace('-', '')}"
        matched_summary_idx[idx] = event_key
        matched_canonical[idx] = next_id
        matched_status[idx] = "new"
        report.new_events += 1
        report.new_cluster_ids.append(next_id)
        next_id += 1

    # -- 4. Update registry --------------------------------------------------
    for idx, summary in enumerate(summaries):
        key = matched_summary_idx[idx]
        events[key] = {
            "cluster_id": int(matched_canonical[idx]),
            "centroid_lat": summary["centroid_lat"],
            "centroid_lon": summary["centroid_lon"],
            "first_detection": summary["first_detection"],
            "last_seen": summary["last_seen"],
            "observation_count": summary["observation_count"],
            "last_run_utc": run_utc,
            "identity_status_last": matched_status[idx],
        }
    registry["events"] = events
    registry["max_ever_cluster_id"] = max(
        int(registry.get("max_ever_cluster_id", -1)),
        next_id - 1,
    )
    registry["bootstrap"] = False
    report.max_ever_cluster_id = int(registry["max_ever_cluster_id"])

    # -- 5. Build row-aligned outputs ----------------------------------------
    canonical_ids = fresh_cluster_ids.copy()
    event_keys: List[str] = [""] * len(fresh_cluster_ids)
    statuses: List[str] = [""] * len(fresh_cluster_ids)

    summary_by_fresh = {s["fresh_id"]: i for i, s in enumerate(summaries)}
    for row_pos, fresh_id in enumerate(fresh_cluster_ids):
        s_idx = summary_by_fresh.get(int(fresh_id))
        if s_idx is None:
            # Detection had invalid coordinates and formed no summary; keep the
            # fresh grouping id so the row is never silently dropped.
            canonical_ids[row_pos] = int(fresh_id)
            event_keys[row_pos] = "UNKNOWN"
            statuses[row_pos] = "unresolved"
            continue
        canonical_ids[row_pos] = matched_canonical[s_idx]
        event_keys[row_pos] = matched_summary_idx[s_idx]
        statuses[row_pos] = matched_status[s_idx]

    logger.info(
        "Event identity resolved: %d cluster(s) — continued=%d bootstrap_continued=%d "
        "new=%d (new ids: %s); match radius %.2f km; max_ever_cluster_id=%d",
        report.clusters_total, report.continued, report.bootstrap_matched,
        report.new_events, report.new_cluster_ids[:10], match_radius_km,
        report.max_ever_cluster_id,
    )
    return canonical_ids, event_keys, statuses, report


def apply_identity_to_frame(
    india_df: pd.DataFrame,
    fresh_cluster_ids: np.ndarray,
    canonical_ids: np.ndarray,
    event_keys: List[str],
    identity_statuses: List[str],
) -> pd.DataFrame:
    """
    Return a copy of the India-filtered detection frame with canonical
    cluster_id, event_key, identity_status and legacy (fresh) id attached —
    the per-detection artifact that movement analysis and the GIS builder
    consume.
    """
    out = india_df.copy()
    if len(out) != len(canonical_ids):
        raise ValueError(
            f"Row-count mismatch applying identity: frame {len(out)} vs ids {len(canonical_ids)}"
        )
    out["legacy_cluster_id"] = fresh_cluster_ids.astype(int)
    out["cluster_id"] = canonical_ids.astype(int)
    out["event_key"] = event_keys
    out["identity_status"] = identity_statuses
    return out
