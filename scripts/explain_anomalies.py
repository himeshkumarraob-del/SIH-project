#!/usr/bin/env python3
"""
CLI entry point for anomaly explanation and characterization.

Reads data/processed/firms_anomalies.csv, uses the AnomalyExplainer to
add characterization and explanation strings, and saves the output to
data/processed/firms_ai_results.csv.

Usage:
    python scripts/explain_anomalies.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.models.anomaly_explainer import ThermalAnomalyExplainer
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.explain_anomalies")

def main() -> int:
    cfg = get_config()
    input_path = cfg.processed_data_dir / "firms_anomalies.csv"
    output_path = cfg.processed_data_dir / "firms_ai_results.csv"
    
    if not input_path.exists():
        logger.error(f"Input anomalies file not found: {input_path}")
        print(f"ERROR: Input anomalies file not found: {input_path}")
        return 1
        
    try:
        df = pd.read_csv(input_path)
        logger.info(f"Loaded {len(df)} records from {input_path}")
        
        explainer = ThermalAnomalyExplainer()
        results_df = explainer.explain(df)
        
        results_df.to_csv(output_path, index=False)
        logger.info(f"Saved explained AI results to {output_path}")
        
        total_records = len(results_df)
        char_counts = results_df["anomaly_characterization"].value_counts()
        
        print("\n=== Anomaly Explanation Summary ===")
        print(f"Records processed:       {total_records}")
        print("\nCharacterization Counts:")
        for char, count in char_counts.items():
            print(f"  {char:30s} {count}")
            
        print(f"\nOutput file saved to:    {output_path}")
        
        print("\n--- Example Explanations (Sample of 5 anomalous records) ---")
        anomalies_only = results_df[results_df["abnormality_level"].isin(["HIGH", "ELEVATED"])]
        if not anomalies_only.empty:
            sample_size = min(5, len(anomalies_only))
            examples = anomalies_only.sample(sample_size, random_state=42)
            for _, row in examples.iterrows():
                print(f"Cluster ID: {row['cluster_id']} (Level: {row['abnormality_level']})")
                print(f"  Characterization: {row['anomaly_characterization']}")
                print(f"  Explanation:      {row['explanation']}")
                print(f"  Factors:          {row['contributing_factors']}\n")
        else:
            print("No anomalies found to explain.")
            
        print("===================================\n")
        
    except Exception as exc:
        logger.exception("Anomaly explanation failed")
        print(f"ERROR: Anomaly explanation failed: {exc}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
