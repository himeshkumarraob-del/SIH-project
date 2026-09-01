"""
Tests for src/models/industrial_classifier.py and src/osm/osm_context.py.

Verifies evidence scoring, category assignments, missing data fallbacks (OSM/LULC),
scientific guardrails (OSM alone cannot prove industrial fire), rationale presence,
and dataset non-mutation.
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import pytest

from src.models.industrial_classifier import IndustrialClassifier
from src.osm.osm_context import OSMContextExtractor

def _make_dummy_cluster_record(
    cluster_id=1,
    active_days=1,
    pers_cat="isolated",
    max_frp=5.0,
    bt_diff_max=15.0,
    max_bright_ti4=310.0,
    movement_status="INSUFFICIENT_DATA",
    total_movement_distance_km=0.0,
    osm_facility_type="UNKNOWN",
    osm_distance_km=float("inf"),
    land_cover_class="UNKNOWN"
) -> pd.DataFrame:
    return pd.DataFrame([{
        "cluster_id": cluster_id,
        "active_days": active_days,
        "persistence_category": pers_cat,
        "max_frp": max_frp,
        "bt_diff_max": bt_diff_max,
        "max_bright_ti4": max_bright_ti4,
        "movement_status": movement_status,
        "total_movement_distance_km": total_movement_distance_km,
        "osm_facility_type": osm_facility_type,
        "osm_distance_km": osm_distance_km,
        "land_cover_class": land_cover_class
    }])

def test_industrial_context_evidence():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=5,
        pers_cat="persistent",
        movement_status="STATIONARY",
        total_movement_distance_km=0.0,
        bt_diff_max=45.0,
        max_bright_ti4=350.0,
        osm_facility_type="refinery",
        osm_distance_km=0.3
    )
    res = classifier.classify_clusters(df)
    
    assert res.iloc[0]["classification_label"] == "Industrial-context thermal event"
    assert res.iloc[0]["classification_score"] >= 0.70
    assert "activity is persistent" in res.iloc[0]["classification_rationale"]
    assert "industrial facility detected nearby" in res.iloc[0]["classification_rationale"]

def test_agricultural_context_evidence():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=1,
        pers_cat="isolated",
        max_frp=12.0,
        bt_diff_max=10.0,
        movement_status="INSUFFICIENT_DATA",
        total_movement_distance_km=0.1,
        land_cover_class="cropland"
    )
    res = classifier.classify_clusters(df)
    
    assert res.iloc[0]["classification_label"] == "Agricultural-context thermal event"
    assert res.iloc[0]["classification_score"] >= 0.50

def test_forest_natural_context_evidence():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=3,
        pers_cat="short_lived_repeated",
        max_frp=35.0,
        movement_status="MOVING",
        total_movement_distance_km=2.5,
        land_cover_class="forest"
    )
    res = classifier.classify_clusters(df)
    
    assert res.iloc[0]["classification_label"] == "Forest/Natural-context thermal event"
    assert res.iloc[0]["classification_score"] >= 0.60
    assert "active spatial displacement observed" in res.iloc[0]["classification_rationale"]

def test_unknown_insufficient_evidence():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=1,
        pers_cat="isolated",
        max_frp=1.0,
        bt_diff_max=2.0,
        movement_status="INSUFFICIENT_DATA"
    )
    res = classifier.classify_clusters(df)
    
    assert res.iloc[0]["classification_label"] == "Unknown / Insufficient Evidence"
    assert res.iloc[0]["classification_score"] == 0.0

def test_missing_osm_data_fallback():
    extractor = OSMContextExtractor(use_network=False)
    df_coords = pd.DataFrame([{"latitude": 20.0, "longitude": 78.0}])
    res_osm = extractor.extract_context(df_coords)
    
    assert res_osm.iloc[0]["osm_facility_type"] == "UNKNOWN"
    assert res_osm.iloc[0]["osm_distance_km"] == float("inf")

def test_missing_land_cover_data_noted_in_rationale():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=5,
        pers_cat="persistent",
        movement_status="STATIONARY",
        land_cover_class="UNKNOWN"
    )
    res = classifier.classify_clusters(df)
    
    assert "land-cover context is UNKNOWN" in res.iloc[0]["classification_rationale"]

def test_osm_proximity_alone_cannot_prove_industrial_classification():
    classifier = IndustrialClassifier()
    # Close to OSM facility (0.1 km), BUT moving rapidly (2.0 km) and single-day/transient
    df = _make_dummy_cluster_record(
        active_days=1,
        pers_cat="isolated",
        movement_status="MOVING",
        total_movement_distance_km=2.0,
        osm_facility_type="factory",
        osm_distance_km=0.1
    )
    res = classifier.classify_clusters(df)
    
    # Must NOT be classified as Industrial-context thermal event because movement contradicts industrial stack!
    assert res.iloc[0]["classification_label"] != "Industrial-context thermal event"

def test_prohibited_terms_never_output():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(active_days=10, pers_cat="persistent", osm_facility_type="refinery", osm_distance_km=0.1)
    res = classifier.classify_clusters(df)
    
    label = res.iloc[0]["classification_label"]
    prohibited = ["Confirmed Industrial Fire", "Confirmed Factory Fire", "Definite Explosion", "Confirmed Gas Leak"]
    for term in prohibited:
        assert term not in label

def test_score_bounded_0_to_1():
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record(
        active_days=10, pers_cat="persistent", bt_diff_max=100.0, max_bright_ti4=400.0,
        movement_status="STATIONARY", osm_facility_type="factory", osm_distance_km=0.1, land_cover_class="built-up"
    )
    res = classifier.classify_clusters(df)
    
    assert 0.0 <= res.iloc[0]["classification_score"] <= 1.0

def test_input_datasets_remain_unchanged():
    ai_file = Path("data/processed/firms_ai_results.csv")
    move_file = Path("data/processed/thermal_movement.csv")
    
    assert ai_file.exists()
    assert move_file.exists()
    
    mtime_ai_before = os.path.getmtime(ai_file)
    mtime_move_before = os.path.getmtime(move_file)
    
    classifier = IndustrialClassifier()
    df = _make_dummy_cluster_record()
    classifier.classify_clusters(df)
    
    assert mtime_ai_before == os.path.getmtime(ai_file)
    assert mtime_move_before == os.path.getmtime(move_file)
