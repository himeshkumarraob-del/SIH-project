# thermal-intelligence

AI-based detection and classification of industrial fires and persistent
thermal sources, using NASA FIRMS, OpenStreetMap, and satellite data.

> **Status: Phase 1–2 (project setup + FIRMS ingestion) only.**
> Preprocessing, persistence, OSM enrichment, ML, and the API are not
> built yet — this README will be extended as each phase lands.

## What this system does (and does not) claim

This project distinguishes explicitly between:

1. **What NASA FIRMS observes** — satellite-detected thermal
   anomalies / active-fire detections. FIRMS does **not** tell us what
   caused a detection.
2. **What our pipeline calculates** — clustering, persistence,
   distances to OSM features. These are computed facts about the data,
   not judgments about cause.
3. **What the ML model predicts** — a probabilistic, explainable
   estimate of what a thermal anomaly is *probably* associated with.
4. **What is a risk estimate** — a transparent, configurable score,
   explicitly labeled "AI-Assisted Risk Score," not a calibrated
   probability or a legal finding.

The system never claims a "confirmed industrial fire" — only NASA FIRMS
active-fire/thermal-anomaly observations, AI-estimated classifications,
and risk scores with stated confidence.

## Project structure

```
thermal-intelligence/
├── data/
│   ├── raw/          # untouched FIRMS CSV downloads (never overwritten)
│   ├── interim/       # intermediate cleaning outputs
│   ├── processed/     # final cleaned/feature-engineered datasets
│   └── external/      # e.g. India boundary shapefile, OSM extracts
├── src/
│   ├── config.py           # central config loader (config.yaml + .env)
│   ├── logging_setup.py    # shared logging
│   ├── ingestion/           # PHASE 2-3: FIRMS API client + downloader
│   ├── preprocessing/       # PHASE 4-5: cleaning, features (not yet built)
│   ├── persistence/         # PHASE 6-7: clustering, persistence (not yet built)
│   ├── osm/                 # PHASE 8: OSM industrial context (not yet built)
│   ├── features/            # feature engineering (not yet built)
│   ├── models/              # ML training code (not yet built)
│   ├── anomaly/             # anomaly detection (not yet built)
│   ├── risk/                # risk scoring (not yet built)
│   └── api/                 # FastAPI service (not yet built)
├── tests/
├── models/            # saved model artifacts (not yet used)
├── reports/           # data-quality reports, logs, evaluation plots
├── scripts/           # CLI entry points
├── .env.example
├── requirements.txt
└── config.yaml
```

## Setup

```bash
cd thermal-intelligence
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set FIRMS_MAP_KEY to a real key from
# https://firms.modaps.eosdis.nasa.gov/api/map_key/
```

## Configuration

- **`config.yaml`** — non-secret settings: study-area bounding box,
  FIRMS product list, paths, logging. Edit this to change behavior.
- **`.env`** — secrets only (`FIRMS_MAP_KEY`). Never commit this file.

The study-area bounding box (`west=68, south=6, east=97, north=36`) is
an **approximate India bounding box, not an India boundary** — it also
covers parts of Pakistan, Nepal, Bangladesh, Myanmar, Sri Lanka, and
ocean. A real boundary-polygon filter is planned for Phase 4
(`src/preprocessing/boundary_filter.py`) and is not yet implemented.

## Running the downloader

```bash
# From the project root (so `src` is importable):
cd thermal-intelligence

# Small test range first (recommended before a full pull):
PYTHONPATH=. python scripts/download_firms_data.py --start 2026-08-20 --end 2026-08-22

# Default ~30-day historical pull (VIIRS NOAA-20 + NOAA-21, Standard Processing):
PYTHONPATH=. python scripts/download_firms_data.py

# Specific products / custom range:
PYTHONPATH=. python scripts/download_firms_data.py \
    --start 2026-07-01 --end 2026-07-30 \
    --products viirs_noaa20_sp viirs_noaa21_sp
```

Each request is:
- Logged to `reports/logs/firms_download_log.jsonl` (one JSON object per
  request: date, satellite/source, record count, saved filename, HTTP
  status, and any error) — this is the audit trail required by Phase 3.
- Saved as its own file under `data/raw/`, named
  `firms_<product>_<source>_<start>_to_<end>.csv`. **Existing raw files
  are never overwritten** — a re-run skips a file that's already there
  and logs that it did so.

FIRMS's area API caps how many days one request can cover
(`firms.max_days_per_request` in `config.yaml`, currently 10). The
downloader automatically splits any longer range into multiple
requests — you never need to chunk dates by hand.

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

Current tests cover config loading, FIRMS URL construction, product
validation, and date-range chunking — all without hitting the network
(no real `FIRMS_MAP_KEY` needed to run them; the test file sets a dummy
one to satisfy config loading).

## Known limitations at this stage

- No India-boundary (as opposed to bounding-box) filtering yet.
- No data cleaning/validation yet — raw CSVs are saved as-is.
- No retry/backoff on transient FIRMS API failures yet (failures are
  logged, not retried).
- `FirmsRequestResult.error` detection for FIRMS's plain-text error
  payloads is heuristic (looks for "invalid"/"error" in the first
  line) — should be hardened once we've seen real error responses.

## Next phases (not yet built)

Phase 4 (cleaning) → Phase 5 (features) → Phase 6 (clustering) →
Phase 7 (persistence) → Phase 8 (OSM context) → Phase 9 (labeling
inspection) → Phase 10 (ML) → ... → Phase 16 (FastAPI service).
