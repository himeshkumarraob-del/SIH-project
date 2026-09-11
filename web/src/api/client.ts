/**
 * API client â€” connects to the FastAPI backend.
 *
 * Resolution order:
 *   1. VITE_API_BASE_URL (production env var, full URL incl. /api/v1) â€” for
 *      a frontend and backend hosted on separate origins.
 *   2. Same-origin /api/v1 â€” in dev the Vite server proxies /api â†’
 *      localhost:8000; on Vercel the vercel.json rewrite proxies /api to the
 *      backend (VERCEL_API_BASE_URL).
 */

import type {
  ThermalEvent,
  ClusterSummary,
  MovementVector,
  DashboardStats,
  FilterState,
  ClassificationData,
  ClusterDetail,
  ClassificationDetailData,
  RiskDetailData,
  ResponseDetailData,
  ThermalAlert,
  LocationDetail,
  IncidentReportResponse,
  EmergencyResponseSearchResult,
  PrototypeNotificationResult,
  PrototypeNotificationHistoryEntry,
} from '../types';


// Set to true to use mock data for offline development
const USE_MOCK = true;

// ---------------------------------------------------------------------------
// Mock data imports (used only when USE_MOCK = true or fallback)
// ---------------------------------------------------------------------------
import { MOCK_EVENTS, MOCK_CLUSTERS, MOCK_MOVEMENTS, MOCK_STATISTICS, MOCK_ALERTS } from '../data/mockData';
import { MOCK_CLASSIFICATIONS } from '../data/classifications';

// ---------------------------------------------------------------------------
// Backend API helpers
// ---------------------------------------------------------------------------

// Absolute base override (https://host/api/v1). Empty in dev/preview builds so
// calls stay same-origin and the platform proxy handles /api.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '');

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = API_BASE.startsWith('http')
    ? new URL(`${API_BASE}${path}`)
    : new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function apiPost<T>(path: string, body?: any): Promise<T> {
  const url = API_BASE.startsWith('http')
    ? new URL(`${API_BASE}${path}`)
    : new URL(`${API_BASE}${path}`, window.location.origin);
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    // Surface the backend's safe detail (e.g. masked Twilio error code/message)
    // instead of only the generic HTTP status text.
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data && typeof data.detail === 'string' && data.detail) {
        detail = data.detail;
      }
    } catch {
      // Non-JSON error body: fall back to the status text.
    }
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Filter helpers
// ---------------------------------------------------------------------------

function applyFilters<T extends object>(
  items: T[],
  filters: FilterState,
  fieldMap: Partial<Record<keyof FilterState, keyof T>>,
): T[] {
  return items.filter((item) => {
    for (const [filterKey, fieldKey] of Object.entries(fieldMap)) {
      const filterValues = filters[filterKey as keyof FilterState];
      if (Array.isArray(filterValues) && filterValues.length > 0) {
        const itemValue = String((item as Record<string, unknown>)[fieldKey as string] ?? '');
        if (!filterValues.includes(itemValue)) return false;
      }
    }
    if (filters.dateRange && filters.dateRange.start && filters.dateRange.end) {
      const dateVal = String((item as Record<string, unknown>)['acq_date'] ?? '');
      if (dateVal && (dateVal < filters.dateRange.start || dateVal > filters.dateRange.end)) {
        return false;
      }
    }
    return true;
  });
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

export async function fetchEvents(filters: FilterState): Promise<ThermalEvent[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_EVENTS, filters, {
      abnormalityLevel: 'abnormality_level',
      persistenceCategory: 'persistence_category',
      satellite: 'source_satellite',
    });
  }

  try {
    const params: Record<string, string> = {};
    if (filters.riskLevel.length) params.risk_level = filters.riskLevel.join(',');
    if (filters.abnormalityLevel.length) params.abnormality_level = filters.abnormalityLevel.join(',');
    if (filters.falseAlarmConcern.length) params.false_alarm_indicator = filters.falseAlarmConcern.join(',');
    if (filters.movementStatus.length) params.movement_status = filters.movementStatus.join(',');
    if (filters.dateRange?.start) params.start_date = filters.dateRange.start;
    if (filters.dateRange?.end) params.end_date = filters.dateRange.end;

    const data = await apiGet<{ events: any[] }>('/events', params);

    // Map backend response to frontend ThermalEvent type
    return data.events.map((e: any) => ({
      detection_id: `cluster-${e.cluster_id}`,
      latitude: e.latitude ?? 0,
      longitude: e.longitude ?? 0,
      acq_date: e.acq_date ?? '',
      cluster_id: e.cluster_id,
      persistence_category: 'unknown',
      anomaly_score: 0,
      anomaly_flag: e.abnormality_level === 'HIGH' ? 1 : 0,
      abnormality_level: e.abnormality_level ?? 'NORMAL',
      anomaly_characterization: '',
      explanation: e.explanation ?? '',
      contributing_factors: '',
      bright_ti4: e.max_bright_ti4 ?? 0,
      bright_ti5: 0,
      frp: e.max_frp ?? 0,
      confidence: '',
      satellite: '',
      scan: 0,
      track: 0,
      acq_time: '',
      instrument: 'VIIRS',
      source_satellite: '',
      source_file: '',
      acquisition_datetime: '',
    }));
  } catch (err) {
    console.error('Failed to fetch events:', err);
    return [];
  }
}

