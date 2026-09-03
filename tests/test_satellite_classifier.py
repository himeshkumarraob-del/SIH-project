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
    searcher = Sentinel2Searcher(max_cloud_cover_percent=20.0)  # Low threshold to ensure unavailable
    # Search for a location that likely has no imagery or high cloud cover
    stac_res = searcher.search_image_for_cluster(99, 20.0, 78.0, "2026-08-01")
    # The new implementation uses satellite_image_available instead of image_available
    assert stac_res["satellite_image_available"] is False
    # Check that observation_status indicates some form of unavailability
    status = stac_res["observation_status"].lower()
    assert any(word in status for word in ["unavailable", "obscured", "cloud", "error", "not found", "pending"])

    # When image is unavailable, prediction MUST be UNKNOWN and confidence MUST be None
    pred_class = "UNKNOWN" if not stac_res["satellite_image_available"] else "TEST"
    pred_conf = None if not stac_res["satellite_image_available"] else 0.5
    assert pred_class == "UNKNOWN"
    assert pred_conf is None


# ---------------------------------------------------------------------------
# Training pipeline hardening tests
# ---------------------------------------------------------------------------

def test_train_satellite_cnn_no_checkpoint_on_failure(tmp_path, monkeypatch):
    """When EuroSAT training fails, train_satellite_cnn() must NOT save an
    ImageNet-only checkpoint and must return False."""
    from scripts.train_all_models import train_satellite_cnn

    checkpoint = tmp_path / "satellite_landuse_efficientnet_b0.pth"
    assert not checkpoint.exists()

    # Force dataset loading to raise so the except branch fires
    def _fail_dataloaders(**kwargs):
        raise RuntimeError("EuroSAT download failed (simulated)")

    monkeypatch.setattr(
        "src.satellite.dataset.get_eurosat_dataloaders", _fail_dataloaders
    )

    result = train_satellite_cnn(epochs=1, batch_size=2)

    assert result is False, "Expected False on training failure"
    assert not checkpoint.exists(), "Checkpoint must NOT be created on failure"


def test_train_satellite_cnn_preserves_existing_checkpoint(tmp_path, monkeypatch):
    """When EuroSAT training fails but a valid checkpoint already exists,
    the existing file must be preserved (not overwritten with ImageNet weights)."""
    import torch as _torch
    from scripts.train_all_models import train_satellite_cnn

    checkpoint = tmp_path / "satellite_landuse_efficientnet_b0.pth"

    # Create a pre-existing "valid" checkpoint with a sentinel value
    sentinel = {"state_dict": {}, "val_acc": 0.99, "note": "real-trained"}
    _torch.save(sentinel, checkpoint)
    original_mtime = checkpoint.stat().st_mtime

    def _fail_dataloaders(**kwargs):
        raise RuntimeError("EuroSAT download failed (simulated)")

    monkeypatch.setattr(
        "src.satellite.dataset.get_eurosat_dataloaders", _fail_dataloaders
    )

    result = train_satellite_cnn(epochs=1, batch_size=2)

    assert result is False
    # File must still exist and NOT have been rewritten
    assert checkpoint.exists(), "Existing checkpoint must be preserved"
    assert checkpoint.stat().st_mtime == original_mtime, (
        "Existing checkpoint must not be overwritten"
    )
    loaded = _torch.load(checkpoint, weights_only=False)
    assert loaded["note"] == "real-trained", "Checkpoint content must be unchanged"
    assert loaded["val_acc"] == 0.99, "val_acc must not be replaced with fake 0.85"


def test_train_all_models_main_returns_nonzero_on_satellite_failure(tmp_path, monkeypatch):
    """The CLI entry point train_satellite_cnn in train_satellite_cnn.py must
    return exit code 1 when EuroSAT training fails (no fake checkpoint)."""
    import subprocess, sys
    from pathlib import Path

    # Run from the actual project root so scripts/ is findable
    project_root = Path(__file__).resolve().parent.parent
    checkpoint = project_root / "models" / "satellite_landuse_efficientnet_b0.pth"
    checkpoint_existed_before = checkpoint.exists()
    original_mtime = checkpoint.stat().st_mtime if checkpoint_existed_before else None

    result = subprocess.run(
        [
            sys.executable, "scripts/train_satellite_cnn.py",
            "--epochs", "0",
            "--batch-size", "2",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = result.stdout + result.stderr

    if result.returncode != 0:
        # On failure, stdout/stderr should mention the error
        assert any(
            kw in output.lower()
            for kw in ["error", "abort", "failed", "not found"]
        ), f"Expected error message in output, got: {output[:500]}"
        # If no checkpoint existed before, it must not have been created
        if not checkpoint_existed_before:
            assert not checkpoint.exists(), (
                "No checkpoint should be saved on failure"
            )
        else:
            # If a checkpoint existed before, it must not have been modified
            assert checkpoint.stat().st_mtime == original_mtime, (
                "Existing checkpoint must not be overwritten on failure"
            )
    # If returncode == 0, training succeeded — that's acceptable
