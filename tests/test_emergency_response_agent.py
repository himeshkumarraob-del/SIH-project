from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.response.emergency_response_agent import EmergencyResponseAgent
from src.response.fire_station_locator import FireStationLocator


class MockProvider:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent = []

    def send(self, to_number: str, body: str, variables=None):
        if self.fail:
            raise RuntimeError("provider down")
        self.sent.append((to_number, body, variables))
        return {"message_id": "SM123", "status": "queued"}


def _stations(path: Path) -> Path:
    pd.DataFrame([
        {"osm_type": "node", "osm_id": 1, "name": "Far Station", "latitude": 28.8, "longitude": 77.4},
        {"osm_type": "node", "osm_id": 2, "name": "Near Station", "latitude": 28.611, "longitude": 77.201},
        {"osm_type": "node", "osm_id": 3, "name": "Outside Station", "latitude": 30.0, "longitude": 79.0},
    ]).to_csv(path, index=False)
    return path


def _event(**overrides):
    base = {
        "cluster_id": 42,
        "latitude": 28.61,
        "longitude": 77.20,
        "risk_score": 91.0,
        "risk_level": "HIGH",
        "classification_label": "Industrial-context thermal event",
        "false_alarm_indicator": "LOW",
        "detection_reliability": "HIGH",
        "observation_count": 5,
        "active_days": 3,
        "persistence_category": "persistent",
    }
    base.update(overrides)
    return base


def _alert(**overrides):
    base = {
        "alert_id": "TAL-00042",
        "cluster_id": 42,
        "severity": "CRITICAL",
        "status": "ACTIVE",
        "evidence_confidence": "HIGH",
        "suppressed": False,
        "risk_score": 91.0,
        "false_alarm_indicator": "LOW",
        "classification_label": "Industrial-context thermal event",
        "observation_count": 5,
        "active_days": 3,
    }
    base.update(overrides)
    return base


def _agent(tmp_path: Path, provider=None, recipient="+15551234567"):
    locator = FireStationLocator(stations_path=_stations(tmp_path / "stations.csv"), search_radius_km=50.0)
    return EmergencyResponseAgent(locator=locator, provider=provider, history_path=tmp_path / "history.csv", recipient=recipient)


def test_station_ranking_and_nearest_selection(tmp_path):
    result = _agent(tmp_path).search(_event(), _alert())
    assert result["station_available"] is True
    assert result["stations"][0]["station_name"] == "Near Station"
    assert result["nearest_station"]["station_name"] == "Near Station"
    assert result["stations"][0]["distance_km"] <= result["stations"][1]["distance_km"]


def test_no_station_case(tmp_path):
    locator = FireStationLocator(stations_path=_stations(tmp_path / "stations.csv"), search_radius_km=50.0)
    agent = EmergencyResponseAgent(locator=locator, history_path=tmp_path / "history.csv", recipient="+15551234567")
    result = agent.search(_event(latitude=10.0, longitude=60.0), _alert())
    assert result["station_available"] is False
    assert result["status_message"] == "NO VERIFIED FIRE STATION FOUND WITHIN 50 KM"
    assert result["stations"] == []


def test_missing_recipient_configuration(tmp_path, monkeypatch):
    # Hermetic: ensure no ambient PROTOTYPE_SMS_TO leaks in from a loaded .env.
    monkeypatch.delenv("PROTOTYPE_SMS_TO", raising=False)
    agent = _agent(tmp_path, provider=MockProvider(), recipient="")
    with pytest.raises(RuntimeError, match="PROTOTYPE_SMS_TO"):
        agent.send_notification(_event(), _alert(), confirmed=True)


def test_eligibility_rules_reject_low_evidence(tmp_path):
    ok, reason = _agent(tmp_path).evaluate_eligibility(_event(), _alert(evidence_confidence="LOW"))
    assert ok is False
    assert "HIGH evidence" in reason


def test_suppressed_alert_rejection(tmp_path):
    ok, reason = _agent(tmp_path).evaluate_eligibility(_event(), _alert(suppressed=True))
    assert ok is False
    assert "Suppressed" in reason


def test_high_false_alarm_rejection(tmp_path):
    ok, reason = _agent(tmp_path).evaluate_eligibility(_event(false_alarm_indicator="HIGH"), _alert(false_alarm_indicator="HIGH"))
    assert ok is False
    assert "High false-alarm" in reason