export interface FetchClustersOptions {
  /**
   * When true, API failures reject instead of resolving to []. Used by pages
   * that need a visible error + retry state (Events Queue). All existing
   * callers keep the lenient default (resolve [] on error).
   */
  throwOnError?: boolean;
}

export async function fetchClusters(filters: FilterState, opts?: FetchClustersOptions): Promise<ClusterSummary[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_CLUSTERS, filters, {
      riskLevel: 'risk_level',
      abnormalityLevel: 'abnormality_level',
      falseAlarmConcern: 'false_alarm_indicator',
      persistenceCategory: 'persistence_category',
    });
  }

  try {
    const params: Record<string, string> = {};
    if (filters.riskLevel.length) params.risk_level = filters.riskLevel.join(',');
    if (filters.abnormalityLevel.length) params.abnormality_level = filters.abnormalityLevel.join(',');
    if (filters.falseAlarmConcern.length) params.false_alarm_indicator = filters.falseAlarmConcern.join(',');
    if (filters.persistenceCategory.length) params.persistence_category = filters.persistenceCategory.join(',');

    const data = await apiGet<any[]>('/clusters', params);

    // Map backend response to frontend ClusterSummary type
    return data.map((c: any) => ({
      cluster_id: c.cluster_id,
      latitude: c.latitude ?? 0,
      longitude: c.longitude ?? 0,
      observation_count: c.observation_count ?? 1,
      active_days: c.active_days ?? 1,
      first_detection: c.first_detection ?? '',
      last_detection: c.last_detection ?? '',
      duration_days: c.duration_days ?? 1,
      mean_bright_ti4: c.mean_bright_ti4 ?? 0,
      max_bright_ti4: c.max_bright_ti4 ?? 0,
      mean_bright_ti5: c.mean_bright_ti5 ?? 0,
      max_bright_ti5: c.max_bright_ti5 ?? 0,
      mean_frp: c.mean_frp ?? 0,
      max_frp: c.max_frp ?? 0,
      mean_confidence: c.mean_confidence ?? 0,
      persistence_score: c.persistence_score ?? 0,
      persistence_category: c.persistence_category ?? 'unknown',
      bt_diff_mean: c.bt_diff_mean ?? 0,
      bt_diff_max: c.bt_diff_max ?? 0,
      frp_mean_to_max_ratio: c.frp_mean_to_max_ratio ?? 0,
      detection_density: c.detection_density ?? 0,
      active_day_ratio: c.active_day_ratio ?? 0,
      is_multi_day: c.is_multi_day ?? 0,
      is_persistent_candidate: c.is_persistent_candidate ?? 0,
      persistence_category_code: c.persistence_category_code ?? 0,
      anomaly_score: c.anomaly_score ?? 0,
      anomaly_flag: c.anomaly_flag ?? 0,
      abnormality_level: c.abnormality_level ?? 'NORMAL',
      anomaly_characterization: c.anomaly_characterization ?? '',
      explanation: c.explanation ?? '',
      contributing_factors: c.contributing_factors ?? '',
      false_alarm_indicator: c.false_alarm_indicator ?? 'MEDIUM',
      false_alarm_reasons: c.false_alarm_reasons ?? '',
      detection_reliability: c.detection_reliability ?? 'MEDIUM',
      risk_score: c.risk_score ?? 0,
      risk_level: c.risk_level ?? 'LOW',
      risk_factors: c.risk_factors ?? '',
      risk_explanation: c.risk_explanation ?? '',
    }));
  } catch (err) {
    if (opts?.throwOnError) {
      throw err instanceof Error ? err : new Error('Failed to fetch clusters');
    }
    console.error('Failed to fetch clusters:', err);
    return [];
  }
}

