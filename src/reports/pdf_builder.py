"""
PDF Builder for ThermalWatch Local Thermal Incident Reports using ReportLab.

Renders a 2-4 page official document with:
- Dark navy branding headers (#0f172a / #1e293b)
- Risk/severity badges & indicators
- Location block & reverse-geocoded table
- Thermal observation metrics
- Classification & movement vector evidence
- Recommended decision-support actions
- Official disclaimers
"""

from __future__ import annotations

import io
from typing import Any, Dict
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from src.reports.incident_report_generator import IncidentReportData
from src.logging_setup import get_logger

logger = get_logger("src.reports.pdf_builder")


def build_incident_pdf(data: IncidentReportData) -> bytes:
    """Render IncidentReportData into a PDF byte stream."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom Palette
    NAVY_PRIMARY = colors.HexColor("#0f172a")
    NAVY_SECONDARY = colors.HexColor("#1e293b")
    ACCENT_BLUE = colors.HexColor("#0284c7")
    TEXT_DARK = colors.HexColor("#0f172a")
    BG_LIGHT = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#cbd5e1")

    # Severity Colors
    sev_upper = data.severity.upper()
    if sev_upper == "CRITICAL":
        SEV_BG = colors.HexColor("#991b1b")
        SEV_TEXT = colors.white
    elif sev_upper == "HIGH":
        SEV_BG = colors.HexColor("#c2410c")
        SEV_TEXT = colors.white
    elif sev_upper == "MEDIUM":
        SEV_BG = colors.HexColor("#d97706")
        SEV_TEXT = colors.white
    else:
        SEV_BG = colors.HexColor("#15803d")
        SEV_TEXT = colors.white

    # Custom Styles
    style_header_title = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.white,
        alignment=TA_LEFT,
    )

    style_header_sub = ParagraphStyle(
        "HeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_LEFT,
    )

    style_sec_heading = ParagraphStyle(
        "SecHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
    )

    style_cell_label = ParagraphStyle(
        "CellLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=NAVY_PRIMARY,
    )

    style_cell_val = ParagraphStyle(
        "CellVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK,
    )

    style_body = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=TEXT_DARK,
    )

    style_disclaimer = ParagraphStyle(
        "ReportDisclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # 1. Header Banner Box
    loc_header = data.location.get("formatted_location_header", "Unknown Location") if data.location else "Unknown Location"
    header_content = [
        [
            Paragraph("THERMALWATCH", style_header_title),
            Paragraph(f"<b>CLUSTER #{data.cluster_id}</b>", ParagraphStyle("HeaderRight", parent=style_header_title, alignment=TA_RIGHT)),
        ],
        [
            Paragraph("LOCAL THERMAL INCIDENT REPORT | DECISION SUPPORT", style_header_sub),
            Paragraph(f"Generated: {data.report_generated_at}", ParagraphStyle("HeaderSubRight", parent=style_header_sub, alignment=TA_RIGHT)),
        ],
    ]
    header_table = Table(header_content, colWidths=[340, 200])
    header_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY_PRIMARY),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    # 2. Location Summary Header & Severity Badge
    summary_box_data = [
        [
            Paragraph(f"<b>INCIDENT LOCATION</b><br/><font size=11 color='#0284c7'><b>{loc_header}</b></font>", style_body),
            Paragraph(
                f"<font size=10><b>SEVERITY LEVEL</b></font><br/>"
                f"<font size=14><b>{data.severity}</b></font><br/>"
                f"<font size=8>Risk Score: {data.risk_score:.1f} / 100</font>",
                ParagraphStyle("BadgeText", parent=style_body, alignment=TA_CENTER, textColor=colors.white),
            ),
        ]
    ]
    summary_table = Table(summary_box_data, colWidths=[410, 130])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), BG_LIGHT),
            ("BACKGROUND", (1, 0), (1, 0), SEV_BG),
            ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 12))

    def make_section_header(title_text: str) -> Table:
        t = Table([[Paragraph(title_text, style_sec_heading)]], colWidths=[540])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), NAVY_SECONDARY),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        return t

    # --- SECTION A: INCIDENT IDENTIFICATION ---
    story.append(make_section_header("A. INCIDENT IDENTIFICATION"))
    loc = data.location or {}
    sec_a_data = [
        [Paragraph("Cluster ID", style_cell_label), Paragraph(str(data.cluster_id), style_cell_val), Paragraph("State", style_cell_label), Paragraph(str(loc.get("state", "Not available")), style_cell_val)],
        [Paragraph("Coordinates", style_cell_label), Paragraph(f"{data.location.get('latitude', 0.0):.4f}, {data.location.get('longitude', 0.0):.4f}", style_cell_val), Paragraph("District", style_cell_label), Paragraph(str(loc.get("district", "Not available")), style_cell_val)],
        [Paragraph("City / Town", style_cell_label), Paragraph(str(loc.get("city_town", "Not available")), style_cell_val), Paragraph("Locality / Colony", style_cell_label), Paragraph(str(loc.get("locality_colony", "Not available")), style_cell_val)],
        [Paragraph("Street / Road", style_cell_label), Paragraph(str(loc.get("street_road", "Not available")), style_cell_val), Paragraph("PIN Code", style_cell_label), Paragraph(str(loc.get("postcode", "Not available")), style_cell_val)],
        [Paragraph("Landmark", style_cell_label), Paragraph(str(loc.get("landmark", "Not available")), style_cell_val), Paragraph("Geocoded Address", style_cell_label), Paragraph(str(loc.get("display_name", "Not available")), style_cell_val)],
    ]
    table_a = Table(sec_a_data, colWidths=[100, 170, 100, 170])
    table_a.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("BACKGROUND", (2, 0), (2, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(table_a)
    story.append(Spacer(1, 10))

    # --- SECTION B: THERMAL OBSERVATION ---
    story.append(make_section_header("B. THERMAL OBSERVATION"))
    sec_b_data = [
        [Paragraph("FIRMS Detections", style_cell_label), Paragraph(str(data.observation_count), style_cell_val), Paragraph("First Detected", style_cell_label), Paragraph(str(data.first_detected), style_cell_val)],
        [Paragraph("Active Days", style_cell_label), Paragraph(f"{data.active_days} day(s)", style_cell_val), Paragraph("Last Detected", style_cell_label), Paragraph(str(data.last_detected), style_cell_val)],
        [Paragraph("Maximum FRP", style_cell_label), Paragraph(f"{data.max_frp:.1f} MW", style_cell_val), Paragraph("Brightness Temp (TI4)", style_cell_label), Paragraph(f"{data.brightness_temp_ti4:.1f} K", style_cell_val)],
        [Paragraph("Thermal Contrast (ΔT)", style_cell_label), Paragraph(f"{data.thermal_contrast_k:.1f} K", style_cell_val), Paragraph("Persistence Category", style_cell_label), Paragraph(str(data.persistence_category).upper(), style_cell_val)],
    ]
    table_b = Table(sec_b_data, colWidths=[100, 170, 100, 170])
    table_b.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("BACKGROUND", (2, 0), (2, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table_b)
    story.append(Spacer(1, 10))

    # --- SECTION C: RISK ASSESSMENT ---
    story.append(make_section_header("C. RISK ASSESSMENT"))
    sec_c_data = [
        [Paragraph("Risk Score / Level", style_cell_label), Paragraph(f"<b>{data.risk_score:.1f} / 100</b> ({data.risk_level})", style_cell_val), Paragraph("False-Alarm Concern", style_cell_label), Paragraph(str(data.false_alarm_concern), style_cell_val)],
        [Paragraph("Evidence Reliability", style_cell_label), Paragraph(str(data.evidence_reliability_level), style_cell_val), Paragraph("Primary Risk Factors", style_cell_label), Paragraph(str(data.risk_factors), style_cell_val)],
    ]
    table_c = Table(sec_c_data, colWidths=[100, 170, 100, 170])
    table_c.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("BACKGROUND", (2, 0), (2, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table_c)
    story.append(Spacer(1, 10))

    # --- SECTION D: CLASSIFICATION ---
    story.append(make_section_header("D. INDUSTRIAL / LANDCOVER CLASSIFICATION"))
    sec_d_data = [
        [Paragraph("Classification Label", style_cell_label), Paragraph(f"<b>{data.classification_label}</b> (Conf: {data.classification_confidence:.1f}%)", style_cell_val)],
        [Paragraph("OSM Industrial Context", style_cell_label), Paragraph(str(data.osm_industrial_context), style_cell_val)],
        [Paragraph("Sentinel-2 Context", style_cell_label), Paragraph(str(data.sentinel2_cnn_context), style_cell_val)],
        [Paragraph("Cloud & Sensor Limits", style_cell_label), Paragraph(str(data.cloud_imagery_limitations), style_cell_val)],
    ]
    table_d = Table(sec_d_data, colWidths=[130, 410])
    table_d.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table_d)
    story.append(Spacer(1, 10))

    # --- SECTION E: THERMAL ACTIVITY MOVEMENT ---
    story.append(make_section_header("E. THERMAL ACTIVITY MOVEMENT"))
    sec_e_data = [
        [Paragraph("Movement Status", style_cell_label), Paragraph(str(data.movement_status), style_cell_val), Paragraph("Direction", style_cell_label), Paragraph(str(data.movement_direction), style_cell_val)],
        [Paragraph("Direction Confidence", style_cell_label), Paragraph(str(data.direction_confidence), style_cell_val), Paragraph("Displacement (km)", style_cell_label), Paragraph(f"{data.displacement_km:.2f} km", style_cell_val)],
        [Paragraph("Movement Rate", style_cell_label), Paragraph(f"{data.movement_rate_km_per_day:.2f} km/day", style_cell_val), Paragraph("Movement Pattern", style_cell_label), Paragraph(str(data.directional_consistency), style_cell_val)],
    ]
    table_e = Table(sec_e_data, colWidths=[100, 170, 100, 170])
    table_e.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("BACKGROUND", (2, 0), (2, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table_e)
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"<i>Note: {data.movement_disclaimer}</i>", style_disclaimer))
    story.append(Spacer(1, 8))

    # --- SECTION F: LOCAL SURROUNDINGS ---
    story.append(make_section_header("F. LOCAL SURROUNDINGS & INFRASTRUCTURE"))
    sec_f_data = [
        [Paragraph("Industrial Infra", style_cell_label), Paragraph(str(data.nearby_industrial_infrastructure), style_cell_val)],
        [Paragraph("Nearby Roads", style_cell_label), Paragraph(str(data.nearby_roads), style_cell_val)],
        [Paragraph("Nearest Fire Station", style_cell_label), Paragraph(f"{data.nearest_fire_station_name} ({data.distance_to_fire_station_km})", style_cell_val)],
        [Paragraph("Nearby Landmarks", style_cell_label), Paragraph(str(data.nearby_landmarks), style_cell_val)],
    ]
    table_f = Table(sec_f_data, colWidths=[130, 410])
    table_f.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table_f)
    story.append(Spacer(1, 10))

    # --- SECTION G: WHY FLAGGED ---
    story.append(make_section_header("G. WHY THIS EVENT WAS FLAGGED"))
    why_box = Table([[Paragraph(data.why_flagged_explanation, style_body)]], colWidths=[540])
    why_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, ACCENT_BLUE),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(why_box)
    story.append(Spacer(1, 10))

    # --- SECTION H: RECOMMENDED NEXT ACTIONS ---
    story.append(make_section_header("H. RECOMMENDED NEXT ACTIONS (DECISION SUPPORT)"))
    actions_list = data.recommended_actions or ["Continue standard monitoring."]
    actions_markup = "<br/>".join([f"• {a}" for a in actions_list])
    act_box = Table([[Paragraph(actions_markup, style_body)]], colWidths=[540])
    act_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(act_box)
    story.append(Spacer(1, 10))

    # --- SECTION I: REPORT DISCLAIMER ---
    story.append(make_section_header("I. REPORT DISCLAIMER"))
    disc_box = Table([[Paragraph(data.disclaimer, style_disclaimer)]], colWidths=[540])
    disc_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(disc_box)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
