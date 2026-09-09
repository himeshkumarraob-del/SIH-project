"""
Thermal Alert / Alarm Engine (Decision-Support).

Generates structured THERMAL ACTIVITY ALERTS from the existing processed
intelligence dataset:

    FIRMS -> Persistence -> False Alarm Intelligence -> Industrial
    Classification -> Risk Intelligence -> Movement/Direction
    -> THERMAL ALERT ENGINE -> Structured Alert

This is an alert-generation and decision-support component that operates on
available (non-real-time) FIRMS data. It does NOT claim real-time fire
dispatch, instant alarm delivery, or guaranteed emergency notification.

IMPORTANT TERMINOLOGY
---------------------
The word "alert" here always means a *thermal anomaly alert* /
*decision-support alert* / *priority inspection alert*. A CRITICAL alert means
the processed thermal evidence is strong and internally consistent; it does NOT
assert a confirmed industrial fire, confirmed fire spread, or guaranteed hazard.

SEVERITY RULES (documented, deterministic)
------------------------------------------
Severity is derived primarily from the EXISTING risk index (risk_score 0-100 /
risk_level), which already embeds false-alarm attenuation. Additional
false-alarm suppression rules (below) keep a high false-alarm concern from
producing an actionable critical alarm purely because an anomaly exists.

    CRITICAL  risk_score >= 85 AND risk_level == HIGH
              AND false_alarm_indicator == LOW AND detection_reliability == HIGH
    HIGH      risk_score >= 60 (risk_level == HIGH)
    MEDIUM    risk_score >= 30 (risk_level == MEDIUM)
    LOW       otherwise (risk_level == LOW -> informational)

False-alarm suppression / downgrade rules:
    * false_alarm_indicator == HIGH caps severity at MEDIUM (defensive; the
      risk engine normally already attenuates these events below HIGH).
    * false_alarm_indicator == HIGH with evidence_confidence LOW/INSUFFICIENT
      -> alert is SUPPRESSED (suppressed=True): the thermal anomaly is retained
      for monitoring, but it is not presented as an operator alert.
    * The underlying thermal event is NEVER deleted.

EVIDENCE CONFIDENCE (categorical, from actual fields -- never a fabricated %)
-----------------------------------------------------------------------------
    HIGH        false_alarm_indicator == LOW and detection_reliability == HIGH
    MODERATE    false_alarm_indicator == MEDIUM or detection_reliability == MEDIUM
    LOW         false_alarm_indicator == HIGH or detection_reliability == LOW
    INSUFFICIENT  required core fields missing / unparseable

LIFECYCLE / STATE (file-based)
------------------------------
Status transitions: ACTIVE -> ACKNOWLEDGED -> RESOLVED.
An alert may also go ACTIVE -> RESOLVED directly (acknowledgement is optional).

DEDUPLICATION
-------------
One deterministic alert per cluster: alert_id = "TAL-{cluster_id:05d}".
Re-running generation upserts in place (no duplicate rows). A previous RESOLVED
alert stays RESOLVED unless the incoming severity rank is HIGHER than the
severity under which it was resolved (escalation reopens it as ACTIVE).

ESCALATION
----------
Severity increases are recorded in the history file with previous/new severity
and a reason. No timer-based escalation or downgrade: severity always reflects
the latest processed intelligence.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.logging_setup import get_logger

logger = get_logger("models.alert_engine")

SEVERITY_ORDER: Dict[str, int] = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
STATUS_ORDER: List[str] = ["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]

# Documented rule thresholds -------------------------------------------------
CRITICAL_RISK_MIN = 85.0      # very high risk score
HIGH_RISK_MIN = 60.0          # matches the existing risk engine's HIGH bound
MEDIUM_RISK_MIN = 30.0        # matches the existing risk engine's MEDIUM bound
STRONG_FRP_MW = 20.0
ELEVATED_FRP_MW = 10.0
HIGH_BRIGHTNESS_K = 340.0
HIGH_CONTRAST_K = 45.0

_NA_VALUES = ("", "nan", "none", "unknown", "insufficient", "insufficient_evidence",
              "insufficient_data", "unavailable", "no fire station within",
              "fire station data unavailable", "invalid coordinates")

# Keys that are textual even when empty; CSV round-trips empty strings as NaN,
# so the record sanitizer maps NaN back to "" for these keys.
_TEXT_KEYS = {
    "severity", "status", "evidence_confidence", "suppression_reason", "risk_level",
    "classification_label", "false_alarm_indicator", "detection_reliability",
    "persistence_category", "movement_direction", "movement_pattern",
    "nearest_station_name", "reasons", "alert_rationale", "created_at", "updated_at",
    "alert_id", "event_key",
}


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in _NA_VALUES:
        return ""
    return s


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (TypeError, ValueError):
        return default


class ThermalAlertEngine:
    """
    Pure, deterministic alert generator.

    Consumes the merged processed-intelligence frame (see
    build_intelligence_frame) and returns one structured alert row per cluster.
    """

    def generate_alerts(self, df: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
        required = ["cluster_id"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for alert generation: {missing}")

        created_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            rows.append(self._generate_single(row, created_at))
        out = pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    def _generate_single(self, row: pd.Series, created_at: str) -> Dict[str, Any]:
        cluster_id = _to_int(row.get("cluster_id"))
        risk_score = _to_float(row.get("risk_score"))
        risk_level = _clean_str(row.get("risk_level")).upper() or "LOW"
        fa = _clean_str(row.get("false_alarm_indicator")).upper()
        reliability = _clean_str(row.get("detection_reliability")).upper()

        risk_valid = row.get("risk_score") is not None and not (
            isinstance(row.get("risk_score"), float) and math.isnan(float(row.get("risk_score")))
        )
        fa_valid = fa in ("LOW", "MEDIUM", "HIGH")

        # --- Evidence confidence --------------------------------------
        if not risk_valid or not fa_valid:
            evidence = "INSUFFICIENT"
        elif fa == "LOW" and reliability == "HIGH":
            evidence = "HIGH"
        elif fa == "MEDIUM" or reliability == "MEDIUM":
            evidence = "MODERATE"
        elif fa == "HIGH" or reliability == "LOW":
            evidence = "LOW"
        else:
            evidence = "MODERATE"

        # --- Base severity from the existing risk index ---------------
        if risk_level == "HIGH" and risk_score >= CRITICAL_RISK_MIN and fa == "LOW" and reliability == "HIGH":
            severity = "CRITICAL"
        elif risk_score >= HIGH_RISK_MIN:
            severity = "HIGH"
        elif risk_score >= MEDIUM_RISK_MIN:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # --- False-alarm suppression / downgrade -----------------------
        # A high false-alarm concern with weak evidence means the thermal
        # anomaly is real enough to retain for monitoring but NOT strong enough
        # to present as an operator alert. The event is never deleted.
        suppressed = False
        suppression_reason = ""
        downgrade_note = ""
        if fa == "HIGH":
            if SEVERITY_ORDER.get(severity, 1) > SEVERITY_ORDER["MEDIUM"]:
                severity = "MEDIUM"
                downgrade_note = "Downgraded: high false-alarm concern caps severity at MEDIUM. "
            if evidence in ("LOW", "INSUFFICIENT"):
                suppressed = True
                severity = "LOW"  # retained for monitoring, not an operator alert
                suppression_reason = (
                    "High false-alarm concern with weak evidence confidence: thermal anomaly "
                    "retained for monitoring but suppressed as an operator alert."
                )

        # --- Real evidence fields --------------------------------------
        classification = _clean_str(row.get("classification_label"))
        classification_score = _to_float(row.get("classification_score"))
        persistence_category = _clean_str(row.get("persistence_category")).lower() or "isolated"
        active_days = _to_int(row.get("active_days"), default=1)
        observation_count = _to_int(row.get("observation_count"), default=1)
        max_frp = _to_float(row.get("max_frp"))
        max_bright = _to_float(row.get("max_bright_ti4"))
        bt_diff = _to_float(row.get("bt_diff_max"))

        movement_direction = _clean_str(row.get("direction"))
        movement_pattern = _clean_str(row.get("movement_pattern")) or "insufficient_evidence"
        bearing = row.get("movement_bearing_degrees")
        bearing_val = None if movement_direction == "" else (_to_float(bearing) if bearing is not None else None)
        if bearing_val is not None and not movement_direction:
            bearing_val = None
        movement_rate = row.get("movement_rate_km_per_day")
        movement_rate_val = _to_float(movement_rate) if movement_rate is not None else None

        # Response integration (never fabricate a station) ---------------
        station_available = bool(row.get("station_available")) if not pd.isna(row.get("station_available", None)) else False
        station_name = _clean_str(row.get("nearest_station_name"))
        if not station_available:
            station_name = ""
        station_dist_raw = row.get("station_distance_km")
        station_dist = None
        if station_available:
            try:
                sd = float(station_dist_raw)
                station_dist = round(sd, 2) if math.isfinite(sd) else None
            except (TypeError, ValueError):
                station_dist = None

        lat = _to_float(row.get("latitude"), default=float("nan"))
        lon = _to_float(row.get("longitude"), default=float("nan"))
        lat = None if math.isnan(lat) else round(lat, 5)
        lon = None if math.isnan(lon) else round(lon, 5)

        # --- Reasons (generated from actual fields) --------------------
        reasons: List[str] = []
        if risk_valid and risk_score >= MEDIUM_RISK_MIN:
            reasons.append(f"Risk score {risk_score:.0f}/100 ({severity} risk)")
        if fa == "LOW":
            reasons.append("Low false-alarm concern")
        elif fa == "HIGH":
            reasons.append("High false-alarm concern")
        if reliability == "HIGH":
            reasons.append("High evidence reliability")
        if persistence_category in ("persistent", "short_lived_repeated") or active_days >= 2:
            if persistence_category == "persistent" or active_days >= 4:
                reasons.append(f"Persistent multi-day thermal activity ({active_days} active days)")
            else:
                reasons.append(f"Recurring thermal activity ({active_days} active days)")
        elif observation_count == 1:
            reasons.append("Single observation (no temporal recurrence)")
        if max_frp >= STRONG_FRP_MW:
            reasons.append(f"Strong thermal power (FRP {max_frp:.1f} MW)")
        elif max_frp >= ELEVATED_FRP_MW:
            reasons.append(f"Elevated thermal power (FRP {max_frp:.1f} MW)")
        if max_bright >= HIGH_BRIGHTNESS_K or bt_diff >= HIGH_CONTRAST_K:
            reasons.append("Peak thermal intensity / high spectral contrast")
        if "industrial" in classification.lower():
            reasons.append(f"Industrial context detected (score {classification_score:.2f})")
        elif "agricultural" in classification.lower():
            reasons.append("Agricultural-context event")
        elif "forest" in classification.lower():
            reasons.append("Forest/Natural-context event")
        if movement_direction:
            reasons.append(
                f"Thermal activity movement {movement_direction}"
                + (f" (confidence {_clean_str(row.get('direction_confidence'))})" if _clean_str(row.get("direction_confidence")) else "")
            )
        if station_available and station_name:
            dist_txt = f" ({station_dist:.1f} km)" if station_dist is not None else ""
            reasons.append(f"Verified fire station nearby: {station_name}{dist_txt}")
        if suppressed:
            reasons.append("Suppressed for monitoring (high false-alarm concern, weak evidence)")
        if downgrade_note:
            reasons.append(downgrade_note.rstrip(". "))
        if not reasons:
            reasons.append("Routine thermal baseline / informational monitoring")

        rationale = (
            "Decision-support thermal anomaly alert. "
            + downgrade_note
            + "; ".join(reasons)
            + ". Does not constitute a confirmed fire declaration."
        )

        return {
            "alert_id": f"TAL-{cluster_id:05d}",
            "cluster_id": cluster_id,
            # Stable physical-event identity (see src/persistence/event_identity.py).
            # Survives cluster_id remapping across re-ingestion cycles.
            "event_key": _clean_str(row.get("event_key")),
            "severity": severity,
            "status": "ACTIVE",
            "evidence_confidence": evidence,
            "suppressed": suppressed,
            "suppression_reason": suppression_reason,
            "risk_score": round(risk_score, 1) if risk_valid else None,
            "risk_level": risk_level,
            "classification_label": classification or "Unknown / Insufficient Evidence",
            "classification_score": round(classification_score, 3),
            "false_alarm_indicator": fa or "UNKNOWN",
            "detection_reliability": reliability or "UNKNOWN",
            "observation_count": observation_count,
            "active_days": active_days,
            "persistence_category": persistence_category,
            "max_frp": round(max_frp, 2),
            "max_bright_ti4": round(max_bright, 2),
            "bt_diff_max": round(bt_diff, 2),
            "movement_direction": movement_direction or None,
            "movement_bearing_degrees": bearing_val,
            "movement_rate_km_per_day": movement_rate_val,
            "movement_pattern": movement_pattern,
            "latitude": lat,
            "longitude": lon,
            "nearest_station_name": station_name,
            "station_distance_km": station_dist,
            "station_available": station_available,
            "reasons": "; ".join(reasons),
            "alert_rationale": rationale,
            "created_at": created_at,
            "updated_at": created_at,
            "is_decision_support_only": True,
        }


# ============================================================================
# Intelligence assembly (shared by the CLI script and the FastAPI backend)
# ============================================================================

def build_intelligence_frame(data_dir: Path) -> pd.DataFrame:
    """
    Merge the existing processed intelligence CSVs into one cluster-level frame
    suitable for alert generation. Reuses existing outputs; performs no new
    risk/classification/movement computation.
    """
    data_dir = Path(data_dir)
    risk_path = data_dir / "firms_risk_results.csv"
    if not risk_path.exists():
        raise FileNotFoundError(f"Missing required dataset: {risk_path}")
    risk = pd.read_csv(risk_path)

    frame = risk.copy()

    gis_path = data_dir / "gis_thermal_events.csv"
    if gis_path.exists():
        gis = pd.read_csv(gis_path)
        if "latitude" in gis.columns:
            centroids = gis.groupby("cluster_id").agg(
                latitude=("latitude", "mean"), longitude=("longitude", "mean")
            ).reset_index()
            frame = pd.merge(frame, centroids, on="cluster_id", how="left", suffixes=("", "_gis"))

    classification_path = data_dir / "firms_industrial_classification.csv"
    if classification_path.exists():
        cls = pd.read_csv(classification_path)
        cols = ["cluster_id", "classification_label", "classification_score", "classification_rationale",
                "osm_facility_type", "osm_distance_km", "predicted_landcover_class", "prediction_confidence"]
        avail = [c for c in cols if c in cls.columns]
        frame = pd.merge(frame, cls[avail], on="cluster_id", how="left", suffixes=("", "_cls"))

    movement_path = data_dir / "thermal_movement.csv"
    if movement_path.exists():
        mov = pd.read_csv(movement_path)
        mcols = ["cluster_id", "direction", "movement_bearing_degrees", "movement_rate_km_per_day",
                 "movement_pattern", "direction_confidence"]
        avail = [c for c in mcols if c in mov.columns]
        frame = pd.merge(frame, mov[avail], on="cluster_id", how="left", suffixes=("", "_mov"))

    emergency_path = data_dir / "emergency_alerts.csv"
    if emergency_path.exists():
        em = pd.read_csv(emergency_path)
        ecols = ["cluster_id", "nearest_station_name", "station_distance_km", "station_available"]
        avail = [c for c in ecols if c in em.columns]
        frame = pd.merge(frame, em[avail], on="cluster_id", how="left", suffixes=("", "_em"))

    for col in ("latitude", "longitude"):
        if col not in frame.columns:
            frame[col] = float("nan")
    if "false_alarm_indicator" not in frame.columns:
        frame["false_alarm_indicator"] = "MEDIUM"
    if "detection_reliability" not in frame.columns:
        frame["detection_reliability"] = "MEDIUM"
    if "classification_label" not in frame.columns:
        frame["classification_label"] = "Unknown / Insufficient Evidence"
    return frame


# ============================================================================
# File-based store: dedup, lifecycle, escalation, history
# ============================================================================

class ThermalAlertStore:
    """
    File-based alert store operating on processed-data CSVs:

        <data_dir>/thermal_alerts.csv       current snapshot (upserted each run)
        <data_dir>/thermal_alert_history.csv  severity/state change history

    Rules:
      * Dedup: one row per cluster; alert_id deterministic (TAL-{cluster:05d}).
      * sync(): upsert a freshly generated frame; escalations and any severity
        change are written to the history file.
      * A RESOLVED alert stays RESOLVED unless the new severity rank is higher
        than the rank at which it was resolved (reopens as ACTIVE).
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.data_dir / "thermal_alerts.csv"
        self.history_path = self.data_dir / "thermal_alert_history.csv"
        # severity of the last resolved state per cluster (persisted so a later
        # sync() knows whether an incoming severity is a genuine escalation)
        self._meta_path = self.data_dir / "thermal_alert_meta.json"

    # -- loading -------------------------------------------------------
    def _load_snapshot(self) -> pd.DataFrame:
        if self.snapshot_path.exists():
            try:
                return pd.read_csv(self.snapshot_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"Failed to load alert snapshot {self.snapshot_path}: {exc}")
        return pd.DataFrame()

    def _load_history(self) -> pd.DataFrame:
        if self.history_path.exists():
            try:
                return pd.read_csv(self.history_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"Failed to load alert history {self.history_path}: {exc}")
        return pd.DataFrame()

    def _load_meta(self) -> Dict[str, Any]:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - defensive
                pass
        return {}

    def _save_meta(self, meta: Dict[str, Any]) -> None:
        self._meta_path.write_text(json.dumps(meta), encoding="utf-8")

    # -- upsert / sync -------------------------------------------------
    def sync(self, fresh: pd.DataFrame, run_reason: str = "pipeline rerun") -> pd.DataFrame:
        """
        Upsert a freshly generated alert frame. Returns the effective snapshot.

        - Existing statuses are preserved.
        - Severity changes (any direction) are logged to the history file with
          previous/new severity and the current status.
        - Escalation of an alert resolved at a lower severity reopens it ACTIVE.
        """
        fresh = fresh.copy()
        if fresh.empty:
            return fresh
        fresh = fresh.set_index("cluster_id", drop=False)

        old = self._load_snapshot()
        meta = self._load_meta()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        history_rows: List[Dict[str, Any]] = []

        old_by_cid: Dict[int, Dict[str, Any]] = {}
        if not old.empty:
            for _, r in old.iterrows():
                try:
                    old_by_cid[int(r["cluster_id"])] = r.to_dict()
                except (KeyError, ValueError, TypeError):
                    continue

        effective_rows = []
        for _, row in fresh.iterrows():
            cid = int(row["cluster_id"])
            prev = old_by_cid.get(cid)
            prev_sev = _clean_str(prev.get("severity")).upper() if prev is not None else ""
            new_sev = _clean_str(row.get("severity")).upper()
            prev_status = _clean_str(prev.get("status")).upper() if prev is not None else ""

            if prev is not None:
                # Preserve previous status unless escalation reopens a RESOLVED alert.
                if prev_status == "RESOLVED":
                    resolved_meta = meta.get(str(cid), {})
                    resolved_at_sev = str(resolved_meta.get("resolved_severity", "")).upper()
                    if new_sev and resolved_at_sev and SEVERITY_ORDER.get(new_sev, 1) > SEVERITY_ORDER.get(resolved_at_sev, 0):
                        status = "ACTIVE"
                        history_rows.append({
                            "alert_id": row["alert_id"], "cluster_id": cid,
                            "previous_severity": prev_sev, "new_severity": new_sev,
                            "status": "ACTIVE",
                            "timestamp": now,
                            "reason": f"Escalation reopens resolved alert ({prev_sev} -> {new_sev}): {run_reason}",
                        })
                    else:
                        status = "RESOLVED"
                else:
                    status = prev_status if prev_status in STATUS_ORDER else "ACTIVE"
            else:
                status = "ACTIVE"

            # Severity changed -> history entry (including genuine escalation).
            if prev is not None and prev_sev and new_sev and prev_sev != new_sev:
                reason = f"Severity updated by {run_reason}"
                if SEVERITY_ORDER.get(new_sev, 1) > SEVERITY_ORDER.get(prev_sev, 1):
                    reason = f"Escalation {prev_sev} -> {new_sev} ({run_reason})"
                history_rows.append({
                    "alert_id": row["alert_id"], "cluster_id": cid,
                    "previous_severity": prev_sev, "new_severity": new_sev,
                    "status": status, "timestamp": now, "reason": reason,
                })

            rec = row.to_dict()
            rec["status"] = status
            rec["updated_at"] = now
            effective_rows.append(rec)
            if status == "RESOLVED":
                meta[str(cid)] = {"resolved_severity": new_sev, "resolved_at": now}
            elif status == "ACTIVE" and str(cid) in meta:
                meta.pop(str(cid), None)

        eff = pd.DataFrame(effective_rows)
        # Deterministic column order; alert_id first.
        base_cols = [c for c in ["alert_id", "cluster_id"] if c in eff.columns]
        other_cols = [c for c in eff.columns if c not in base_cols]
        eff = eff[base_cols + other_cols].sort_values("cluster_id").reset_index(drop=True)
        eff.to_csv(self.snapshot_path, index=False)

        if history_rows:
            hist = pd.DataFrame(history_rows)
            if self.history_path.exists():
                try:
                    hist_old = pd.read_csv(self.history_path)
                    hist = pd.concat([hist_old, hist], ignore_index=True)
                except Exception:  # pragma: no cover - defensive
                    pass
            hist.to_csv(self.history_path, index=False)

        self._save_meta(meta)
        logger.info(f"Thermal alert snapshot upserted: {len(eff)} alerts -> {self.snapshot_path}")
        return eff

    # -- lifecycle transitions ----------------------------------------
    def _transition(self, cluster_id: int, new_status: str) -> Dict[str, Any]:
        snapshot = self._load_snapshot()
        if snapshot.empty:
            raise KeyError(f"Alert for cluster {cluster_id} not found (no snapshot)")
        mask = snapshot["cluster_id"].astype(int) == int(cluster_id)
        if not mask.any():
            raise KeyError(f"Alert for cluster {cluster_id} not found")
        idx = snapshot.index[mask][0]
        current_status = _clean_str(snapshot.at[idx, "status"]).upper()

        valid = {"ACKNOWLEDGED": ["ACTIVE"], "RESOLVED": ["ACTIVE", "ACKNOWLEDGED"]}
        allowed = valid.get(new_status)
        if allowed is None or current_status not in allowed:
            raise ValueError(
                f"Cannot transition alert TAL-{int(cluster_id):05d} from {current_status} to {new_status}"
            )

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snapshot.at[idx, "status"] = new_status
        snapshot.at[idx, "updated_at"] = now
        snapshot.to_csv(self.snapshot_path, index=False)

        meta = self._load_meta()
        if new_status == "RESOLVED":
            sev = _clean_str(snapshot.at[idx, "severity"]).upper()
            meta[str(int(cluster_id))] = {"resolved_severity": sev, "resolved_at": now}
        elif str(int(cluster_id)) in meta:
            meta.pop(str(int(cluster_id)), None)
        self._save_meta(meta)

        hist = self._load_history()
        entry = pd.DataFrame([{
            "alert_id": f"TAL-{int(cluster_id):05d}", "cluster_id": int(cluster_id),
            "previous_severity": "", "new_severity": "",
            "status": new_status, "timestamp": now,
            "reason": f"Status changed {current_status} -> {new_status}",
        }])
        hist = pd.concat([hist, entry], ignore_index=True) if not hist.empty else entry
        hist.to_csv(self.history_path, index=False)

        return snapshot.loc[idx].to_dict()

    def acknowledge(self, cluster_id: int) -> Dict[str, Any]:
        return self._transition(cluster_id, "ACKNOWLEDGED")

    def resolve(self, cluster_id: int) -> Dict[str, Any]:
        return self._transition(cluster_id, "RESOLVED")

    # -- queries -------------------------------------------------------
    def list_alerts(self, severity: Optional[str] = None, status: Optional[str] = None,
                    cluster_id: Optional[int] = None) -> List[Dict[str, Any]]:
        df = self._load_snapshot()
        if df.empty:
            return []
        if severity:
            df = df[df["severity"].astype(str).str.upper() == severity.upper()]
        if status:
            df = df[df["status"].astype(str).str.upper() == status.upper()]
        if cluster_id is not None:
            df = df[df["cluster_id"].astype(int) == int(cluster_id)]
        records = df.to_dict(orient="records")
        return [_sanitize_record(r) for r in records]

    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        df = self._load_snapshot()
        if df.empty:
            return None
        mask = df["alert_id"].astype(str) == str(alert_id)
        if not mask.any():
            return None
        return _sanitize_record(df.loc[mask].iloc[0].to_dict())


def _sanitize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe record: None instead of NaN, native int/float/bool types,
    and empty strings preserved for text keys (CSV round-trip artifact)."""
    out: Dict[str, Any] = {}
    for k, v in rec.items():
        is_nan = v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
        if is_nan:
            out[k] = "" if k in _TEXT_KEYS else None
        elif k == "suppressed" or k == "station_available" or k == "is_decision_support_only":
            try:
                out[k] = bool(v)
            except Exception:  # pragma: no cover - defensive
                out[k] = False
        elif isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = float(v) if isinstance(v, float) else v
        elif isinstance(v, str):
            out[k] = v
        else:
            try:
                out[k] = v.item() if hasattr(v, "item") else v
            except Exception:  # pragma: no cover - defensive
                out[k] = str(v)
    return out
