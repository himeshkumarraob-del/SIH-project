#!/usr/bin/env python3
"""
CLI entry point for anomaly detection.

Reads data/processed/firms_features.csv, fits the anomaly detector,
generates anomaly scores/flags/levels, saves the model/scaler, and 
outputs data/processed/firms_anomalies.csv.

Usage:
    python scripts/run_anomaly_detection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.models.anomaly_detector import ThermalAnomalyDetector
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.run_anomaly_detection")

def main() -> int:
    cfg = get_config()
    input_path = cfg.processed_data_dir / "firms_features.csv"
    output_path = cfg.processed_data_dir / "firms_anomalies.csv"
    model_dir = cfg.models_dir
    
    if not input_path.exists():
        logger.error(f"Input features file not found: {input_path}")
        print(f"ERROR: Input features file not found: {input_path}")
        return 1
        
    try:
        df = pd.read_csv(input_path)
        logger.info(f"Loaded {len(df)} records from {input_path}")
        
        detector = ThermalAnomalyDetector()
        detector.fit(df)
        
        results_df = detector.predict(df)
        
        results_df.to_csv(output_path, index=False)
        logger.info(f"Saved anomaly results to {output_path}")
        
        detector.save(model_dir)
        logger.info(f"Saved model and scaler to {model_dir}")
        
        # Summary statistics
        total_records = len(results_df)
        anomalies = results_df["anomaly_flag"].sum()
        anomaly_pct = (anomalies / total_records) * 100 if total_records > 0 else 0
        
        levels_counts = results_df["abnormality_level"].value_counts()
        normal_count = levels_counts.get("NORMAL", 0)
        elevated_count = levels_counts.get("ELEVATED", 0)
        high_count = levels_counts.get("HIGH", 0)
        
        print("\n=== Anomaly Detection Summary ===")
        print(f"Records processed:       {total_records}")
        print(f"Anomalous records:       {anomalies}")
        print(f"Anomaly percentage:      {anomaly_pct:.2f}%")
        print("\nAbnormality Levels:")
        print(f"  NORMAL:                {normal_count}")
        print(f"  ELEVATED:              {elevated_count}")
        print(f"  HIGH:                  {high_count}")
        print(f"\nOutput file saved to:    {output_path}")
        print(f"Model saved to:          {model_dir / 'isolation_forest.joblib'}")
        print(f"Scaler saved to:         {model_dir / 'robust_scaler.joblib'}")
        print("=================================\n")
        
    except Exception as exc:
        logger.exception("Anomaly detection failed")
        print(f"ERROR: Anomaly detection failed: {exc}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