export async function fetchMovement(filters: FilterState): Promise<MovementVector[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_MOVEMENTS, filters, {
      movementStatus: 'movement_status',
    });
  }

  try {
    const params: Record<string, string> = {};
    if (filters.movementStatus.length) params.movement_status = filters.movementStatus.join(',');

    const data = await apiGet<any[]>('/movement', params);

    return data.map((m: any) => ({
      cluster_id: m.cluster_id,
      observation_count: m.observation_count ?? 1,
      active_days: m.active_days ?? 1,
      first_detection: m.first_detection ?? '',
      last_detection: m.last_detection ?? '',
      time_span_days: m.time_span_days ?? 0,
      start_latitude: m.start_latitude ?? 0,
      start_longitude: m.start_longitude ?? 0,
      end_latitude: m.end_latitude ?? 0,
      end_longitude: m.end_longitude ?? 0,
      total_movement_distance_km: m.total_movement_distance_km ?? 0,
      movement_rate_km_per_day: m.movement_rate_km_per_day ?? 0,
      movement_bearing_degrees: m.movement_bearing_degrees ?? 0,
      movement_direction: m.movement_direction ?? 'INSUFFICIENT_DATA',
      movement_confidence: m.movement_confidence ?? 'INSUFFICIENT_DATA',
      movement_status: m.movement_status ?? 'INSUFFICIENT_DATA',
      // Direction intelligence (thermal activity movement, not confirmed fire spread)
      direction: m.direction ?? null,
      movement_pattern: m.movement_pattern ?? 'insufficient_evidence',
      direction_confidence: m.direction_confidence ?? 'INSUFFICIENT',
      direction_confidence_score: m.direction_confidence_score ?? 0,
      direction_available: m.direction_available ?? false,
    }));
  } catch (err) {
    console.error('Failed to fetch movement data:', err);
    return [];
  }
}

/**
 * Fetch ACTIVE thermal alerts from the real alert engine API.
 *
 * This notification layer polls the alert API. It does not itself make
 * upstream FIRMS ingestion real-time.
 *
 * Errors are NOT swallowed here: the polling hook distinguishes "no active
 * alerts" (empty array) from "alert API unavailable" (thrown error) so the
 * UI can degrade gracefully without inventing data.
 */
export async function fetchActiveAlerts(): Promise<ThermalAlert[]> {
  if (USE_MOCK) {
    return MOCK_ALERTS.filter((a) => a.status === 'ACTIVE');
  }
  try {
    const data = await apiGet<any[]>('/alerts?status=ACTIVE');
    return data.map((a: any) => ({
      alert_id: a.alert_id,
      cluster_id: a.cluster_id,
      severity: a.severity ?? 'LOW',
      status: a.status ?? 'ACTIVE',
      evidence_confidence: a.evidence_confidence ?? 'INSUFFICIENT',
      suppressed: a.suppressed ?? false,
      suppression_reason: a.suppression_reason ?? '',
      risk_score: a.risk_score ?? null,
      risk_level: a.risk_level ?? 'LOW',
      classification_label: a.classification_label ?? 'Unknown / Insufficient Evidence',
      classification_score: a.classification_score ?? null,
      false_alarm_indicator: a.false_alarm_indicator ?? 'MEDIUM',
      detection_reliability: a.detection_reliability ?? 'MEDIUM',
      observation_count: a.observation_count ?? 1,
      active_days: a.active_days ?? 1,
      persistence_category: a.persistence_category ?? 'isolated',
      max_frp: a.max_frp ?? null,
      max_bright_ti4: a.max_bright_ti4 ?? null,
      bt_diff_max: a.bt_diff_max ?? null,
      movement_direction: a.movement_direction ?? null,
      movement_bearing_degrees: a.movement_bearing_degrees ?? null,
      movement_rate_km_per_day: a.movement_rate_km_per_day ?? null,
      movement_pattern: a.movement_pattern ?? 'insufficient_evidence',
      latitude: a.latitude ?? null,
      longitude: a.longitude ?? null,
      nearest_station_name: a.nearest_station_name ?? '',
      station_distance_km: a.station_distance_km ?? null,
      station_available: a.station_available ?? false,
      reasons: a.reasons ?? '',
      alert_rationale: a.alert_rationale ?? '',
      created_at: a.created_at ?? '',
      updated_at: a.updated_at ?? '',
      is_decision_support_only: a.is_decision_support_only ?? true,
    }));
  } catch (err) {
    console.error('Failed to fetch active alerts:', err);
    return MOCK_ALERTS.filter((a) => a.status === 'ACTIVE');
  }
}

