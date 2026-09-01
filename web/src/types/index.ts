/** Detection-level record (from gis_thermal_events.csv — 4,524 rows) */
export interface ThermalEvent {
  detection_id: string;
  latitude: number;
  longitude: number;
  acq_date: string;
  cluster_id: number;
  persistence_category: string;
  anomaly_score: number;
  anomaly_flag: number;
  abnormality_level: 'NORMAL' | 'ELEVATED' | 'HIGH';
  anomaly_characterization: string;
  explanation: string;
  contributing_factors: string;
  bright_ti4: number;
  bright_ti5: number;
  frp: number;
  confidence: string;
  satellite: string;
  scan: number;
  track: number;
  acq_time: string;
  instrument: string;
  source_satellite: string;
  source_file: string;
  acquisition_datetime: string;
}

/** Cluster-level record (from firms_risk_results.csv — 1,792 rows) */
export interface ClusterSummary {
  cluster_id: number;
  latitude?: number;
  longitude?: number;
  observation_count: number;
  active_days: number;
  first_detection: string;
  last_detection: string;
  duration_days: number;
  mean_bright_ti4: number;
  max_bright_ti4: number;
  mean_bright_ti5: number;
  max_bright_ti5: number;
  mean_frp: number;
  max_frp: number;
  mean_confidence: number;
  persistence_score: number;
  persistence_category: string;
  bt_diff_mean: number;
  bt_diff_max: number;
  frp_mean_to_max_ratio: number;
  detection_density: number;
  active_day_ratio: number;
  is_multi_day: number;
  is_persistent_candidate: number;
  persistence_category_code: number;
  anomaly_score: number;
  anomaly_flag: number;
  abnormality_level: 'NORMAL' | 'ELEVATED' | 'HIGH';
  anomaly_characterization: string;
  explanation: string;
  contributing_factors: string;
  false_alarm_indicator: 'LOW' | 'MEDIUM' | 'HIGH';
  false_alarm_reasons: string;
  detection_reliability: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  risk_factors: string;
  risk_explanation: string;
}

/** Movement vector record (from thermal_movement.csv — 1,792 rows) */
export interface MovementVector {
  cluster_id: number;
  observation_count: number;
  active_days: number;
  first_detection: string;
  last_detection: string;
  time_span_days: number;
  start_latitude: number;
  start_longitude: number;
  end_latitude: number;
  end_longitude: number;
  total_movement_distance_km: number;
  movement_rate_km_per_day: number;
  movement_bearing_degrees: number;
  movement_direction: string;
  movement_confidence: string;
  movement_status: 'MOVING' | 'STATIONARY' | 'INSUFFICIENT_DATA';
}

/** Dashboard aggregated statistics */
export interface DashboardStats {
  total_detections: number;
  active_clusters: number;
  high_risk_count: number;
  moving_count: number;
  high_false_alarm_count: number;
  anomaly_distribution: { NORMAL: number; ELEVATED: number; HIGH: number };
  risk_distribution: { LOW: number; MEDIUM: number; HIGH: number };
  false_alarm_distribution: { LOW: number; MEDIUM: number; HIGH: number };
  movement_distribution: { INSUFFICIENT_DATA: number; STATIONARY: number; MOVING: number };
}

/** Industrial fire classification record (from firms_industrial_classification.csv — 1,792 rows) */
export interface ClassificationData {
  cluster_id: number;
  classification_label: string;
  classification_score: number;
  classification_rationale: string;
  active_days: number;
  persistence_category: string;
  max_bright_ti4: number;
  bt_diff_max: number;
  max_frp: number;
  movement_status: string;
  total_movement_distance_km: number;
  osm_facility_type: string;
  osm_distance_km: number;
  land_cover_class: string;
}

/** Active filter state */
export interface FilterState {
  riskLevel: string[];
  abnormalityLevel: string[];
  falseAlarmConcern: string[];
  movementStatus: string[];
  persistenceCategory: string[];
  dateRange: { start: string; end: string } | null;
  satellite: string[];
}

export const EMPTY_FILTERS: FilterState = {
  riskLevel: [],
  abnormalityLevel: [],
  falseAlarmConcern: [],
  movementStatus: [],
  persistenceCategory: [],
  dateRange: null,
  satellite: [],
};
