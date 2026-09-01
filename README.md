# SIH Thermal Intelligence Engine (`thermal-intelligence`)

AI-driven detection, clustering, anomaly assessment, evidence explanation, false-alarm analysis, risk indexing, GIS mapping, and movement tracking for satellite thermal anomalies (NASA FIRMS) across India.

---

## What This System Does (and Does Not) Claim

1. **NASA FIRMS Detections:** Observational satellite thermal anomalies (VIIRS NOAA-20 & NOAA-21). NASA FIRMS does not classify physical causes.
2. **Spatio-Temporal Persistence:** Groups spatially close and temporally chained detections into candidate clusters (Haversine distance + Connected Components).
3. **Isolation Forest Anomaly Detection:** Unsupervised statistical outlier modeling on scaled cluster feature vectors. Flags statistical abnormality (`NORMAL`, `ELEVATED`, `HIGH`), not physical hazards.
4. **Explainable AI:** Evidence-based factor attribution explaining why a cluster is anomalous (e.g. `HIGH_THERMAL_INTENSITY`, `PERSISTENT_THERMAL_ACTIVITY`) without claiming unverified physical causes like "forest fire" or "industrial explosion".
5. **False Alarm Intelligence:** Evaluates supporting evidence strength (`LOW`, `MEDIUM`, `HIGH` concern / detection reliability). `HIGH` false-alarm concern indicates weak supporting evidence (e.g., single-pass observation), NOT a confirmed false alarm.
6. **Risk Intelligence:** An experimental, interpretable risk index (0–100) combining statistical abnormality, FRP energy, persistence, and reliability penalties. It is **NOT** a calibrated probability of fire or guaranteed physical danger.
7. **Thermal Activity Movement:** Measures spatial displacement, bearing, and movement rates of satellite detection centroids across active dates. It is **NOT** a claim of physical fire spread.

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
     data/processed/gis_thermal_events.csv
                       │
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
| **GIS Mapping** | **COMPLETE** | 4 / 4 PASSED | `reports/thermal_india_map.html`, `gis_thermal_events.csv` |
| **Thermal Activity Movement** | **COMPLETE** | 11 / 11 PASSED | `data/processed/thermal_movement.csv` |
| **Backend REST API** | *PLANNED* | — | *(Upcoming FastAPI Layer)* |
| **Frontend Web UI** | *PLANNED* | — | *(Upcoming Next.js / Vite Dashboard)* |

---

## Novelty Progress Matrix

- **Novel Feature 1:** *Unspecified / Future Exploration*
- **Novel Feature 2 — False Alarm Intelligence:** **COMPLETED** (Evidence-based false alarm concern indicator & detection reliability).
- **Novel Feature 3 — Thermal Activity Movement:** **COMPLETED** (Geospatial tracking of thermal detection centroids, bearing, and rates).
- **Novel Feature 4 — Vulnerability-Aware Risk:** *PLANNED / NOT YET IMPLEMENTED* (Note: Current Risk Index is evidence/anomaly-based; future Vulnerability-Aware Risk will incorporate exposure data such as population, land-use, or infrastructure).
- **Novel Feature 5 — Explainable AI:** **COMPLETED** (Deterministic factor attribution and human-readable anomaly justifications).

---

## Repository Structure

```
ai-engine/
├── README.md                     # Root team documentation & quick start guide
├── config.yaml                   # Core application configuration settings
├── requirements.txt              # Python package dependencies
├── .env.example                  # Environment template for secrets (FIRMS_MAP_KEY)
├── data/
│   ├── external/                 # Static GeoJSON boundaries (india_boundary.geojson)
│   ├── interim/                  # Cleaned merged CSVs (firms_clean.csv)
│   ├── processed/                # Production datasets (firms_india, persistence, features, anomalies, etc.)
│   └── raw/                      # Raw CSV files from NASA FIRMS API
├── docs/                         # Detailed architecture, dataset, & API specifications
│   ├── README.md                 # Documentation sitemap
│   ├── PROJECT_STATUS.md         # Full project status breakdown & metrics
│   ├── SYSTEM_ARCHITECTURE.md    # System modules & flow diagrams
│   ├── DATA_DICTIONARY.md        # Comprehensive dataset schema definitions
│   ├── BACKEND_REQUIREMENTS.md   # Proposed REST API specifications
│   ├── FRONTEND_REQUIREMENTS.md  # Proposed UI/UX dashboard specifications
│   └── TEAM_DEVELOPMENT_GUIDE.md # Developer onboarding & API contract
├── models/                       # Serialized ML artifacts (isolation_forest.joblib, robust_scaler.joblib)
├── reports/                      # Interactive HTML maps (thermal_india_map.html)
├── src/
│   ├── config.py                 # Central configuration loader (.env + config.yaml)
│   ├── logging_setup.py          # Unified application logging framework
│   ├── features/                 # Feature extraction module
│   ├── gis/                      # Folium map builder & Thermal Movement analyzer
│   ├── ingestion/                # NASA FIRMS API client & range chunker
│   ├── models/                   # Anomaly detector, explainer, false alarm, & risk modules
│   ├── persistence/              # Haversine grid-blocked connected components clustering
│   └── preprocessing/            # Data cleaning & India boundary point-in-polygon filter
├── scripts/                      # Executable CLI entry points for each pipeline stage
└── tests/                        # 68 unit tests covering all completed modules
```

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

To run the complete test suite (68 tests across 11 modules):
```bash
pytest -v
```

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

# 11. Interactive GIS Map Construction
python scripts/build_gis_map.py
```

---

## Scientific Guardrails & Limitations

- **Observational Data Only:** The system processes active thermal observations from satellite infrared channels. It does not replace ground-based fire department validation.
- **No Ground-Truth Assumptions:** Anomaly scoring and false-alarm concern levels are derived strictly from physical evidence (spectral contrast, FRP, persistence, observation count).
- **Movement Tracking:** Thermal activity movement measures spatial displacement of detection centroids over time and should not be cited as confirmed physical fire front propagation.

---

## Future Work

- **Backend Service Layer:** FastAPI REST API wrapping processed datasets and pipeline execution modules.
- **Frontend Dashboard:** Interactive Web UI (Next.js / Vite) with dynamic map rendering, filter drawers, and priority triage tables.
- **Vulnerability-Aware Risk:** Integrating external contextual datasets (population density, land-use, infrastructure proximity).
