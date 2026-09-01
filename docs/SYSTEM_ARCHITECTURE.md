# System Architecture Specification

This document details the code structure, module breakdown, dataflow pipeline, and file-level responsibilities for the Thermal Intelligence Engine.

---

## Folder Structure

```
ai-engine/
├── config.yaml                   # Core application configuration settings
├── requirements.txt              # Python package dependencies
├── .env.example                  # Environment template for secrets (FIRMS_MAP_KEY)
├── backend/                      # FastAPI REST API service
│   ├── __init__.py
│   ├── main.py                   # FastAPI server & route handlers
│   └── schemas.py                # Pydantic JSON response models
├── data/
│   ├── external/                 # Static GeoJSON boundaries & satellite datasets
│   ├── interim/                  # Cleaned merged CSVs (firms_clean.csv)
│   ├── processed/                # Production datasets (firms_india, persistence, features, anomalies, etc.)
│   └── raw/                      # Raw API CSV files from NASA FIRMS
├── docs/                         # Team architecture & API documentation
├── models/                       # Serialized ML models & scalers
├── reports/                      # Standalone generated artifacts (thermal_india_map.html, evaluation reports)
├── src/
│   ├── config.py                 # Central config loader (.env + config.yaml)
│   ├── logging_setup.py          # Unified application logging framework
│   ├── features/                 # Feature extraction module
│   ├── gis/                      # Folium map builder & Thermal Movement analyzer
│   ├── ingestion/                # NASA FIRMS API client & range chunker
│   ├── models/                   # Anomaly detector, explainer, false alarm, risk, & industrial classifier
│   ├── osm/                      # OpenStreetMap industrial context extractor
│   ├── persistence/              # Haversine grid-blocked connected components clustering
│   ├── preprocessing/            # Data cleaning & India boundary point-in-polygon filter
│   ├── response/                 # Fire station proximity locator & emergency alert engine
│   └── satellite/                # PyTorch EfficientNet-B0 CNN, EuroSAT dataset, Sentinel-2 STAC search
├── scripts/                      # CLI execution entry points for pipeline stages
└── tests/                        # Comprehensive 97-test unit suite (14 test modules)
```

---

## Complete System Data Flow Diagram

```
               [ NASA FIRMS API ]
                       │ (HTTP CSV Download)
                       ▼
             data/raw/firms_*.csv
                       │ (Coordinate Validation & Deduplication)
                       ▼
          data/interim/firms_clean.csv
                       │ (Point-in-Polygon GeoJSON WGS84 Filter)
                       ▼
         data/processed/firms_india.csv  (4,524 Detections)
                       │ (Haversine Grid-Blocked Connected Components)
                       ▼
      data/processed/firms_persistence.csv  (1,792 Clusters)
                       │ (24 Feature Extractions)
                       ▼
       data/processed/firms_features.csv  (1,792 Feature Rows)
                       │ (RobustScaler + Isolation Forest)
                       ▼
      data/processed/firms_anomalies.csv  (Outlier Scores & Levels)
                       │ (Evidence Factor Attribution)
                       ▼
     data/processed/firms_ai_results.csv  (Explainable AI Results)
             ┌─────────┴─────────┐
             ▼                   ▼
data/processed/firms_false_alarm.csv   data/processed/firms_risk_results.csv
 (False Alarm Intelligence)             (Risk Intelligence Index 0-100)
             │                   │
             └─────────┬─────────┘
                       ▼
      data/processed/thermal_movement.csv
      (Thermal Activity Movement Analysis)
                       │
                       ▼
      data/processed/satellite_context.csv
      (Copernicus Sentinel-2 STAC Search + EfficientNet-B0 CNN)
                       │
                       ▼
  data/processed/firms_industrial_classification.csv
  (Multi-Source Evidence Fusion Classification)
                       │
                       ▼
      data/processed/emergency_alerts.csv
      (Fire Station Locator & Decision Support Alerts)
                       │
                       ├──────────────────────────┐
                       ▼                          ▼
     data/processed/gis_thermal_events.csv   [ FastAPI REST Service ]
                       │                      (http://localhost:8000)
                       ▼
       reports/thermal_india_map.html
        (Standalone Folium Interactive Map)
```
