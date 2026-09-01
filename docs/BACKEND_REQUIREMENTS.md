# Backend Requirements & API Specification

*(Status: Proposed / Future Architecture - Not Yet Implemented)*

This document specifies the architecture, data access guidelines, filtering logic, and REST API contract for the upcoming Backend API service layer (FastAPI / Python).

---

## Primary Data Sources for Backend

1. **Master GIS Point Detections:** `data/processed/gis_thermal_events.csv`
2. **AI Cluster Summaries:** `data/processed/firms_ai_results.csv`
3. **False Alarm Intelligence:** `data/processed/firms_false_alarm.csv`
4. **Risk Intelligence Index:** `data/processed/firms_risk_results.csv`
5. **Thermal Movement:** `data/processed/thermal_movement.csv`

---

## Extended Proposed API Endpoints

### 1. `GET /api/v1/health`
- **Purpose:** Service health & status diagnostic check.

### 2. `GET /api/v1/events`
- **Purpose:** Query point thermal detection records with filtering and pagination.
- **Supported Parameters:** `abnormality_level`, `false_alarm_indicator`, `risk_level`, `persistence_category`, `movement_status`, `satellite`, `start_date`, `end_date`, `page`, `limit`.

### 3. `GET /api/v1/movement`
- **Purpose:** Retrieve thermal activity movement vectors for clusters with `movement_status = MOVING`.
- **Response Payload:**
  ```json
  [
    {
      "cluster_id": 1325,
      "movement_status": "MOVING",
      "start_latitude": 20.123,
      "start_longitude": 78.456,
      "end_latitude": 20.111,
      "end_longitude": 78.450,
      "total_movement_distance_km": 1.295,
      "movement_rate_km_per_day": 1.312,
      "movement_bearing_degrees": 180.0,
      "movement_direction": "S",
      "movement_confidence": "MEDIUM"
    }
  ]
  ```

### 4. `GET /api/v1/statistics`
- **Purpose:** Comprehensive dashboard analytics payload returning counts across abnormality levels, false alarm concern, risk index, and thermal movement.
