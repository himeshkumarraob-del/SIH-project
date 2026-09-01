# Backend Requirements & API Specification

*(Status: Proposed / Future Architecture - Not Yet Implemented)*

This document specifies the architecture, data access guidelines, filtering logic, and REST API contract for the upcoming Backend API service layer (FastAPI / Python).

---

## Backend Architectural Overview

The Backend service acts as an API gateway between the existing AI Engine/Data outputs and the future Web Dashboard frontend.

```
+--------------------------+
|  Processed CSV Data /    |
|  AI Models & Pipeline    |
+--------------------------+
             │
             ▼
+--------------------------+
|   Backend API Service    | <--- FastAPI / Python
|  (Data Loader & Filters) |
+--------------------------+
             │
             ▼ REST JSON Endpoints
+--------------------------+
|   Frontend Web UI        | <--- Next.js / Vite
+--------------------------+
```

---

## Primary Data Sources for Backend

1. **Master GIS Point Detections:** [`data/processed/gis_thermal_events.csv`](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/data/processed/gis_thermal_events.csv)
   - Used for point-level map rendering, spatial queries, and point detail popups.
2. **AI Cluster Summaries:** [`data/processed/firms_ai_results.csv`](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/data/processed/firms_ai_results.csv)
   - Used for cluster-level analytics, distribution charts, and cluster search.

---

## Proposed API Endpoints

### 1. `GET /api/v1/health`
- **Purpose:** Service health & status diagnostic check.
- **Response:**
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "data_loaded": true,
    "total_events": 4524,
    "total_clusters": 1792
  }
  ```

---

### 2. `GET /api/v1/events`
- **Purpose:** Query point thermal detection records with filtering and pagination.
- **Query Parameters:**
  - `abnormality_level` *(optional, enum: `NORMAL`, `ELEVATED`, `HIGH`)*
  - `persistence_category` *(optional, enum: `isolated`, `short_lived_repeated`, `persistent`)*
  - `characterization` *(optional, string)*
  - `satellite` *(optional, string: `N20`, `N21`)*
  - `start_date` *(optional, string format `YYYY-MM-DD`)*
  - `end_date` *(optional, string format `YYYY-MM-DD`)*
  - `page` *(optional, default `1`)*
  - `limit` *(optional, default `100`)*
- **Response Structure:**
  ```json
  {
    "total": 4524,
    "page": 1,
    "limit": 100,
    "data": [
      {
        "detection_id": 1,
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
    ]
  }
  ```

---

### 3. `GET /api/v1/events/{detection_id}`
- **Purpose:** Retrieve full detail payload for a single detection point.
- **Response:** Single JSON object as structured above.

---

### 4. `GET /api/v1/events/high-risk`
- **Purpose:** Rapid access endpoint for top anomalous events (`abnormality_level = HIGH` sorted by `anomaly_score` descending).

---

### 5. `GET /api/v1/clusters`
- **Purpose:** Retrieve aggregated cluster summary list for cluster list views and table pagination.
- **Query Parameters:** `page`, `limit`, `abnormality_level`, `persistence_category`.

---

### 6. `GET /api/v1/clusters/{cluster_id}`
- **Purpose:** Fetch detailed cluster summary along with all associated point detection child records.

---

### 7. `GET /api/v1/statistics`
- **Purpose:** Dashboard metric cards and chart distribution payloads.
- **Response Structure:**
  ```json
  {
    "total_detections": 4524,
    "total_clusters": 1792,
    "abnormality_counts": {
      "NORMAL": 2345,
      "ELEVATED": 594,
      "HIGH": 1585
    },
    "persistence_counts": {
      "isolated": 1503,
      "short_lived_repeated": 254,
      "persistent": 35
    },
    "date_range": {
      "min": "2026-08-01",
      "max": "2026-08-30"
    }
  }
  ```

---

### 8. `GET /api/v1/map-data`
- **Purpose:** GeoJSON payload for lightweight front-end map rendering (FeatureCollection).

---

## GIS Integration Rules

- The Backend should wrap `build_india_map(events_df, output_path)` from [`src/gis/map_builder.py`](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/src/gis/map_builder.py) whenever an HTML map export is requested.
- For dynamic web frontend interactions, the backend serves lightweight GeoJSON/JSON responses from `/api/v1/map-data` so the web map renders dynamically without reloading full HTML pages.

---

## Future Real-Time Pipeline Integration

When real-time execution is enabled:
1. Trigger `/scripts/download_firms_data.py`.
2. Execute automated cleaning, filtering, persistence, and feature extraction.
3. Run `ThermalAnomalyDetector.load(models_dir).predict(df)` in-memory.
4. Pass results to `ThermalAnomalyExplainer().explain(df)`.
5. Update database/CSV cache for instant REST serving.
