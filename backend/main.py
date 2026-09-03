"""
FastAPI REST API Service for SIH Thermal Intelligence Engine.

Serves real processed datasets from the pipeline output CSVs.
Provides endpoints for events, clusters, statistics, map data,
and per-cluster detail views with anomaly/risk/classification info.

Usage:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from backend.schemas import (
    EventSummary,
    PaginatedEventsResponse,
    DashboardStatistics,
    ClusterDetail,
    AlertResponse,
    MovementVector,
    ClassificationDetail,
    RiskDetail,
    ThermalAlert,
    AlertTransitionResult,
)
from src.config import get_config
from src.logging_setup import get_logger
from src.models.alert_engine import (
    ThermalAlertEngine,
    ThermalAlertStore,
    build_intelligence_frame,
)

logger = get_logger("backend.main")

app = FastAPI(
    title="SIH Thermal Intelligence Engine REST API",
    description=(
        "Production REST API exposing NASA FIRMS, AI anomaly, false alarm, "
        "risk index, thermal movement, classification, satellite context, "
        "and alert datasets for the Thermal Intelligence Dashboard."
    ),
    version="2.0.0",
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory cached master dataframe
# ---------------------------------------------------------------------------
_MASTER_DF: Optional[pd.DataFrame] = None

# ---------------------------------------------------------------------------
# Thermal Alert Engine store (lazy; file-based persistence)
# ---------------------------------------------------------------------------
_ALERT_STORE: Optional[ThermalAlertStore] = None


def _get_alert_store() -> ThermalAlertStore:
    """Return the file-backed thermal-alert store.

    If no snapshot has been generated yet, the store is populated from the
    existing processed intelligence (same code path as the CLI generator), so
    the API is self-consistent with data/processed/thermal_alerts.csv.
    """
    global _ALERT_STORE
    if _ALERT_STORE is not None:
        return _ALERT_STORE

    cfg = get_config()
    data_dir = cfg.processed_data_dir
    store = ThermalAlertStore(data_dir)
    if not store.snapshot_path.exists():
        try:
            frame = build_intelligence_frame(data_dir)
            engine = ThermalAlertEngine()
            fresh = engine.generate_alerts(frame)
            store.sync(fresh, run_reason="api bootstrap")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Failed to bootstrap thermal alert snapshot: {exc}")
    _ALERT_STORE = store
    return _ALERT_STORE


def _load_csv(path: Path) -> Optional[pd.DataFrame]:
    """Load a CSV if it exists, otherwise return None."""
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as exc:
            logger.warning(f"Failed to load {path}: {exc}")
    return None


def load_master_dataframe() -> pd.DataFrame:
    """Load and merge all processed CSVs into a single master dataframe."""
    global _MASTER_DF
    if _MASTER_DF is not None and not _MASTER_DF.empty:
        return _MASTER_DF

    cfg = get_config()
    proc = cfg.processed_data_dir

    # Start with AI results as the base (has cluster_id, anomaly info)
    ai_df = _load_csv(proc / "firms_ai_results.csv")
    if ai_df is None or ai_df.empty:
        logger.warning("No firms_ai_results.csv found. Master dataframe will be empty.")
        _MASTER_DF = pd.DataFrame()
        return _MASTER_DF

    df = ai_df.copy()

    # Add centroid lat/lon from GIS events if available
    gis_df = _load_csv(proc / "gis_thermal_events.csv")
    if gis_df is not None and "cluster_id" in gis_df.columns:
        centroids = gis_df.groupby("cluster_id").agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            acq_date=("acq_date", "min"),
        ).reset_index()
        df = pd.merge(df, centroids, on="cluster_id", how="left", suffixes=("", "_gis"))
    else:
        # Fallback coordinates
        if "latitude" not in df.columns:
            df["latitude"] = 20.0
        if "longitude" not in df.columns:
            df["longitude"] = 78.0
        if "acq_date" not in df.columns:
            df["acq_date"] = ""

    # Merge downstream datasets on cluster_id
    merge_files = [
        ("firms_false_alarm.csv", "fa_"),
        ("firms_risk_results.csv", "risk_"),
        ("thermal_movement.csv", "move_"),
        ("firms_industrial_classification.csv", "cls_"),
        ("satellite_context.csv", "sat_"),
        ("emergency_alerts.csv", "alert_"),
    ]

    for filename, prefix in merge_files:
        sub_df = _load_csv(proc / filename)
        if sub_df is not None and "cluster_id" in sub_df.columns:
            # Only add columns that don't already exist (avoid duplicates)
            new_cols = [c for c in sub_df.columns if c not in df.columns or c == "cluster_id"]
            if len(new_cols) > 1:  # more than just cluster_id
                df = pd.merge(df, sub_df[list(set(new_cols))], on="cluster_id", how="left")

    # Ensure critical columns have defaults
    defaults = {
        "abnormality_level": "NORMAL",
        "risk_level": "LOW",
        "risk_score": 0.0,
        "false_alarm_indicator": "MEDIUM",
        "detection_reliability": "MEDIUM",
        "classification_label": "Unknown",
        "movement_status": "INSUFFICIENT_DATA",
        "latitude": 20.0,
        "longitude": 78.0,
        "observation_count": 1,
        "active_days": 1,
        "max_frp": 0.0,
        "max_bright_ti4": 0.0,
        "bt_diff_max": 0.0,
        "anomaly_characterization": "",
        "explanation": "",
        "classification_score": 0.0,
        "classification_rationale": "",
        "total_movement_distance_km": 0.0,
        "alert_priority": "NO ALERT",
        "recommended_action": "Routine monitoring",
        "nearest_station_name": "Unknown Station",
        "station_distance_km": 0.0,
        "alert_rationale": "",
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val

    _MASTER_DF = df
    logger.info(f"Loaded master API dataset with {len(df)} cluster records.")
    return _MASTER_DF


@app.on_event("startup")
def startup_event():
    load_master_dataframe()


@app.get("/api/v1/health")
def health_check():
    df = load_master_dataframe()
    return {
        "status": "healthy",
        "total_records_loaded": len(df),
        "api_version": "2.0.0",
    }


@app.get("/api/v1/statistics", response_model=DashboardStatistics)
def get_statistics():
    df = load_master_dataframe()
    if df.empty:
        raise HTTPException(status_code=404, detail="No processed data loaded.")

    # Count raw detections from GIS events or use the cluster count
    gis_df = _load_csv(get_config().processed_data_dir / "gis_thermal_events.csv")
    total_detections = len(gis_df) if gis_df is not None else len(df)

    # Compute distributions
    anomaly_dist = {"NORMAL": 0, "ELEVATED": 0, "HIGH": 0}
    risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    fa_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    move_dist = {"INSUFFICIENT_DATA": 0, "STATIONARY": 0, "MOVING": 0}

    for level in df["abnormality_level"].fillna("NORMAL"):
        key = str(level).upper()
        if key in anomaly_dist:
            anomaly_dist[key] += 1

    for level in df["risk_level"].fillna("LOW"):
        key = str(level).upper()
        if key in risk_dist:
            risk_dist[key] += 1

    for level in df["false_alarm_indicator"].fillna("MEDIUM"):
        key = str(level).upper()
        if key in fa_dist:
            fa_dist[key] += 1

    for level in df["movement_status"].fillna("INSUFFICIENT_DATA"):
        key = str(level).upper()
        if key in move_dist:
            move_dist[key] += 1

    high_risk_count = int(risk_dist.get("HIGH", 0))
    moving_count = int(move_dist.get("MOVING", 0))
    high_fa_count = int(fa_dist.get("HIGH", 0))

    return {
        "total_detections": total_detections,
        "active_clusters": len(df),
        "high_risk_count": high_risk_count,
        "moving_count": moving_count,
        "high_false_alarm_count": high_fa_count,
        "anomaly_distribution": anomaly_dist,
        "risk_distribution": risk_dist,
        "false_alarm_distribution": fa_dist,
        "movement_distribution": move_dist,
    }


@app.get("/api/v1/events", response_model=PaginatedEventsResponse)
def get_events(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    risk_level: Optional[str] = None,
    abnormality_level: Optional[str] = None,
    false_alarm_indicator: Optional[str] = None,
    classification_label: Optional[str] = None,
    movement_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Return paginated event summaries with optional filtering."""
    df = load_master_dataframe()
    filtered = df.copy()

    if risk_level:
        levels = [l.strip().upper() for l in risk_level.split(",")]
        filtered = filtered[filtered["risk_level"].str.upper().isin(levels)]
    if abnormality_level:
        levels = [l.strip().upper() for l in abnormality_level.split(",")]
        filtered = filtered[filtered["abnormality_level"].str.upper().isin(levels)]
    if false_alarm_indicator:
        levels = [l.strip().upper() for l in false_alarm_indicator.split(",")]
        filtered = filtered[filtered["false_alarm_indicator"].str.upper().isin(levels)]
    if classification_label:
        filtered = filtered[
            filtered["classification_label"].str.contains(
                classification_label, case=False, na=False
            )
        ]
    if movement_status:
        levels = [l.strip().upper() for l in movement_status.split(",")]
        filtered = filtered[filtered["movement_status"].str.upper().isin(levels)]
    if start_date:
        filtered = filtered[filtered["acq_date"] >= start_date]
    if end_date:
        filtered = filtered[filtered["acq_date"] <= end_date]

    total = len(filtered)
    pages = math.ceil(total / limit) if total > 0 else 1

    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_df = filtered.iloc[start_idx:end_idx]

    events = []
    for _, row in page_df.iterrows():
        events.append(EventSummary(
            cluster_id=int(row["cluster_id"]),
            latitude=float(row.get("latitude", 0.0)),
            longitude=float(row.get("longitude", 0.0)),
            acq_date=str(row.get("acq_date", "")),
            abnormality_level=str(row.get("abnormality_level", "NORMAL")),
            false_alarm_indicator=str(row.get("false_alarm_indicator", "MEDIUM")),
            risk_score=float(row.get("risk_score", 0.0)),
            risk_level=str(row.get("risk_level", "LOW")),
            classification_label=str(row.get("classification_label", "Unknown")),
            classification_score=float(row.get("classification_score", 0.0)),
            movement_status=str(row.get("movement_status", "INSUFFICIENT_DATA")),
            max_frp=float(row.get("max_frp", 0.0)),
            max_bright_ti4=float(row.get("max_bright_ti4", 0.0)),
            explanation=str(row.get("explanation", "")),
            observation_count=int(row.get("observation_count", 1)),
            active_days=int(row.get("active_days", 1)),
        ))

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "events": events,
    }


