# Thermal Intelligence Engine (`thermal-intelligence`)

Welcome to the **Thermal Intelligence Engine** codebase. This repository contains an end-to-end data processing, spatio-temporal clustering, unsupervised machine learning, anomaly explanation, and interactive GIS mapping pipeline for satellite thermal anomalies (NASA FIRMS) across India.

---

## System Pipeline Architecture

```
NASA FIRMS API
     ↓
Data Ingestion (NRT & SP VIIRS NOAA-20/21)
     ↓
Data Preprocessing & Cleaning (Coordinate validation, deduplication)
     ↓
India Boundary Filtering (Point-in-polygon WGS84 GIS filter)
     ↓
Persistence & Spatio-Temporal Clustering (Haversine distance + Connected Components)
     ↓
Feature Engineering (24 thermal, temporal, & spectral ratio features)
     ↓
Isolation Forest Anomaly Detection (RobustScaler + Unsupervised Outlier Modeling)
     ↓
Anomaly Explanation & Characterization (Evidence-based factor attribution)
     ↓
GIS Interactive Mapping (Folium / Leaflet visual rendering)
     ↓
Backend API (NOT YET IMPLEMENTED - Planned)
     ↓
Frontend Dashboard (NOT YET IMPLEMENTED - Planned)
```

---

## Status Summary

- **Completed Phases:**
  - ✅ **Data Ingestion Pipeline:** NASA FIRMS API client, 10-day chunking, automated caching.
  - ✅ **Data Cleaning & Filtering:** Spatial coordinate cleaning, exact deduplication, India polygon clipping.
  - ✅ **Persistence Analysis:** Spatio-temporal clustering (`_UnionFind` grid-blocking), duration & recurrence tracking.
  - ✅ **Feature Engineering:** 24 deterministic features without synthetic ground-truth assumptions.
  - ✅ **AI/ML Anomaly Detection:** Isolation Forest + `RobustScaler` producing `anomaly_score`, `anomaly_flag`, and `abnormality_level` (`NORMAL`, `ELEVATED`, `HIGH`).
  - ✅ **Anomaly Explanation:** Deterministic factor attribution generating `anomaly_characterization`, `explanation`, and `contributing_factors`.
  - ✅ **GIS Interactive Mapping:** Folium HTML map generator (`reports/thermal_india_map.html`) with marker clustering, layer toggles, and popups.
- **Future / Planned Work:**
  - ⏳ **Backend API:** FastAPI REST endpoints for dynamic data access and query filtering.
  - ⏳ **Frontend Dashboard:** Interactive Web UI (Next.js / Vite) consuming Backend REST APIs.

---

## Documentation Navigation

Detailed documentation is organized within the `docs/` folder:

1. [**`PROJECT_STATUS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/PROJECT_STATUS.md) — Comprehensive status report of completed components, metrics, and test coverage.
2. [**`SYSTEM_ARCHITECTURE.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/SYSTEM_ARCHITECTURE.md) — Deep dive into code structure, module responsibilities, inputs/outputs, and dataflow.
3. [**`DATA_DICTIONARY.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/DATA_DICTIONARY.md) — Field-level schema documentation for all intermediate and production CSV datasets.
4. [**`BACKEND_REQUIREMENTS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/BACKEND_REQUIREMENTS.md) — Detailed REST API specification, endpoint designs, filtering rules, and backend integration guide.
5. [**`FRONTEND_REQUIREMENTS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/FRONTEND_REQUIREMENTS.md) — UX/UI dashboard specifications, widget layouts, event detail panels, and API consumption guide.
6. [**`TEAM_DEVELOPMENT_GUIDE.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/TEAM_DEVELOPMENT_GUIDE.md) — Developer onboarding, environment setup, Git branching strategies, role ownership, and API contracts.

---

## Quick Start & Reproduction

### 1. Installation
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Running Unit Tests
```bash
pytest -v
```
*(43 out of 43 tests passing)*

### 3. Pipeline Execution Scripts
```bash
# 1. Ingestion (Requires FIRMS_MAP_KEY in .env)
python scripts/download_firms_data.py

# 2. Cleaning & Deduplication
python scripts/clean_firms_data.py

# 3. India Boundary Filtering
python scripts/filter_india_boundary.py

# 4. Persistence Analysis & Clustering
python scripts/analyze_persistence.py

# 5. Feature Engineering
python scripts/build_features.py

# 6. AI/ML Anomaly Detection
python scripts/run_anomaly_detection.py

# 7. Anomaly Explanation & Characterization
python scripts/explain_anomalies.py

# 8. GIS Interactive Map Construction
python scripts/build_gis_map.py
```
