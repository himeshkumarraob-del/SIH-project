# Data Dictionary & Schema Documentation

This document provides schema definitions, descriptions, and data types for all intermediate and production datasets within `data/processed/`.

---

## Data Hierarchy & Relationship Model

```
FIRMS Detections (firms_india.csv - Point Detections)
       │
       ├── grouped by Spatio-Temporal Proximity into
       ▼
Clusters (firms_persistence.csv - Cluster Summaries)
       │
       ├── transformed into
       ▼
Features (firms_features.csv - 24 Derived Numerical Vector Features)
       │
       ├── scored by Isolation Forest into
       ▼
Anomalies (firms_anomalies.csv - Scores, Flags & Abnormality Levels)
       │
       ├── attributed by Explainer Engine into
       ▼
AI Results (firms_ai_results.csv - Characterizations & Explanations)
       │
       ├── merged with Point Detections into
       ▼
GIS Thermal Events (gis_thermal_events.csv - Master Event Dataset)
```

---

## Production Datasets

### 1. `data/processed/firms_india.csv`
- **Purpose:** Cleaned satellite thermal point detections located inside India boundary.
- **Creator Module:** `src/preprocessing/india_boundary_filter.py`
- **Rows:** 4,524 detections
- **Role:** Intermediate Production Input

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `latitude` | `float64` | WGS84 Latitude of thermal detection center point. |
| `longitude` | `float64` | WGS84 Longitude of thermal detection center point. |
| `bright_ti4` | `float64` | VIIRS I-4 Channel Brightness Temperature (Kelvin, ~3.9 µm). |
| `scan` | `float64` | Pixel scan size (km). |
| `track` | `float64` | Pixel track size (km). |
| `acq_date` | `string` | Acquisition date (`YYYY-MM-DD`). |
| `acq_time` | `int64` / `string` | Acquisition time (`HHMM` UTC). |
| `satellite` | `string` | Satellite identifier (`N20` = NOAA-20, `N21` = NOAA-21). |
| `instrument` | `string` | Sensor name (`VIIRS`). |
| `confidence` | `string` | Quality confidence category (`l` = low, `n` = nominal, `h` = high). |
| `version` | `string` | FIRMS data processing version. |
| `bright_ti5` | `float64` | VIIRS I-5 Channel Brightness Temperature (Kelvin, ~11 µm). |
| `frp` | `float64` | Fire Radiative Power (Megawatts - MW). |
| `daynight` | `string` | Observation time flag (`D` = Day, `N` = Night). |

---

### 2. `data/processed/firms_persistence.csv`
- **Purpose:** Spatio-temporally clustered summary records representing discrete thermal source locations across time.
- **Creator Module:** `src/persistence/persistence_analysis.py`
- **Rows:** 1,792 clusters
- **Role:** Intermediate Production Output

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `cluster_id` | `int64` | Unique cluster integer ID. |
| `observation_count` | `int64` | Total satellite point detections in cluster. |
| `active_days` | `int64` | Distinct calendar days on which cluster was detected. |
| `first_detection` | `string` | Earliest detection date in cluster. |
| `last_detection` | `string` | Latest detection date in cluster. |
| `duration_days` | `int64` | Total calendar span of cluster (`last_detection - first_detection + 1`). |
| `mean_bright_ti4` | `float64` | Cluster mean VIIRS I-4 brightness temperature (K). |
| `max_bright_ti4` | `float64` | Cluster peak VIIRS I-4 brightness temperature (K). |
| `mean_bright_ti5` | `float64` | Cluster mean VIIRS I-5 brightness temperature (K). |
| `max_bright_ti5` | `float64` | Cluster peak VIIRS I-5 brightness temperature (K). |
| `mean_frp` | `float64` | Cluster average Fire Radiative Power (MW). |
| `max_frp` | `float64` | Cluster peak Fire Radiative Power (MW). |
| `mean_confidence` | `float64` | Ordinal mean confidence score (`1`=low, `2`=nominal, `3`=high). |
| `persistence_score` | `float64` | Ratio of cluster active days to total dataset observation window. |
| `persistence_category` | `string` | Category (`isolated`, `short_lived_repeated`, `persistent`). |

---