@app.get("/api/v1/clusters")
def get_clusters(
    risk_level: Optional[str] = None,
    abnormality_level: Optional[str] = None,
    false_alarm_indicator: Optional[str] = None,
    persistence_category: Optional[str] = None,
):
    """Return cluster summaries for map/table display."""
    df = load_master_dataframe()
    filtered = df.copy()

    if risk_level:
        levels = [l.strip().upper() for l in risk_level.split(",")]
        filtered = filtered[filtered["risk_level"].str.upper().isin(levels)]
    if abnormality_level:
        levels = [l.strip().upper() for l in abnormality_level.split(",")]
        filtered = filtered[filtered["abnormality_level"].str.upper().isin(levels)]
    if false_alarm_indicator:
        levels = [l.strip().upper() for l in false_alarm_indicator.split(",")]
        filtered = filtered[filtered["false_alarm_indicator"].str.upper().isin(levels)]
    if persistence_category:
        cats = [c.strip().lower() for c in persistence_category.split(",")]
        if "persistence_category" in filtered.columns:
            filtered = filtered[filtered["persistence_category"].str.lower().isin(cats)]

    cols = [
        "cluster_id", "latitude", "longitude", "risk_level", "risk_score",
        "abnormality_level", "classification_label", "observation_count",
        "active_days", "first_detection", "last_detection", "duration_days",
        "mean_bright_ti4", "max_bright_ti4", "mean_bright_ti5", "max_bright_ti5",
        "mean_frp", "max_frp", "mean_confidence", "persistence_score",
        "persistence_category", "bt_diff_mean", "bt_diff_max",
        "frp_mean_to_max_ratio", "detection_density", "active_day_ratio",
        "is_multi_day", "is_persistent_candidate", "persistence_category_code",
        "anomaly_score", "anomaly_flag", "abnormality_level",
        "anomaly_characterization", "explanation", "contributing_factors",
        "false_alarm_indicator", "false_alarm_reasons", "detection_reliability",
        "risk_score", "risk_level", "risk_factors", "risk_explanation",
    ]
    available_cols = [c for c in cols if c in filtered.columns]
    return filtered[available_cols].to_dict(orient="records")


