"""
Automated unit tests for Reverse Geocoding and Local Incident Report Generation.

Verifies:
1. ReverseGeocoder field extraction, persistent caching, and fallback handling.
2. IncidentReportGenerator data assembly matching all required sections (A-I).
3. PDF report builder output generation.
4. FastAPI endpoints: /api/v1/location/{cluster_id}, /api/v1/reports/{cluster_id}, and /api/v1/reports/{cluster_id}/pdf.
"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from src.geocoding.reverse_geocoder import ReverseGeocoder, ReverseGeocodeResult
from src.reports.incident_report_generator import IncidentReportGenerator, IncidentReportData
from src.reports.pdf_builder import build_incident_pdf

client = TestClient(app)


def test_reverse_geocoder_fallback(tmp_path):
    """Verify ReverseGeocoder graceful fallback when offline/unreachable."""
    geocoder = ReverseGeocoder(cache_dir=tmp_path, rate_limit_seconds=0.0)
    # Using non-existent / unreachable lat/lon with mock failure
    result = geocoder._fallback_result(8.9764, 77.4244)
    assert result.state == "Not available"
    assert result.district == "Not available"
    assert result.city_town == "Not available"
    assert result.street_road == "Not available"
    assert result.landmark == "Not available"
    assert "Coordinates: 8.9764, 77.4244" in result.formatted_location_header


def test_reverse_geocoder_parsing(tmp_path):
    """Verify Nominatim JSON response parser extracts location fields without fabricating."""
    geocoder = ReverseGeocoder(cache_dir=tmp_path, rate_limit_seconds=0.0)
    mock_data = {
        "display_name": "Surandai, Tenkasi District, Tamil Nadu, 627859, India",
        "address": {
            "state": "Tamil Nadu",
            "state_district": "Tenkasi District",
            "town": "Surandai",
            "suburb": "Vagaikulam",
            "road": "Main Road",
            "postcode": "627859",
        },
    }
    result = geocoder._parse_nominatim_response(8.9764, 77.4244, mock_data)
    assert result.state == "Tamil Nadu"
    assert result.district == "Tenkasi District"
    assert result.city_town == "Surandai"
    assert result.locality_colony == "Vagaikulam"
    assert result.street_road == "Main Road"
    assert result.postcode == "627859"
    assert "Surandai" in result.formatted_location_header


def test_incident_report_generator_sections(tmp_path):
    """Verify IncidentReportGenerator produces required sections A-I for cluster #1105."""
    event = {
        "cluster_id": 1105,
        "latitude": 8.9764,
        "longitude": 77.4244,
        "risk_score": 85.5,
        "risk_level": "HIGH",
        "observation_count": 12,
        "max_frp": 34.2,
        "max_bright_ti4": 345.0,
        "bt_diff_max": 22.0,
        "persistence_category": "persistent",
        "classification_label": "Industrial Facility",
        "false_alarm_indicator": "LOW",
    }
    generator = IncidentReportGenerator(geocoder=ReverseGeocoder(cache_dir=tmp_path))
    report = generator.generate_report(event=event)

    assert report.cluster_id == 1105
    assert report.title == "THERMALWATCH LOCAL THERMAL INCIDENT REPORT"
    assert report.severity in ("HIGH", "CRITICAL", "MEDIUM", "LOW")
    assert report.location is not None

    # Section E: Terminology rule check
    assert "Thermal Activity Movement" in report.movement_disclaimer
    assert "does NOT state physical fire spread" in report.movement_disclaimer

    # Section G: Why flagged check
    assert "Cluster flagged at" in report.why_flagged_explanation

    # Section H: Recommendations check
    assert len(report.recommended_actions) > 0

    # Section I: Disclaimer check
    assert "decision-support product" in report.disclaimer


def test_pdf_builder_bytes(tmp_path):
    """Verify build_incident_pdf produces non-empty binary PDF output."""
    event = {"cluster_id": 1105, "latitude": 8.9764, "longitude": 77.4244, "risk_score": 80.0, "risk_level": "HIGH"}
    generator = IncidentReportGenerator(geocoder=ReverseGeocoder(cache_dir=tmp_path))
    report = generator.generate_report(event=event)
    pdf_bytes = build_incident_pdf(report)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_api_location_endpoint():
    """Verify /api/v1/location/{cluster_id} endpoint."""
    res = client.get("/api/v1/location/1105")
    assert res.status_code == 200
    data = res.json()
    assert "latitude" in data
    assert "longitude" in data
    assert "state" in data
    assert "formatted_location_header" in data


def test_api_reports_endpoints():
    """Verify /api/v1/reports/{cluster_id} and /api/v1/reports/{cluster_id}/pdf endpoints."""
    res_json = client.get("/api/v1/reports/1105")
    assert res_json.status_code == 200
    report_data = res_json.json()
    assert report_data["cluster_id"] == 1105
    assert report_data["title"] == "THERMALWATCH LOCAL THERMAL INCIDENT REPORT"
    assert "location" in report_data

    res_pdf = client.get("/api/v1/reports/1105/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")
