# SIH Thermal Intelligence Engine (`thermal-intelligence`)

AI-driven detection, clustering, anomaly assessment, evidence explanation, false-alarm analysis, risk indexing, thermal activity movement tracking, industrial source classification, satellite CNN visual land-use analysis, operational alert decision-support, and REST API service for NASA FIRMS satellite thermal anomalies across India.

---

## What This System Does (and Does Not) Claim

1. **NASA FIRMS Detections:** Observational satellite thermal anomalies (VIIRS NOAA-20 & NOAA-21). NASA FIRMS does not classify physical causes.
2. **Spatio-Temporal Persistence:** Groups spatially close and temporally chained detections into candidate clusters (Haversine distance + Connected Components).
3. **Isolation Forest Anomaly Detection:** Unsupervised statistical outlier modeling on scaled cluster feature vectors. Flags statistical abnormality (`NORMAL`, `ELEVATED`, `HIGH`), not physical hazards.
4. **Explainable AI:** Evidence-based factor attribution explaining why a cluster is anomalous (e.g. `HIGH_THERMAL_INTENSITY`, `PERSISTENT_THERMAL_ACTIVITY`) without claiming unverified physical causes.
5. **False Alarm Intelligence:** Evaluates supporting evidence strength (`LOW`, `MEDIUM`, `HIGH` concern / detection reliability). `HIGH` false-alarm concern indicates weak supporting evidence (e.g., single-pass observation), NOT a confirmed false alarm.
6. **Risk Intelligence:** An experimental, interpretable risk index (0–100) combining statistical abnormality, FRP energy, persistence, and reliability penalties. It is **NOT** a calibrated probability of fire or guaranteed physical danger.
7. **Thermal Activity Movement:** Measures spatial displacement, bearing, and movement rates of satellite detection centroids across active dates. It is **NOT** a claim of physical fire spread.
8. **Industrial Source Classification:** Segregates events into `Industrial-context thermal event`, `Agricultural-context thermal event`, `Forest/Natural-context thermal event`, or `Unknown / Insufficient Evidence` using multi-source evidence fusion (FIRMS signals, persistence, movement, OSM industrial proximity, and satellite CNN visual context).
9. **Satellite CNN Visual Land-Use Context:** EfficientNet-B0 trained on EuroSAT Sentinel-2 RGB imagery to classify visual land-use characteristics (e.g. Industrial, Forest, Crop). Confidence represents visual similarity (**MODEL CONFIDENCE**), NOT "probability of fire".
10. **Emergency Response Decision Support:** Identifies nearest regional fire stations and provides operational alert recommendations (`HIGH PRIORITY ALERT`, `MONITOR / REVIEW`, `NO ALERT`). It is **DECISION SUPPORT**, not an actual emergency dispatch.

---

## Current Architecture & Data Pipeline

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

---

## Completed Modules & Status

| Module / Component | Status | Test Status | Primary Output Artifact |
| :--- | :---: | :---: | :--- |
| **Data Ingestion** | **COMPLETE** | 9 / 9 PASSED | `data/raw/*.csv` |
| **Data Preprocessing & Cleaning** | **COMPLETE** | 3 / 3 PASSED | `data/interim/firms_clean.csv` |
| **India Boundary Filtering** | **COMPLETE** | 3 / 3 PASSED | `data/processed/firms_india.csv` (4,524 records) |
| **Persistence Clustering** | **COMPLETE** | 7 / 7 PASSED | `data/processed/firms_persistence.csv` (1,792 clusters) |
| **Feature Engineering** | **COMPLETE** | 5 / 5 PASSED | `data/processed/firms_features.csv` (24 features) |
| **Isolation Forest Anomaly Detection** | **COMPLETE** | 5 / 5 PASSED | `data/processed/firms_anomalies.csv` |
| **Explainable Anomaly Characterization** | **COMPLETE** | 7 / 7 PASSED | `data/processed/firms_ai_results.csv` |
| **False Alarm Intelligence** | **COMPLETE** | 6 / 6 PASSED | `data/processed/firms_false_alarm.csv` |
| **Risk Intelligence (0-100 Index)** | **COMPLETE** | 8 / 8 PASSED | `data/processed/firms_risk_results.csv` |
| **Thermal Activity Movement** | **COMPLETE** | 11 / 11 PASSED | `data/processed/thermal_movement.csv` |
| **OSM Industrial Context Extractor** | **COMPLETE** | Included | Proximity metrics |
| **Industrial Source Classification** | **COMPLETE** | 10 / 10 PASSED | `firms_industrial_classification.csv` |
| **Satellite CNN (EfficientNet-B0 / EuroSAT)** | **COMPLETE** | 5 / 5 PASSED | `data/processed/satellite_context.csv` |
| **Fire Station Locator & Operational Alerts** | **COMPLETE** | 6 / 6 PASSED | `data/processed/emergency_alerts.csv` |
| **FastAPI REST API Service** | **COMPLETE** | 8 / 8 PASSED | `http://localhost:8000` (Endpoints: `/events`, `/statistics`, `/clusters`, `/map-data`, etc.) |
| **GIS Mapping** | **COMPLETE** | 4 / 4 PASSED | `reports/thermal_india_map.html`, `gis_thermal_events.csv` |

---

## Environment Setup & Installation

```bash
# Clone the repository
git clone https://github.com/himeshkumarraob-del/sih-thermal-intelliegence.git
cd sih-thermal-intelliegence

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and insert your NASA FIRMS API key
```

---

## Running Unit Tests

To run the complete test suite (97 tests across 14 modules):
```bash
pytest -v
```

---

## Starting the FastAPI REST API Server

```bash
uvicorn backend.main:app --reload --port 8000
```
Access API documentation at: `http://localhost:8000/docs`

---

## Pipeline Execution Commands

Run the pipeline stages sequentially:

```bash
# 1. Ingestion (NASA FIRMS)
python scripts/download_firms_data.py

# 2. Cleaning & Deduplication
python scripts/clean_firms_data.py

# 3. India Boundary Filtering
python scripts/filter_india_boundary.py

# 4. Persistence Analysis & Clustering
python scripts/analyze_persistence.py

# 5. Feature Engineering
python scripts/build_features.py

# 6. Isolation Forest Anomaly Detection
python scripts/run_anomaly_detection.py

# 7. Explainable Anomaly Characterization
python scripts/explain_anomalies.py

# 8. False Alarm Intelligence
python scripts/analyze_false_alarms.py

# 9. Risk Intelligence Index
python scripts/calculate_risk.py

# 10. Thermal Activity Movement Analysis
python scripts/analyze_thermal_movement.py

# 11. Satellite CNN Training & Inference
python scripts/train_satellite_cnn.py
python scripts/run_satellite_inference.py

# 12. Industrial Source Classification
python scripts/classify_industrial_fires.py

# 13. Fire Station Locator & Emergency Alert Generation
python scripts/generate_alerts.py

# 14. Interactive GIS Map Construction
python scripts/build_gis_map.py
```