@app.get("/api/v1/map-data")
def get_map_data():
    """Return GeoJSON FeatureCollection for map rendering."""
    df = load_master_dataframe()
    records = []
    for _, row in df.iterrows():
        records.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(row.get("longitude", 0.0)),
                    float(row.get("latitude", 0.0)),
                ],
            },
            "properties": {
                "cluster_id": int(row["cluster_id"]),
                "risk_score": float(row.get("risk_score", 0.0)),
                "risk_level": str(row.get("risk_level", "LOW")),
                "abnormality_level": str(row.get("abnormality_level", "NORMAL")),
                "false_alarm_indicator": str(row.get("false_alarm_indicator", "MEDIUM")),
                "classification_label": str(row.get("classification_label", "Unknown")),
                "movement_status": str(row.get("movement_status", "INSUFFICIENT_DATA")),
            },
        })
    return {"type": "FeatureCollection", "features": records}


def _clean_movement_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize a movement CSV row for JSON: nulls stay null, numerics convert."""
    out: Dict[str, Any] = {}
    for key, val in row.items():
        if val is None or (isinstance(val, float) and math.isnan(val)):
            out[key] = None
        elif key == "direction":
            # Direction is only meaningful when direction_available is true.
            out[key] = str(val) if str(val).strip() else None
        elif key == "cluster_id":
            out[key] = int(val)
        elif key in ("observation_count", "active_days", "direction_confidence_score"):
            out[key] = int(float(val)) if val is not None else 0
        elif key == "direction_available":
            out[key] = bool(val)
        elif isinstance(val, (int, float)):
            out[key] = float(val)
        else:
            out[key] = str(val)
    return out


@app.get("/api/v1/movement")
def get_movement(
    movement_status: Optional[str] = None,
    cluster_id: Optional[int] = None,
):
    """Return movement vector + direction intelligence data for clusters.

    Direction fields (direction, movement_pattern, direction_confidence,
    direction_confidence_score, direction_available) describe the movement of
    *detected thermal activity* only, and never claim physical fire-front
    propagation. Null direction means no defensible direction could be inferred.
    """
    df = load_master_dataframe()

    # Try to load movement CSV directly for more complete data
    move_df = _load_csv(get_config().processed_data_dir / "thermal_movement.csv")
    if move_df is not None and not move_df.empty:
        result_df = move_df
    else:
        # Fall back to master df columns
        move_cols = [
            "cluster_id", "observation_count", "active_days",
            "first_detection", "last_detection",
            "start_latitude", "start_longitude",
            "end_latitude", "end_longitude",
            "total_movement_distance_km", "movement_rate_km_per_day",
            "movement_bearing_degrees", "movement_direction",
            "movement_confidence", "movement_status",
        ]
        available = [c for c in move_cols if c in df.columns]
        result_df = df[available].copy() if available else pd.DataFrame()

    if result_df.empty:
        return []

    if movement_status:
        statuses = [s.strip().upper() for s in movement_status.split(",")]
        if "movement_status" in result_df.columns:
            result_df = result_df[result_df["movement_status"].str.upper().isin(statuses)]

    if cluster_id is not None:
        if "cluster_id" in result_df.columns:
            result_df = result_df[result_df["cluster_id"] == cluster_id]
        else:
            return []

    records = result_df.to_dict(orient="records")
    return [_clean_movement_row(r) for r in records]


@app.get("/api/v1/events/{cluster_id}", response_model=ClusterDetail)
def get_cluster_detail(cluster_id: int):
    """Return detailed information for a specific cluster."""
    df = load_master_dataframe()
    match = df[df["cluster_id"] == cluster_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Cluster ID {cluster_id} not found.")

    row = match.iloc[0]
    return {
        "cluster_id": int(row["cluster_id"]),
        "latitude": float(row.get("latitude", 0.0)),
        "longitude": float(row.get("longitude", 0.0)),
        "observation_count": int(row.get("observation_count", 1)),
        "active_days": int(row.get("active_days", 1)),
        "first_detection": str(row.get("first_detection", "")),
        "last_detection": str(row.get("last_detection", "")),
        "duration_days": int(row["duration_days"]) if pd.notna(row.get("duration_days")) else None,
        "persistence_category": str(row.get("persistence_category", "")),
        "max_frp": float(row.get("max_frp", 0.0)),
        "max_bright_ti4": float(row.get("max_bright_ti4", 0.0)),
        "bt_diff_max": float(row.get("bt_diff_max", 0.0)),
        "abnormality_level": str(row.get("abnormality_level", "NORMAL")),
        "anomaly_characterization": str(row.get("anomaly_characterization", "")),
        "explanation": str(row.get("explanation", "")),
        "false_alarm_indicator": str(row.get("false_alarm_indicator", "MEDIUM")),
        "detection_reliability": str(row.get("detection_reliability", "MEDIUM")),
        "risk_score": float(row.get("risk_score", 0.0)),
        "risk_level": str(row.get("risk_level", "LOW")),
        "classification_label": str(row.get("classification_label", "Unknown")),
        "classification_score": float(row.get("classification_score", 0.0)),
        "classification_rationale": str(row.get("classification_rationale", "")),
        "movement_status": str(row.get("movement_status", "INSUFFICIENT_DATA")),
        "total_movement_distance_km": float(row.get("total_movement_distance_km", 0.0)),
    }


@app.get("/api/v1/classification/{cluster_id}")
def get_classification_detail(cluster_id: int):
    """Return classification details for a specific cluster."""
    df = load_master_dataframe()
    match = df[df["cluster_id"] == cluster_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Cluster ID {cluster_id} not found.")
    row = match.iloc[0]
    # Sanitize non-finite numeric values to avoid JSON serialization errors
    osm_dist = float(row.get("osm_distance_km", 999.0))
    if not math.isfinite(osm_dist):
        osm_dist = 999.0
    pred_conf = float(row.get("prediction_confidence", 0.0))
    if not math.isfinite(pred_conf):
        pred_conf = 0.0
    return {
        "cluster_id": int(row["cluster_id"]),
        "classification_label": str(row.get("classification_label", "Unknown")),
        "classification_score": float(row.get("classification_score", 0.0)),
        "classification_rationale": str(row.get("classification_rationale", "")),
        "osm_facility_type": str(row.get("osm_facility_type", "UNKNOWN")),
        "osm_distance_km": osm_dist,
        "predicted_landcover_class": str(row.get("predicted_landcover_class", "UNKNOWN")),
        "prediction_confidence": pred_conf,
    }


@app.get("/api/v1/risk/{cluster_id}")
def get_risk_detail(cluster_id: int):
    """Return risk intelligence details for a specific cluster."""
    df = load_master_dataframe()
    match = df[df["cluster_id"] == cluster_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Cluster ID {cluster_id} not found.")
    row = match.iloc[0]
    return {
        "cluster_id": int(row["cluster_id"]),
        "risk_score": float(row.get("risk_score", 0.0)),
        "risk_level": str(row.get("risk_level", "LOW")),
        "risk_factors": str(row.get("risk_factors", "")),
        "risk_explanation": str(row.get("risk_explanation", "")),
    }


@app.get("/api/v1/response/{cluster_id}", response_model=AlertResponse)
def get_response_detail(cluster_id: int):
    """Return alert/response details for a specific cluster."""
    df = load_master_dataframe()
    match = df[df["cluster_id"] == cluster_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Cluster ID {cluster_id} not found.")
    row = match.iloc[0]
    # No verified fire station within the search radius is represented honestly:
    # station_available=False and a null distance (never a fabricated value).
    station_dist = float(row.get("station_distance_km", 0.0))
    if not math.isfinite(station_dist) or station_dist <= 0.0:
        station_dist = None
    station_available = bool(row.get("station_available", station_dist is not None))
    if station_dist is None:
        station_available = False
    return {
        "cluster_id": int(row["cluster_id"]),
        "risk_score": float(row.get("risk_score", 0.0)),
        "risk_level": str(row.get("risk_level", "LOW")),
        "alert_priority": str(row.get("alert_priority", "NO ALERT")),
        "recommended_action": str(row.get("recommended_action", "Routine monitoring")),
        "nearest_station_name": str(row.get("nearest_station_name", "Unknown Station")),
        "station_distance_km": station_dist,
        "station_available": station_available,
        "alert_rationale": str(row.get("alert_rationale", "")),
        "is_decision_support_only": True,
    }


# ============================================================================
# Thermal Alert Engine API (decision-support alerts)
# ============================================================================


@app.get("/api/v1/alerts", response_model=List[ThermalAlert])
def get_alerts(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    cluster_id: Optional[int] = None,
    suppressed: Optional[bool] = None,
):
    """Return generated thermal alerts, optionally filtered.

    Alerts are decision-support classifications of processed thermal evidence;
    they are NOT confirmed fire declarations.
    """
    store = _get_alert_store()
    records = store.list_alerts(severity=severity, status=status, cluster_id=cluster_id)
    if suppressed is not None:
        records = [r for r in records if bool(r.get("suppressed")) == suppressed]
    # Sort: severity rank desc, then risk score desc within severity.
    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    records.sort(key=lambda r: (
        -sev_rank.get(str(r.get("severity", "LOW")).upper(), 1),
        -(r.get("risk_score") if isinstance(r.get("risk_score"), (int, float)) else -1),
    ))
    return records


@app.get("/api/v1/alerts/{alert_id}", response_model=ThermalAlert)
def get_alert_detail(alert_id: str):
    """Return one thermal alert by alert_id (e.g. TAL-01105)."""
    store = _get_alert_store()
    alert = store.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert


@app.post("/api/v1/alerts/{alert_id}/acknowledge", response_model=AlertTransitionResult)
def acknowledge_alert(alert_id: str):
    """Acknowledge an ACTIVE thermal alert (ACTIVE -> ACKNOWLEDGED)."""
    store = _get_alert_store()
    try:
        cid = int(alert_id.replace("TAL-", "").lstrip("0") or "0")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    try:
        updated = store.acknowledge(cid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "alert_id": str(updated.get("alert_id", alert_id)),
        "cluster_id": int(cid),
        "status": str(updated.get("status", "ACKNOWLEDGED")),
        "severity": str(updated.get("severity", "")),
        "updated_at": str(updated.get("updated_at", "")),
        "detail": f"Alert {alert_id} acknowledged.",
    }


@app.post("/api/v1/alerts/{alert_id}/resolve", response_model=AlertTransitionResult)
def resolve_alert(alert_id: str):
    """Resolve an ACTIVE or ACKNOWLEDGED thermal alert (-> RESOLVED)."""
    store = _get_alert_store()
    try:
        cid = int(alert_id.replace("TAL-", "").lstrip("0") or "0")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    try:
        updated = store.resolve(cid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "alert_id": str(updated.get("alert_id", alert_id)),
        "cluster_id": int(cid),
        "status": str(updated.get("status", "RESOLVED")),
        "severity": str(updated.get("severity", "")),
        "updated_at": str(updated.get("updated_at", "")),
        "detail": f"Alert {alert_id} resolved.",
    }


@app.get("/api/v1/alerts-history", response_model=List[Dict[str, Any]])
def get_alert_history(alert_id: Optional[str] = None, cluster_id: Optional[int] = None):
    """Return alert severity/state history (escalations and status changes)."""
    store = _get_alert_store()
    hist = store._load_history()
    if hist.empty:
        return []
    if alert_id:
        hist = hist[hist["alert_id"].astype(str) == str(alert_id)]
    if cluster_id is not None:
        hist = hist[hist["cluster_id"].astype(int) == int(cluster_id)]
    records = hist.to_dict(orient="records")
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                clean[k] = None
            else:
                clean[k] = v
        out.append(clean)
    return out
