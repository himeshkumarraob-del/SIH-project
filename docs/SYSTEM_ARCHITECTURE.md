# System Architecture Specification

This document details the code structure, module breakdown, dataflow pipeline, and file-level responsibilities for the Thermal Intelligence Engine.

---

## Folder Structure

```
ai-engine/
├── config.yaml                   # Core application configuration settings
├── requirements.txt              # Python package dependencies
├── .env.example                  # Environment template for secrets (FIRMS_MAP_KEY)
├── data/
│   ├── external/                 # Static GeoJSON boundaries (india_boundary.geojson)
│   ├── interim/                  # Cleaned merged CSVs (firms_clean.csv)
│   ├── processed/                # Production datasets (firms_india, persistence, features, anomalies, etc.)
│   └── raw/                      # Raw API CSV files from NASA FIRMS
├── docs/                         # Team architecture & API documentation
├── models/                       # Serialized ML models & scalers (isolation_forest.joblib, robust_scaler.joblib)
├── reports/                      # Standalone generated artifacts (thermal_india_map.html)
├── src/
│   ├── config.py                 # Central config loader (.env + config.yaml)
│   ├── logging_setup.py          # Unified application logging framework
│   ├── features/
│   │   ├── __init__.py
│   │   └── feature_engineering.py# Feature extraction logic
│   ├── gis/
│   │   ├── __init__.py
│   │   ├── map_builder.py        # Folium interactive map builder
│   │   └── thermal_movement.py   # Thermal activity movement & bearing analyzer
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── downloader.py         # Multi-product range chunker & downloader
│   │   └── firms_client.py       # NASA FIRMS API client wrapper
│   ├── models/
│   │   ├── __init__.py
│   │   ├── anomaly_detector.py   # IsolationForest + RobustScaler model
│   │   ├── anomaly_explainer.py  # Factor attribution & characterization engine
│   │   ├── false_alarm_detector.py # False Alarm Intelligence module
│   │   └── risk_intelligence.py  # Risk Index (0-100) scoring engine
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── persistence_analysis.py# Haversine grid-blocked connected components clustering
│   └── preprocessing/
│       ├── __init__.py
│       ├── clean_firms.py        # Coordinate validation & deduplication
│       └── india_boundary_filter.py # Point-in-polygon boundary filter
├── scripts/                      # CLI execution entry points
│   ├── download_firms_data.py
│   ├── clean_firms_data.py
│   ├── filter_india_boundary.py
│   ├── analyze_persistence.py
│   ├── build_features.py
│   ├── run_anomaly_detection.py
│   ├── explain_anomalies.py
│   ├── analyze_false_alarms.py
│   ├── calculate_risk.py
│   ├── analyze_thermal_movement.py
│   └── build_gis_map.py
└── tests/                        # Comprehensive 68-test unit suite
    ├── test_ingestion.py
    ├── test_preprocessing.py
    ├── test_india_boundary_filter.py
    ├── test_persistence.py
    ├── test_features.py
    ├── test_anomaly_detector.py
    ├── test_anomaly_explainer.py
    ├── test_false_alarm_detector.py
    ├── test_risk_intelligence.py
    ├── test_thermal_movement.py
    └── test_gis_map.py
```

---

## Core Module Breakdown

### 1. `src/config.py`
- **Purpose:** Centralized source of truth for `config.yaml` settings and `.env` secrets.
- **Used By:** All modules across ingestion, preprocessing, persistence, features, models, GIS, and movement analysis.

### 2. `src/ingestion/firms_client.py` & `downloader.py`
- **Purpose:** Manages NASA FIRMS API interaction, rate limits, and 10-day date chunking.
- **Used By:** `scripts/download_firms_data.py`.

### 3. `src/preprocessing/clean_firms.py` & `india_boundary_filter.py`
- **Purpose:** Validates WGS84 coordinates, deduplicates, and clips detections against `india_boundary.geojson`.
- **Used By:** `scripts/clean_firms_data.py`, `scripts/filter_india_boundary.py`.

### 4. `src/persistence/persistence_analysis.py`
- **Purpose:** Spatio-temporal clustering using Haversine distance and connected components (`_UnionFind`).
- **Used By:** `scripts/analyze_persistence.py`, `src/features/feature_engineering.py`, `scripts/build_gis_map.py`, `scripts/analyze_thermal_movement.py`.

### 5. `src/features/feature_engineering.py`
- **Purpose:** Derives 24 statistical, spectral contrast, and temporal density features per cluster.
- **Used By:** `scripts/build_features.py`, `src/models/anomaly_detector.py`.

### 6. `src/models/anomaly_detector.py`
- **Purpose:** Unsupervised Isolation Forest outlier modeling on scaled feature vectors.
- **Used By:** `scripts/run_anomaly_detection.py`, `src/models/anomaly_explainer.py`.

### 7. `src/models/anomaly_explainer.py`
- **Purpose:** Deterministic factor attribution for anomaly justifications (`HIGH_THERMAL_INTENSITY`, etc.).
- **Used By:** `scripts/explain_anomalies.py`, `scripts/build_gis_map.py`, `scripts/calculate_risk.py`.

### 8. `src/models/false_alarm_detector.py`
- **Purpose:** Evaluates evidence reliability (`LOW`, `MEDIUM`, `HIGH` false alarm concern) to prevent sensor noise misinterpretation.
- **Used By:** `scripts/analyze_false_alarms.py`, `src/models/risk_intelligence.py`.

### 9. `src/models/risk_intelligence.py`
- **Purpose:** Computes an interpretable 0–100 Risk Index combining abnormality, FRP, persistence, and reliability penalties.
- **Used By:** `scripts/calculate_risk.py`.

### 10. `src/gis/thermal_movement.py`
- **Purpose:** Calculates daily cluster centroids, Haversine displacement, initial compass bearing, 8-way cardinal direction, and daily rate.
- **Used By:** `scripts/analyze_thermal_movement.py`.

### 11. `src/gis/map_builder.py`
- **Purpose:** Generates interactive Folium HTML map (`reports/thermal_india_map.html`) with marker clustering, popups, and layer toggles.
- **Used By:** `scripts/build_gis_map.py`.

---

## Complete System Data Flow Diagram

```
[ NASA FIRMS API ]
       │ (HTTP CSV Download)
       ▼
data/raw/firms_*.csv
       │ (Cleaning & Deduplication)
       ▼
data/interim/firms_clean.csv
       │ (Point-in-Polygon GeoJSON Filter)
       ▼
data/processed/firms_india.csv
       │ (Haversine Grid-Blocked Connected Components)
       ▼
data/processed/firms_persistence.csv
       │ (24 Feature Extractions)
       ▼
data/processed/firms_features.csv
       │ (RobustScaler + Isolation Forest)
       ▼
data/processed/firms_anomalies.csv
       │ (Factor Attribution Explainer)
       ▼
data/processed/firms_ai_results.csv
       ├───► False Alarm Intelligence ───► data/processed/firms_false_alarm.csv
       │                                                 │
       └───► Risk Intelligence Engine  ◄─────────────────┘
                     │
                     ▼
       data/processed/firms_risk_results.csv
                     │
     ┌───────────────┴───────────────┐
     ▼                               ▼
Thermal Activity Movement     GIS Master Events
     │                               │
     ▼                               ▼
data/processed/thermal_movement.csv   data/processed/gis_thermal_events.csv
                                     │
                                     ▼
                      reports/thermal_india_map.html
```
