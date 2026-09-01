# Team Development Guide & Collaboration Guidelines

This document provides developer onboarding steps, Git workflow rules, role responsibilities, safety directives, and the proposed Backend-Frontend API Contract.

---

## Team Roles & Ownership Matrix

| Role | Primary Ownership Areas | Core File Responsibilities |
| :--- | :--- | :--- |
| **Person 1 (AI/ML Engineer)** | Anomaly detection, characterization explainer, false alarm intelligence, risk intelligence index. | `src/features/`, `src/models/`, `models/`, `tests/test_anomaly_detector.py`, `tests/test_anomaly_explainer.py`, `tests/test_false_alarm_detector.py`, `tests/test_risk_intelligence.py`. |
| **Person 2 (Data Engineer)** | FIRMS API ingestion, cleaning, boundary filtering, spatio-temporal persistence. | `src/ingestion/`, `src/preprocessing/`, `src/persistence/`, `config.yaml`, `src/config.py`, pipeline tests. |
| **GIS Developer** | Interactive mapping, Leaflet/Folium map building, Thermal Activity Movement tracking. | `src/gis/`, `scripts/build_gis_map.py`, `scripts/analyze_thermal_movement.py`, `tests/test_gis_map.py`, `tests/test_thermal_movement.py`, `reports/thermal_india_map.html`. |
| **Backend Developer** | REST API service, data access gateway, dynamic filter endpoints. | *(Upcoming)* `src/api/`, backend tests, database/CSV reader layer. |
| **Frontend Developer** | Next.js / React dashboard UI, map integration, filter widgets, event tables. | *(Upcoming)* `web/`, frontend UI components, API client hooks. |

---

## Critical Safety & Integrity Rules

- 🚫 **NEVER Commit Secrets:** Do not commit `.env` or hardcode `FIRMS_MAP_KEY` in source code.
- 🚫 **Do NOT Modify Raw Datasets:** Never manually edit or overwrite files in `data/raw/` or `data/external/`.
- 🚫 **Do NOT Change Pipeline Schemas:** Do not silently rename or drop columns from existing CSV files in `data/processed/`.
- 🚫 **Do NOT Alter ML Isolation Forest Logic:** Changes to `src/models/anomaly_detector.py` must be coordinated with Person 1 (AI/ML Lead).
- 🚫 **Do NOT Invent Ground-Truth Labels:** Never claim a thermal anomaly is a "confirmed fire" or "industrial explosion". Use scientifically defensible terms like *Thermal Activity Movement* and *Risk Index*.
- ✅ **ALWAYS Run Tests:** Ensure all 68 tests pass cleanly (`pytest -v`) before pushing.