def test_successful_sms_provider_call_is_mocked(tmp_path):
    provider = MockProvider()
    result = _agent(tmp_path, provider=provider).send_notification(_event(), _alert(), confirmed=True)
    assert result["send_status"] == "SENT"
    assert result["recipient_masked"].endswith("4567")
    assert provider.sent
    assert "not a confirmed fire" in provider.sent[0][1]
    assert provider.sent[0][2]["1"] == "CRITICAL"  # content variables passed through


def test_provider_failure(tmp_path):
    with pytest.raises(RuntimeError, match="SMS provider failure"):
        _agent(tmp_path, provider=MockProvider(fail=True)).send_notification(_event(), _alert(), confirmed=True)


def test_agent_reraises_sanitized_twilio_detail(monkeypatch, tmp_path):
    """The agent must preserve the safe Twilio code/message when re-raising so
    the API can surface the exact rejection instead of a generic 502 text."""
    from src.response.emergency_response_agent import TwilioSmsProvider

    class FakeResponse:
        status_code = 400

        @staticmethod
        def json():
            return {
                "code": 572006,
                "message": "Invalid template name. Trial accounts can only use predefined SMS templates.",
            }

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", lambda *a, **k: FakeResponse())
    provider = TwilioSmsProvider(account_sid="ACSECRET", auth_token="AUTHSECRET", from_number="+17372212163")
    agent = _agent(tmp_path, provider=provider)
    with pytest.raises(RuntimeError) as exc_info:
        agent.send_notification(_event(), _alert(), confirmed=True)
    msg = str(exc_info.value)
    assert "HTTP 400" in msg
    assert "twilio_code=572006" in msg
    assert "Trial accounts" in msg
    # No double prefix and no secrets/phones.
    assert msg.count("SMS provider failure") == 1
    assert "ACSECRET" not in msg
    assert "AUTHSECRET" not in msg
    assert "+17372212163" not in msg
    assert "+15551234567" not in msg

    rows = agent.history(cluster_id=42)
    assert rows[0]["send_status"] == "FAILED"
    assert "twilio_code=572006" in rows[0]["failure_reason"]
    assert "+17372212163" not in rows[0]["failure_reason"]


def test_build_content_variables_are_sequential(tmp_path):
    agent = _agent(tmp_path)
    variables = agent.build_content_variables(_event(), _alert(), {"station_name": "Near Station", "distance_km": 12.5})
    assert list(variables.keys()) == [str(i) for i in range(1, 11)]
    assert variables["1"] == "CRITICAL"
    assert variables["2"] == "42"
    assert variables["3"] == "91"
    assert variables["4"] == "28.61000,77.20000"
    assert variables["5"] == "Industrial-context thermal event"
    assert variables["6"] == "HIGH"
    assert variables["7"] == "5"
    assert variables["8"] == "3"
    assert variables["9"] == "Near Station"
    assert variables["10"] == "12.5"


def test_twilio_content_template_mode_uses_contentsid_and_no_body(monkeypatch):
    """ContentSid mode must send ContentSid + ContentVariables and omit Body
    (sending both triggers Twilio error 35127)."""
    import json as _json

    from src.response.emergency_response_agent import TwilioSmsProvider

    captured = {}

    def fake_post(url, data, auth, timeout):
        captured["data"] = data
        captured["auth"] = auth

        class OkResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"sid": "SM123", "status": "queued"}

        return OkResponse()

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", fake_post)
    provider = TwilioSmsProvider(
        account_sid="ACSECRET",
        auth_token="AUTHSECRET",
        from_number="+15559990000",
        content_sid="HXTEMPLATE",
        content_variables={"9": "Env Station"},
    )
    result = provider.send(
        "+15550001111",
        "ignored free-form body",
        variables={"1": "CRITICAL", "2": "1105"},
    )
    assert result["message_id"] == "SM123"
    data = captured["data"]
    assert data["ContentSid"] == "HXTEMPLATE"
    assert "Body" not in data
    assert captured["auth"] == ("ACSECRET", "AUTHSECRET")
    variables = _json.loads(data["ContentVariables"])
    assert variables["1"] == "CRITICAL"
    assert variables["2"] == "1105"
    # Env-configured defaults are kept for placeholders the message did not set.
    assert variables["9"] == "Env Station"