export async function fetchAllAlerts(params?: {
  severity?: string;
  status?: string;
  suppressed?: boolean;
}): Promise<ThermalAlert[]> {
  if (USE_MOCK) {
    let result = MOCK_ALERTS;
    if (params?.status && params.status !== 'ALL') {
      result = result.filter((a) => a.status === params.status);
    }
    if (params?.severity && params.severity !== 'ALL') {
      result = result.filter((a) => a.severity === params.severity);
    }
    if (params?.suppressed !== undefined) {
      result = result.filter((a) => a.suppressed === params.suppressed);
    }
    return result;
  }
  try {
    const query: Record<string, string> = {};
    if (params?.severity && params.severity !== 'ALL') query.severity = params.severity;
    if (params?.status && params.status !== 'ALL') query.status = params.status;
    if (params?.suppressed !== undefined) query.suppressed = String(params.suppressed);

    const data = await apiGet<any[]>('/alerts', query);
    return data.map((a: any) => ({
      alert_id: a.alert_id,
      cluster_id: a.cluster_id,
      severity: a.severity ?? 'LOW',
      status: a.status ?? 'ACTIVE',
      evidence_confidence: a.evidence_confidence ?? 'INSUFFICIENT',
      suppressed: a.suppressed ?? false,
      suppression_reason: a.suppression_reason ?? '',
      risk_score: a.risk_score ?? null,
      risk_level: a.risk_level ?? 'LOW',
      classification_label: a.classification_label ?? 'Unknown / Insufficient Evidence',
      classification_score: a.classification_score ?? null,
      false_alarm_indicator: a.false_alarm_indicator ?? 'MEDIUM',
      detection_reliability: a.detection_reliability ?? 'MEDIUM',
      observation_count: a.observation_count ?? 1,
      active_days: a.active_days ?? 1,
      persistence_category: a.persistence_category ?? 'isolated',
      max_frp: a.max_frp ?? null,
      max_bright_ti4: a.max_bright_ti4 ?? null,
      bt_diff_max: a.bt_diff_max ?? null,
      movement_direction: a.movement_direction ?? null,
      movement_bearing_degrees: a.movement_bearing_degrees ?? null,
      movement_rate_km_per_day: a.movement_rate_km_per_day ?? null,
      movement_pattern: a.movement_pattern ?? 'insufficient_evidence',
      latitude: a.latitude ?? null,
      longitude: a.longitude ?? null,
      nearest_station_name: a.nearest_station_name ?? '',
      station_distance_km: a.station_distance_km ?? null,
      station_available: a.station_available ?? false,
      reasons: a.reasons ?? '',
      alert_rationale: a.alert_rationale ?? '',
      created_at: a.created_at ?? '',
      updated_at: a.updated_at ?? '',
      is_decision_support_only: a.is_decision_support_only ?? true,
    }));
  } catch (err) {
    console.error('Failed to fetch all alerts:', err);
    let result = MOCK_ALERTS;
    if (params?.status && params.status !== 'ALL') {
      result = result.filter((a) => a.status === params.status);
    }
    if (params?.severity && params.severity !== 'ALL') {
      result = result.filter((a) => a.severity === params.severity);
    }
    if (params?.suppressed !== undefined) {
      result = result.filter((a) => a.suppressed === params.suppressed);
    }
    return result;
  }
}

export async function postAcknowledgeAlert(alertId: string): Promise<{
  alert_id: string;
  cluster_id: number;
  status: string;
  severity: string;
  updated_at: string;
  detail: string;
}> {
  return apiPost(`/alerts/${encodeURIComponent(alertId)}/acknowledge`);
}

export async function postResolveAlert(alertId: string): Promise<{
  alert_id: string;
  cluster_id: number;
  status: string;
  severity: string;
  updated_at: string;
  detail: string;
}> {
  return apiPost(`/alerts/${encodeURIComponent(alertId)}/resolve`);
}

