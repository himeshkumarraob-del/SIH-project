# System Architecture Specification

This document details the code structure, module breakdown, dataflow pipeline, and file-level responsibilities for the Thermal Intelligence Engine.

---

## Folder Structure

```
ai-engine/
├── config.yaml                   # Core application configuration settings
├── requirements.txt              # Python package dependencies
├── .env.example                  # Environment template for secrets (FIRMS_MAP_KEY)
├── config/                       # Custom configuration helpers
├── data/
│   ├── external/                 # Static GeoJSON boundaries (india_boundary.geojson)
│   ├── interim/                  # Cleaned merged CSVs (firms_clean.csv)
│   ├── processed/                # Production datasets (firms_india, persistence, features, anomalies, ai_results, gis_events)
│   └── raw/                      # Raw API CSV files from NASA FIRMS
├── models/                       # Serialized ML models & scalers (isolation_forest.joblib, robust_scaler.joblib)
├── reports/                      # Standalone generated artifacts (thermal_india_map.html)
├── src/
│   ├── __init__.py
│   ├── config.py                 # Central config loader (.env + config.yaml)
│   ├── logging_setup.py          # Unified application logging framework
│   ├── features/
│   │   ├── __init__.py
│   │   └── feature_engineering.py# Feature extraction logic
│   ├── geo/                      # Geographic & spatial tools
│   ├── gis/
│   │   ├── __init__.py
│   │   └── map_builder.py        # Folium interactive map builder
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── downloader.py         # Multi-product range chunker & downloader
│   │   └── firms_client.py       # NASA FIRMS API client wrapper
│   ├── models/
│   │   ├── __init__.py
│   │   ├── anomaly_detector.py   # IsolationForest + RobustScaler model
│   │   └── anomaly_explainer.py  # Factor attribution & characterization engine
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── persistence_analysis.py# Haversine grid-blocked connected components clustering
│   └── preprocessing/
│       ├── __init__.py
│       ├── cleaner.py            # Coordinate validation & deduplication
│       └── india_boundary_filter.py # Point-in-polygon boundary filter
├── scripts/                      # CLI execution entry points
│   ├── download_firms_data.py
│   ├── clean_firms_data.py
│   ├── filter_india_boundary.py
│   ├── analyze_persistence.py
│   ├── build_features.py
│   ├── run_anomaly_detection.py
│   ├── explain_anomalies.py
│   └── build_gis_map.py
├── tests/                        # Comprehensive PyTest unit test suite
│   ├── test_ingestion.py
│   ├── test_preprocessing.py
│   ├── test_india_boundary_filter.py
│   ├── test_persistence.py
│   ├── test_features.py
│   ├── test_anomaly_detector.py
│   ├── test_anomaly_explainer.py
│   └── test_gis_map.py
└── docs/                         # Team architecture & API documentation
```

---

## Core Module Breakdown

### 1. `src/config.py`
- **Purpose:** Centralized, lazily-loaded single source of truth for configuration (`config.yaml`) and secrets (`.env`).
- **Input:** `config.yaml`, `.env` environment variables.
- **Output:** Strongly typed configuration classes (`Config`, `BoundingBox`, `PersistenceConfig`).
- **Used By:** All modules across ingestion, preprocessing, persistence, features, AI models, and GIS.

### 2. `src/ingestion/firms_client.py` & `downloader.py`
- **Purpose:** Manages NASA FIRMS API interaction, URL construction, rate limiting, and 10-day date chunking.
- **Input:** API Key, bounding box, product key, date range.
- **Output:** Raw CSV files stored in `data/raw/`.
- **Used By:** `scripts/download_firms_data.py`.

### 3. `src/preprocessing/cleaner.py` & `india_boundary_filter.py`
- **Purpose:** Validates WGS84 coordinate bounds `[-90,90]`, `[-180,180]`, removes duplicates, and performs point-in-polygon clipping against `india_boundary.geojson`.
- **Input:** `data/raw/*.csv`, `data/external/india_boundary.geojson`.
- **Output:** `data/interim/firms_clean.csv`, `data/processed/firms_india.csv`.
- **Used By:** `scripts/clean_firms_data.py`, `scripts/filter_india_boundary.py`.

### 4. `src/persistence/persistence_analysis.py`
- **Purpose:** Performs spatio-temporal clustering using Haversine distance and connected components (`_UnionFind`) with coarse grid-cell blocking.
- **Input:** `data/processed/firms_india.csv`.
- **Output:** `data/processed/firms_persistence.csv` (Cluster-level summary records with `persistence_category` and `persistence_score`).
- **Used By:** `scripts/analyze_persistence.py`, `src/features/feature_engineering.py`, `scripts/build_gis_map.py`.

### 5. `src/features/feature_engineering.py`
- **Purpose:** Extracts 24 statistical, spectral contrast, and temporal density features per cluster without ground-truth assumptions.
- **Input:** `data/processed/firms_persistence.csv`.
- **Output:** `data/processed/firms_features.csv`.
- **Used By:** `scripts/build_features.py`, `src/models/anomaly_detector.py`.

### 6. `src/models/anomaly_detector.py`
- **Purpose:** Scaled unsupervised anomaly detection using `RobustScaler` + `IsolationForest` on 10 specific features.
- **Input:** `data/processed/firms_features.csv`.
- **Output:** `data/processed/firms_anomalies.csv` (`anomaly_score`, `anomaly_flag`, `abnormality_level`), serialized `models/isolation_forest.joblib` and `models/robust_scaler.joblib`.
- **Used By:** `scripts/run_anomaly_detection.py`, `src/models/anomaly_explainer.py`.

### 7. `src/models/anomaly_explainer.py`
- **Purpose:** Deterministic factor attribution determining why an anomaly occurred (e.g. intensity vs. energy vs. persistence).
- **Input:** `data/processed/firms_anomalies.csv`.
- **Output:** `data/processed/firms_ai_results.csv` (`anomaly_characterization`, `explanation`, `contributing_factors`).
- **Used By:** `scripts/explain_anomalies.py`, `scripts/build_gis_map.py`.

### 8. `src/gis/map_builder.py`
- **Purpose:** Constructs reusable Folium HTML maps with marker clustering, layer controls, and popups.
- **Input:** Event DataFrame (`gis_thermal_events.csv`), optional GeoJSON path.
- **Output:** `reports/thermal_india_map.html`.
- **Used By:** `scripts/build_gis_map.py`, future Backend API services.

---

## Data Flow Diagram

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
       │ (Haversine & UnionFind Clustering)
       ▼
data/processed/firms_persistence.csv
       │ (Feature Derivation)
       ▼
data/processed/firms_features.csv
       │ (RobustScaler + IsolationForest)
       ▼
data/processed/firms_anomalies.csv
       │ (Factor Attribution Explainer)
       ▼
data/processed/firms_ai_results.csv
       │ (Join Detections + Clusters + AI Results)
       ▼
data/processed/gis_thermal_events.csv
       │ (Folium HTML Map Builder)
       ▼
reports/thermal_india_map.html
```
