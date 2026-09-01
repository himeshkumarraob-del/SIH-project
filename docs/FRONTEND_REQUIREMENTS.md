# Frontend Requirements & Web Dashboard Specification

*(Status: Proposed / Future Architecture - Not Yet Implemented)*

This document outlines the user interface, widget hierarchy, design principles, interactive map behaviors, and API consumption guidelines for the Thermal Intelligence Web Dashboard.

---

## Layout & View Components

### 1. Dashboard Overview Header
Top-level metric cards displaying key performance indicators:
- **Total Detections:** `4,524`
- **Active Thermal Clusters:** `1,792`
- **High-Risk Events (Index >= 60):** `98` (Red badge)
- **Moving Clusters:** `55` (Arrow indicator badge)
- **High False Alarm Concern:** `1,037` (Yellow/Gray warning chip)

---

### 2. Interactive India Map View
Primary map view referencing the behaviors in `src/gis/map_builder.py` and `src/gis/thermal_movement.py`:
- **Default Position:** Bounding box centered on India `[20.5937, 78.9629]`, zoom level 5.
- **Color Coding:**
  - 🔴 **HIGH Anomaly / High Risk:** Red markers (`#d9534f`)
  - 🟠 **ELEVATED Event:** Orange markers (`#f0ad4e`)
  - 🟢 **NORMAL Event:** Green markers (`#5cb85c`)
- **Thermal Activity Movement Overlay:** Direction arrows / vectors indicating movement trajectory for clusters with `movement_status = MOVING`.

---

### 3. Filter & Control Panel
Allows operational users to filter events across both map and table views:
- **Abnormality Level Checklist:** `NORMAL`, `ELEVATED`, `HIGH`.
- **False Alarm Concern Checklist:** `LOW` (Reliable), `MEDIUM`, `HIGH` (Weak Evidence).
- **Risk Level Checklist:** `LOW`, `MEDIUM`, `HIGH`.
- **Movement Status Checklist:** `MOVING`, `STATIONARY`, `INSUFFICIENT_DATA`.
- **Date Range Picker:** Filter by acquisition start and end dates.

---

### 4. Event Detail Side Panel
When an event marker or table row is selected, display:
- **Cluster & Detection IDs:** ID details and coordinates.
- **AI Assessment & Risk Score:**
  - Risk Score Index Gauge (0–100).
  - False Alarm Concern level (`LOW`, `MEDIUM`, `HIGH`) and reasons.
  - Anomaly characterization & explanation text.
- **Thermal Activity Movement Section:**
  - Movement status (`MOVING` / `STATIONARY` / `INSUFFICIENT_DATA`).
  - Net displacement distance (km) and rate (km/day).
  - Compass direction (`NE`, `SW`, etc.) and bearing angle.