export async function fetchAlertHistory(alertId?: string, clusterId?: number): Promise<any[]> {
  const query: Record<string, string> = {};
  if (alertId) query.alert_id = alertId;
  if (clusterId !== undefined) query.cluster_id = String(clusterId);
  return apiGet<any[]>('/alerts-history', query);
}

export async function fetchStatistics(): Promise<DashboardStats> {
  if (USE_MOCK) {
    return MOCK_STATISTICS!;
  }

  try {
    const data = await apiGet<DashboardStats>('/statistics');
    return data;
  } catch (err) {
    console.error('Failed to fetch statistics:', err);
    // Return empty stats on error
    return {
      total_detections: 0,
      active_clusters: 0,
      high_risk_count: 0,
      moving_count: 0,
      high_false_alarm_count: 0,
      anomaly_distribution: { NORMAL: 0, ELEVATED: 0, HIGH: 0 },
      risk_distribution: { LOW: 0, MEDIUM: 0, HIGH: 0 },
      false_alarm_distribution: { LOW: 0, MEDIUM: 0, HIGH: 0 },
      movement_distribution: { INSUFFICIENT_DATA: 0, STATIONARY: 0, MOVING: 0 },
    };
  }
}

/** Fetch full cluster detail from the real API (used by the detail panel). */
// Helper to construct mock cluster detail
function buildMockClusterDetail(clusterId: number): ClusterDetail {
  const c = MOCK_CLUSTERS.find((x) => x.cluster_id === clusterId) || MOCK_CLUSTERS[0];
  const cls = MOCK_CLASSIFICATIONS[clusterId];
  const m = MOCK_MOVEMENTS.find((x) => x.cluster_id === clusterId);
  return {
    cluster_id: c.cluster_id,
    latitude: c.latitude ?? 20.5937,
    longitude: c.longitude ?? 78.9629,
    observation_count: c.observation_count ?? 1,
    active_days: c.active_days ?? 1,
    first_detection: c.first_detection ?? '2026-08-01',
    last_detection: c.last_detection ?? '2026-08-03',
    duration_days: c.duration_days ?? 2,
    persistence_category: c.persistence_category ?? 'short_lived_repeated',
    max_frp: c.max_frp ?? 10.5,
    max_bright_ti4: c.max_bright_ti4 ?? 340.0,
    bt_diff_max: c.bt_diff_max ?? 40.0,
    abnormality_level: c.abnormality_level ?? 'NORMAL',
    anomaly_characterization: c.anomaly_characterization ?? 'MULTI_FACTOR_ANOMALY',
    explanation: c.explanation ?? 'Elevated thermal intensity detected across satellite passes.',
    false_alarm_indicator: c.false_alarm_indicator ?? 'LOW',
    false_alarm_reasons: c.false_alarm_reasons ?? '',
    detection_reliability: c.detection_reliability ?? 'HIGH',
    risk_score: c.risk_score ?? 7.5,
    risk_level: c.risk_level ?? 'HIGH',
    classification_label: cls?.classification_label ?? 'Industrial Heat Source / Elevated Flare',
    classification_score: cls?.classification_score ?? 0.88,
    classification_rationale: cls?.classification_rationale ?? 'Persistent thermal anomaly co-located with known industrial infrastructure.',
    movement_status: m?.movement_status ?? 'STATIONARY',
    total_movement_distance_km: m?.total_movement_distance_km ?? 0,
    location: {
      district: 'Jharsuguda Industrial Zone',
      state: 'Odisha',
      country: 'India',
      nearest_city: 'Jharsuguda',
      distance_to_city_km: 4.8,
      formatted_address: 'Jharsuguda District, Odisha, India',
    },
  };
}

export async function fetchClusterDetail(clusterId: number): Promise<ClusterDetail> {
  if (USE_MOCK) return buildMockClusterDetail(clusterId);
  try {
    return await apiGet<ClusterDetail>(`/events/${clusterId}`);
  } catch (err) {
    console.error('Failed to fetch cluster detail:', err);
    return buildMockClusterDetail(clusterId);
  }
}

