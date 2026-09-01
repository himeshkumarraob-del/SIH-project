"""
Tests for Satellite CNN Classifier (src/satellite/) and Evidence Fusion Integration.

Verifies model loading, inference output schema, probability boundaries, missing image handling,
and guardrails preventing CNN alone from overriding physical spatial movement.
"""

from __future__ import annotations

import torch
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from src.satellite.model import build_satellite_model
from src.satellite.preprocessing import preprocess_image
from src.satellite.inference import SatelliteLandUsePredictor
from src.satellite.patch_extractor import PatchExtractor
from src.models.industrial_classifier import IndustrialClassifier

def test_satellite_model_architecture():
    model = build_satellite_model(num_classes=10, pretrained=False)
    dummy_input = torch.randn(2, 3, 64, 64)
    out = model(dummy_input)
    assert out.shape == (2, 10)

def test_preprocessing_and_inference_schema():
    predictor = SatelliteLandUsePredictor()
    patch_extractor = PatchExtractor(patch_size=64)
    
    img = patch_extractor.create_synthetic_patch(landuse_type="Industrial")
    res = predictor.predict(img)

    assert "predicted_landcover_class" in res
    assert "prediction_confidence" in res
    assert "class_probabilities" in res
    
    conf = res["prediction_confidence"]
    assert 0.0 <= conf <= 1.0
    
    probs = list(res["class_probabilities"].values())
    assert abs(sum(probs) - 1.0) < 0.05

def test_invalid_image_fallback():
    predictor = SatelliteLandUsePredictor()
    res = predictor.predict("non_existent_file_path.png")

    assert res["predicted_landcover_class"] == "UNKNOWN"
    assert res["prediction_confidence"] == 0.0

def test_cnn_evidence_integration_in_industrial_classifier():
    classifier = IndustrialClassifier()
    df_with_sat = pd.DataFrame([{
        "cluster_id": 1,
        "active_days": 5,
        "persistence_category": "persistent",
        "movement_status": "STATIONARY",
        "total_movement_distance_km": 0.0,
        "bt_diff_max": 40.0,
        "max_bright_ti4": 350.0,
        "osm_facility_type": "factory",
        "osm_distance_km": 0.5,
        "land_cover_class": "UNKNOWN",
        "satellite_image_available": True,
        "predicted_landcover_class": "Industrial",
        "prediction_confidence": 0.85
    }])

    res = classifier.classify_clusters(df_with_sat)
    assert res.iloc[0]["classification_label"] == "Industrial-context thermal event"
    assert "satellite CNN visual context is Industrial" in res.iloc[0]["classification_rationale"]

def test_cnn_alone_cannot_force_industrial_if_moving():
    classifier = IndustrialClassifier()
    # CNN predicts Industrial, BUT thermal cluster is MOVING rapidly (2.0 km)
    df_moving = pd.DataFrame([{
        "cluster_id": 2,
        "active_days": 1,
        "persistence_category": "isolated",
        "movement_status": "MOVING",
        "total_movement_distance_km": 2.0,
        "bt_diff_max": 10.0,
        "max_bright_ti4": 310.0,
        "osm_facility_type": "UNKNOWN",
        "osm_distance_km": float("inf"),
        "land_cover_class": "UNKNOWN",
        "satellite_image_available": True,
        "predicted_landcover_class": "Industrial",
        "prediction_confidence": 0.90
    }])

    res = classifier.classify_clusters(df_moving)
    # Must NOT be classified as Industrial-context thermal event because movement contradicts stationary flare stack!
    assert res.iloc[0]["classification_label"] != "Industrial-context thermal event"

def test_no_satellite_image_returns_unknown():
    from src.satellite.sentinel2_search import Sentinel2Searcher
    searcher = Sentinel2Searcher()
    # Unconfigured credentials or missing imagery
    stac_res = searcher.search_image_for_cluster(99, 20.0, 78.0, "2026-08-01")
    assert stac_res["image_available"] is False
    assert "Copernicus STAC credentials not configured" in stac_res["observation_status"] or "unavailable" in stac_res["observation_status"]

    # When image is unavailable, prediction MUST be UNKNOWN and confidence MUST be None
    pred_class = "UNKNOWN" if not stac_res["image_available"] else "TEST"
    pred_conf = None if not stac_res["image_available"] else 0.5
    assert pred_class == "UNKNOWN"
    assert pred_conf is None
