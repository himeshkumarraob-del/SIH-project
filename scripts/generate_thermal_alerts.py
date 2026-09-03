#!/usr/bin/env python3
"""
CLI entry point for the Thermal Alert / Alarm Engine (decision support).

1. Reads the existing processed intelligence datasets:
   - firms_risk_results.csv (risk index + false-alarm + persistence + thermal)
   - gis_thermal_events.csv (cluster centroids)
   - firms_industrial_classification.csv (industrial context)
   - thermal_movement.csv (movement/direction)
   - emergency_alerts.csv (verified fire-station proximity)
2. Runs the deterministic ThermalAlertEngine.
3. Upserts data/processed/thermal_alerts.csv (dedup per cluster, one alert
   per cluster, idempotent across reruns) and appends severity/state changes
   to data/processed/thermal_alert_history.csv.

Usage:
    python scripts/generate_thermal_alerts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_config
from src.logging_setup import get_logger
from src.models.alert_engine import ThermalAlertEngine, ThermalAlertStore, build_intelligence_frame

logger = get_logger("scripts.generate_thermal_alerts")


def main() -> int:
    cfg = get_config()
    data_dir = cfg.processed_data_dir

    try:
        frame = build_intelligence_frame(data_dir)
        logger.info(f"Built intelligence frame with {len(frame)} clusters")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    engine = ThermalAlertEngine()
    fresh = engine.generate_alerts(frame)

    store = ThermalAlertStore(data_dir)
    snapshot = store.sync(fresh, run_reason="alert generation")

    # ---- Summary -----------------------------------------------------
    sev = snapshot["severity"].value_counts().to_dict()
    status = snapshot["status"].value_counts().to_dict()
    conf = snapshot["evidence_confidence"].value_counts().to_dict()
    suppressed = int(snapshot["suppressed"].sum()) if "suppressed" in snapshot else 0
    industrial = int(
        snapshot["classification_label"].astype(str).str.contains("Industrial", na=False).sum()
    ) if "classification_label" in snapshot else 0
    st_avail = int(snapshot["station_available"].sum()) if "station_available" in snapshot else 0
    st_missing = int((~snapshot["station_available"]).sum()) if "station_available" in snapshot else 0

    history_rows = 0
    if store.history_path.exists():
        try:
            history_rows = len(_read_csv(store.history_path))
        except Exception:  # pragma: no cover
            history_rows = 0

    print("\n=== Thermal Alert Engine Summary ===")
    print(f"Total alerts:                 {len(snapshot)}")
    print(f"  CRITICAL:                   {sev.get('CRITICAL', 0)}")
    print(f"  HIGH:                       {sev.get('HIGH', 0)}")
    print(f"  MEDIUM:                     {sev.get('MEDIUM', 0)}")
    print(f"  LOW:                        {sev.get('LOW', 0)}")
    print(f"Suppressed (monitoring only): {suppressed}")
    print("Evidence confidence:")
    for c in ["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]:
        print(f"  {c:<14} {conf.get(c, 0)}")
    print("Status:")
    for s in ["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]:
        print(f"  {s:<14} {status.get(s, 0)}")
    print(f"Industrial-context alerts:    {industrial}")
    print(f"With verified fire station:   {st_avail}")
    print(f"Without verified station:     {st_missing}")
    print(f"History entries:              {history_rows}")
    print(f"\nOutput: {store.snapshot_path}")
    print("=============================================================\n")
    return 0


def _read_csv(path: Path):
    import pandas as pd
    return pd.read_csv(path)


if __name__ == "__main__":
    sys.exit(main())
