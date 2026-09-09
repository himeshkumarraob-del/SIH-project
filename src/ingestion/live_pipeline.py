"""
Live pipeline orchestration: re-runs the EXISTING ThermalWatch intelligence
stages over historical + newly ingested observations.

This module reuses the same functions that scripts/run_full_pipeline.py uses
— no stage logic is duplicated or replaced:

    clean -> India filter -> persistence + STABLE IDENTITY -> features ->
    anomaly -> explain -> false alarm -> risk -> movement -> classification ->
    thermal alerts (ThermalAlertStore.sync) -> GIS events

Differences from the batch runner (all safety-motivated):
  * every API-served output is written atomically with a rollback backup
  * the anomaly model is refit on current data, then persisted (same as batch)
  * the satellite CNN stage is NOT run live: the existing satellite_context.csv
    is reused as-is; new event ids have no satellite context (rendered as
    UNKNOWN / Insufficient Evidence downstream) and torch is never imported —
    predictions are never fabricated
  * the alert snapshot is upserted via ThermalAlertStore.sync(), which
    preserves ACKNOWLEDGED/RESOLVED operator state (continuity is guaranteed
    upstream by the identity layer's canonical cluster_id remap)
  * a failed stage aborts BEFORE later overwrites; each overwrite is backed up

TERMINOLOGY: stages process "thermal detections/events" — never "fires".
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_config
from src.logging_setup import get_logger
from src.persistence.atomic_io import write_csv_atomic

logger = get_logger("ingestion.live_pipeline")


def run_live_pipeline(satellite_reuse: bool = True) -> bool:
    """
    Re-run the intelligence pipeline over the current raw dataset
    (historical + live files). Returns True when every stage succeeded,
    False when any stage failed (existing processed data remains backed up,
    never destroyed).
    """
    cfg = get_config()
    proc = cfg.processed_data_dir
    stages: list[tuple[str, bool]] = []

    def _record(name: str, ok: bool) -> bool:
        stages.append((name, ok))
        logger.info("Live stage %s: %s", name, "ok" if ok else "FAILED/SKIPPED")
        return ok

    started = time.time()
    logger.info("Live pipeline run starting (satellite_reuse=%s)", satellite_reuse)

    # -- Stage 2: clean + dedup (existing logic, unchanged) -------------------
    try:
        from src.preprocessing.clean_firms import run_cleaning_pipeline, save_cleaned_dataset
        df, report = run_cleaning_pipeline()
        save_cleaned_dataset(df)  # interim output; plain write acceptable
        _record("clean", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline abort: cleaning failed: %s", exc)
        _record("clean", False)
        return False

    # -- Stage 3: India boundary filter ----------------------------------------
    try:
        from src.preprocessing.india_boundary_filter import (
            run_india_filter_pipeline,
            save_india_dataset,
        )
        india_df, india_report = run_india_filter_pipeline()
        save_india_dataset(india_df)  # rewritten by the identity stage below
        _record("india_filter", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline abort: India filter failed: %s", exc)
        _record("india_filter", False)
        return False

    # -- Stage 4 + identity: persistence + stable event identity ---------------
    # run_persistence_pipeline() performs clustering, registry continuity
    # matching, canonical cluster_id remap, and rewrites firms_india.csv with
    # per-detection identity columns (atomic + backed up).
    try:
        from src.persistence.persistence_analysis import (
            run_persistence_pipeline,
            save_persistence_dataset,
        )
        clusters, pers_report = run_persistence_pipeline()
        save_persistence_dataset(clusters)
        _record("persistence_identity", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline abort: persistence/identity failed: %s", exc)
        _record("persistence_identity", False)
        return False

    # -- Stage 5: features ------------------------------------------------------
    try:
        from src.features.feature_engineering import run_feature_pipeline, save_features_dataset
        feats, _ = run_feature_pipeline()
        save_features_dataset(feats)
        _record("features", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: features failed: %s", exc)
        _record("features", False)
        return False

    # -- Stage 6: anomaly detection (refit + persist, same as batch) -----------
    try:
        from src.models.anomaly_detector import ThermalAnomalyDetector
        df_feats = pd.read_csv(proc / "firms_features.csv")
        detector = ThermalAnomalyDetector(contamination=0.05)
        detector.fit(df_feats)
        results = detector.predict(df_feats)
        write_csv_atomic(results, proc / "firms_anomalies.csv")
        detector.save(cfg.models_dir)
        _record("anomaly", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: anomaly detection failed: %s", exc)
        _record("anomaly", False)
        return False

    # -- Stage 7: explainable characterization ----------------------------------
    try:
        from src.models.anomaly_explainer import ThermalAnomalyExplainer
        df_ano = pd.read_csv(proc / "firms_anomalies.csv")
        results = ThermalAnomalyExplainer().explain(df_ano)
        write_csv_atomic(results, proc / "firms_ai_results.csv")
        _record("explain", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: explain failed: %s", exc)
        _record("explain", False)
        return False

    # -- Stage 8: false-alarm intelligence --------------------------------------
    try:
        from src.models.false_alarm_detector import FalseAlarmDetector
        df_ai = pd.read_csv(proc / "firms_ai_results.csv")
        results = FalseAlarmDetector().evaluate(df_ai)
        fa_cols = ["cluster_id", "false_alarm_indicator", "false_alarm_reasons", "detection_reliability"]
        write_csv_atomic(results[fa_cols], proc / "firms_false_alarm.csv")
        _record("false_alarm", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: false alarm failed: %s", exc)
        _record("false_alarm", False)
        return False

    # -- Stage 9: risk intelligence ----------------------------------------------
    try:
        from src.models.risk_intelligence import RiskIntelligenceEngine
        df_ai = pd.read_csv(proc / "firms_ai_results.csv")
        fa_path = proc / "firms_false_alarm.csv"
        if fa_path.exists():
            fa_df = pd.read_csv(fa_path)
            for col in ("false_alarm_indicator", "detection_reliability"):
                if col in fa_df.columns and col not in df_ai.columns:
                    df_ai = pd.merge(df_ai, fa_df[["cluster_id", col]], on="cluster_id", how="left")
        results = RiskIntelligenceEngine().calculate_risk(df_ai)
        risk_cols = ["cluster_id", "risk_score", "risk_level", "risk_factors", "risk_explanation"]
        write_csv_atomic(results[risk_cols], proc / "firms_risk_results.csv")
        _record("risk", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: risk failed: %s", exc)
        _record("risk", False)
        return False

    # -- Stage 10: movement (reads identity-annotated firms_india.csv) ----------
    try:
        from src.gis.thermal_movement import ThermalMovementAnalyzer
        india_identity = pd.read_csv(proc / "firms_india.csv")
        results = ThermalMovementAnalyzer().analyze_clusters(india_identity)
        write_csv_atomic(results, proc / "thermal_movement.csv")
        _record("movement", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: movement failed: %s", exc)
        _record("movement", False)
        return False

    # -- Stage 12: industrial classification (reuses OSM cache + satellite reuse)
    try:
        from src.models.industrial_classifier import IndustrialClassifier
        df_ai = pd.read_csv(proc / "firms_ai_results.csv")
        move_df = pd.read_csv(proc / "thermal_movement.csv")
        move_cols = [c for c in ("cluster_id", "movement_status", "total_movement_distance_km", "movement_direction") if c in move_df.columns]
        df_ai = pd.merge(df_ai, move_df[move_cols], on="cluster_id", how="left")
        sat_path = proc / "satellite_context.csv"
        if satellite_reuse and sat_path.exists():
            # Reuse existing satellite context verbatim; event ids absent from
            # it simply carry no satellite columns (honest UNKNOWN downstream).
            sat_df = pd.read_csv(sat_path)
            df_ai = pd.merge(df_ai, sat_df, on="cluster_id", how="left")
        results = IndustrialClassifier().classify_clusters(df_ai)
        cls_cols = ["cluster_id", "classification_label", "classification_score", "classification_rationale"]
        write_csv_atomic(results[cls_cols], proc / "firms_industrial_classification.csv")
        _record("classification", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: classification failed: %s", exc)
        _record("classification", False)
        return False

    # -- Stage 13: thermal alerts (decision-support) — upsert, never overwrite state
    try:
        from src.models.alert_engine import (
            ThermalAlertEngine,
            ThermalAlertStore,
            build_intelligence_frame,
        )
        store = ThermalAlertStore(proc)
        frame = build_intelligence_frame(proc)
        fresh = ThermalAlertEngine().generate_alerts(frame)
        store.sync(fresh, run_reason="live ingestion rerun")
        _record("alerts", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: alerts failed: %s", exc)
        _record("alerts", False)
        return False

    # -- Stage 14: GIS events (one row per detection, canonical cluster ids) ----
    try:
        from src.gis.map_builder import MapBuilder
        india_identity = pd.read_csv(proc / "firms_india.csv")
        # Per-detection identity + anomaly context feeds the GIS builder.
        ai_per_cluster = pd.read_csv(proc / "firms_ai_results.csv")
        india_identity = pd.merge(
            india_identity,
            ai_per_cluster[["cluster_id", "abnormality_level", "anomaly_score", "persistence_category", "anomaly_characterization", "explanation"]],
            on="cluster_id", how="left",
        )
        builder = MapBuilder()
        gis_events = builder.build_gis_events(india_identity)
        write_csv_atomic(gis_events, proc / "gis_thermal_events.csv")
        _record("gis", True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Live pipeline: GIS failed: %s", exc)
        _record("gis", False)
        return False

    all_ok = all(ok for _, ok in stages)
    logger.info(
        "Live pipeline finished in %.1fs: %d/%d stages ok (all_ok=%s)",
        time.time() - started, sum(ok for _, ok in stages), len(stages), all_ok,
    )
    return all_ok
