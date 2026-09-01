import { findClusterSummary, findMovement, findClassification } from '../api/client';
import RiskGauge from './RiskGauge';
import type { ThermalEvent } from '../types';
import { formatCoordinate, formatDistance, formatRate, formatDegrees } from '../utils/formatters';

interface EventDetailPanelProps {
  event: ThermalEvent | null;
  onClose: () => void;
}

export default function EventDetailPanel({ event, onClose }: EventDetailPanelProps) {
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

  const cluster = findClusterSummary(event.cluster_id);
  const movement = findMovement(event.cluster_id);
  const classification = findClassification(event.cluster_id);

  const abnormalityColor =
    event.abnormality_level === 'HIGH' ? 'text-red-600' :
    event.abnormality_level === 'ELEVATED' ? 'text-orange-600' :
    'text-green-600';

  return (
    <aside className="w-80 flex-shrink-0 bg-white border-l border-slate-200 overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-navy-900">
            Cluster #{event.cluster_id}
          </h2>
          <p className="text-xs text-slate-500">
            {formatCoordinate(event.latitude, event.longitude)}
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

      {/* Risk Gauge */}
      {cluster && (
        <div className="px-4 py-4 border-b border-slate-100 flex justify-center">
          <RiskGauge score={cluster.risk_score} level={cluster.risk_level} />
        </div>
      )}

      {/* AI Assessment */}
      <div className="px-4 py-3 border-b border-slate-100">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          AI Assessment
        </h3>
        <div className="space-y-2">
          <InfoRow label="AI Abnormality" value={event.abnormality_level} valueClass={abnormalityColor} />
          {cluster && (
            <>
              <InfoRow label="Detection Reliability" value={cluster.detection_reliability}
                valueClass={cluster.detection_reliability === 'HIGH' ? 'text-green-600' : cluster.detection_reliability === 'LOW' ? 'text-red-600' : 'text-amber-600'} />
              <InfoRow label="False Alarm Concern" value={cluster.false_alarm_indicator}
                valueClass={cluster.false_alarm_indicator === 'LOW' ? 'text-green-600' : cluster.false_alarm_indicator === 'HIGH' ? 'text-red-600' : 'text-amber-600'} />
              <InfoRow label="Persistence" value={cluster.persistence_category?.replace(/_/g, ' ') ?? '—'} valueClass="text-slate-700" />
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
          <InfoRow label="FRP" value={`${event.frp.toFixed(1)} MW`} />
          <InfoRow label="Brightness TI4" value={`${event.bright_ti4.toFixed(1)} K`} />
          {event.bright_ti5 > 0 && <InfoRow label="Brightness TI5" value={`${event.bright_ti5.toFixed(1)} K`} />}
          {cluster && (
            <>
              <InfoRow label="Observations" value={String(cluster.observation_count)} />
              <InfoRow label="Active Days" value={String(cluster.active_days)} />
              <InfoRow label="Duration" value={`${cluster.duration_days} days`} />
              <InfoRow label="Date Range" value={`${cluster.first_detection} — ${cluster.last_detection}`} />
            </>
          )}
          <InfoRow label="Satellite" value={event.source_satellite || '—'} />
        </div>
      </div>

      {/* AI Characterization */}
      <div className="px-4 py-3 border-b border-slate-100">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          AI Characterization
        </h3>
        <div className="space-y-2">
          <InfoRow label="Classification" value={event.anomaly_characterization?.replace(/_/g, ' ') ?? '—'} valueClass="text-slate-700" />
          {cluster?.contributing_factors && cluster.contributing_factors !== 'none' && (
            <div>
              <span className="text-xs text-slate-500 block mb-1">Contributing Factors</span>
              <div className="flex flex-wrap gap-1">
                {cluster.contributing_factors.split(',').map((f, i) => (
                  <span key={i} className="inline-block px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">
                    {f.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fire Source Classification */}
      {classification && (
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Fire Source Classification
          </h3>
          <div className="space-y-2">
            {/* Classification Label */}
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs text-slate-500 flex-shrink-0">Classification</span>
              <span className={`text-xs font-semibold text-right ${
                classification.classification_label.includes('Industrial') ? 'text-red-700' :
                classification.classification_label.includes('Agricultural') ? 'text-amber-700' :
                classification.classification_label.includes('Forest') ? 'text-green-700' :
                'text-slate-500'
              }`}>
                {classification.classification_label}
              </span>
            </div>
            {/* Classification Score */}
            <InfoRow
              label="Classification Score"
              value={classification.classification_score.toFixed(2)}
              valueClass="text-slate-700"
            />
            {/* Supporting Evidence / Rationale */}
            <div className="mt-1">
              <span className="text-xs text-slate-500 block mb-1">Supporting Evidence</span>
              <div className="bg-slate-50 border border-slate-100 rounded p-2">
                {classification.classification_rationale.split('\n').map((line, i) => {
                  // First line is the label itself — skip it, we show it above
                  if (i === 0) return null;
                  // Section header lines
                  if (line.startsWith('Supporting evidence:')) {
                    return (
                      <span key={i} className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-0.5">
                        {line.replace(':', '')}
                      </span>
                    );
                  }
                  // Bullet points
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
          </div>
        </div>
      )}

      {/* Why Flagged */}
      <div className="px-4 py-3 border-b border-slate-100">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Why This Event Is Flagged
        </h3>
        <p className="text-xs text-slate-600 leading-relaxed">
          {event.explanation || 'No explanation available.'}
        </p>
        {cluster?.risk_explanation && (
          <p className="text-xs text-slate-600 leading-relaxed mt-2">
            {cluster.risk_explanation}
          </p>
        )}
        {cluster?.risk_factors && cluster.risk_factors !== 'Standard thermal baseline' && (
          <div className="mt-2 flex flex-wrap gap-1">
            {cluster.risk_factors.split('; ').map((f, i) => (
              <span key={i} className="inline-block px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">
                {f}
              </span>
            ))}
          </div>
        )}
        {cluster?.false_alarm_reasons && cluster.false_alarm_reasons !== 'strong supporting evidence' && (
          <p className="text-xs text-slate-500 mt-2 italic">
            False-alarm reasons: {cluster.false_alarm_reasons}
          </p>
        )}
      </div>

      {/* Thermal Activity Movement */}
      {movement && (
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Thermal Activity Movement
          </h3>
          <div className="space-y-2">
            <InfoRow label="Status" value={movement.movement_status}
              valueClass={movement.movement_status === 'MOVING' ? 'text-amber-600' : movement.movement_status === 'STATIONARY' ? 'text-green-600' : 'text-slate-500'} />
            {movement.movement_status === 'MOVING' && (
              <>
                <InfoRow label="Direction" value={movement.movement_direction} />
                <InfoRow label="Bearing" value={formatDegrees(movement.movement_bearing_degrees)} />
                <InfoRow label="Distance" value={formatDistance(movement.total_movement_distance_km)} />
                <InfoRow label="Rate" value={formatRate(movement.movement_rate_km_per_day)} />
                <InfoRow label="Confidence" value={movement.movement_confidence} />
                <InfoRow label="Time Span" value={`${movement.time_span_days.toFixed(1)} days`} />
              </>
            )}
          </div>
        </div>
      )}

      {/* Safety Note */}
      <div className="px-4 py-2">
        <p className="text-[10px] text-slate-400 leading-relaxed">
          This dashboard is a decision-support tool. Risk indices and anomaly assessments are
          experimental and should not be treated as confirmed physical hazard declarations.
        </p>
      </div>
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