def test_twilio_freeform_mode_keeps_body(monkeypatch):
    from src.response.emergency_response_agent import TwilioSmsProvider

    captured = {}

    def fake_post(url, data, auth, timeout):
        captured["data"] = data

        class OkResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"sid": "SM456", "status": "queued"}

        return OkResponse()

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", fake_post)
    provider = TwilioSmsProvider(account_sid="ACSECRET", auth_token="AUTHSECRET", from_number="+15559990000")
    provider.send("+15550001111", "free-form advisory text")
    assert captured["data"]["Body"] == "free-form advisory text"
    assert "ContentSid" not in captured["data"]
    assert "ContentVariables" not in captured["data"]


def test_malformed_content_variables_env_raises(monkeypatch):
    from src.response.emergency_response_agent import TwilioSmsProvider

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACSECRET")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "AUTHSECRET")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")
    monkeypatch.setenv("TWILIO_CONTENT_VARIABLES", "not-json")
    with pytest.raises(RuntimeError, match="TWILIO_CONTENT_VARIABLES"):
        TwilioSmsProvider.from_env()


def _fake_alert_for_cluster(cluster_id):
    """Deterministic CRITICAL alert for API tests; the ambient global alert
    store is shared/mutated by other test files, so we never depend on it."""
    assert cluster_id == 1105
    return {
        "alert_id": "TAL-01105",
        "cluster_id": 1105,
        "severity": "CRITICAL",
        "status": "ACTIVE",
        "evidence_confidence": "HIGH",
        "suppressed": False,
        "risk_score": 100.0,
        "false_alarm_indicator": "LOW",
        "classification_label": "Industrial-context thermal event",
        "observation_count": 21,
        "active_days": 5,
    }


def test_twilio_trial_template_sends_template_id_as_body(monkeypatch):
    """Trial accounts require Body to be exactly one of the predefined template
    ids (Twilio docs "Try out SMS"); no ContentSid/ContentVariables are used."""
    from src.response.emergency_response_agent import TwilioSmsProvider

    captured = {}

    def fake_post(url, data, auth, timeout):
        captured["data"] = data
        captured["auth"] = auth

        class OkResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"sid": "SM123", "status": "queued"}

        return OkResponse()

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", fake_post)
    provider = TwilioSmsProvider(
        account_sid="ACSECRET",
        auth_token="AUTHSECRET",
        from_number="+15559990000",
        template_name="sms_event_notifications",
    )
    result = provider.send(
        "+15550001111",
        "ignored free-form alert text",
        variables={"1": "CRITICAL", "2": "1105"},
    )
    assert result["message_id"] == "SM123"
    assert captured["auth"] == ("ACSECRET", "AUTHSECRET")
    data = captured["data"]
    assert data["Body"] == "sms_event_notifications"
    assert "ContentSid" not in data
    assert "ContentVariables" not in data


def test_twilio_trial_template_accepts_console_label(monkeypatch):
    """The Console label "Event Notifications" maps to sms_event_notifications."""
    from src.response.emergency_response_agent import TwilioSmsProvider

    captured = {}

    def fake_post(url, data, auth, timeout):
        captured["data"] = data

        class OkResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"sid": "SM124", "status": "queued"}

        return OkResponse()

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", fake_post)
    provider = TwilioSmsProvider(
        account_sid="ACSECRET", auth_token="AUTHSECRET", from_number="+15559990000",
        template_name="Event Notifications",
    )
    provider.send("+15550001111", "ignored")
    assert captured["data"]["Body"] == "sms_event_notifications"


def test_twilio_invalid_trial_template_raises_config_error():
    from src.response.emergency_response_agent import TwilioSmsProvider

    provider = TwilioSmsProvider(
        account_sid="ACSECRET", auth_token="AUTHSECRET", from_number="+15559990000",
        template_name="sms_freeform_typo",
    )
    with pytest.raises(RuntimeError, match="TWILIO_TEMPLATE_NAME") as exc_info:
        provider.send("+15550001111", "body")
    assert "sms_event_notifications" in str(exc_info.value)


