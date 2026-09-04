"""Emergency Response Agent for prototype decision-support notifications.

This module reuses the real fire-station dataset and existing alert evidence.
It never declares a confirmed emergency and never dispatches government services.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd
import requests

from src.logging_setup import get_logger
from src.response.fire_station_locator import FireStationLocator

logger = get_logger("response.emergency_response_agent")

HISTORY_COLUMNS = [
    "alert_id", "cluster_id", "timestamp", "recipient_masked", "severity",
    "selected_station", "distance_km", "send_status", "provider_message_id",
    "failure_reason",
]


class SmsProvider(Protocol):
    def send(self, to_number: str, body: str, variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        ...


# Predefined SMS templates Twilio permits on TRIAL accounts (see Twilio docs:
# "Try out Twilio SMS Messaging"). During trial the Messages API `Body` must be
# exactly one of these template ids - free-form text is rejected with error
# 572006. The Content API (ContentSid) is NOT available on trial accounts.
PREDEFINED_TEMPLATE_IDS = frozenset({
    "sms_2fa",
    "sms_appointment_reminders",
    "sms_order_confirmation",
    "sms_delivery_updates",
    "sms_customer_support",
    "sms_marketing_promotions",
    "sms_event_notifications",
    "sms_account_alerts",
    "sms_feedback_surveys",
    "sms_internal_alerts",
})

# Console-friendly labels shown by the trial "Try Out SMS" screen, mapped to
# the template ids the API actually accepts.
_PREDEFINED_TEMPLATE_ALIASES = {
    "event notifications": "sms_event_notifications",
    "2fa": "sms_2fa",
    "appointment reminders": "sms_appointment_reminders",
    "order confirmation": "sms_order_confirmation",
    "delivery updates": "sms_delivery_updates",
    "customer support": "sms_customer_support",
    "marketing promotions": "sms_marketing_promotions",
    "account alerts": "sms_account_alerts",
    "feedback surveys": "sms_feedback_surveys",
    "internal alerts": "sms_internal_alerts",
}


def _normalize_predefined_template(value: str) -> str:
    """Normalize a TWILIO_TEMPLATE_NAME value to a valid predefined template id.

    Accepts either the raw id (sms_event_notifications) or the Console-friendly
    label ("Event Notifications"). Raises RuntimeError for anything else so a
    typo fails loudly instead of producing another opaque 572006.
    """
    normalized = value.strip().lower()
    normalized = _PREDEFINED_TEMPLATE_ALIASES.get(normalized, normalized)
    if normalized not in PREDEFINED_TEMPLATE_IDS:
        valid = ", ".join(sorted(PREDEFINED_TEMPLATE_IDS))
        raise RuntimeError(
            "Invalid SMS provider configuration: TWILIO_TEMPLATE_NAME must be one of the "
            f"Twilio trial predefined templates: {valid}."
        )
    return normalized


@dataclass
class TwilioSmsProvider:
    account_sid: str
    auth_token: str
    from_number: str
    content_sid: Optional[str] = None
    content_variables: Optional[Dict[str, str]] = None
    # Twilio trial predefined template id (e.g. "sms_event_notifications", the
    # "Event Notifications" example in the Console's Try Out SMS screen). When
    # set, the Messages API request sends Body=<template id> exactly as the
    # trial flow requires; free-form text is not allowed on trial accounts.
    # Only meaningful for trial accounts - leave unset on upgraded accounts.
    template_name: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TwilioSmsProvider":
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        from_number = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
        missing = [name for name, val in [
            ("TWILIO_ACCOUNT_SID", sid),
            ("TWILIO_AUTH_TOKEN", token),
            ("TWILIO_FROM_NUMBER", from_number),
        ] if not val]
        if missing:
            raise RuntimeError(f"Missing SMS credentials: {', '.join(missing)}")
        content_sid = os.environ.get("TWILIO_CONTENT_SID", "").strip() or None
        raw_template = os.environ.get("TWILIO_TEMPLATE_NAME", "").strip()
        if raw_template and content_sid:
            raise RuntimeError(
                "Invalid SMS provider configuration: set only one of TWILIO_TEMPLATE_NAME "
                "(trial predefined template) or TWILIO_CONTENT_SID (registered content template)."
            )
        return cls(
            account_sid=sid,
            auth_token=token,
            from_number=from_number,
            content_sid=content_sid,
            content_variables=_parse_content_variables(os.environ.get("TWILIO_CONTENT_VARIABLES", "")),
            template_name=_normalize_predefined_template(raw_template) if raw_template else None,
        )

    def send(self, to_number: str, body: str, variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data: Dict[str, str] = {"To": to_number, "From": self.from_number}
        if self.content_sid:
            # Registered Content API template (upgraded accounts only; the
            # Content API is unavailable on trial accounts). Body MUST be
            # omitted when ContentSid is set (Twilio error 35127).
            data["ContentSid"] = self.content_sid
            resolved = dict(self.content_variables or {})
            if variables:
                resolved.update(variables)
            if resolved:
                data["ContentVariables"] = json.dumps(resolved, separators=(",", ":"))
        elif self.template_name:
            # Trial predefined-template mode: Body must be exactly one of the
            # predefined template ids (Twilio error 572006 otherwise). Content
            # variables cannot accompany Body (Twilio error 35127), so the
            # recipient receives Twilio's predefined text for the template.
            data["Body"] = _normalize_predefined_template(self.template_name)
        else:
            data["Body"] = body
        response = requests.post(
            url,
            data=data,
            auth=(self.account_sid, self.auth_token),
            timeout=15,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"SMS provider failure: HTTP {response.status_code}"
                + _twilio_error_detail(response)
            )
        payload = response.json()
        return {"provider": "twilio", "message_id": payload.get("sid"), "status": payload.get("status", "sent")}


def _parse_content_variables(raw: str) -> Optional[Dict[str, str]]:
    """Parse the optional TWILIO_CONTENT_VARIABLES JSON string.

    Returns None when unset/empty and raises RuntimeError on malformed JSON so
    misconfiguration fails loudly instead of silently sending a broken template.
    """
    value = (raw or "").strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except ValueError as exc:
        raise RuntimeError(
            "Invalid SMS provider configuration: TWILIO_CONTENT_VARIABLES must be a JSON object "
            f"(e.g. {{\"1\": \"CRITICAL\"}})."
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid SMS provider configuration: TWILIO_CONTENT_VARIABLES must be a JSON object.")
    return {str(k): str(v) for k, v in parsed.items()}


def _twilio_error_detail(response: Any) -> str:
    """Return Twilio's non-secret error code/message from a failed response.

    Phone-like substrings are masked so no recipient/sender numbers are ever
    persisted or surfaced. Returns "" when the body has no parseable error.
    """
    try:
        payload = response.json()
    except Exception:
        return ""
    code = payload.get("code") if isinstance(payload, dict) else None
    message = payload.get("message") if isinstance(payload, dict) else None
    parts = []
    if code is not None:
        parts.append(f"twilio_code={code}")
    if message:
        parts.append(f"message={_mask_phones(str(message))}")
    return " " + "; ".join(parts) if parts else ""


def _mask_phones(text: str) -> str:
    """Mask E.164-looking phone numbers in arbitrary provider text."""
    import re

    return re.sub(r"\+?\d[\d\s().-]{6,}\d", lambda m: mask_phone(m.group(0)), text)


def _sanitize_failure(exc: Exception, provider: Any) -> str:
    """Build a safe, loggable failure string from a provider exception.

    Phone-like substrings are masked and any configured Twilio secrets
    (Account SID / Auth Token, which can appear in request exception text)
    are redacted so they can never be persisted or surfaced.
    """
    text = _mask_phones(str(exc)) if str(exc) else exc.__class__.__name__
    for secret in (getattr(provider, "account_sid", ""), getattr(provider, "auth_token", "")):
        if secret and len(secret) >= 6:
            text = text.replace(secret, "[REDACTED]")
    return text


def mask_phone(value: str) -> str:
    clean = "".join(ch for ch in str(value) if ch.isdigit() or ch == "+")
    if len(clean) <= 4:
        return "****"
    return f"{'*' * max(len(clean) - 4, 0)}{clean[-4:]}"


def _clean_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    text = str(value).strip()
    return text if text else default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        out = float(value)
        return int(out) if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


class EmergencyResponseAgent:
    """Prepare ranked station search and prototype SMS notifications."""

    def __init__(
        self,
        locator: Optional[FireStationLocator] = None,
        provider: Optional[SmsProvider] = None,
        history_path: Optional[Path] = None,
        recipient: Optional[str] = None,
    ):
        self.locator = locator or FireStationLocator(search_radius_km=50.0)
        self.provider = provider
        self.recipient = recipient
        self.history_path = history_path or (Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "prototype_notification_history.csv")

    def search(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
        cluster_id = _to_int(event.get("cluster_id"))
        lat = _to_float(event.get("latitude"), default=float("nan"))
        lon = _to_float(event.get("longitude"), default=float("nan"))
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise ValueError("Cluster coordinates are unavailable or invalid.")

        stations = self.locator.find_nearby_stations(lat, lon, limit=limit)
        nearest = stations[0] if stations else None
        eligible, reason = self.evaluate_eligibility(event, alert, station_available=nearest is not None)
        return {
            "cluster_id": cluster_id,
            "search_radius_km": self.locator.search_radius_km,
            "event": self._event_payload(event, alert),
            "stations": stations,
            "nearest_station": nearest,
            "station_available": nearest is not None,
            "status_message": "STATIONS FOUND" if nearest else "NO VERIFIED FIRE STATION FOUND WITHIN 50 KM",
            "notification_eligible": eligible,
            "eligibility_reason": reason,
            "is_decision_support_only": True,
        }

    def evaluate_eligibility(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]], station_available: bool = True) -> tuple[bool, str]:
        severity = self._severity(event, alert)
        evidence = _clean_str((alert or {}).get("evidence_confidence"), _clean_str(event.get("detection_reliability"), "INSUFFICIENT")).upper()
        false_alarm = _clean_str((alert or {}).get("false_alarm_indicator"), _clean_str(event.get("false_alarm_indicator"), "UNKNOWN")).upper()
        suppressed = bool((alert or {}).get("suppressed", False))
        status = _clean_str((alert or {}).get("status"), "ACTIVE").upper()

        if severity not in {"CRITICAL", "HIGH"}:
            return False, "Unsupported alert severity for prototype notification."
        if suppressed:
            return False, "Suppressed alerts cannot send prototype notifications."
        if status == "RESOLVED":
            return False, "Resolved alerts cannot send prototype notifications."
        if false_alarm == "HIGH":
            return False, "High false-alarm-concern events require verification before notification."
        if false_alarm != "LOW":
            return False, "Prototype notification requires LOW false-alarm concern."
        if evidence != "HIGH":
            return False, "Prototype notification requires HIGH evidence confidence."
        if not station_available:
            return False, "No verified fire station found within 50 km."
        return True, "Eligible for operator-confirmed prototype decision-support notification."

    def send_notification(
        self,
        event: Dict[str, Any],
        alert: Optional[Dict[str, Any]] = None,
        station_id: Optional[str] = None,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        if not confirmed:
            raise PermissionError("Explicit operator confirmation is required before sending.")

        search = self.search(event, alert)
        if not search["station_available"]:
            self._record(event, alert, None, "FAILED", "", "No verified station within 50 km")
            raise LookupError("No verified fire station found within 50 km.")

        selected = search["nearest_station"]
        if station_id:
            matches = [s for s in search["stations"] if s["station_id"] == station_id]
            if not matches:
                raise LookupError("Selected verified fire station was not found within 50 km.")
            selected = matches[0]

        eligible, reason = self.evaluate_eligibility(event, alert, station_available=True)
        if not eligible:
            self._record(event, alert, selected, "REJECTED", "", reason)
            raise PermissionError(reason)

        recipient = (self.recipient or os.environ.get("PROTOTYPE_SMS_TO", "")).strip()
        if not recipient:
            self._record(event, alert, selected, "FAILED", "", "Missing PROTOTYPE_SMS_TO")
            raise RuntimeError("Missing prototype recipient configuration: PROTOTYPE_SMS_TO")

        provider = self.provider or TwilioSmsProvider.from_env()
        message = self.build_message(event, alert, selected)
        variables = self.build_content_variables(event, alert, selected)
        try:
            result = provider.send(recipient, message, variables=variables)
        except Exception as exc:
            failure = _sanitize_failure(exc, provider)
            if failure.startswith("SMS provider failure: "):
                failure = failure[len("SMS provider failure: "):]
            self._record(event, alert, selected, "FAILED", "", failure)
            raise RuntimeError(f"SMS provider failure: {failure}") from exc

        provider_message_id = str(result.get("message_id") or "")
        self._record(event, alert, selected, "SENT", provider_message_id, "")
        return {
            "cluster_id": _to_int(event.get("cluster_id")),
            "alert_id": _clean_str((alert or {}).get("alert_id"), f"TAL-{_to_int(event.get('cluster_id')):05d}"),
            "send_status": "SENT",
            "recipient_masked": mask_phone(recipient),
            "selected_station": selected,
            "provider_message_id": provider_message_id or None,
            "is_decision_support_only": True,
            "detail": "Prototype / Decision-Support Notification sent. No government emergency service has been dispatched by ThermalWatch.",
        }

    def build_message(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]], station: Dict[str, Any]) -> str:
        severity = self._severity(event, alert)
        cid = _to_int(event.get("cluster_id"))
        risk_score = _to_float((alert or {}).get("risk_score", event.get("risk_score")))
        lat = _to_float(event.get("latitude"))
        lon = _to_float(event.get("longitude"))
        classification = _clean_str((alert or {}).get("classification_label"), _clean_str(event.get("classification_label"), "Unknown"))
        evidence = _clean_str((alert or {}).get("evidence_confidence"), _clean_str(event.get("detection_reliability"), "UNKNOWN"))
        detections = _to_int((alert or {}).get("observation_count", event.get("observation_count")), 1)
        active_days = _to_int((alert or {}).get("active_days", event.get("active_days")), 1)
        station_name = station.get("station_name", "Verified fire station")
        station_dist = _to_float(station.get("distance_km"))
        return (
            "ThermalWatch prototype decision-support alert. "
            f"Severity {severity}; cluster {cid}; risk {risk_score:.0f}/100; "
            f"coordinates {lat:.5f},{lon:.5f}; classification {classification}; "
            f"evidence {evidence}; detections {detections}, active days {active_days}. "
            f"Nearest verified fire station: {station_name} ({station_dist:.1f} km). "
            "Advisory thermal anomaly information only; not a confirmed fire or official dispatch."
        )

    def build_content_variables(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]], station: Dict[str, Any]) -> Dict[str, str]:
        """Ordered placeholders for a Twilio content template (ContentSid mode).

        Values are sequential (1..10) as required by the Twilio Content API so an
        operator can design a registered/predefined template that references them
        by number, e.g. \"ThermalWatch {{1}} alert cluster {{2}}, risk {{3}}/100;\n        nearest station {{9}} ({{10}} km). {{4}}; {{5}}; evidence {{6}};\n        detections {{7}}, active days {{8}}. Advisory only; not official dispatch.\"
        """
        cid = _to_int(event.get("cluster_id"))
        risk_score = _to_float((alert or {}).get("risk_score", event.get("risk_score")))
        lat = _to_float(event.get("latitude"))
        lon = _to_float(event.get("longitude"))
        classification = _clean_str((alert or {}).get("classification_label"), _clean_str(event.get("classification_label"), "Unknown"))
        evidence = _clean_str((alert or {}).get("evidence_confidence"), _clean_str(event.get("detection_reliability"), "UNKNOWN"))
        detections = _to_int((alert or {}).get("observation_count", event.get("observation_count")), 1)
        active_days = _to_int((alert or {}).get("active_days", event.get("active_days")), 1)
        return {
            "1": self._severity(event, alert),
            "2": str(cid),
            "3": f"{risk_score:.0f}",
            "4": f"{lat:.5f},{lon:.5f}",
            "5": classification,
            "6": evidence,
            "7": str(detections),
            "8": str(active_days),
            "9": station.get("station_name", "Verified fire station"),
            "10": f"{_to_float(station.get('distance_km')):.1f}",
        }

    def history(self, cluster_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        df = pd.read_csv(self.history_path)
        if cluster_id is not None and "cluster_id" in df.columns:
            df = df[df["cluster_id"].astype(int) == int(cluster_id)]
        records = df.fillna("").to_dict(orient="records")
        # Normalize CSV empties back to None for numeric fields so the API
        # schema can validate rows (e.g. FAILED attempts with no station).
        for record in records:
            if "distance_km" in record and record["distance_km"] == "":
                record["distance_km"] = None
        return records

    def _record(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]], station: Optional[Dict[str, Any]], status: str, provider_message_id: str, failure: str) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        recipient = (self.recipient or os.environ.get("PROTOTYPE_SMS_TO", "")).strip()
        row = {
            "alert_id": _clean_str((alert or {}).get("alert_id"), f"TAL-{_to_int(event.get('cluster_id')):05d}"),
            "cluster_id": _to_int(event.get("cluster_id")),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "recipient_masked": mask_phone(recipient) if recipient else "",
            "severity": self._severity(event, alert),
            "selected_station": (station or {}).get("station_name", ""),
            "distance_km": (station or {}).get("distance_km"),
            "send_status": status,
            "provider_message_id": provider_message_id,
            "failure_reason": failure,
        }
        old = pd.read_csv(self.history_path) if self.history_path.exists() else pd.DataFrame(columns=HISTORY_COLUMNS)
        pd.concat([old, pd.DataFrame([row])], ignore_index=True)[HISTORY_COLUMNS].to_csv(self.history_path, index=False)

    def _event_payload(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "cluster_id": _to_int(event.get("cluster_id")),
            "alert_id": _clean_str((alert or {}).get("alert_id"), f"TAL-{_to_int(event.get('cluster_id')):05d}"),
            "severity": self._severity(event, alert),
            "risk_score": _to_float((alert or {}).get("risk_score", event.get("risk_score"))),
            "risk_level": _clean_str(event.get("risk_level"), "LOW"),
            "classification_label": _clean_str((alert or {}).get("classification_label"), _clean_str(event.get("classification_label"), "Unknown")),
            "evidence_confidence": _clean_str((alert or {}).get("evidence_confidence"), _clean_str(event.get("detection_reliability"), "UNKNOWN")),
            "false_alarm_indicator": _clean_str((alert or {}).get("false_alarm_indicator"), _clean_str(event.get("false_alarm_indicator"), "UNKNOWN")),
            "detection_reliability": _clean_str(event.get("detection_reliability"), "UNKNOWN"),
            "observation_count": _to_int((alert or {}).get("observation_count", event.get("observation_count")), 1),
            "active_days": _to_int((alert or {}).get("active_days", event.get("active_days")), 1),
            "persistence_category": _clean_str((alert or {}).get("persistence_category"), _clean_str(event.get("persistence_category"), "unknown")),
            "latitude": round(_to_float(event.get("latitude")), 5),
            "longitude": round(_to_float(event.get("longitude")), 5),
            "suppressed": bool((alert or {}).get("suppressed", False)),
        }

    def _severity(self, event: Dict[str, Any], alert: Optional[Dict[str, Any]]) -> str:
        alert_severity = _clean_str((alert or {}).get("severity"), "").upper()
        if alert_severity:
            return alert_severity
        risk_level = _clean_str(event.get("risk_level"), "LOW").upper()
        return "HIGH" if risk_level == "HIGH" else risk_level
