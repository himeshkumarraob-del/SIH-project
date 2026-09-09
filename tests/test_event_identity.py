"""
Regression tests for the stable thermal-event identity layer.

Covers:
  * the two highest-risk failure modes identified in the live-ingestion plan:
      - cluster_id churn across pipeline re-runs (TAL-{id} mis-association)
      - historical + live data merging (new observations must not renumber
        existing events)
  * alert-continuity guarantees for ACKNOWLEDGED / RESOLVED state
  * bootstrap alignment against legacy artifacts (cluster 1105 preservation)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PersistenceConfig  # noqa: E402
from src.persistence.event_identity import (  # noqa: E402
    apply_identity_to_frame,
    bootstrap_registry_from_legacy,
    build_event_key,
    empty_registry,
    resolve_event_identity,
)
from src.persistence.persistence_analysis import (  # noqa: E402
    cluster_detections,
    compute_cluster_features,
)


def _pcfg() -> PersistenceConfig:
    # Mirrors config.yaml persistence thresholds (1 km / 3 days).
    return PersistenceConfig(
        spatial_distance_km=1.0,
        temporal_window_days=3,
        persistent_min_active_days=5,
        repeated_min_active_days=2,
    )


def _det(lat, lon, y, m, d, hhmm=830, sat="NOAA-20", frp=5.0):
    """One FIRMS-style detection row."""
    day = pd.Timestamp(y, m, d)
    return {
        "latitude": float(lat),
        "longitude": float(lon),
        "bright_ti4": 330.0,
        "bright_ti5": 290.0,
        "frp": frp,
        "confidence": "n",
        "acq_date": day.date().isoformat(),
        "acq_time": str(hhmm).zfill(4),
        "satellite": "N20",
        "instrument": "VIIRS",
        "source_satellite": sat,
        "detection_id": f"{lat:.5f}|{lon:.5f}|{y}{m:02d}{d:02d}{hhmm:04d}",
    }


def _site(rows, center=(24.0, 78.0), day=1, n=3, hhmm=830, sat="NOAA-20"):
    """A tight cluster of detections around a center point on a given day."""
    for i in range(n):
        rows.append(_det(center[0] + 0.001 * i, center[1] + 0.001 * i, 2026, 9, day, hhmm, sat))
    return rows


def _fresh_ids(df):
    return cluster_detections(df, _pcfg())


def _resolve(df, registry, bootstrap=None):
    fresh = _fresh_ids(df)
    return resolve_event_identity(
        df,
        fresh,
        registry,
        bootstrap_entries=bootstrap,
        spatial_distance_km=1.0,
    )


def _make_registry(df, ids, keys):
    reg = empty_registry()
    reg["max_ever_cluster_id"] = int(pd.Series(ids).max())
    reg["events"] = {}
    tmp = pd.DataFrame(
        {
            "cluster_id": ids,
            "event_key": keys,
            "latitude": df["latitude"].to_numpy(),
            "longitude": df["longitude"].to_numpy(),
            "acq_date": df["acq_date"].to_numpy(),
        }
    )
    for cid, g in tmp.groupby("cluster_id"):
        reg["events"][g["event_key"].iloc[0]] = {
            "cluster_id": int(cid),
            "centroid_lat": float(g["latitude"].mean()),
            "centroid_lon": float(g["longitude"].mean()),
            "first_detection": str(g["acq_date"].min()),
            "last_seen": str(g["acq_date"].max()),
            "observation_count": int(len(g)),
            "last_run_utc": "2026-09-08T00:00:00+00:00",
        }
    reg["max_ever_cluster_id"] = max(reg["max_ever_cluster_id"], int(tmp["cluster_id"].max()))
    return reg


# ---------------------------------------------------------------------------
# Determinism / event key
# ---------------------------------------------------------------------------

def test_event_key_deterministic_and_satellite_scoped():
    k1 = build_event_key(24.012345, 78.012345, "NOAA-20")
    k2 = build_event_key(24.0121, 78.0122, "NOAA-20")  # same cell, not on a boundary
    assert k1 == k2, "anchors within the same ~111 m cell must share a key"
    k_other_sat = build_event_key(24.012345, 78.012345, "NOAA-21")
    assert k1 != k_other_sat, "satellite must be part of the key"
    k_shifted = build_event_key(24.02, 78.02, "NOAA-20")
    assert k1 != k_shifted, "distinct anchor cells must not collide"


def test_clustering_is_deterministic():
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    _site(rows, center=(27.5, 80.0), day=2)
    df = pd.DataFrame(rows)
    fresh_a = _fresh_ids(df.sample(frac=1.0, random_state=1).reset_index(drop=True))
    fresh_b = _fresh_ids(df.sample(frac=1.0, random_state=2).reset_index(drop=True))
    # group membership (canonical labels are derived separately) is what matters
    a_members = set(map(tuple, pd.DataFrame({"lat": df["latitude"]}).assign(fresh=fresh_a).groupby("fresh").indices.values()))
    b_members = set(map(tuple, pd.DataFrame({"lat": df["latitude"]}).assign(fresh=fresh_b).groupby("fresh").indices.values()))
    assert len(a_members) == len(b_members) == 2


# ---------------------------------------------------------------------------
# Identity across re-runs / new observations / merged data
# ---------------------------------------------------------------------------

def test_identity_stable_when_new_observations_added():
    """Run 1: two sites. Run 2: same sites + new detections at site A (more
    observations, same physical events). Canonical ids must not change."""
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    _site(rows, center=(27.0, 80.5), day=2)
    df1 = pd.DataFrame(rows)
    ids1, keys1, _, _ = _resolve(df1, empty_registry())
    reg = _make_registry(df1, ids1, keys1)

    # Run 2: add observations to site A only.
    rows2 = [r for r in rows]
    rows2.append(_det(24.0005, 78.0005, 2026, 9, 3))  # new day at site A
    df2 = pd.DataFrame(rows2)
    ids2, keys2, _, report2 = _resolve(df2, reg)

    id1_a = ids1[np.argmin(np.abs(df1["latitude"].to_numpy() - 24.0))]
    id2_a = ids2[np.argmin(np.abs(df2["latitude"].to_numpy() - 24.0))]
    assert id1_a == id2_a, "site A canonical id must survive new observations"
    assert report2.new_events == 0, f"expected no new events, got {report2.new_events}"
    assert report2.continued == 2
    # Canonical id set identical across runs
    assert set(ids2.tolist()) == set(ids1.tolist())


def test_identity_stable_when_same_observation_fetched_again():
    """Re-running the exact same input (overlap fetch) must be a no-op on ids."""
    rows = []
    _site(rows, center=(24.0, 78.0), day=1, n=4)
    df = pd.DataFrame(rows)
    ids1, keys1, _, _ = _resolve(df, empty_registry())
    reg = _make_registry(df, ids1, keys1)
    ids2, keys2, _, report2 = _resolve(df, reg)
    assert list(ids1) == list(ids2)
    assert report2.new_events == 0 and report2.continued == 1
    # Same event_key both runs
    assert set(keys1) == set(keys2)


def test_two_day_overlap_window_does_not_duplicate_events():
    """Day1 fetched in cycle 1; days 1-2 fetched again in cycle 2 (overlap).
    The event must keep its identity and not fork into two events."""
    rows = []
    _site(rows, center=(24.0, 78.0), day=1, n=2)
    df1 = pd.DataFrame(rows)
    ids1, keys1, _, _ = _resolve(df1, empty_registry())
    reg = _make_registry(df1, ids1, keys1)

    rows2 = rows + [_det(24.001, 78.001, 2026, 9, 2), _det(24.002, 78.002, 2026, 9, 2)]
    df2 = pd.DataFrame(rows2)
    ids2, keys2, _, report2 = _resolve(df2, reg)
    assert report2.new_events == 0
    assert set(ids2.tolist()) == set(ids1.tolist())


def test_distinct_sites_never_merge_or_swap_ids():
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    _site(rows, center=(28.5, 84.0), day=1)
    _site(rows, center=(31.0, 76.0), day=1)
    df = pd.DataFrame(rows)
    ids, keys, statuses, report = _resolve(df, empty_registry())
    assert report.new_events == 3
    assert len(set(ids.tolist())) == 3
    # Deterministic ordering: canonical ids assigned by cluster size desc,
    # then fresh id — verify sorted determinism by re-running from scratch.
    ids_b, _, _, _ = _resolve(df, empty_registry())
    assert list(ids) == list(ids_b)


def test_new_events_never_reuse_retired_ids():
    """A site goes silent; a brand-new site appears. The new site must get a
    fresh id above max_ever_cluster_id, not the retired one."""
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    df1 = pd.DataFrame(rows)
    ids1, keys1, _, _ = _resolve(df1, empty_registry())
    old_id = int(ids1[0])
    reg = _make_registry(df1, ids1, keys1)

    # Registry entry expired (older than 14 days, simulated via last_run_utc)
    key = next(iter(reg["events"]))
    reg["events"][key]["last_run_utc"] = "2026-08-01T00:00:00+00:00"
    reg["events"][key]["last_seen"] = "2026-08-01"

    # New, far-away site on a later date
    rows2 = [_det(19.0, 73.0, 2026, 9, 5), _det(19.001, 73.001, 2026, 9, 5)]
    df2 = pd.DataFrame(rows2)
    pre_run_max = reg["max_ever_cluster_id"]  # resolve() advances the registry in place
    ids2, _, _, report2 = _resolve(df2, reg)
    new_id = int(ids2[0])
    assert new_id != old_id
    assert new_id > pre_run_max, "new ids must be above max ever issued"
    assert reg["max_ever_cluster_id"] == new_id


def test_identity_survives_historical_plus_live_merge():
    """30-day historical data + fresh live observations merged: legacy events
    keep ids; only genuinely new sites get new ids."""
    # Historical: site A on days 1-3.
    rows = []
    for day in (1, 2, 3):
        _site(rows, center=(24.0, 78.0), day=day, n=2)
    # Historical: site B day 2.
    _site(rows, center=(26.5, 79.5), day=2, n=2)
    hist = pd.DataFrame(rows)

    # Live: site A day 4 (new observations, same event) + brand-new site C.
    live = pd.DataFrame(
        [
            _det(24.0005, 78.0005, 2026, 9, 4),
            _det(24.0015, 78.0015, 2026, 9, 4),
            _det(21.0, 75.0, 2026, 9, 4),
            _det(21.001, 75.001, 2026, 9, 4),
        ]
    )
    merged = pd.concat([hist, live], ignore_index=True)

    # Cycle 1 processes historical only.
    ids_h, keys_h, _, _ = _resolve(hist, empty_registry())
    reg = _make_registry(hist, ids_h, keys_h)
    # Cycle 2 processes merged historical+live.
    ids_m, keys_m, statuses_m, report_m = _resolve(merged, reg)

    idA_hist = ids_h[np.argmin(np.abs(hist["latitude"].to_numpy() - 24.0))]
    idA_merged = ids_m[np.argmin(np.abs(merged["latitude"].to_numpy() - 24.0))]
    idB_merged = ids_m[np.argmin(np.abs(merged["latitude"].to_numpy() - 26.5))]
    idC_merged = ids_m[np.argmin(np.abs(merged["latitude"].to_numpy() - 21.0))]

    assert idA_hist == idA_merged
    assert idB_merged in ids_h.tolist()
    assert report_m.new_events == 1
    assert idC_merged not in ids_h.tolist()
    assert "continued" in statuses_m


# ---------------------------------------------------------------------------
# Cluster feature computation on canonical ids
# ---------------------------------------------------------------------------

def test_compute_cluster_features_on_canonical_ids():
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    _site(rows, center=(26.0, 79.0), day=2)
    df = pd.DataFrame(rows)
    fresh = _fresh_ids(df)
    # arbitrary canonical labels (per row: fresh 0 -> 1100, fresh 1 -> 1101)
    canonical = np.where(fresh == fresh.min(), 1100, 1101)
    feats = compute_cluster_features(df, canonical, _pcfg())
    assert sorted(feats["cluster_id"].tolist()) == [1100, 1101]
    assert set(feats.columns) >= {"event_key", "identity_status"}
    # observation_count sums must match the raw row count
    assert int(feats["observation_count"].sum()) == len(df)


def test_apply_identity_to_frame_columns():
    rows = []
    _site(rows, center=(24.0, 78.0), day=1)
    df = pd.DataFrame(rows)
    fresh = _fresh_ids(df)
    canonical = np.full(len(df), 1105, dtype=int)
    out = apply_identity_to_frame(df, fresh, canonical, ["EVK-TEST"] * len(df), ["new"] * len(df))
    assert "event_key" in out.columns and "identity_status" in out.columns
    assert (out["cluster_id"] == 1105).all()
    assert (out["legacy_cluster_id"] == fresh).all()


# ---------------------------------------------------------------------------
# Bootstrap alignment (legacy preservation)
# ---------------------------------------------------------------------------

def test_bootstrap_preserves_legacy_cluster_ids():
    """Legacy gis_thermal_events membership must be reconstructed so legacy
    canonical ids (e.g. 1105) survive the first identity run."""
    rows = []
    _site(rows, center=(24.0, 78.0), day=1, n=2)
    _site(rows, center=(27.0, 80.0), day=2, n=2)
    df = pd.DataFrame(rows)
    fresh = _fresh_ids(df)

    # Legacy world: same clustering, but ids happened to be 1104 and 1105.
    legacy = {int(f): 1104 + int(f) for f in np.unique(fresh)}
    gis_df = df.copy()
    gis_df["cluster_id"] = [legacy[int(f)] for f in fresh]

    reg, boot = bootstrap_registry_from_legacy(gis_df, max_known_cluster_id=1105)
    assert reg["max_ever_cluster_id"] == 1105

    ids, keys, statuses, report = _resolve(df, reg, bootstrap=boot)
    # Site at lat 24.0 must keep legacy id 1104; site at 27.0 must keep 1105.
    id_low = int(ids[np.argmin(np.abs(df["latitude"].to_numpy() - 24.0))])
    id_high = int(ids[np.argmin(np.abs(df["latitude"].to_numpy() - 27.0))])
    assert {id_low, id_high} == {1104, 1105}
    assert report.bootstrap_matched == 2
    assert report.new_events == 0
    assert all(s in ("bootstrap_continued",) for s in statuses)


def test_bootstrap_1105_exact_preservation():
    """Direct regression for the deployed artifact: cluster 1105 must remain
    1105 after re-clustering + identity resolution on unchanged input."""
    rows = []
    _site(rows, center=(23.5, 86.2), day=1, n=5)
    df = pd.DataFrame(rows)
    fresh = _fresh_ids(df)
    gis_df = df.copy()
    gis_df["cluster_id"] = 1105  # legacy world: this was cluster 1105
    reg, boot = bootstrap_registry_from_legacy(gis_df, max_known_cluster_id=1105)
    ids, _, statuses, _ = _resolve(df, reg, bootstrap=boot)
    assert (ids == 1105).all()
    assert set(statuses) == {"bootstrap_continued"}


# ---------------------------------------------------------------------------
# Alert continuity (integration with the alert engine semantics)
# ---------------------------------------------------------------------------

def test_alert_continuity_ack_resolved_state_survives_reingestion():
    """ACKNOWLEDGED/RESOLVED state must stay attached to the same physical
    event after a re-ingestion that changes fresh clustering labels."""
    from src.models.alert_engine import ThermalAlertEngine, ThermalAlertStore

    tmp = Path(__file__).parent / "_tmp_alerts_identity"
    tmp.mkdir(exist_ok=True)
    for p in tmp.glob("thermal_alert*"):
        p.unlink()

    # Cycle 1: event exists, gets canonical id 1105, operator ACKNOWLEDGES.
    rows = []
    _site(rows, center=(23.5, 86.2), day=1, n=4)
    df1 = pd.DataFrame(rows)
    ids1, keys1, _, _ = _resolve(df1, empty_registry())
    cid1 = int(ids1[0])
    # Force the canonical id to 1105 for determinism of the TAL id.
    ids1 = np.full_like(ids1, 1105)

    def _frame(cid, df):
        return pd.DataFrame(
            {
                "cluster_id": [cid],
                "event_key": keys1[0],
                "risk_score": [72.0],
                "risk_level": ["HIGH"],
                "false_alarm_indicator": ["LOW"],
                "detection_reliability": ["HIGH"],
                "classification_label": ["Industrial context"],
                "classification_score": [0.8],
                "persistence_category": ["persistent"],
                "active_days": [3],
                "observation_count": [12],
                "max_frp": [25.0],
                "max_bright_ti4": [345.0],
                "bt_diff_max": [50.0],
                "latitude": [df["latitude"].mean()],
                "longitude": [df["longitude"].mean()],
                "direction": [None],
                "movement_pattern": ["insufficient_evidence"],
                "direction_confidence": [None],
                "movement_bearing_degrees": [None],
                "movement_rate_km_per_day": [None],
                "station_available": [False],
                "nearest_station_name": [""],
                "station_distance_km": [None],
            }
        )

    store = ThermalAlertStore(tmp)
    fresh1 = ThermalAlertEngine().generate_alerts(_frame(1105, df1))
    store.sync(fresh1, run_reason="cycle 1")
    store.acknowledge(1105)

    # Cycle 2: new observations arrive; fresh clustering would label the site
    # with a different sequential id (e.g. 7), but canonical id must stay 1105.
    rows2 = rows + [_det(23.5005, 86.2005, 2026, 9, 2), _det(23.5015, 86.2015, 2026, 9, 3)]
    df2 = pd.DataFrame(rows2)
    ids2, _, _, report2 = _resolve(df2, _make_registry(df1, ids1, keys1))
    cid2 = int(ids2[0])

    assert cid2 == 1105, (
        f"canonical id drifted: {cid1} -> {cid2}; ACKNOWLEDGED state would "
        "attach to a different physical event"
    )
    assert report2.new_events == 0

    # Upsert the regenerated alerts; status must be preserved as ACKNOWLEDGED.
    fresh2 = ThermalAlertEngine().generate_alerts(_frame(1105, df2))
    eff = store.sync(fresh2, run_reason="cycle 2 (live ingestion)")
    row = eff[eff["cluster_id"] == 1105].iloc[0]
    assert row["status"] == "ACKNOWLEDGED"
    assert row["alert_id"] == "TAL-01105"


def test_alert_continuity_resolved_not_reopened_without_escalation():
    from src.models.alert_engine import ThermalAlertEngine, ThermalAlertStore

    tmp = Path(__file__).parent / "_tmp_alerts_identity2"
    tmp.mkdir(exist_ok=True)
    for p in tmp.glob("thermal_alert*"):
        p.unlink()

    rows = []
    _site(rows, center=(23.5, 86.2), day=1, n=3)
    df1 = pd.DataFrame(rows)
    keys1 = ["EVK-TEST-1105"] * len(df1)  # event_keys are per-row like ids
    ids1 = np.full(len(df1), 1105, dtype=int)  # canonical ids are per-row

    def _frame(cid, df, risk=72.0):
        return pd.DataFrame(
            {
                "cluster_id": [cid],
                "event_key": keys1[0],
                "risk_score": [risk],
                "risk_level": ["HIGH" if risk >= 60 else "LOW"],
                "false_alarm_indicator": ["LOW"],
                "detection_reliability": ["HIGH"],
                "classification_label": ["Industrial context"],
                "classification_score": [0.8],
                "persistence_category": ["persistent"],
                "active_days": [3],
                "observation_count": [len(df)],
                "max_frp": [25.0],
                "max_bright_ti4": [345.0],
                "bt_diff_max": [50.0],
                "latitude": [df["latitude"].mean()],
                "longitude": [df["longitude"].mean()],
                "direction": [None],
                "movement_pattern": ["insufficient_evidence"],
                "direction_confidence": [None],
                "movement_bearing_degrees": [None],
                "movement_rate_km_per_day": [None],
                "station_available": [False],
                "nearest_station_name": [""],
                "station_distance_km": [None],
            }
        )

    store = ThermalAlertStore(tmp)
    store.sync(ThermalAlertEngine().generate_alerts(_frame(1105, df1)), run_reason="c1")
    store.resolve(1105)

    # Later cycle: same physical event, lower intensity -> stays RESOLVED.
    rows2 = rows + [_det(23.5005, 86.2005, 2026, 9, 4)]
    df2 = pd.DataFrame(rows2)
    ids2, _, _, _ = _resolve(
        df2,
        _make_registry(df1, ids1, keys1),
    )
    assert int(ids2[0]) == 1105
    eff = store.sync(ThermalAlertEngine().generate_alerts(_frame(1105, df2, risk=40.0)), run_reason="c2")
    assert eff[eff["cluster_id"] == 1105].iloc[0]["status"] == "RESOLVED"