### 3. `data/processed/firms_features.csv`
- **Purpose:** 23 numerical feature vectors derived per cluster for machine learning model consumption.
- **Creator Module:** `src/features/feature_engineering.py`
- **Rows:** 1,792 rows
- **Role:** Intermediate Model Input

| Feature Column | Type | Description |
| :--- | :--- | :--- |
| `bt_diff_mean` | `float64` | Spectral temperature contrast (`mean_bright_ti4 - mean_bright_ti5`). |
| `bt_diff_max` | `float64` | Peak spectral temperature contrast (`max_bright_ti4 - max_bright_ti5`). |
| `frp_mean_to_max_ratio` | `float64` | Intensity dynamics ratio (`mean_frp / max_frp`). |
| `detection_density` | `float64` | Daily detection density (`observation_count / duration_days`). |
| `active_day_ratio` | `float64` | Active day ratio within cluster span (`active_days / duration_days`). |
| `is_multi_day` | `int64` | Binary flag (`1` if `active_days > 1`, else `0`). |
| `is_persistent_candidate` | `int64` | Binary flag (`1` if category is `persistent`, else `0`). |
| `persistence_category_code` | `int64` | Categorical integer code (`0`=isolated, `1`=short_lived, `2`=persistent). |

---

### 4. `data/processed/firms_anomalies.csv`
- **Purpose:** Isolation Forest statistical anomaly scoring results.
- **Creator Module:** `src/models/anomaly_detector.py`
- **Rows:** 1,792 rows
- **Role:** Model Output

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `anomaly_score` | `float64` | Negated Isolation Forest decision score (higher = more anomalous). Range: `[-0.22, +0.2082]`. |
| `anomaly_flag` | `int64` | Outlier binary flag (`1` = anomaly, `0` = normal). |
| `abnormality_level` | `string` | Threshold level (`NORMAL`, `ELEVATED`, `HIGH`). |

---

### 5. `data/processed/firms_ai_results.csv`
- **Purpose:** Explained AI dataset containing deterministic factor characterization.
- **Creator Module:** `src/models/anomaly_explainer.py`
- **Rows:** 1,792 rows
- **Role:** Production AI Output

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `anomaly_characterization` | `string` | Label (`NORMAL_THERMAL_ACTIVITY`, `HIGH_THERMAL_INTENSITY`, `HIGH_THERMAL_ENERGY`, `PERSISTENT_THERMAL_ACTIVITY`, `SHORT_LIVED_EXTREME_EVENT`, `RECURRING_THERMAL_ACTIVITY`, `MULTI_FACTOR_ANOMALY`, `STATISTICAL_ANOMALY`). |
| `explanation` | `string` | Natural language justification statement explaining contributing drivers. |
| `contributing_factors` | `string` | Comma-separated list of feature names triggering thresholds. |

---

### 6. `data/processed/gis_thermal_events.csv`
- **Purpose:** Master GIS event dataset combining individual point detections with cluster metrics and AI results.
- **Creator Module:** `scripts/build_gis_map.py`
- **Rows:** 4,524 point detections
- **Role:** Primary Input for Backend & GIS Services

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `detection_id` | `int64` | Unique point detection identifier. |
| `latitude` | `float64` | WGS84 Latitude coordinate. |
| `longitude` | `float64` | WGS84 Longitude coordinate. |
| `acq_date` | `string` | Acquisition date (`YYYY-MM-DD`). |
| `cluster_id` | `int64` | Cluster association integer ID. |
| `persistence_category` | `string` | Cluster category (`isolated`, `short_lived_repeated`, `persistent`). |
| `anomaly_score` | `float64` | Cluster anomaly score. |
| `anomaly_flag` | `int64` | Binary anomaly flag. |
| `abnormality_level` | `string` | Level (`NORMAL`, `ELEVATED`, `HIGH`). |
| `anomaly_characterization` | `string` | AI evidence characterization. |
| `explanation` | `string` | Human-readable explanation sentence. |
| `contributing_factors` | `string` | Feature factors triggering anomaly. |
| `bright_ti4` | `float64` | VIIRS I-4 brightness temperature (K). |
| `bright_ti5` | `float64` | VIIRS I-5 brightness temperature (K). |
| `frp` | `float64` | Fire Radiative Power (MW). |
| `confidence` | `string` | Quality confidence (`l`, `n`, `h`). |
| `satellite` | `string` | Satellite source (`N20`, `N21`). |
