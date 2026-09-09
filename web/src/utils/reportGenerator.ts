/**
 * Frontend Incident Report Generator & Download Handler.
 *
 * Calls the backend PDF report endpoint `downloadIncidentReportPdf(clusterId)`.
 * If the backend API endpoint is unreachable, falls back to generating a print/PDF
 * window using the structured report data from `fetchIncidentReport(clusterId)`.
 */

import { downloadIncidentReportPdf, fetchIncidentReport } from '../api/client';
import type { IncidentReportResponse } from '../types';

export async function triggerIncidentReportDownload(clusterId: number): Promise<void> {
  try {
    // Attempt official backend PDF download
    await downloadIncidentReportPdf(clusterId);
  } catch (err) {
    console.warn('Backend PDF endpoint unavailable, generating client report fallback:', err);
    try {
      const report = await fetchIncidentReport(clusterId);
      openClientReportPrintWindow(report);
    } catch (fallbackErr) {
      alert(`Could not generate incident report for Cluster #${clusterId}. Please check network connection.`);
    }
  }
}

export function openClientReportPrintWindow(report: IncidentReportResponse): void {
  const win = window.open('', '_blank', 'width=900,height=1000');
  if (!win) {
    alert('Please allow popups to view and print the Incident Report.');
    return;
  }

  const actionsList = (report.recommended_actions || [])
    .map((act) => `<li style="margin-bottom: 4px;">${act}</li>`)
    .join('');

  const html = `
    <!DOCTYPE html>
    <html>
      <head>
        <title>ThermalWatch Incident Report - Cluster #${report.cluster_id}</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; margin: 0; padding: 24px; line-height: 1.4; background: #fff; }
          .header { background: #0f172a; color: #fff; padding: 16px 20px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; }
          .header h1 { margin: 0; font-size: 20px; font-weight: 800; letter-spacing: 0.5px; }
          .header .sub { font-size: 11px; color: #94a3b8; margin-top: 4px; }
          .summary-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; margin: 16px 0; }
          .loc-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; }
          .sev-badge { background: ${report.severity === 'CRITICAL' ? '#991b1b' : report.severity === 'HIGH' ? '#c2410c' : '#d97706'}; color: #fff; text-align: center; padding: 12px; border-radius: 6px; }
          .sev-badge h2 { margin: 0; font-size: 20px; }
          .section { margin-top: 20px; }
          .section-title { background: #1e293b; color: #fff; padding: 6px 10px; font-size: 12px; font-weight: 700; border-radius: 4px; }
          table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }
          th, td { border: 1px solid #cbd5e1; padding: 6px 10px; text-align: left; vertical-align: top; }
          td.label { background: #f8fafc; font-weight: 600; width: 140px; }
          .why-box { background: #f0f9ff; border: 1px solid #0284c7; padding: 10px; border-radius: 4px; font-size: 12px; margin-top: 8px; }
          .disclaimer { background: #f1f5f9; border: 1px solid #cbd5e1; padding: 8px; border-radius: 4px; font-size: 11px; color: #475569; font-style: italic; margin-top: 16px; }
          @media print {
            .no-print { display: none; }
            body { padding: 0; }
          }
        </style>
      </head>
      <body>
        <div class="no-print" style="margin-bottom: 12px; text-align: right;">
          <button onclick="window.print()" style="background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: 600; cursor: pointer;">Print / Save PDF</button>
        </div>

        <div class="header">
          <div>
            <h1>THERMALWATCH</h1>
            <div class="sub">LOCAL THERMAL INCIDENT REPORT | DECISION SUPPORT</div>
          </div>
          <div style="text-align: right;">
            <div style="font-weight: 700; font-size: 16px;">CLUSTER #${report.cluster_id}</div>
            <div class="sub">${report.report_generated_at}</div>
          </div>
        </div>

        <div class="summary-grid">
          <div class="loc-box">
            <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Location Context</div>
            <div style="font-size: 15px; font-weight: 700; color: #0284c7; margin-top: 4px;">${report.location.formatted_location_header}</div>
            <div style="font-size: 12px; color: #475569; margin-top: 2px;">Coordinates: ${report.location.latitude.toFixed(4)}, ${report.location.longitude.toFixed(4)}</div>
          </div>
          <div class="sev-badge">
            <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Severity Level</div>
            <h2>${report.severity}</h2>
            <div style="font-size: 11px; margin-top: 2px;">Risk Score: ${report.risk_score.toFixed(1)} / 100</div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">A. INCIDENT IDENTIFICATION</div>
          <table>
            <tr><td class="label">Cluster ID</td><td>${report.cluster_id}</td><td class="label">State</td><td>${report.location.state}</td></tr>
            <tr><td class="label">Coordinates</td><td>${report.location.latitude.toFixed(4)}, ${report.location.longitude.toFixed(4)}</td><td class="label">District</td><td>${report.location.district}</td></tr>
            <tr><td class="label">City / Town</td><td>${report.location.city_town}</td><td class="label">Locality / Colony</td><td>${report.location.locality_colony}</td></tr>
            <tr><td class="label">Street / Road</td><td>${report.location.street_road}</td><td class="label">PIN Code</td><td>${report.location.postcode}</td></tr>
            <tr><td class="label">Landmark</td><td>${report.location.landmark}</td><td class="label">Address</td><td>${report.location.display_name}</td></tr>
          </table>
        </div>

        <div class="section">
          <div class="section-title">B. THERMAL OBSERVATION</div>
          <table>
            <tr><td class="label">FIRMS Detections</td><td>${report.observation_count}</td><td class="label">First Detected</td><td>${report.first_detected}</td></tr>
            <tr><td class="label">Active Days</td><td>${report.active_days} day(s)</td><td class="label">Last Detected</td><td>${report.last_detected}</td></tr>
            <tr><td class="label">Max FRP</td><td>${report.max_frp.toFixed(1)} MW</td><td class="label">Brightness Temp (TI4)</td><td>${report.brightness_temp_ti4.toFixed(1)} K</td></tr>
            <tr><td class="label">Thermal Contrast (ΔT)</td><td>${report.thermal_contrast_k.toFixed(1)} K</td><td class="label">Persistence Category</td><td>${report.persistence_category.toUpperCase()}</td></tr>
          </table>
        </div>

        <div class="section">
          <div class="section-title">C. RISK ASSESSMENT</div>
          <table>
            <tr><td class="label">Risk Score / Level</td><td><strong>${report.risk_score.toFixed(1)} / 100</strong> (${report.risk_level})</td><td class="label">False-Alarm Concern</td><td>${report.false_alarm_concern}</td></tr>
            <tr><td class="label">Evidence Reliability</td><td>${report.evidence_reliability_level}</td><td class="label">Primary Risk Factors</td><td>${report.risk_factors}</td></tr>
          </table>
        </div>

        <div class="section">
          <div class="section-title">D. INDUSTRIAL / LANDCOVER CLASSIFICATION</div>
          <table>
            <tr><td class="label">Classification Label</td><td><strong>${report.classification_label}</strong> (Confidence: ${report.classification_confidence.toFixed(1)}%)</td></tr>
            <tr><td class="label">OSM Industrial Context</td><td>${report.osm_industrial_context}</td></tr>
            <tr><td class="label">Sentinel-2 Context</td><td>${report.sentinel2_cnn_context}</td></tr>
            <tr><td class="label">Cloud & Sensor Limits</td><td>${report.cloud_imagery_limitations}</td></tr>
          </table>
        </div>

        <div class="section">
          <div class="section-title">E. THERMAL ACTIVITY MOVEMENT</div>
          <table>
            <tr><td class="label">Movement Status</td><td>${report.movement_status}</td><td class="label">Direction</td><td>${report.movement_direction}</td></tr>
            <tr><td class="label">Direction Confidence</td><td>${report.direction_confidence}</td><td class="label">Displacement</td><td>${report.displacement_km.toFixed(2)} km</td></tr>
            <tr><td class="label">Movement Rate</td><td>${report.movement_rate_km_per_day.toFixed(2)} km/day</td><td class="label">Pattern</td><td>${report.directional_consistency}</td></tr>
          </table>
          <div style="font-size: 10px; color: #64748b; font-style: italic; margin-top: 4px;">${report.movement_disclaimer}</div>
        </div>

        <div class="section">
          <div class="section-title">F. LOCAL SURROUNDINGS & INFRASTRUCTURE</div>
          <table>
            <tr><td class="label">Industrial Infra</td><td>${report.nearby_industrial_infrastructure}</td></tr>
            <tr><td class="label">Nearby Roads</td><td>${report.nearby_roads}</td></tr>
            <tr><td class="label">Nearest Fire Station</td><td>${report.nearest_fire_station_name} (${report.distance_to_fire_station_km})</td></tr>
            <tr><td class="label">Nearby Landmarks</td><td>${report.nearby_landmarks}</td></tr>
          </table>
        </div>

        <div class="section">
          <div class="section-title">G. WHY THIS EVENT WAS FLAGGED</div>
          <div class="why-box">${report.why_flagged_explanation}</div>
        </div>

        <div class="section">
          <div class="section-title">H. RECOMMENDED NEXT ACTIONS (DECISION SUPPORT)</div>
          <ul style="font-size: 12px; margin-top: 6px; padding-left: 20px;">
            ${actionsList}
          </ul>
        </div>

        <div class="disclaimer">
          <strong>Disclaimer:</strong> ${report.disclaimer}
        </div>
      </body>
    </html>
  `;

  win.document.open();
  win.document.write(html);
  win.document.close();
}