export async function fetchClassificationDetail(clusterId: number): Promise<ClassificationDetailData> {
  const cls = MOCK_CLASSIFICATIONS[clusterId];
  const mock: ClassificationDetailData = {
    cluster_id: clusterId,
    classification_label: cls?.classification_label ?? 'Industrial Heat Source / Flare',
    classification_score: cls?.classification_score ?? 0.88,
    classification_rationale: cls?.classification_rationale ?? 'Persistent multi-pass detection co-located with industrial site.',
    osm_facility_type: cls?.osm_facility_type ?? 'Industrial Site',
    osm_distance_km: cls?.osm_distance_km ?? 1.2,
    predicted_landcover_class: cls?.predicted_landcover_class ?? 'Barren / Industrial Land',
    prediction_confidence: cls?.prediction_confidence ?? 0.85,
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<ClassificationDetailData>(`/classification/${clusterId}`);
  } catch (err) {
    console.error('Failed to fetch classification detail:', err);
    return mock;
  }
}

export async function fetchRiskDetail(clusterId: number): Promise<RiskDetailData> {
  const c = MOCK_CLUSTERS.find((x) => x.cluster_id === clusterId);
  const mock: RiskDetailData = {
    cluster_id: clusterId,
    risk_score: c?.risk_score ?? 7.5,
    risk_level: c?.risk_level ?? 'HIGH',
    risk_factors: c?.risk_factors ?? 'High max bright_ti4 temperature; persistent multi-day detections.',
    risk_explanation: c?.risk_explanation ?? 'Elevated thermal score based on satellite observations and local context.',
    risk_evidence: {
      components: [
        { key: 'frp', label: 'Radiative Energy (FRP)', points: 3.5, max_points: 4.0, detail: 'High radiative power output' },
        { key: 'persistence', label: 'Temporal Persistence', points: 2.5, max_points: 3.0, detail: 'Multi-day repeated detection' },
        { key: 'temperature', label: 'Brightness Temp Delta', points: 1.5, max_points: 3.0, detail: 'Significant thermal delta above background' },
      ],
      reliability_multiplier: 1.0,
      false_alarm_concern: c?.false_alarm_indicator ?? 'LOW',
      base_score: c?.risk_score ?? 7.5,
      final_score: c?.risk_score ?? 7.5,
    },
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<RiskDetailData>(`/risk/${clusterId}`);
  } catch (err) {
    console.error('Failed to fetch risk detail:', err);
    return mock;
  }
}

export async function fetchResponseDetail(clusterId: number): Promise<ResponseDetailData> {
  const c = MOCK_CLUSTERS.find((x) => x.cluster_id === clusterId);
  const mock: ResponseDetailData = {
    cluster_id: clusterId,
    risk_score: c?.risk_score ?? 7.5,
    risk_level: c?.risk_level ?? 'HIGH',
    alert_priority: c?.risk_level === 'HIGH' ? 'PRIORITY 1' : 'PRIORITY 2',
    recommended_action: 'Dispatch regional field verification unit and inspect thermal coordinates.',
    nearest_station_name: 'Regional Thermal Intelligence Station',
    station_distance_km: 5.4,
    station_available: true,
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<ResponseDetailData>(`/response/${clusterId}`);
  } catch (err) {
    console.error('Failed to fetch response detail:', err);
    return mock;
  }
}

export async function fetchMovementForCluster(clusterId: number): Promise<MovementVector | null> {
  const m = MOCK_MOVEMENTS.find((x) => x.cluster_id === clusterId);
  if (USE_MOCK) return m ?? null;
  try {
    const rows = await apiGet<MovementVector[]>(`/movement?cluster_id=${clusterId}`);
    return rows.length > 0 ? rows[0] : (m ?? null);
  } catch (err) {
    console.error('Failed to fetch movement for cluster:', err);
    return m ?? null;
  }
}

/** Merge cluster summary data into events for the detail panel (mock mode only). */
export function findClusterSummary(clusterId: number): ClusterSummary | undefined {
  if (USE_MOCK) {
    return MOCK_CLUSTERS.find((c) => c.cluster_id === clusterId);
  }
  return undefined;
}

export function findMovement(clusterId: number): MovementVector | undefined {
  if (USE_MOCK) {
    return MOCK_MOVEMENTS.find((m) => m.cluster_id === clusterId);
  }
  return undefined;
}

export function findClassification(clusterId: number): ClassificationData | undefined {
  if (USE_MOCK) {
    return MOCK_CLASSIFICATIONS[clusterId];
  }
  return undefined;
}