def test_from_env_template_wiring_and_conflict(monkeypatch):
    from src.response.emergency_response_agent import TwilioSmsProvider

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACSECRET")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "AUTHSECRET")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")
    monkeypatch.setenv("TWILIO_TEMPLATE_NAME", "Event Notifications")
    provider = TwilioSmsProvider.from_env()
    assert provider.template_name == "sms_event_notifications"

    # Trial template mode and Content API mode are mutually exclusive.
    monkeypatch.setenv("TWILIO_CONTENT_SID", "HXabcdef")
    with pytest.raises(RuntimeError, match="only one of TWILIO_TEMPLATE_NAME"):
        TwilioSmsProvider.from_env()

    monkeypatch.delenv("TWILIO_TEMPLATE_NAME")
    monkeypatch.delenv("TWILIO_CONTENT_SID")
    assert TwilioSmsProvider.from_env().template_name is None


def test_api_sends_via_trial_predefined_template(monkeypatch, tmp_path):
    """End-to-end through the real endpoint: with TWILIO_TEMPLATE_NAME set the
    request sends Body=<predefined template id> and records a masked SENT row."""
    from fastapi.testclient import TestClient

    import backend.main as backend_main
    from src.response.emergency_response_agent import EmergencyResponseAgent

    captured = {}

    def fake_post(url, data, auth, timeout):
        captured["data"] = data

        class OkResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"sid": "SM999", "status": "queued"}

        return OkResponse()

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", fake_post)
    monkeypatch.setenv("PROTOTYPE_SMS_TO", "+15550001111")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACSECRET")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "AUTHSECRET")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")
    monkeypatch.setenv("TWILIO_TEMPLATE_NAME", "sms_event_notifications")

    def fake_agent():
        return EmergencyResponseAgent(history_path=tmp_path / "history.csv", recipient="+15550001111")

    monkeypatch.setattr(backend_main, "_emergency_response_agent", fake_agent)
    monkeypatch.setattr(backend_main, "_alert_for_cluster", _fake_alert_for_cluster)
    client = TestClient(backend_main.app)
    response = client.post("/api/v1/emergency-response/1105/prototype-notification", json={"confirmed": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["send_status"] == "SENT"
    assert body["provider_message_id"] == "SM999"
    assert "decision-support" in body["detail"].lower()
    assert captured["data"]["Body"] == "sms_event_notifications"
    assert "ContentSid" not in captured["data"]

    # History records the masked recipient, not the number.
    rows = fake_agent().history(cluster_id=1105)
    assert rows and rows[-1]["send_status"] == "SENT"
    assert rows[-1]["recipient_masked"].endswith("1111")
    assert "+15550001111" not in str(rows[-1])


def test_api_returns_safe_twilio_detail_on_provider_failure(monkeypatch, tmp_path):
    """The POST endpoint must return the sanitized Twilio rejection (572006) in
    the 502 detail instead of the generic 'SMS provider failure.' text, and must
    never leak credentials or phone numbers."""
    from fastapi.testclient import TestClient

    import backend.main as backend_main
    from src.response.emergency_response_agent import EmergencyResponseAgent

    class FakeResponse:
        status_code = 400

        @staticmethod
        def json():
            return {
                "code": 572006,
                "message": "Invalid template name. Trial accounts can only use predefined SMS templates.",
            }

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", lambda *a, **k: FakeResponse())
    monkeypatch.setenv("PROTOTYPE_SMS_TO", "+15550001111")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACSECRET")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "AUTHSECRET")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")

    def fake_agent():
        return EmergencyResponseAgent(history_path=tmp_path / "history.csv", recipient="+15550001111")

    monkeypatch.setattr(backend_main, "_emergency_response_agent", fake_agent)
    monkeypatch.setattr(backend_main, "_alert_for_cluster", _fake_alert_for_cluster)
    client = TestClient(backend_main.app)
    response = client.post("/api/v1/emergency-response/1105/prototype-notification", json={"confirmed": True})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "twilio_code=572006" in detail
    assert "Trial accounts" in detail
    assert "ACSECRET" not in detail and "AUTHSECRET" not in detail
    assert "+15550001111" not in detail and "+15559990000" not in detail

    # History records the same sanitized reason via the same history file.
    agent = fake_agent()
    rows = agent.history(cluster_id=1105)
    assert rows and rows[-1]["send_status"] == "FAILED"
    assert "twilio_code=572006" in rows[-1]["failure_reason"]


def test_twilio_error_detail_records_code_and_masks_phones(monkeypatch, tmp_path):
    """Twilio 4xx responses must surface their non-secret error code/message in
    the history record, with phone-like substrings masked."""
    from src.response.emergency_response_agent import TwilioSmsProvider

    class FakeResponse:
        status_code = 400

        @staticmethod
        def json():
            return {
                "code": 21606,
                "message": "The 'From' number +17372212163 is not a valid, SMS-capable Twilio number",
                "more_info": "https://www.twilio.com/docs/errors/21606",
            }

    monkeypatch.setattr("src.response.emergency_response_agent.requests.post", lambda *a, **k: FakeResponse())

    provider = TwilioSmsProvider(account_sid="ACSECRET", auth_token="AUTHSECRET", from_number="+17372212163")
    with pytest.raises(RuntimeError) as exc_info:
        provider.send("+15550001111", "test body")
    err = str(exc_info.value)
    assert "HTTP 400" in err
    assert "twilio_code=21606" in err
    assert "21606" in err
    # Phone numbers must be masked, never leaked.
    assert "+17372212163" not in err
    assert "+15550001111" not in err

    # The agent records the same sanitized failure reason.
    agent = _agent(tmp_path, provider=provider)
    with pytest.raises(RuntimeError):
        agent.send_notification(_event(), _alert(), confirmed=True)
    rows = agent.history(cluster_id=42)
    assert rows[0]["send_status"] == "FAILED"
    assert "twilio_code=21606" in rows[0]["failure_reason"]
    assert "+17372212163" not in rows[0]["failure_reason"]


def test_unknown_cluster_api_returns_404():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/v1/emergency-response/99999999/stations")
    assert response.status_code == 404


def test_secret_values_never_returned_by_api(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("PROTOTYPE_SMS_TO", "+15550001111")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACSECRET")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "AUTHSECRET")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")
    client = TestClient(app)
    response = client.get("/api/v1/emergency-response/1/stations")
    text = response.text
    assert "AUTHSECRET" not in text
    assert "ACSECRET" not in text
    assert "+15550001111" not in text


def test_history_normalizes_stationless_rows(tmp_path):
    """FAILED attempts (no station) must round-trip with distance_km=None."""
    agent = _agent(tmp_path)
    with pytest.raises(LookupError):
        agent.send_notification(_event(latitude=10.0, longitude=60.0), _alert(), confirmed=True)

    rows = agent.history(cluster_id=42)
    assert len(rows) == 1
    assert rows[0]["send_status"] == "FAILED"
    assert rows[0]["distance_km"] is None
    assert rows[0]["recipient_masked"].endswith("4567")


def test_history_records_sent_and_failed_attempts(tmp_path):
    agent = _agent(tmp_path, provider=MockProvider())
    agent.send_notification(_event(), _alert(), confirmed=True)
    with pytest.raises(LookupError):
        agent.send_notification(_event(latitude=10.0, longitude=60.0), _alert(), confirmed=True)

    rows = agent.history()
    assert len(rows) == 2
    by_status = {row["send_status"] for row in rows}
    assert by_status == {"SENT", "FAILED"}
    sent = next(row for row in rows if row["send_status"] == "SENT")
    assert sent["provider_message_id"] == "SM123"


def test_history_endpoint_returns_validated_rows(tmp_path, monkeypatch):
    """The API history endpoint must validate through the pydantic schema,
    including FAILED rows with an empty distance_km column."""
    from fastapi.testclient import TestClient
    from backend.main import app

    # Record a FAILED attempt (no station -> empty distance_km in the CSV).
    agent = EmergencyResponseAgent(
        locator=FireStationLocator(stations_path=_stations(tmp_path / "stations.csv"), search_radius_km=50.0),
        history_path=tmp_path / "history.csv",
        recipient="+15551234567",
    )
    with pytest.raises(LookupError):
        agent.send_notification(_event(latitude=10.0, longitude=60.0), _alert(), confirmed=True)

    # Point the API at the same history file and hit the endpoint.
    monkeypatch.setenv("EMERGENCY_RESPONSE_HISTORY_PATH", str(tmp_path / "history.csv"))
    client = TestClient(app)
    response = client.get("/api/v1/emergency-response/notifications-history?cluster_id=42")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["send_status"] == "FAILED"
    assert rows[0]["distance_km"] is None
    assert rows[0]["recipient_masked"].endswith("4567")
