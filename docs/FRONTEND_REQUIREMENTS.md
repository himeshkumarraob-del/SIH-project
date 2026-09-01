# Frontend Requirements & Web Dashboard Specification

*(Status: Proposed / Future Architecture - Not Yet Implemented)*

This document outlines the user interface, widget hierarchy, design principles, interactive map behaviors, and API consumption guidelines for the Thermal Intelligence Web Dashboard.

---

## Technical Stack & Aesthetic Guidelines

- **Framework:** Next.js / Vite (React + TypeScript).
- **Styling:** Modern Vanilla CSS / TailwindCSS (if configured), Dark Mode first, glassmorphism card UI, vibrant indicators for anomaly levels.
- **Mapping:** Mapbox GL / Leaflet / Folium iframe wrapper.
- **State Management:** TanStack Query (React Query) for REST API caching.

---

## Layout & View Components

### 1. Dashboard Overview Header
Top-level metric cards displaying key performance indicators:
- **Total Detections:** `4,524`
- **Active Thermal Clusters:** `1,792`
- **High-Risk Anomalies:** `1,585` (Red badge)
- **Elevated Events:** `594` (Orange badge)
- **Persistent Sites:** `35` (Blue badge)

---

### 2. Interactive India Map View
Primary map view referencing the behaviors in `src/gis/map_builder.py`:
- **Default Position:** Bounding box centered on India `[20.5937, 78.9629]`, zoom level 5.
- **Controls:**
  - Zoom in/out, mouse-wheel zoom, drag-panning.
  - Reset to India Bounding Box button.
  - Fullscreen toggle.
- **Marker Clustering:** Dynamic grouping of point detections to prevent visual clutter.
- **Color Coding:**
  - 🔴 **HIGH Anomaly:** Red markers (`#d9534f`)
  - 🟠 **ELEVATED Event:** Orange markers (`#f0ad4e`)
  - 🟢 **NORMAL Event:** Green markers (`#5cb85c`)
- **Event Popup Modal:**
  - Cluster ID & Abnormality Level Header
  - Anomaly Score
  - Persistence Category
  - AI Characterization & Explanation text block
  - Contributing Factor Chips (`max_bright_ti4`, `max_frp`, etc.)
  - Thermal metrics (`FRP`, `Brightness Temp`, `Satellite`, `Date`)

---

### 3. Filter & Control Panel
Allows operational users to narrow down visible events across both map and table views:
- **Abnormality Level Checklist:** `NORMAL`, `ELEVATED`, `HIGH`.
- **Persistence Category Checklist:** `isolated`, `short_lived_repeated`, `persistent`.
- **Date Range Picker:** Filter by acquisition start and end dates.
- **Satellite Selector:** `NOAA-20`, `NOAA-21`, `All`.
- **Characterization Filter Dropdown:** Filter by `MULTI_FACTOR_ANOMALY`, `HIGH_THERMAL_INTENSITY`, etc.

---

### 4. Event Detail Side Panel
When a user clicks any event marker on the map or row in the table, slide in a details panel displaying:
- **Event Identifiers:** Cluster ID, Detection ID.
- **Location:** WGS84 Latitude & Longitude with copy-to-clipboard button.
- **AI Assessment Card:**
  - Anomaly Score gauge meter.
  - Abnormality badge (`HIGH` / `ELEVATED` / `NORMAL`).
  - Evidence-based characterization title.
  - Explanation sentence explaining physical evidence.
  - Contributing factor tags.
- **Thermal Physical Properties:**
  - VIIRS I-4 Temperature (Kelvin).
  - VIIRS I-5 Temperature (Kelvin).
  - Fire Radiative Power (MW).
  - Confidence rating.

---

### 5. High-Risk Event Priority Table
A searchable, sortable data table for rapid triage:
- **Columns:** `Cluster ID`, `Acquisition Date`, `Coordinates`, `Abnormality Level`, `Anomaly Score`, `Persistence Category`, `FRP (MW)`, `Characterization`.
- **Sort default:** `Anomaly Score` descending.
- **Pagination:** 25 / 50 / 100 rows per page.

---

### 6. Safety & Terminology Directives
- **NO Ground-Truth Claims:** The frontend MUST NOT display terms like *"Industrial Explosion"* or *"Forest Fire"* unless supported by external land-use data.
- **Use Official Terminology:** Always display characterizations verbatim as returned by the API (`HIGH_THERMAL_INTENSITY`, `PERSISTENT_THERMAL_ACTIVITY`, etc.).
