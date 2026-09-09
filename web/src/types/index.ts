/** Detection-level record (from gis_thermal_events.csv â€” 4,524 rows) */
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

/** Cluster-level record (from firms_risk_results.csv â€” 1,792 rows) */
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

/** Movement vector record (from thermal_movement.csv â€” 1,792 rows) */
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
  /** Direction intelligence â€” movement of DETECTED THERMAL ACTIVITY, not confirmed fire spread. */
  direction: string | null;
  movement_pattern: 'directional' | 'erratic' | 'stationary' | 'insufficient_evidence';
  direction_confidence: 'HIGH' | 'MODERATE' | 'PRELIMINARY' | 'INSUFFICIENT';
  direction_confidence_score: number;
  direction_available: boolean;
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

/** Industrial fire classification record (from firms_industrial_classification.csv â€” 1,792 rows) */
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

export interface LocationDetail {
  latitude: number;
  longitude: number;
  state: string;
  district: string;
  city_town: string;
  locality_colony: string;
  street_road: string;
  landmark: string;
  postcode: string;
  display_name: string;
  formatted_location_header: string;
}

/** Cluster-level detail from /api/v1/events/{cluster_id} */
export interface ClusterDetail {
  cluster_id: number;
  latitude: number;
  longitude: number;
  observation_count: number;
  active_days: number;
  first_detection: string;
  last_detection: string;
  duration_days: number | null;
  persistence_category: string;
  max_frp: number;
  max_bright_ti4: number;
  bt_diff_max: number;
  abnormality_level: string;
  anomaly_characterization: string;
  explanation: string;
  false_alarm_indicator: string;
  false_alarm_reasons?: string;
  detection_reliability: string;
  risk_score: number;
  risk_level: string;
  classification_label: string;
  classification_score: number;
  classification_rationale: string;
  movement_status: string;
  total_movement_distance_km: number;
  location?: LocationDetail;
}


/** Classification + OSM + satellite context from /api/v1/classification/{cluster_id} */
export interface ClassificationDetailData {
  cluster_id: number;
  classification_label: string;
  classification_score: number;
  classification_rationale: string;
  osm_facility_type: string;
  osm_distance_km: number;
  predicted_landcover_class: string;
  prediction_confidence: number;
}

/** One contribution to the existing Risk Index (raw points out of max_points). */
export interface RiskEvidenceComponent {
  key: string;
  label: string;
  points: number;
  max_points: number;
  detail: string;
}

/** Backward-compatible breakdown of the existing risk score (final_score === risk_score). */
export interface RiskEvidence {
  components: RiskEvidenceComponent[];
  reliability_multiplier: number;
  false_alarm_concern: string;
  base_score: number;
  final_score: number;
}

/** Risk intelligence from /api/v1/risk/{cluster_id} */
export interface RiskDetailData {
  cluster_id: number;
  risk_score: number;
  risk_level: string;
  risk_factors: string;
  risk_explanation: string;
  risk_evidence?: RiskEvidence | null;
}

/** Response/alert detail from /api/v1/response/{cluster_id} */
export interface ResponseDetailData {
  cluster_id: number;
  risk_score: number;
  risk_level: string;
  alert_priority: string;
  recommended_action: string;
  nearest_station_name: string;
  station_distance_km: number | null;
  station_available: boolean;
  alert_rationale: string;
  is_decision_support_only: boolean;
}

/** Thermal alert record from the Thermal Alert Engine (/api/v1/alerts).
 *  Decision-support classification of processed thermal evidence â€” never a
 *  confirmed fire declaration. */
export interface ThermalAlert {
  alert_id: string;
  cluster_id: number;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';
  evidence_confidence: 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT';
  suppressed: boolean;
  suppression_reason: string;
  risk_score: number | null;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  classification_label: string;
  classification_score: number | null;
  false_alarm_indicator: 'LOW' | 'MEDIUM' | 'HIGH';
  detection_reliability: 'HIGH' | 'MEDIUM' | 'LOW';
  observation_count: number;
  active_days: number;
  persistence_category: string;
  max_frp: number | null;
  max_bright_ti4: number | null;
  bt_diff_max: number | null;
  movement_direction: string | null;
  movement_bearing_degrees: number | null;
  movement_rate_km_per_day: number | null;
  movement_pattern: string;
  latitude: number | null;
  longitude: number | null;
  nearest_station_name: string;
  station_distance_km: number | null;
  station_available: boolean;
  reasons: string;
  alert_rationale: string;
  created_at: string;
  updated_at: string;
  is_decision_support_only: boolean;
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

export interface FireStationCandidate {
  station_id: string;
  station_name: string;
  station_latitude: number;
  station_longitude: number;
  distance_km: number;
  contact_phone: string | null;
  verified_source: string;
}

export interface EmergencyEventContext {
  cluster_id: number;
  alert_id: string;
  severity: string;
  risk_score: number;
  risk_level: string;
  classification_label: string;
  evidence_confidence: string;
  false_alarm_indicator: string;
  detection_reliability: string;
  observation_count: number;
  active_days: number;
  persistence_category: string;
  latitude: number;
  longitude: number;
  suppressed: boolean;
}

export interface EmergencyResponseSearchResult {
  cluster_id: number;
  search_radius_km: number;
  event: EmergencyEventContext;
  stations: FireStationCandidate[];
  nearest_station: FireStationCandidate | null;
  station_available: boolean;
  status_message: string;
  notification_eligible: boolean;
  eligibility_reason: string;
  is_decision_support_only: boolean;
}

export interface PrototypeNotificationResult {
  cluster_id: number;
  alert_id: string;
  send_status: string;
  recipient_masked: string;
  selected_station: FireStationCandidate;
  provider_message_id: string | null;
  is_decision_support_only: boolean;
  detail: string;
}

export interface PrototypeNotificationHistoryEntry {
  alert_id: string;
  cluster_id: number;
  timestamp: string;
  recipient_masked: string;
  severity: string;
  selected_station: string;
  distance_km: number | null;
  send_status: string;
  provider_message_id: string;
  failure_reason: string;
}

export interface IncidentReportResponse {
  title: string;
  report_generated_at: string;
  cluster_id: number;
  severity: string;
  risk_score: number;
  location: LocationDetail;
  observation_count: number;
  first_detected: string;
  last_detected: string;
  active_days: number;
  max_frp: number;
  brightness_temp_ti4: number;
  thermal_contrast_k: number;
  persistence_category: string;
  risk_level: string;
  risk_factors: string;
  false_alarm_concern: string;
  evidence_reliability_level: string;
  classification_label: string;
  classification_confidence: number;
  osm_industrial_context: string;
  sentinel2_cnn_context: string;
  cloud_imagery_limitations: string;
  movement_status: string;
  movement_direction: string;
  direction_confidence: string;
  displacement_km: number;
  movement_rate_km_per_day: number;
  directional_consistency: string;
  movement_disclaimer: string;
  nearby_industrial_infrastructure: string;
  nearby_roads: string;
  nearest_fire_station_name: string;
  distance_to_fire_station_km: string;
  nearby_landmarks: string;
  why_flagged_explanation: string;
  recommended_actions: string[];
  action_type: string;
  disclaimer: string;
}

