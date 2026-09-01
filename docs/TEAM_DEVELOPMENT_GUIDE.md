# Team Development Guide & Collaboration Guidelines

This document provides developer onboarding steps, Git workflow rules, role responsibilities, safety directives, and the proposed Backend-Frontend API Contract.

---

## Team Roles & Ownership Matrix

| Role | Primary Ownership Areas | Core File Responsibilities |
| :--- | :--- | :--- |
| **Person 1 (AI/ML Engineer)** | Feature engineering, anomaly modeling, model evaluation, factor attribution. | `src/features/`, `src/models/`, `models/`, `tests/test_anomaly_detector.py`, `tests/test_anomaly_explainer.py`. |
| **Person 2 (Data Engineer)** | FIRMS API ingestion, cleaning, boundary filtering, spatio-temporal persistence. | `src/ingestion/`, `src/preprocessing/`, `src/persistence/`, `config.yaml`, `src/config.py`, pipeline tests. |
| **GIS Developer** | Interactive mapping, Leaflet/Folium map building, spatial layer controls. | `src/gis/`, `scripts/build_gis_map.py`, `tests/test_gis_map.py`, `reports/thermal_india_map.html`. |
| **Backend Developer** | REST API service, data access gateway, dynamic filter endpoints. | *(Upcoming)* `src/api/`, backend tests, database/CSV reader layer. |
| **Frontend Developer** | Next.js / React dashboard UI, map integration, filter widgets, event tables. | *(Upcoming)* `web/`, frontend UI components, API client hooks. |

---

## Developer Workflow & Git Protocol

### 1. Environment Setup
```bash
git clone <repository-url>
cd ai-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and insert your NASA FIRMS API key
```

### 2. Feature Branching Workflow
1. Pull the latest `main` branch before starting work:
   ```bash
   git checkout main
   git pull origin main
   ```
2. Create a feature branch matching your role:
   ```bash
   git checkout -b feature/backend-api-setup
   # or
   git checkout -b feature/frontend-dashboard
   ```
3. Commit changes with clear, descriptive messages:
   ```bash
   git commit -m "feat(backend): add GET /api/v1/events endpoint with level filtering"
   ```
4. Run unit tests before creating a pull request:
   ```bash
   pytest -v
   ```
5. Open a Pull Request (PR) against `main`. Require review from module owner before merging.

---

## Critical Safety & Integrity Rules

- 🚫 **NEVER Commit Secrets:** Do not commit `.env` or hardcode `FIRMS_MAP_KEY` in source code.
- 🚫 **Do NOT Modify Raw Datasets:** Never manually edit or overwrite files in `data/raw/` or `data/external/`.
- 🚫 **Do NOT Change Pipeline Schemas:** Do not silently rename or drop columns from `firms_india.csv`, `firms_persistence.csv`, `firms_features.csv`, or `gis_thermal_events.csv`.
- 🚫 **Do NOT Alter ML Isolation Forest Logic:** Changes to `src/models/anomaly_detector.py` or feature extraction must be coordinated with Person 1 (AI/ML Lead).
- 🚫 **Do NOT Invent Ground-Truth Labels:** Never claim a thermal anomaly is an "industrial fire" or "forest fire" without external verified land-use data.
- ✅ **ALWAYS Run Tests:** Ensure all 43 tests pass cleanly (`pytest -v`) before pushing.

---

## Backend & Frontend Proposed API Contract

*(Proposed Contract - For Backend & Frontend Team Alignment)*

### Integration Architecture
```
Frontend (Next.js)  ─── GET /api/v1/events?level=HIGH ───►  Backend API (FastAPI)
                                                                 │
                                                    Reads & Filters
                                                                 ▼
                                                  gis_thermal_events.csv
```

### Canonical Event Object JSON Schema

```json
{
  "detection_id": 858,
  "cluster_id": 858,
  "latitude": 28.6139,
  "longitude": 77.2090,
  "acq_date": "2026-08-20",
  "persistence_category": "persistent",
  "anomaly_score": 0.2082,
  "anomaly_flag": 1,
  "abnormality_level": "HIGH",
  "anomaly_characterization": "MULTI_FACTOR_ANOMALY",
  "explanation": "High abnormality primarily associated with elevated thermal intensity and thermal energy (FRP).",
  "contributing_factors": "max_bright_ti4,max_frp",
  "bright_ti4": 367.0,
  "bright_ti5": 302.32,
  "frp": 12.56,
  "confidence": "n",
  "satellite": "N20"
}
```

### Endpoint Handoff Summary

| Endpoint | Method | Response Type | Description |
| :--- | :---: | :--- | :--- |
| `/api/v1/health` | GET | `Object` | Service readiness and record count diagnostics. |
| `/api/v1/events` | GET | `Array[Event]` | Filterable, paginated point detection events. |
| `/api/v1/events/{id}` | GET | `Event` | Single event detail object. |
| `/api/v1/events/high-risk` | GET | `Array[Event]` | Top anomalous events sorted by `anomaly_score`. |
| `/api/v1/clusters` | GET | `Array[Cluster]` | Cluster-level summaries. |
| `/api/v1/statistics` | GET | `Object` | Counts for abnormality levels, persistence categories, and date range. |
| `/api/v1/map-data` | GET | `GeoJSON` | FeatureCollection for interactive web rendering. |