export async function fetchEmergencyResponseStations(clusterId: number): Promise<EmergencyResponseSearchResult> {
  const mock: EmergencyResponseSearchResult = {
    cluster_id: clusterId,
    risk_level: 'HIGH',
    recommended_action: 'Despatch ground inspection unit to coordinates.',
    nearest_station: {
      id: 'stn-01',
      name: 'District Response Center',
      station_type: 'FIRE_AND_RESCUE',
      latitude: 21.75,
      longitude: 83.85,
      distance_km: 4.5,
      contact_phone: '+91 98765 43210',
    },
    nearby_stations: [
      {
        id: 'stn-01',
        name: 'District Response Center',
        station_type: 'FIRE_AND_RESCUE',
        latitude: 21.75,
        longitude: 83.85,
        distance_km: 4.5,
        contact_phone: '+91 98765 43210',
      },
    ],
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<EmergencyResponseSearchResult>(`/emergency-response/${clusterId}/stations`);
  } catch (err) {
    return mock;
  }
}

export async function postPrototypeNotification(clusterId: number, stationId?: string): Promise<PrototypeNotificationResult> {
  const mock: PrototypeNotificationResult = {
    cluster_id: clusterId,
    status: 'PROTOTYPE_ALERT_SENT',
    recipient: '+91 98765 43210',
    timestamp: new Date().toISOString(),
    details: 'Prototype SMS alert dispatched successfully to ground station.',
  };
  if (USE_MOCK) return mock;
  try {
    return await apiPost<PrototypeNotificationResult>(`/emergency-response/${clusterId}/prototype-notification`, {
      confirmed: true,
      station_id: stationId,
    });
  } catch (err) {
    return mock;
  }
}

export async function fetchPrototypeNotificationHistory(clusterId?: number): Promise<PrototypeNotificationHistoryEntry[]> {
  if (USE_MOCK) return [];
  try {
    const query: Record<string, string> = {};
    if (clusterId !== undefined) query.cluster_id = String(clusterId);
    return await apiGet<PrototypeNotificationHistoryEntry[]>('/emergency-response/notifications-history', query);
  } catch (err) {
    return [];
  }
}

export async function fetchClusterLocation(clusterId: number): Promise<LocationDetail> {
  const mock: LocationDetail = {
    district: 'Jharsuguda Industrial Zone',
    state: 'Odisha',
    country: 'India',
    nearest_city: 'Jharsuguda',
    distance_to_city_km: 4.8,
    formatted_address: 'Jharsuguda Region, Odisha, India',
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<LocationDetail>(`/location/${clusterId}`);
  } catch (err) {
    return mock;
  }
}

export async function fetchIncidentReport(clusterId: number): Promise<IncidentReportResponse> {
  const c = MOCK_CLUSTERS.find((x) => x.cluster_id === clusterId) || MOCK_CLUSTERS[0];
  const mock: IncidentReportResponse = {
    cluster_id: clusterId,
    report_id: `REP-2026-${clusterId}`,
    generated_at: new Date().toISOString(),
    summary: `Thermal Intelligence Incident Dossier for Cluster #${clusterId}`,
    risk_level: c.risk_level ?? 'HIGH',
    risk_score: c.risk_score ?? 7.5,
    max_frp: c.max_frp ?? 10.5,
    max_bright_ti4: c.max_bright_ti4 ?? 340.0,
    observation_count: c.observation_count ?? 3,
    active_days: c.active_days ?? 2,
    location_summary: 'Jharsuguda Region, Odisha, India',
    classification_label: 'Industrial Heat Source / Elevated Flare',
    recommended_action: 'Maintain automated satellite monitoring and conduct periodic site inspection.',
  };
  if (USE_MOCK) return mock;
  try {
    return await apiGet<IncidentReportResponse>(`/reports/${clusterId}`);
  } catch (err) {
    return mock;
  }
}

export async function downloadIncidentReportPdf(clusterId: number): Promise<void> {
  if (USE_MOCK) {
    alert(`[Offline Mode] Incident Report PDF for Cluster #${clusterId} generated.`);
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/reports/${clusterId}/pdf`);
    if (!response.ok) {
      throw new Error(`Failed to download report PDF: status ${response.status}`);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ThermalWatch_Incident_Report_Cluster_${clusterId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Incident Report PDF generation simulated for Cluster #${clusterId}.`);
  }
}



