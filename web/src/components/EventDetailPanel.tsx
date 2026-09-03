import { useEffect, useState } from 'react';
import RiskGauge from './RiskGauge';
import {
  fetchClusterDetail,
  fetchClassificationDetail,
  fetchRiskDetail,
  fetchResponseDetail,
  fetchMovementForCluster,
} from '../api/client';
import type {
  ThermalEvent,
  ClusterDetail,
  ClassificationDetailData,
  RiskDetailData,
  ResponseDetailData,
  MovementVector,
} from '../types';
import { formatCoordinate, formatDistance, formatRate, formatDegrees } from '../utils/formatters';

interface EventDetailPanelProps {
  event: ThermalEvent | null;
  onClose: () => void;
}

export default function EventDetailPanel({ event, onClose }: EventDetailPanelProps) {
  const [detail, setDetail] = useState<ClusterDetail | null>(null);
  const [classification, setClassification] = useState<ClassificationDetailData | null>(null);
  const [risk, setRisk] = useState<RiskDetailData | null>(null);
  const [response, setResponse] = useState<ResponseDetailData | null>(null);
  const [movement, setMovement] = useState<MovementVector | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clusterId = event?.cluster_id ?? null;

  useEffect(() => {
    if (clusterId === null) {
      setDetail(null);
      setClassification(null);
      setRisk(null);
      setResponse(null);
      setMovement(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchClusterDetail(clusterId),
      fetchClassificationDetail(clusterId),
      fetchRiskDetail(clusterId),
      fetchResponseDetail(clusterId),
      fetchMovementForCluster(clusterId),
    ])
      .then(([d, c, r, resp, m]) => {
        if (cancelled) return;
        setDetail(d);
        setClassification(c);
        setRisk(r);
        setResponse(resp);
        setMovement(m);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(`Unable to load cluster details: ${err.message}`);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [clusterId]);

  if (!event) {
    return (
      <aside className="w-80 flex-shrink-0 bg-white border-l border-slate-200 overflow-y-auto flex items-center justify-center">
        <div className="text-center px-6">
          <svg className="w-10 h-10 text-slate-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
          </svg>
          <p className="text-sm text-slate-400">Select an event on the map or table</p>
        </div>
      </aside>
    );
  }

  const riskScore = risk?.risk_score ?? detail?.risk_score ?? 0;
  const riskLevel = risk?.risk_level ?? detail?.risk_level ?? 'LOW';
  const abnormalityColor =
    event.abnormality_level === 'HIGH' ? 'text-red-600' :
    event.abnormality_level === 'ELEVATED' ? 'text-orange-600' :
    'text-green-600';

  // Satellite context: honest representation (a land-cover CNN is context, not a fire detector)
  const satClass = classification?.predicted_landcover_class ?? 'UNKNOWN';
  const satConf = classification?.prediction_confidence ?? 0;
  const hasSatellite = satClass && satClass !== 'UNKNOWN' && satClass !== 'None' && satConf > 0;

  return (
    <aside className="w-80 flex-shrink-0 bg-white border-l border-slate-200 overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-navy-900">
            Cluster #{event.cluster_id}
          </h2>
          <p className="text-xs text-slate-500">
            {detail ? formatCoordinate(detail.latitude, detail.longitude) : formatCoordinate(event.latitude, event.longitude)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {loading && (
        <div className="px-4 py-6 text-center text-xs text-slate-400">Loading cluster intelligence…</div>
      )}

      {!loading && error && (
        <div className="px-4 py-6 text-center text-xs text-red-500">{error}</div>
      )}

      {!loading && !error && (
        <>
          {/* Risk Gauge */}
          <div className="px-4 py-4 border-b border-slate-100 flex justify-center">
            <RiskGauge score={riskScore} level={riskLevel} />
          </div>

          {/* AI Assessment */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              AI Assessment
            </h3>
            <div className="space-y-2">
              <InfoRow label="AI Abnormality" value={event.abnormality_level || 'NORMAL'} valueClass={abnormalityColor} />
              {detail && (
                <>
                  <InfoRow label="Detection Reliability" value={detail.detection_reliability}
                    valueClass={detail.detection_reliability === 'HIGH' ? 'text-green-600' : detail.detection_reliability === 'LOW' ? 'text-red-600' : 'text-amber-600'} />
                  <InfoRow label="False Alarm Concern" value={detail.false_alarm_indicator}
                    valueClass={detail.false_alarm_indicator === 'LOW' ? 'text-green-600' : detail.false_alarm_indicator === 'HIGH' ? 'text-red-600' : 'text-amber-600'} />
                  <InfoRow label="Persistence" value={detail.persistence_category?.replace(/_/g, ' ') || '—'} valueClass="text-slate-700" />
                </>
              )}
            </div>
          </div>

          {/* Thermal Evidence */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Thermal Evidence
            </h3>
            <div className="space-y-2">
              <InfoRow label="Max FRP" value={`${(detail?.max_frp ?? event.frp ?? 0).toFixed(1)} MW`} />
              <InfoRow label="Brightness TI4" value={`${(detail?.max_bright_ti4 ?? event.bright_ti4 ?? 0).toFixed(1)} K`} />
              {detail && (
                <>
                  <InfoRow label="BT Contrast (max)" value={`${(detail.bt_diff_max ?? 0).toFixed(1)} K`} />
                  <InfoRow label="Observations" value={String(detail.observation_count)} />
                  <InfoRow label="Active Days" value={String(detail.active_days)} />
                  <InfoRow label="Duration" value={detail.duration_days != null ? `${detail.duration_days} days` : '—'} />
                  <InfoRow label="Date Range" value={`${detail.first_detection} — ${detail.last_detection}`} />
                </>
              )}
            </div>
          </div>

          {/* Fire Source Classification */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Event Source Classification
            </h3>
            <div className="space-y-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-xs text-slate-500 flex-shrink-0">Classification</span>
                <span className={`text-xs font-semibold text-right ${
                  (classification?.classification_label ?? '').includes('Industrial') ? 'text-red-700' :
                  (classification?.classification_label ?? '').includes('Agricultural') ? 'text-amber-700' :
                  (classification?.classification_label ?? '').includes('Forest') ? 'text-green-700' :
                  'text-slate-500'
                }`}>
                  {classification?.classification_label ?? '—'}
                </span>
              </div>
              {classification && (
                <>
                  <InfoRow label="Classification Score" value={classification.classification_score.toFixed(2)} valueClass="text-slate-700" />
                  <div className="mt-1">
                    <span className="text-xs text-slate-500 block mb-1">Supporting Evidence</span>
                    <div className="bg-slate-50 border border-slate-100 rounded p-2 max-h-40 overflow-y-auto">
                      {(classification.classification_rationale ?? '').split('\n').map((line, i) => {
                        if (i === 0) return null;
                        if (line.startsWith('Supporting evidence:')) {
                          return (
                            <span key={i} className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-0.5">
                              {line.replace(':', '')}
                            </span>
                          );
                        }
                        if (line.startsWith('- ')) {
                          return (
                            <div key={i} className="flex gap-1.5 text-[11px] text-slate-600 leading-relaxed">
                              <span className="text-slate-300 flex-shrink-0">•</span>
                              <span>{line.substring(2)}</span>
                            </div>
                          );
                        }
                        return line ? <span key={i} className="block text-[11px] text-slate-600">{line}</span> : null;
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* OSM Industrial Context */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              OSM Industrial Context
            </h3>
            {classification && (
              <div className="space-y-2">
                {classification.osm_facility_type && !['none', 'UNKNOWN'].includes(classification.osm_facility_type) ? (
                  <>
                    <InfoRow label="Facility Type" value={classification.osm_facility_type} valueClass="text-slate-700" />
                    <InfoRow
                      label="Distance"
                      value={classification.osm_distance_km != null && isFinite(classification.osm_distance_km)
                        ? `${classification.osm_distance_km.toFixed(2)} km`
                        : '—'}
                    />
                  </>
                ) : (
                  <p className="text-xs text-slate-500 leading-relaxed">
                    No industrial facility found within 2 km (OSM). Absence of a nearby facility is not
                    evidence of a non-industrial source.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Satellite Context */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Satellite Context
            </h3>
            {hasSatellite ? (
              <div className="space-y-2">
                <InfoRow label="Land-cover (CNN)" value={satClass} valueClass="text-slate-700" />
                <InfoRow label="Model Confidence" value={satConf.toFixed(2)} />
                <p className="text-[10px] text-slate-400 leading-relaxed">
                  Land-cover/context classification from Sentinel-2 imagery. Not a fire detector.
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-500 leading-relaxed">
                Satellite observation unavailable or obscured by cloud cover. Cloud-obscured imagery is
                not negative evidence.
              </p>
            )}
          </div>

          {/* Why Flagged */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Why This Event Is Flagged
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              {event.explanation || detail?.explanation || 'No explanation available.'}
            </p>
            {risk?.risk_explanation && (
              <p className="text-xs text-slate-600 leading-relaxed mt-2">{risk.risk_explanation}</p>
            )}
            {risk?.risk_factors && risk.risk_factors !== 'Standard thermal baseline' && (
              <div className="mt-2 flex flex-wrap gap-1">
                {risk.risk_factors.split('; ').map((f, i) => (
                  <span key={i} className="inline-block px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Thermal Activity Direction (movement of detected thermal activity) */}
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Thermal Activity Direction
            </h3>
            {!movement ? (
              <p className="text-xs text-slate-500">No movement data available for this cluster.</p>
            ) : (
              <div className="space-y-2">
                {movement.movement_status === 'MOVING' && movement.direction_available ? (
                  <>
                    <InfoRow label="Direction" value={movement.direction ?? 'Not available'}
                      valueClass="text-amber-700 font-semibold" />
                    <InfoRow label="Bearing" value={formatDegrees(movement.movement_bearing_degrees)} />
                    <InfoRow label="Movement Rate" value={formatRate(movement.movement_rate_km_per_day)} />
                    <InfoRow label="Total Displacement" value={formatDistance(movement.total_movement_distance_km)} />
                    <InfoRow label="Active Days" value={String(movement.active_days)} />
                    <InfoRow label="Direction Confidence" value={movement.direction_confidence}
                      valueClass={movement.direction_confidence === 'HIGH' ? 'text-green-700 font-semibold' : movement.direction_confidence === 'MODERATE' ? 'text-amber-600' : 'text-slate-500'} />
                    <InfoRow label="Movement Pattern" value={movement.movement_pattern === 'directional' ? 'Directional' : 'Erratic'} />
                  </>
                ) : (
                  <>
                    <InfoRow label="Movement Pattern"
                      value={movement.movement_pattern === 'stationary' ? 'Stationary' : movement.movement_pattern === 'erratic' ? 'Erratic' : 'Insufficient evidence'}
                      valueClass={movement.movement_pattern === 'stationary' ? 'text-green-700' : 'text-slate-500'} />
                    <InfoRow label="Direction" value="Not available" />
                    {movement.movement_status === 'MOVING' && movement.movement_pattern === 'erratic' && (
                      <p className="text-[11px] text-slate-500 leading-relaxed">
                        Net displacement exists but day-to-day directions contradict — no single
                        defensible direction.
                      </p>
                    )}
                    {movement.movement_pattern === 'stationary' && (
                      <InfoRow label="Active Days" value={String(movement.active_days)} />
                    )}
                  </>
                )}
                <p className="text-[10px] text-slate-400 leading-relaxed pt-1 border-t border-slate-100">
                  Direction indicates movement of detected thermal activity. It does not by itself
                  confirm physical fire-front propagation.
                </p>
              </div>
            )}
          </div>

          {/* Operational Response */}
          {response && (
            <div className="px-4 py-3 border-b border-slate-100">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Operational Response (Decision Support)
              </h3>
              <div className="space-y-2">
                <InfoRow label="Alert Priority" value={response.alert_priority}
                  valueClass={response.alert_priority.includes('HIGH') ? 'text-red-600' : response.alert_priority.includes('MONITOR') ? 'text-amber-600' : 'text-green-600'} />
                {response.nearest_station_name && !response.nearest_station_name.toLowerCase().includes('no fire station') && (
                  <>
                    <InfoRow label="Nearest Fire Station" value={response.nearest_station_name} valueClass="text-slate-700" />
                    <InfoRow label="Station Distance" value={response.station_distance_km != null ? `${response.station_distance_km.toFixed(1)} km` : '—'} />
                  </>
                )}
                {response.station_distance_km == null && (
                  <p className="text-xs text-slate-500 italic">
                    No verified fire station within the search radius — contact the nearest district fire service.
                  </p>
                )}
                <p className="text-xs text-slate-600 leading-relaxed mt-1">{response.recommended_action}</p>
              </div>
            </div>
          )}

          {/* Safety Note */}
          <div className="px-4 py-2">
            <p className="text-[10px] text-slate-400 leading-relaxed">
              This dashboard is a decision-support tool. Risk indices and anomaly assessments are
              experimental and should not be treated as confirmed fire declarations.
            </p>
          </div>
        </>
      )}
    </aside>
  );
}

function InfoRow({ label, value, valueClass = 'text-slate-700' }: {
  label: string; value: string; valueClass?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-slate-500 flex-shrink-0">{label}</span>
      <span className={`text-xs font-medium text-right ${valueClass}`}>{value}</span>
    </div>
  );
}
