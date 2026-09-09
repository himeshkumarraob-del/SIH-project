"""
Live NASA FIRMS NRT ingestion — feeds the existing ThermalWatch pipeline.

DESIGN (deliberately boring on purpose)
---------------------------------------
Every cycle, for each configured product (VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT):

    FIRMS Area API (India bbox, 2-day UTC window)
        -> FirmsClient.fetch()                (existing, unchanged)
        -> parse + normalize rows             (satellite N20/N21 -> NOAA-20/21)
        -> dedup vs seen-detection ledger     (stable FIRMS attributes)
        -> atomic append to data/raw/         (firms_*.csv naming convention)
        -> write state JSON for /api/v1/ingestion/status
        -> (caller) re-run the existing processing pipeline

The historical 30-day dataset is NEVER modified: live rows go into separate
per-product, per-UTC-day "live" raw files matching the existing discovery
glob (firms_*.csv), so src/preprocessing.clean_firms needs no changes and its
own drop_duplicates catches anything the ledger misses.

SAFETY PROPERTIES
-----------------
* A failed fetch/parse/append never touches processed data (the pipeline is
  only triggered after a fully successful ingest phase).
* All writes are atomic (temp file + os.replace).
* The state JSON records last attempt/success, per-product and total
  fetched/new/duplicates/rejected, status, and errors — no URLs, no secrets.
* Empty results (header-only CSV) are a legitimate success with new=0.
* One-product-down degrades to "degraded" rather than failing the cycle.

TERMINOLOGY: rows are "thermal observations/detections", never "fires".
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config import Config, get_config
from src.ingestion.firms_client import FirmsClient, FirmsRequestResult
from src.logging_setup import get_logger

logger = get_logger("ingestion.live_ingestion")

# Header-less marker: FIRMS returns just the column header for empty results.
EXPECTED_COLUMNS = [
    "latitude", "longitude", "bright_ti4", "scan", "track",
    "acq_date", "acq_time", "satellite", "instrument", "confidence",
    "version", "bright_ti5", "frp", "daynight",
]

# Ledger retention: seen-detection ids older than this are trimmed. The
# cleaning stage's full-dataset dedup is the safety net afterwards.
LEDGER_RETENTION_DAYS = 14

STATE_FILENAME = "ingestion_state.json"
LEDGER_FILENAME = "ingestion_seen_detections.csv"
LOG_FILENAME = "ingestion_runs.jsonl"

# Satellite code normalization: FIRMS CSV 'satellite' column carries terse
# codes (N20/N21); the cleaner's convention (and detection_id scheme) uses
# filename-derived NOAA-20/NOAA-21 labels, so live rows must match exactly.
SATELLITE_CODE_MAP = {"N20": "NOAA-20", "N21": "NOAA-21", "NPP": "SUOMI-NPP"}


@dataclass
class ProductIngestStats:
    product_key: str
    source: str
    status: str = "skipped"          # ok | degraded | failed | skipped
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    rejected: int = 0
    error: Optional[str] = None


@dataclass
class IngestionAttempt:
    run_utc: str
    trigger: str                     # scheduler | manual | catchup
    status: str = "running"          # running | healthy | degraded | failed
    started_utc: str = ""
    finished_utc: str = ""
    duration_seconds: float = 0.0
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    rejected: int = 0
    pipeline_triggered: bool = False
    pipeline_status: Optional[str] = None
    error: Optional[str] = None
    products: List[ProductIngestStats] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Ledger (seen detection ids) — prevents repeat processing of observations
# ---------------------------------------------------------------------------

def _ledger_path(cfg: Config) -> Path:
    return cfg.processed_data_dir / LEDGER_FILENAME


def _raw_filename_for_live(product_key: str, source: str, day: date) -> str:
    # Same convention as the batch downloader, with a _live_<date> suffix:
    # matches the cleaner's discovery glob (firms_*.csv) without colliding
    # with historical batch files (which are never overwritten).
    return f"firms_{product_key}_{source}_{day.isoformat()}_live.csv"


def _live_files_for(cfg: Config, product_key: str) -> List[Path]:
    return sorted(cfg.raw_data_dir.glob(f"firms_{product_key}_*_{date.today().isoformat()}_live.csv"))


def _load_ledger(cfg: Config) -> pd.DataFrame:
    path = _ledger_path(cfg)
    if path.exists():
        try:
            df = pd.read_csv(path, dtype={"detection_key": str})
        except (OSError, pd.errors.ParserError) as exc:
            logger.warning("Seen-detection ledger unreadable (%s); starting fresh: %s", path, exc)
            return pd.DataFrame(columns=["detection_key", "first_seen_utc"])
        return df
    return pd.DataFrame(columns=["detection_key", "first_seen_utc"])


def _save_ledger(cfg: Config, ledger: pd.DataFrame) -> None:
    path = _ledger_path(cfg)
    tmp = path.with_name(path.name + ".tmp")
    ledger.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _trim_ledger(ledger: pd.DataFrame, retention_days: int = LEDGER_RETENTION_DAYS) -> pd.DataFrame:
    if ledger.empty:
        return ledger
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    first_seen = ledger["first_seen_utc"].astype(str).str.slice(0, 10)
    return ledger[first_seen >= cutoff].reset_index(drop=True)


def detection_row_key(row: Dict[str, Any]) -> str:
    """
    Stable observation key from FIRMS' own attributes — the same tuple the
    cleaning stage dedups on: (latitude, longitude, acq_date, acq_time,
    satellite, instrument). Latitude/longitude quantized to 4 decimals
    (~11 m) so float round-trips through CSV never split one observation.
    """
    try:
        lat = round(float(row["latitude"]), 4)
        lon = round(float(row["longitude"]), 4)
    except (KeyError, TypeError, ValueError):
        return ""  # signal: reject (handled by caller)
    acq_time = str(row.get("acq_time", "")).strip().zfill(4)
    satellite = str(row.get("satellite", "")).strip().upper()
    instrument = str(row.get("instrument", "")).strip().upper()
    return f"{lat:.4f}|{lon:.4f}|{row.get('acq_date', '')}|{acq_time}|{satellite}|{instrument}"


def _parse_firms_csv(csv_text: str) -> List[Dict[str, Any]]:
    """Parse FIRMS CSV text into normalized row dicts. Raises ValueError on
    malformed content (caller records the failure; nothing is written)."""
    text = (csv_text or "").strip()
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    missing = [c for c in ("latitude", "longitude", "acq_date", "acq_time", "satellite") if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"FIRMS CSV missing required columns: {missing}")
    rows: List[Dict[str, Any]] = []
    for raw in reader:
        try:
            lat = float(raw["latitude"])
            lon = float(raw["longitude"])
        except (TypeError, ValueError):
            continue  # reject malformed coordinate row
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        sat = SATELLITE_CODE_MAP.get(str(raw.get("satellite", "")).strip().upper(), str(raw.get("satellite", "")).strip())
        rows.append(
            {
                "latitude": lat,
                "longitude": lon,
                "bright_ti4": raw.get("bright_ti4", ""),
                "scan": raw.get("scan", ""),
                "track": raw.get("track", ""),
                "acq_date": str(raw.get("acq_date", "")).strip(),
                "acq_time": str(raw.get("acq_time", "")).strip().zfill(4),
                "satellite": sat,
                "instrument": str(raw.get("instrument", "VIIRS")).strip(),
                "confidence": str(raw.get("confidence", "")).strip().lower(),
                "version": raw.get("version", ""),
                "bright_ti5": raw.get("bright_ti5", ""),
                "frp": raw.get("frp", ""),
                "daynight": raw.get("daynight", ""),
            }
        )
    return rows


def _append_rows_to_live_files(cfg: Config, product_key: str, source: str, rows: List[Dict[str, Any]]) -> int:
    """Group rows by acq_date and atomically append each group to its per-day
    live raw file (creating it with header when new). Returns rows appended."""
    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_day.setdefault(r["acq_date"], []).append(r)

    appended = 0
    for day_str, day_rows in sorted(by_day.items()):
        target = cfg.raw_data_dir / _raw_filename_for_live(product_key, source, date.fromisoformat(day_str))
        target.parent.mkdir(parents=True, exist_ok=True)
        file_exists = target.exists()
        tmp = target.with_name(target.name + ".tmp")

        if file_exists:
            existing = target.read_text(encoding="utf-8", errors="replace")
            header = existing.splitlines()[0] if existing else ""
            # Prepare new content = existing + appended rows (atomic replace).
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
            if not header:
                writer.writeheader()
            for r in day_rows:
                writer.writerow({c: r.get(c, "") for c in EXPECTED_COLUMNS})
            merged = (existing if existing.endswith("\n") else existing + "\n") + buf.getvalue()
            tmp.write_text(merged, encoding="utf-8")
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
            writer.writeheader()
            for r in day_rows:
                writer.writerow({c: r.get(c, "") for c in EXPECTED_COLUMNS})
            tmp.write_text(buf.getvalue(), encoding="utf-8")

        os.replace(tmp, target)
        appended += len(day_rows)
        logger.info("Appended %d observation(s) to %s", len(day_rows), target.name)
    return appended


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------

def run_ingestion_cycle(
    trigger: str = "manual",
    config: Optional[Config] = None,
    client: Optional[FirmsClient] = None,
    run_pipeline: bool = True,
    fetch_window_days: int = 2,
) -> IngestionAttempt:
    """
    One live-ingestion cycle: fetch -> dedup -> append -> state -> pipeline.

    Returns the IngestionAttempt; the state JSON mirrors it for the API.
    Never raises for expected operational failures (they are recorded in the
    returned attempt and the state file).
    """
    cfg = config or get_config()
    cli = client or FirmsClient(config=cfg)
    attempt = IngestionAttempt(run_utc=utc_now_iso(), trigger=trigger, started_utc=utc_now_iso())
    started = time.time()

    products = cfg.firms_default_product_keys
    ledger = _load_ledger(cfg)
    seen_keys = set(ledger["detection_key"].astype(str)) if not ledger.empty else set()
    new_keys: List[str] = []

    any_success = False
    fatal_error: Optional[str] = None

    for product_key in products:
        try:
            product = cfg.firms_products[product_key]
        except KeyError:
            fatal_error = f"Unknown product_key in default_products: {product_key}"
            attempt.products.append(ProductIngestStats(product_key=product_key, source="?", status="failed", error=fatal_error))
            continue

        start_day = date.today() - timedelta(days=fetch_window_days - 1)
        result: FirmsRequestResult = cli.fetch(product_key, start_day, fetch_window_days)
        stats = ProductIngestStats(product_key=product_key, source=product.source, status="ok")

        if not result.success:
            stats.status = "failed"
            stats.error = result.error
            attempt.products.append(stats)
            logger.warning("FIRMS fetch failed for %s: %s", product_key, result.error)
            continue

        any_success = True
        try:
            rows = _parse_firms_csv(result.csv_text or "")
        except ValueError as exc:
            stats.status = "failed"
            stats.error = f"Malformed FIRMS CSV: {exc}"
            attempt.products.append(stats)
            logger.warning("Malformed CSV for %s: %s", product_key, exc)
            continue

        stats.fetched = len(rows)
        fresh_rows: List[Dict[str, Any]] = []
        for r in rows:
            key = detection_row_key(r)
            if not key:
                stats.rejected += 1
                continue
            if key in seen_keys:
                stats.duplicates += 1
                continue
            fresh_rows.append(r)
            new_keys.append(key)
            seen_keys.add(key)  # guard against dup keys inside one payload

        stats.new = len(fresh_rows)
        if fresh_rows:
            try:
                _append_rows_to_live_files(cfg, product_key, product.source, fresh_rows)
            except OSError as exc:
                stats.status = "failed"
                stats.error = f"Raw append failed: {exc}"
                # Roll back the keys we were about to admit so a retry re-fetches them.
                new_keys = [k for k in new_keys if k not in {detection_row_key(x) for x in fresh_rows}]
                attempt.products.append(stats)
                continue
        attempt.products.append(stats)
        logger.info(
            "Product %s: fetched=%d new=%d duplicates=%d rejected=%d",
            product_key, stats.fetched, stats.new, stats.duplicates, stats.rejected,
        )

    attempt.fetched = sum(p.fetched for p in attempt.products)
    attempt.new = sum(p.new for p in attempt.products)
    attempt.duplicates = sum(p.duplicates for p in attempt.products)
    attempt.rejected = sum(p.rejected for p in attempt.products)

    # ---- cycle status ------------------------------------------------------
    failed = [p for p in attempt.products if p.status == "failed"]
    if not any_success and failed:
        attempt.status = "failed"
        attempt.error = "; ".join(f"{p.product_key}: {p.error}" for p in failed)
    elif failed:
        attempt.status = "degraded"
        attempt.error = "; ".join(f"{p.product_key}: {p.error}" for p in failed)
    else:
        attempt.status = "healthy"

    # Persist the ledger only if no raw-append failed (keys roll back otherwise).
    append_failed = any(p.status == "failed" and p.fetched > 0 for p in attempt.products)
    if not append_failed and new_keys:
        first_seen = utc_now_iso()
        new_rows = pd.DataFrame({"detection_key": new_keys, "first_seen_utc": [first_seen] * len(new_keys)})
        ledger = pd.concat([ledger, new_rows], ignore_index=True) if not ledger.empty else new_rows
        _save_ledger(cfg, _trim_ledger(ledger))

    # ---- pipeline ----------------------------------------------------------
    if run_pipeline and any_success:
        from src.ingestion.live_pipeline import run_live_pipeline
        try:
            pipeline_ok = run_live_pipeline()
            attempt.pipeline_triggered = True
            attempt.pipeline_status = "success" if pipeline_ok else "partial"
        except Exception as exc:  # noqa: BLE001 — a pipeline failure must not lose ingest state
            attempt.pipeline_triggered = True
            attempt.pipeline_status = "failed"
            attempt.error = "; ".join(x for x in [attempt.error, f"pipeline: {exc}"] if x)
            logger.exception("Live pipeline failed after ingestion")

    attempt.finished_utc = utc_now_iso()
    attempt.duration_seconds = round(time.time() - started, 2)

    # ---- state -------------------------------------------------------------
    write_ingestion_state(cfg, attempt)
    _append_run_log(cfg, attempt)
    return attempt


# ---------------------------------------------------------------------------
# State persistence (API-visible; contains no secrets, URLs, or keys)
# ---------------------------------------------------------------------------

def _state_path(cfg: Config) -> Path:
    return cfg.processed_data_dir / STATE_FILENAME


def write_ingestion_state(cfg: Config, attempt: IngestionAttempt) -> Dict[str, Any]:
    """Atomically record the latest attempt. last_successful_ingestion only
    advances on a cycle that ingested data without a failed product."""
    previous = load_ingestion_state(cfg)
    last_success = previous.get("last_successful_ingestion") if previous else None
    if attempt.status in ("healthy", "degraded"):
        last_success = attempt.finished_utc or attempt.run_utc

    payload = {
        "schema_version": 1,
        "status": attempt.status,
        "last_attempt": attempt.run_utc,
        "last_finished": attempt.finished_utc,
        "last_successful_ingestion": last_success,
        "observations_fetched": attempt.fetched,
        "new_observations": attempt.new,
        "duplicates": attempt.duplicates,
        "rejected": attempt.rejected,
        "pipeline_triggered": attempt.pipeline_triggered,
        "pipeline_status": attempt.pipeline_status,
        "error": attempt.error,
        "trigger": attempt.trigger,
        "duration_seconds": attempt.duration_seconds,
        "products": [asdict(p) for p in attempt.products],
    }
    path = _state_path(cfg)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return payload


def load_ingestion_state(cfg: Optional[Config] = None) -> Dict[str, Any]:
    """Read the state JSON ({} when absent/corrupt). Safe to call from the API."""
    cfg = cfg or get_config()
    path = _state_path(cfg)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _append_run_log(cfg: Config, attempt: IngestionAttempt) -> None:
    path = cfg.reports_dir / "logs" / LOG_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "run_utc": attempt.run_utc,
        "status": attempt.status,
        "trigger": attempt.trigger,
        "fetched": attempt.fetched,
        "new": attempt.new,
        "duplicates": attempt.duplicates,
        "rejected": attempt.rejected,
        "pipeline_status": attempt.pipeline_status,
        "error": attempt.error,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
