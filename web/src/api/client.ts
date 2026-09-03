/**
 * API client — connects to the FastAPI backend at localhost:8000.
 * The Vite dev server proxies /api → localhost:8000.
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
} from '../types';

// Set to true to use mock data for offline development
const USE_MOCK = false;

// ---------------------------------------------------------------------------
// Mock data imports (used only when USE_MOCK = true)
// ---------------------------------------------------------------------------
import { MOCK_EVENTS, MOCK_CLUSTERS, MOCK_MOVEMENTS, MOCK_STATISTICS } from '../data/mockData';
import { MOCK_CLASSIFICATIONS } from '../data/classifications';

// ---------------------------------------------------------------------------
// Backend API helpers
// ---------------------------------------------------------------------------

const API_BASE = '/api/v1';

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
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

export async function fetchClusters(filters: FilterState): Promise<ClusterSummary[]> {
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
    // Mock mode has no alert dataset; returning [] keeps the UI honest rather
    // than inventing alerts for offline development.
    return [];
  }
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
export async function fetchClusterDetail(clusterId: number): Promise<ClusterDetail> {
  return apiGet<ClusterDetail>(`/events/${clusterId}`);
}

export async function fetchClassificationDetail(clusterId: number): Promise<ClassificationDetailData> {
  return apiGet<ClassificationDetailData>(`/classification/${clusterId}`);
}

export async function fetchRiskDetail(clusterId: number): Promise<RiskDetailData> {
  return apiGet<RiskDetailData>(`/risk/${clusterId}`);
}

export async function fetchResponseDetail(clusterId: number): Promise<ResponseDetailData> {
  return apiGet<ResponseDetailData>(`/response/${clusterId}`);
}

export async function fetchMovementForCluster(clusterId: number): Promise<MovementVector | null> {
  const rows = await apiGet<MovementVector[]>(`/movement?cluster_id=${clusterId}`);
  return rows.length > 0 ? rows[0] : null;
}

/** Merge cluster summary data into events for the detail panel (mock mode only). */
export function findClusterSummary(clusterId: number): ClusterSummary | undefined {
  if (USE_MOCK) {
    return MOCK_CLUSTERS.find((c) => c.cluster_id === clusterId);
  }
  // For real API mode, we fetch clusters on demand
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
