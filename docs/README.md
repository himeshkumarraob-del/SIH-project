# Thermal Intelligence Documentation Map (`docs/`)

This directory contains technical specifications, architecture guides, data dictionaries, status reports, and API requirements for the **Thermal Intelligence Engine**.

---

## Documentation Index

1. [**`PROJECT_STATUS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/PROJECT_STATUS.md)
   - Status matrix of all 11 completed modules and future work.
   - Exact record counts, distributions (Anomalies, False Alarms, Risk Index, Thermal Movement), and test coverage (68/68 passed).
   - Novelty progress breakdown.

2. [**`SYSTEM_ARCHITECTURE.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/SYSTEM_ARCHITECTURE.md)
   - Complete directory structure and file-by-file purpose.
   - Inputs, outputs, and dependencies for all `src/` modules, `scripts/`, and `tests/`.
   - Complete end-to-end dataflow pipeline diagram.

3. [**`DATA_DICTIONARY.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/DATA_DICTIONARY.md)
   - Schema descriptions and data types for all 9 processed CSV datasets:
     - `firms_india.csv` (4,524 detections)
     - `firms_persistence.csv` (1,792 clusters)
     - `firms_features.csv` (24 features)
     - `firms_anomalies.csv` (Isolation Forest anomaly scores & levels)
     - `firms_ai_results.csv` (Explainable AI characterization & explanations)
     - `firms_false_alarm.csv` (False Alarm Intelligence indicators & reliability)
     - `firms_risk_results.csv` (Risk Intelligence Index 0–100)
     - `gis_thermal_events.csv` (Master GIS point events dataset)
     - `thermal_movement.csv` (Thermal activity displacement & directions)

4. [**`BACKEND_REQUIREMENTS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/BACKEND_REQUIREMENTS.md)
   - Proposed FastAPI service architecture.
   - REST API endpoint specifications (`/health`, `/events`, `/clusters`, `/statistics`, `/map-data`).
   - Query parameter filtering, pagination, and JSON payload definitions.

5. [**`FRONTEND_REQUIREMENTS.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/FRONTEND_REQUIREMENTS.md)
   - Proposed Next.js / Vite web dashboard design.
   - Metric cards, interactive map behaviors, filter drawers, event detail side-panels, and priority triage tables.
   - Safety terminology guardrails.

6. [**`TEAM_DEVELOPMENT_GUIDE.md`**](file:///c:/Users/Himesh%20kumar%20rao/Desktop/SIH/ai-engine/docs/TEAM_DEVELOPMENT_GUIDE.md)
   - Developer environment setup and Git branching workflow.
   - Role ownership matrix (Person 1, Person 2, GIS, Backend, Frontend).
   - Safety rules and canonical Backend-Frontend API JSON contract.
