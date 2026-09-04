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
  const [copiedCoord, setCopiedCoord] = useState(false);

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
      <aside className="hidden lg:flex w-80 lg:w-96 flex-shrink-0 bg-slate-50/90 dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 overflow-y-auto items-center justify-center p-6 transition-colors duration-200">
        <div className="text-center max-w-xs">
          <div className="w-14 h-14 bg-white dark:bg-slate-800 rounded-2xl shadow-xs border border-slate-200 dark:border-slate-700 flex items-center justify-center mx-auto mb-4 text-slate-400">
            <svg className="w-7 h-7 animate-pulse text-navy-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100 tracking-tight mb-1">Select Thermal Cluster</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Click any active cluster marker on the GIS map or high-priority queue to load intelligence dossier.
          </p>
        </div>
      </aside>
    );
  }

  const riskScore = risk?.risk_score ?? detail?.risk_score ?? 0;
  const riskLevel = risk?.risk_level ?? detail?.risk_level ?? 'LOW';
  const abnormality = event.abnormality_level || detail?.abnormality_level || 'NORMAL';

  // Satellite context: honest representation (a land-cover CNN is context, not a fire detector)
  const satClass = classification?.predicted_landcover_class ?? 'UNKNOWN';
  const satConf = classification?.prediction_confidence ?? 0;
  const hasSatellite = satClass && satClass !== 'UNKNOWN' && satClass !== 'None' && satConf > 0;

  const lat = detail ? detail.latitude : event.latitude;
  const lon = detail ? detail.longitude : event.longitude;
  const coordText = formatCoordinate(lat, lon);

  const handleCopyCoord = () => {
    navigator.clipboard.writeText(`${lat.toFixed(5)}, ${lon.toFixed(5)}`);
    setCopiedCoord(true);
    setTimeout(() => setCopiedCoord(false), 2000);
  };

  const panelContent = (
    <div className="flex flex-col h-full overflow-hidden select-none">
      {/* Top Dossier Header */}
      <div className="bg-white dark:bg-slate-900 px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 shadow-2xs">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-navy-900 dark:bg-navy-700 text-white shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Cluster #{event.cluster_id}
            </span>
            <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              {event.instrument || 'VIIRS'} SENSOR
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Close dossier"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={handleCopyCoord}
            className="group flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 hover:text-navy-900 dark:hover:text-white font-mono bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 px-2 py-1 rounded transition-colors"
            title="Click to copy exact decimal coordinates"
          >
            <svg className="w-3.5 h-3.5 text-slate-400 group-hover:text-navy-700 dark:group-hover:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>{coordText}</span>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 ml-0.5">{copiedCoord ? '✓ Copied' : '⧉'}</span>
          </button>

          {detail && (
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              {detail.active_days} {detail.active_days === 1 ? 'day active' : 'days active'}
            </span>
          )}
        </div>
      </div>

      {/* Scrollable Dossier Content */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
        {loading && (
          <div className="py-12 text-center">
            <div className="w-8 h-8 border-2 border-navy-800 dark:border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">Synthesizing Cluster Intelligence…</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">Querying sensor radiometry & models</p>
          </div>
        )}

        {!loading && error && (
          <div className="p-4 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-900 rounded-xl text-center">
            <svg className="w-6 h-6 text-red-500 mx-auto mb-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <p className="text-xs font-bold text-red-700 dark:text-red-300">Cluster Intelligence Unavailable</p>
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1">{error}</p>
          </div>
        )}

        {!loading && !error && (
          <>
            {/* ================================================================= */}
            {/* PRIORITY 1: RISK & INTELLIGENCE ASSESSMENT                        */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Risk & AI Assessment
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P1 · PRIMARY</span>
              </div>

              <div className="p-3.5 space-y-3.5">
                {/* Visual Radial Gauge */}
                <div className="flex justify-center pt-1">
                  <RiskGauge score={riskScore} level={riskLevel} size={150} />
                </div>

                {/* 3-Column Intelligence Micro Indicators */}
                <div className="grid grid-cols-3 gap-1.5 pt-1">
                  {/* Abnormality Level */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2 text-center flex flex-col justify-between">
                    <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                      Abnormality
                    </span>
                    <span className={`inline-block text-[11px] font-bold px-1.5 py-0.5 rounded ${
                      abnormality === 'HIGH' ? 'bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900' :
                      abnormality === 'ELEVATED' ? 'bg-orange-100 dark:bg-orange-950/70 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-900' :
                      'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900'
                    }`}>
                      {abnormality}
                    </span>
                  </div>

                  {/* Detection Reliability */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2 text-center flex flex-col justify-between">
                    <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                      Reliability
                    </span>
                    <span className={`inline-block text-[11px] font-bold px-1.5 py-0.5 rounded ${
                      detail?.detection_reliability === 'HIGH' ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900' :
                      detail?.detection_reliability === 'LOW' ? 'bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900' :
                      'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900'
                    }`}>
                      {detail?.detection_reliability || 'MEDIUM'}
                    </span>
                  </div>

                  {/* False Alarm Concern */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2 text-center flex flex-col justify-between">
                    <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                      False Alarm
                    </span>
                    <span className={`inline-block text-[11px] font-bold px-1.5 py-0.5 rounded ${
                      detail?.false_alarm_indicator === 'LOW' ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900' :
                      detail?.false_alarm_indicator === 'HIGH' ? 'bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900' :
                      'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900'
                    }`}>
                      {detail?.false_alarm_indicator ? `${detail.false_alarm_indicator} CONCERN` : 'MODERATE'}
                    </span>
                  </div>
                </div>

                {/* Persistence Pill */}
                {detail && (
                  <div className="flex items-center justify-between text-xs bg-slate-50 dark:bg-slate-900/60 px-2.5 py-1.5 rounded-lg border border-slate-200/70 dark:border-slate-700/80">
                    <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                      <svg className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="font-medium">Persistence Footprint</span>
                    </div>
                    <span className="font-semibold text-slate-800 dark:text-slate-200 capitalize">
                      {detail.persistence_category?.replace(/_/g, ' ') || '—'}
                    </span>
                  </div>
                )}

                {/* Risk Explanation Text Box */}
                {risk?.risk_explanation && (
                  <div className="bg-slate-50/90 dark:bg-slate-900/60 border-l-2 border-red-500 p-2.5 rounded-r-lg">
                    <p className="text-[11px] font-medium text-slate-700 dark:text-slate-300 leading-relaxed">
                      {risk.risk_explanation}
                    </p>
                  </div>
                )}

                {/* Risk Factors Badges */}
                {risk?.risk_factors && risk.risk_factors !== 'Standard thermal baseline' && (
                  <div className="space-y-1.5 pt-0.5">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                      Active Risk Factors
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {risk.risk_factors.split('; ').map((f, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-50/80 dark:bg-red-950/60 border border-red-200/70 dark:border-red-900/70 text-red-800 dark:text-red-300 rounded-md text-[10px] font-medium"
                        >
                          <span className="w-1 h-1 rounded-full bg-red-500" />
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ================================================================= */}
            {/* PRIORITY 2: EVENT SOURCE CLASSIFICATION & OSM CONTEXT             */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Source Classification
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P2 · TAXONOMY</span>
              </div>

              <div className="p-3.5 space-y-3">
                {/* Classification Hero Badge */}
                <div className="bg-gradient-to-br from-slate-50 to-slate-100/80 dark:from-slate-900 dark:to-slate-850 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        (classification?.classification_label ?? '').includes('Industrial') ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300' :
                        (classification?.classification_label ?? '').includes('Forest') ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300' :
                        (classification?.classification_label ?? '').includes('Agricultural') ? 'bg-orange-100 dark:bg-orange-950/70 text-orange-700 dark:text-orange-300' :
                        'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                      }`}>
                        {(classification?.classification_label ?? '').includes('Industrial') ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                          </svg>
                        ) : (classification?.classification_label ?? '').includes('Forest') ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                          </svg>
                        )}
                      </div>
                      <div>
                        <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                          Identified Type
                        </span>
                        <h4 className="text-xs font-bold text-navy-900 dark:text-slate-100 leading-tight">
                          {classification?.classification_label ?? 'Unclassified Source'}
                        </h4>
                      </div>
                    </div>
                  </div>

                  {/* Confidence Progress Bar */}
                  {classification && (
                    <div className="space-y-1 pt-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-500 dark:text-slate-400 font-medium">Model Confidence</span>
                        <span className="font-mono font-bold text-navy-900 dark:text-slate-100">
                          {Math.round((classification.classification_score ?? 0) * 100)}%
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 ml-1">({classification.classification_score.toFixed(2)})</span>
                        </span>
                      </div>
                      <div className="w-full bg-slate-200/80 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            classification.classification_score >= 0.75 ? 'bg-emerald-500' :
                            classification.classification_score >= 0.5 ? 'bg-amber-500' : 'bg-slate-400'
                          }`}
                          style={{ width: `${Math.min(classification.classification_score * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Supporting Evidence Breakdown */}
                {classification?.classification_rationale && (
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                      Supporting Analytical Evidence
                    </span>
                    <div className="bg-slate-50 dark:bg-slate-900/60 rounded-lg p-2.5 border border-slate-200/70 dark:border-slate-700 space-y-1.5 max-h-44 overflow-y-auto">
                      {(classification.classification_rationale ?? '').split('\n').map((line, i) => {
                        if (i === 0) return null;
                        if (line.startsWith('Supporting evidence:')) return null;
                        if (line.startsWith('- ')) {
                          const clean = line.substring(2);
                          return (
                            <div key={i} className="flex items-start gap-1.5 text-[11px] text-slate-700 dark:text-slate-300 leading-tight">
                              <span className="text-navy-600 dark:text-blue-400 font-bold flex-shrink-0 mt-0.5">›</span>
                              <span>{clean}</span>
                            </div>
                          );
                        }
                        return line.trim() ? (
                          <p key={i} className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal">
                            {line}
                          </p>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                {/* OSM Industrial Proximity Context */}
                <div className="pt-2 border-t border-slate-100 dark:border-slate-700/60">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                      OSM Infrastructure Intelligence
                    </span>
                  </div>

                  {classification?.osm_facility_type && !['none', 'UNKNOWN'].includes(classification.osm_facility_type) ? (
                    <div className="bg-blue-50/60 dark:bg-blue-950/40 border border-blue-200/70 dark:border-blue-900/70 rounded-lg p-2.5 flex items-center justify-between">
                      <div>
                        <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium block">Nearest Mapped Facility</span>
                        <span className="text-xs font-bold text-blue-950 dark:text-blue-200 capitalize">
                          {classification.osm_facility_type.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium block">Distance</span>
                        <span className="text-xs font-mono font-bold text-blue-900 dark:text-blue-300">
                          {classification.osm_distance_km != null && isFinite(classification.osm_distance_km)
                            ? `${classification.osm_distance_km.toFixed(2)} km`
                            : '—'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700 rounded-lg p-2 text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                      No industrial facility found within 2 km (OSM). Absence of a nearby facility is not
                      evidence of a non-industrial source.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* ================================================================= */}
            {/* PRIORITY 3: WHY THIS EVENT IS FLAGGED                             */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Why Flagged
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P3 · ANOMALY</span>
              </div>

              <div className="p-3.5 space-y-2.5">
                {/* Anomaly Characterization / Flag Banner */}
                {(event.anomaly_characterization || detail?.anomaly_characterization) && (
                  <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-300 text-[11px] font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                    <span>{event.anomaly_characterization || detail?.anomaly_characterization}</span>
                  </div>
                )}

                {/* Primary AI Explanation */}
                <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-3">
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
                    {event.explanation || detail?.explanation || 'No anomaly explanation recorded for this cluster.'}
                  </p>
                </div>

                {/* Contributing Factors (if present in event) */}
                {event.contributing_factors && (
                  <div className="space-y-1 pt-1">
                    <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                      Contributing Indicators
                    </span>
                    <p className="text-[11px] text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/60 p-2 rounded border border-slate-100 dark:border-slate-700">
                      {event.contributing_factors}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* ================================================================= */}
            {/* PRIORITY 4: THERMAL MOVEMENT & KINEMATICS                         */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Thermal Movement & Direction
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P4 · KINEMATICS</span>
              </div>

              <div className="p-3.5 space-y-3">
                {!movement ? (
                  <p className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/60 p-3 rounded-lg border border-slate-100 dark:border-slate-700">
                    No movement vector intelligence available for this cluster.
                  </p>
                ) : (
                  <>
                    {/* Movement Status Header Bar */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border shadow-2xs ${
                          movement.movement_status === 'MOVING' ? 'bg-amber-50 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-900' :
                          movement.movement_status === 'STATIONARY' ? 'bg-emerald-50 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-900' :
                          'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700'
                        }`}>
                          {movement.movement_status === 'MOVING' ? '● MOVING CLUSTER' :
                           movement.movement_status === 'STATIONARY' ? '● STATIONARY' : '● INSUFFICIENT DATA'}
                        </span>
                        <span className="text-[11px] text-slate-500 dark:text-slate-400 capitalize font-medium">
                          ({movement.movement_pattern?.replace(/_/g, ' ') || 'unknown pattern'})
                        </span>
                      </div>
                      {movement.direction_confidence && (
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          movement.direction_confidence === 'HIGH' ? 'bg-green-100 dark:bg-green-950/70 text-green-800 dark:text-green-300' :
                          movement.direction_confidence === 'MODERATE' ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300' :
                          'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                        }`}>
                          {movement.direction_confidence} CONFIDENCE
                        </span>
                      )}
                    </div>

                    {/* Visual Compass Vector (when moving and direction available) */}
                    {movement.movement_status === 'MOVING' && movement.direction_available ? (
                      <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700 rounded-xl p-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          {/* SVG Compass Dial */}
                          <div className="relative w-14 h-14 bg-white dark:bg-slate-800 rounded-full border-2 border-slate-200 dark:border-slate-700 flex items-center justify-center shadow-xs flex-shrink-0">
                            <span className="absolute text-[8px] font-bold text-slate-400 dark:text-slate-500 top-0.5">N</span>
                            <span className="absolute text-[8px] font-bold text-slate-400 dark:text-slate-500 bottom-0.5">S</span>
                            <span className="absolute text-[8px] font-bold text-slate-400 dark:text-slate-500 right-1">E</span>
                            <span className="absolute text-[8px] font-bold text-slate-400 dark:text-slate-500 left-1">W</span>
                            {/* Direction Needle */}
                            <div
                              className="w-full h-full flex items-center justify-center transition-transform duration-700"
                              style={{ transform: `rotate(${movement.movement_bearing_degrees ?? 0}deg)` }}
                            >
                              <div className="w-1 h-6 bg-gradient-to-t from-transparent via-amber-500 to-red-500 rounded-full transform -translate-y-1.5 shadow-xs" />
                            </div>
                          </div>

                          <div>
                            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                              Heading / Bearing
                            </span>
                            <span className="text-sm font-bold text-navy-900 dark:text-slate-100">
                              {movement.direction ?? '—'}
                            </span>
                            <span className="text-xs font-mono text-slate-500 dark:text-slate-400 block">
                              {formatDegrees(movement.movement_bearing_degrees)}
                            </span>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                            Rate of Spread
                          </span>
                          <span className="text-sm font-bold font-mono text-amber-700 dark:text-amber-400">
                            {formatRate(movement.movement_rate_km_per_day)}
                          </span>
                          <span className="text-[10px] text-slate-500 dark:text-slate-400 block">
                            Disp: {formatDistance(movement.total_movement_distance_km)}
                          </span>
                        </div>
                      </div>
                    ) : movement.movement_pattern === 'erratic' ? (
                      <div className="bg-amber-50/80 dark:bg-amber-950/60 border border-amber-200/80 dark:border-amber-900 rounded-lg p-2.5 text-xs text-amber-900 dark:text-amber-300 leading-relaxed">
                        <span className="font-bold block mb-0.5">Contradictory Directional Vectors</span>
                        Net displacement exists but day-to-day observations show conflicting bearings — no single defensible propagation direction.
                      </div>
                    ) : (
                      <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/70 dark:border-slate-700 rounded-lg p-2.5 flex items-center justify-between text-xs">
                        <span className="text-slate-600 dark:text-slate-400 font-medium">Stationary Thermal Source</span>
                        <span className="font-mono text-slate-800 dark:text-slate-200 font-bold">
                          {movement.active_days} active days
                        </span>
                      </div>
                    )}

                    {/* Scientific Footnote */}
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed border-t border-slate-100 dark:border-slate-700/60 pt-1.5">
                      Direction indicates movement of detected thermal centroids across VIIRS satellite passes. It does not confirm physical fire-front perimeter spread.
                    </p>
                  </>
                )}
              </div>
            </div>

            {/* ================================================================= */}
            {/* PRIORITY 5: SATELLITE CONTEXT & LAND COVER                        */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Satellite Context (Sentinel-2)
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P5 · OPTICAL</span>
              </div>

              <div className="p-3.5 space-y-2.5">
                {hasSatellite ? (
                  <div className="space-y-3">
                    <div className="bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200/80 dark:border-emerald-900/70 rounded-xl p-3 flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 flex items-center justify-center flex-shrink-0">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                          </svg>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider block">
                            CNN Land-Cover Prediction
                          </span>
                          <span className="text-xs font-bold text-emerald-950 dark:text-emerald-200 capitalize">
                            {satClass.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider block">
                          Confidence
                        </span>
                        <span className="text-xs font-mono font-bold text-emerald-900 dark:text-emerald-300">
                          {Math.round(satConf * 100)}%
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-600 h-full rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(satConf * 100, 100)}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed pt-1">
                        Land-cover context derived from Sentinel-2 multi-spectral CNN. This is surface contextual evidence, not an active flame detector.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700 rounded-xl p-3 space-y-1.5">
                    <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                      <svg className="w-4 h-4 text-slate-400 dark:text-slate-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z" />
                      </svg>
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Imagery Obscured or Unavailable</span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                      Satellite observation unavailable or obscured by local cloud cover. Cloud-obscured imagery is not negative evidence.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* ================================================================= */}
            {/* PRIORITY 6: OPERATIONAL RESPONSE & DECISION SUPPORT               */}
            {/* ================================================================= */}
            {response && (
              <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
                <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-600" />
                    <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                      Operational Response
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">P6 · DISPATCH</span>
                </div>

                <div className="p-3.5 space-y-3">
                  {/* Priority Banner */}
                  <div className={`px-3 py-2 rounded-lg flex items-center justify-between border shadow-2xs ${
                    response.alert_priority.includes('HIGH') || response.alert_priority.includes('CRITICAL')
                      ? 'bg-red-50 dark:bg-red-950/70 border-red-200 dark:border-red-900 text-red-900 dark:text-red-300' :
                    response.alert_priority.includes('MONITOR')
                      ? 'bg-amber-50 dark:bg-amber-950/70 border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-300' :
                      'bg-green-50 dark:bg-green-950/70 border-green-200 dark:border-green-900 text-green-900 dark:text-green-300'
                  }`}>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${
                        response.alert_priority.includes('HIGH') || response.alert_priority.includes('CRITICAL')
                          ? 'bg-red-600 animate-pulse' : 'bg-current'
                      }`} />
                      <span className="text-xs font-bold uppercase tracking-wider">
                        {response.alert_priority}
                      </span>
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">Decision Support</span>
                  </div>

                  {/* Nearest Fire Station Card */}
                  {response.nearest_station_name && !response.nearest_station_name.toLowerCase().includes('no fire station') ? (
                    <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 flex-shrink-0">
                          <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                          </svg>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                            Nearest Verified Station
                          </span>
                          <span className="text-xs font-bold text-navy-900 dark:text-slate-100">
                            {response.nearest_station_name}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
                          Distance
                        </span>
                        <span className="text-xs font-mono font-bold text-navy-900 dark:text-slate-100">
                          {response.station_distance_km != null ? `${response.station_distance_km.toFixed(1)} km` : '—'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-amber-50/70 dark:bg-amber-950/50 border border-amber-200/70 dark:border-amber-900 rounded-lg p-2.5 text-xs text-amber-900 dark:text-amber-300">
                      <p className="font-semibold mb-0.5">No station within immediate search radius</p>
                      <p className="text-[11px] text-amber-800 dark:text-amber-400">
                        Dispatch via District Emergency Operations Center (DEOC) or regional emergency command.
                      </p>
                    </div>
                  )}

                  {/* Recommended Action Directive */}
                  {response.recommended_action && (
                    <div className="bg-navy-900 dark:bg-slate-950 text-white rounded-lg p-3 space-y-1 shadow-xs border border-transparent dark:border-slate-800">
                      <div className="flex items-center gap-1.5 text-amber-400 text-[10px] font-bold uppercase tracking-wider">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span>Recommended Operational Action</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-normal">
                        {response.recommended_action}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ================================================================= */}
            {/* SENSOR RADIOMETRY & PHYSICAL EVIDENCE                             */}
            {/* ================================================================= */}
            <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
              <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
                    Thermal Radiometry Metrics
                  </h3>
                </div>
                <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">PHYSICAL</span>
              </div>

              <div className="p-3.5 space-y-3">
                {/* 4-Tile Radiometric Metrics Grid */}
                <div className="grid grid-cols-2 gap-2">
                  {/* Max FRP */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider">Max FRP</span>
                      <svg className="w-3.5 h-3.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                      </svg>
                    </div>
                    <div className="text-sm font-bold font-mono text-navy-900 dark:text-slate-100">
                      {(detail?.max_frp ?? event.frp ?? 0).toFixed(1)} <span className="text-[10px] font-normal text-slate-500 dark:text-slate-400">MW</span>
                    </div>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500">Fire Radiative Power</span>
                  </div>

                  {/* Brightness Temp TI4 */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider">Brightness TI4</span>
                      <svg className="w-3.5 h-3.5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div className="text-sm font-bold font-mono text-navy-900 dark:text-slate-100">
                      {(detail?.max_bright_ti4 ?? event.bright_ti4 ?? 0).toFixed(1)} <span className="text-[10px] font-normal text-slate-500 dark:text-slate-400">K</span>
                    </div>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500">4µm channel peak</span>
                  </div>

                  {/* BT Contrast */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider">BT Contrast</span>
                      <svg className="w-3.5 h-3.5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                      </svg>
                    </div>
                    <div className="text-sm font-bold font-mono text-navy-900 dark:text-slate-100">
                      {(detail?.bt_diff_max ?? 0).toFixed(1)} <span className="text-[10px] font-normal text-slate-500 dark:text-slate-400">K</span>
                    </div>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500">Δ(TI4 - TI5) diff</span>
                  </div>

                  {/* Observations */}
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-700/80 rounded-lg p-2.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider">Detections</span>
                      <svg className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                    </div>
                    <div className="text-sm font-bold font-mono text-navy-900 dark:text-slate-100">
                      {detail?.observation_count ?? 1} <span className="text-[10px] font-normal text-slate-500 dark:text-slate-400">pts</span>
                    </div>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500">Total satellite passes</span>
                  </div>
                </div>

                {/* Timeline bar */}
                {detail?.first_detection && detail?.last_detection && (
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700 rounded-lg p-2.5 space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                      <span>Temporal Range</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {detail.duration_days != null ? `${detail.duration_days} days span` : '—'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 p-1.5 rounded border border-slate-100 dark:border-slate-700">
                      <span>{detail.first_detection}</span>
                      <span className="text-slate-300 dark:text-slate-600">──────►</span>
                      <span>{detail.last_detection}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Safety & Legal Note */}
            <div className="px-1 py-2 text-center">
              <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed">
                Decision-support GIS intelligence dossier. Risk scores and anomaly models are algorithmic indicators and do not replace physical verification.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Side Panel */}
      <aside className="hidden lg:flex w-80 lg:w-96 flex-shrink-0 bg-slate-50/80 dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 flex-col overflow-hidden h-full transition-colors duration-200">
        {panelContent}
      </aside>

      {/* Mobile / Tablet Full-Width Bottom Sheet / Drawer Modal */}
      <div className="lg:hidden fixed inset-0 z-[1400] flex flex-col justify-end items-center">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
        {/* Modal Drawer Sheet */}
        <div className="relative w-full max-w-2xl max-h-[85vh] bg-white dark:bg-slate-900 rounded-t-2xl shadow-2xl flex flex-col overflow-hidden animate-slideUp z-10 border-t border-slate-200 dark:border-slate-800">
          {/* Mobile Drawer Pull Indicator */}
          <div className="w-12 h-1.5 bg-slate-300 dark:bg-slate-700 rounded-full mx-auto my-2 flex-shrink-0" />
          {panelContent}
        </div>
      </div>
    </>
  );
}

