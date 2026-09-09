import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import IndiaMap from '../components/IndiaMap';
import ClusterTable from '../components/ClusterTable';
import EventDetailPanel from '../components/EventDetailPanel';
import { fetchStatistics, fetchAllAlerts, fetchClusters } from '../api/client';
import { formatNumber } from '../utils/formatters';
import type { ThermalEvent, ClusterSummary, DashboardStats, ThermalAlert } from '../types';

const DEFAULT_VIEW = { lat: 20.5937, lon: 78.9629 };

function makeClusterEvent(
  clusterId: number,
  latitude: number,
  longitude: number,
  extras?: Partial<ThermalEvent>,
): ThermalEvent {
  return {
    detection_id: `cluster-${clusterId}`,
    latitude,
    longitude,
    acq_date: '',
    cluster_id: clusterId,
    persistence_category: 'unknown',
    anomaly_score: 0,
    anomaly_flag: 0,
    abnormality_level: 'NORMAL',
    anomaly_characterization: '',
    explanation: '',
    contributing_factors: '',
    bright_ti4: 0,
    bright_ti5: 0,
    frp: 0,
    confidence: '',
    satellite: '',
    scan: 0,
    track: 0,
    acq_time: '',
    instrument: 'VIIRS',
    source_satellite: '',
    source_file: '',
    acquisition_datetime: '',
    ...extras,
  };
}

export default function OverviewPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [criticalAlerts, setCriticalAlerts] = useState<ThermalAlert[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null);

  useEffect(() => {
    fetchStatistics().then(setStats);
    fetchAllAlerts({ status: 'ACTIVE' }).then((alerts) => {
      setCriticalAlerts(alerts.slice(0, 4));
    });
  }, []);

  const openCluster = useCallback(
    (clusterId: number, latitude: number, longitude: number, extras?: Partial<ThermalEvent>) => {
      setSelectedEvent(makeClusterEvent(clusterId, latitude, longitude, extras));
    },
    [],
  );

  const handleSelectCluster = useCallback(
    (cluster: ClusterSummary) => {
      openCluster(
        cluster.cluster_id,
        cluster.latitude ?? DEFAULT_VIEW.lat,
        cluster.longitude ?? DEFAULT_VIEW.lon,
        {
          acq_date: cluster.first_detection,
          persistence_category: cluster.persistence_category,
          anomaly_score: cluster.anomaly_score,
          anomaly_flag: cluster.anomaly_flag,
          abnormality_level: cluster.abnormality_level,
          anomaly_characterization: cluster.anomaly_characterization,
          explanation: cluster.explanation,
          contributing_factors: cluster.contributing_factors,
          bright_ti4: cluster.max_bright_ti4,
          bright_ti5: cluster.max_bright_ti5,
          frp: cluster.max_frp,
          confidence: String(cluster.mean_confidence),
        },
      );
    },
    [openCluster],
  );

  const cards = stats
    ? [
        {
          label: 'Total Detections',
          value: stats.total_detections,
          valueClass: 'text-slate-900 dark:text-slate-100',
          tint: 'bg-gradient-to-br from-slate-200/90 to-slate-100 text-slate-600 dark:from-slate-700/80 dark:to-slate-800 dark:text-slate-300',
          edge: 'from-slate-400/70 via-slate-300/30 to-transparent',
          glow: 'bg-[radial-gradient(110%_90%_at_100%_0%,rgba(148,163,184,0.14),transparent_62%)]',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          ),
        },
        {
          label: 'Active Clusters',
          value: stats.active_clusters,
          valueClass: 'text-blue-700 dark:text-blue-400',
          tint: 'bg-gradient-to-br from-blue-500/15 to-blue-600/5 text-blue-600 dark:from-blue-500/25 dark:to-blue-600/10 dark:text-blue-400',
          edge: 'from-blue-500/80 via-blue-400/30 to-transparent',
          glow: 'bg-[radial-gradient(110%_90%_at_100%_0%,rgba(59,130,246,0.16),transparent_62%)]',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          ),
        },
        {
          label: 'High-Risk Events',
          value: stats.high_risk_count,
          valueClass: 'text-red-600 dark:text-red-400',
          tint: 'bg-gradient-to-br from-red-500/15 to-orange-500/10 text-red-600 dark:from-red-500/25 dark:to-orange-500/10 dark:text-red-400',
          edge: 'from-red-500/90 via-orange-400/40 to-transparent',
          glow: 'bg-[radial-gradient(110%_90%_at_100%_0%,rgba(239,68,68,0.15),transparent_62%)]',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          ),
        },
        {
          label: 'Moving Clusters',
          value: stats.moving_count,
          valueClass: 'text-orange-600 dark:text-orange-400',
          tint: 'bg-gradient-to-br from-orange-500/15 to-amber-500/10 text-orange-600 dark:from-orange-500/25 dark:to-amber-500/10 dark:text-orange-400',
          edge: 'from-orange-500/80 via-amber-400/30 to-transparent',
          glow: 'bg-[radial-gradient(110%_90%_at_100%_0%,rgba(249,115,22,0.14),transparent_62%)]',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          ),
        },
        {
          label: 'False Alarm Concern',
          value: stats.high_false_alarm_count,
          valueClass: 'text-slate-700 dark:text-slate-300',
          tint: 'bg-gradient-to-br from-slate-200/90 to-slate-100 text-slate-600 dark:from-slate-700/80 dark:to-slate-800 dark:text-slate-300',
          edge: 'from-emerald-500/50 via-slate-300/20 to-transparent',
          glow: 'bg-[radial-gradient(110%_90%_at_100%_0%,rgba(148,163,184,0.12),transparent_62%)]',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ]
    : [];

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 bg-ambient p-3 sm:p-4 lg:p-5 xl:p-6 space-y-4 lg:space-y-5">
      {/* Top Welcome & KPI Header */}
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50/90 dark:bg-emerald-500/[0.08] border border-emerald-200/90 dark:border-emerald-400/20 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-[0.16em] shadow-[0_0_12px_-4px_rgba(16,185,129,0.5)]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_6px_rgba(16,185,129,0.9)]" />
              Live Surveillance
            </span>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-navy-900/[0.04] dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-[0.16em]">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              India · VIIRS
            </span>
          </div>
          <h1 className="text-lg sm:text-2xl font-extrabold text-navy-900 dark:text-slate-100 tracking-tight">
            Thermal Operations Overview
          </h1>
          <p className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 mt-1">
            Satellite anomaly surveillance · risk assessment · decision-support across India
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/map')}
            className="group inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold text-white bg-gradient-to-b from-navy-700 to-navy-900 hover:from-navy-600 hover:to-navy-800 dark:from-blue-600 dark:to-blue-700 dark:hover:from-blue-500 dark:hover:to-blue-600 shadow-[0_1px_2px_rgba(15,23,42,0.3),0_8px_20px_-8px_rgba(37,99,235,0.6)] ring-1 ring-inset ring-white/15 transition-all active:scale-[0.98]"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <span>Full Map View</span>
            <svg className="w-3.5 h-3.5 text-white/60 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
        {cards.map((card, idx) => (
          <div
            key={card.label}
            className={`group relative overflow-hidden rounded-xl border border-slate-200/90 dark:border-white/[0.07] bg-white dark:bg-slate-900/70 dark:backdrop-blur-xl p-3.5 sm:p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_10px_24px_-16px_rgba(15,23,42,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_16px_36px_-20px_rgba(0,0,0,0.7)] transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-300 dark:hover:border-white/[0.14] ${
              idx === 4 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            {/* Ambient corner glow + accent top edge */}
            <div className={`pointer-events-none absolute inset-0 ${card.glow}`} />
            <div className={`pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r ${card.edge}`} />

            <div className="relative flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className={`text-lg sm:text-2xl font-extrabold tabular-nums tracking-tight leading-none ${card.valueClass}`}>
                  {formatNumber(card.value)}
                </div>
                <div className="mt-2 text-[9px] sm:text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500 truncate">
                  {card.label}
                </div>
              </div>
              <div className={`w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center flex-shrink-0 ring-1 ring-inset ring-black/[0.05] dark:ring-white/10 ${card.tint}`}>
                {card.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Map & Active Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 sm:gap-4">
        {/* Left 2 Cols: Main Key Map — the central intelligence surface */}
        <div className="lg:col-span-2 relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 dark:border-white/[0.07] bg-white dark:bg-slate-900/70 dark:backdrop-blur-xl shadow-[0_1px_2px_rgba(15,23,42,0.05),0_16px_40px_-18px_rgba(15,23,42,0.25)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_24px_60px_-30px_rgba(0,0,0,0.85)] h-[400px] sm:h-[480px]">
          {/* Bezel highlight around the live map surface */}
          <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-slate-900/[0.04] dark:ring-white/[0.04] z-[1200]" />
          <div className="flex items-center justify-between gap-2 px-3.5 sm:px-4 py-2.5 sm:py-3 border-b border-slate-100 dark:border-white/[0.06] bg-gradient-to-b from-slate-50/80 to-white/30 dark:from-white/[0.05] dark:to-transparent">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative flex-shrink-0">
                <div className="absolute inset-0 rounded-lg bg-red-500/30 blur-md opacity-70" />
                <div className="relative w-7 h-7 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 text-white flex items-center justify-center shadow-[0_2px_8px_-2px_rgba(239,68,68,0.7)] ring-1 ring-inset ring-white/25">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                  </svg>
                </div>
              </div>
              <div className="min-w-0">
                <h2 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100 truncate">
                  Active Thermal Signatures & Propagation
                </h2>
                <p className="hidden sm:block text-[10px] text-slate-400 dark:text-slate-500 truncate">
                  Geospatial anomaly surface · NASA VIIRS · CNN triage
                </p>
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50/90 dark:bg-emerald-500/[0.08] border border-emerald-200/90 dark:border-emerald-400/20 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider flex-shrink-0 shadow-[0_0_14px_-6px_rgba(16,185,129,0.6)]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_6px_rgba(16,185,129,0.9)]" />
              VIIRS · LIVE
            </span>
          </div>
          <div className="flex-1 relative min-h-0">
            <IndiaMap selectedEvent={selectedEvent} onSelectEvent={(e) => setSelectedEvent(e)} />
          </div>
        </div>

        {/* Right 1 Col: Latest Critical & High Alerts Card */}
        <div className="relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 dark:border-white/[0.07] bg-white dark:bg-slate-900/70 dark:backdrop-blur-xl p-3.5 sm:p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_16px_40px_-18px_rgba(15,23,42,0.25)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_24px_60px_-30px_rgba(0,0,0,0.85)] min-h-[280px]">
          <div className="pointer-events-none absolute -top-16 -right-16 w-48 h-48 rounded-full bg-red-500/[0.07] dark:bg-red-500/[0.06] blur-2xl" />
          <div className="relative flex items-center justify-between gap-2 pb-3 mb-3 border-b border-slate-100 dark:border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <div className="relative flex-shrink-0">
                <div className="absolute inset-0 rounded-lg bg-amber-500/30 blur-md opacity-60" />
                <div className="relative w-7 h-7 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 text-white flex items-center justify-center shadow-[0_2px_8px_-2px_rgba(249,115,22,0.6)] ring-1 ring-inset ring-white/25">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
              </div>
              <div className="min-w-0">
                <h3 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">
                  Priority Alert Queue
                </h3>
                <p className="hidden sm:block text-[10px] text-slate-400 dark:text-slate-500">
                  CRITICAL / HIGH triage stream
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate('/alerts')}
              className="group inline-flex items-center gap-1 text-[11px] font-bold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex-shrink-0"
            >
              <span>View all ({criticalAlerts.length})</span>
              <svg className="w-3 h-3 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
          </div>

          <div className="relative flex-1 min-h-0 overflow-y-auto space-y-2">
            {criticalAlerts.length > 0 ? (
              criticalAlerts.map((alert) => {
                const isCritical = alert.severity === 'CRITICAL';
                return (
                  <div
                    key={alert.alert_id}
                    onClick={() => openCluster(alert.cluster_id, alert.latitude ?? DEFAULT_VIEW.lat, alert.longitude ?? DEFAULT_VIEW.lon)}
                    className={`relative overflow-hidden rounded-xl border p-3 transition-all cursor-pointer group/alert ${
                      isCritical
                        ? 'bg-red-50/60 dark:bg-red-950/[0.14] border-red-100 dark:border-red-900/30 hover:bg-red-50 dark:hover:bg-red-950/25 hover:border-red-200 dark:hover:border-red-500/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_10px_24px_-14px_rgba(239,68,68,0.45)]'
                        : 'bg-orange-50/50 dark:bg-orange-950/[0.12] border-orange-100 dark:border-orange-900/25 hover:bg-orange-50 dark:hover:bg-orange-950/20 hover:border-orange-200 dark:hover:border-orange-500/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_10px_24px_-14px_rgba(249,115,22,0.4)]'
                    }`}
                  >
                    {/* Severity accent edge */}
                    <div className={`absolute left-0 top-2.5 bottom-2.5 w-[3px] rounded-full bg-gradient-to-b ${
                      isCritical ? 'from-red-500 to-orange-400' : 'from-orange-500 to-amber-400'
                    }`} />
                    <div className="pl-2.5">
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold tracking-[0.08em] text-white shadow-sm ${
                              isCritical
                                ? 'bg-gradient-to-b from-red-500 to-red-600 shadow-red-900/40'
                                : 'bg-gradient-to-b from-orange-400 to-orange-500 shadow-orange-900/30'
                            }`}
                          >
                            {alert.severity}
                          </span>
                          <span className="text-xs font-bold text-navy-900 dark:text-slate-200 truncate">
                            Cluster #{alert.cluster_id}
                          </span>
                        </div>
                        <span className={`text-[10px] font-mono font-bold flex-shrink-0 ${
                          isCritical ? 'text-red-600 dark:text-red-400' : 'text-orange-600 dark:text-orange-400'
                        }`}>
                          RISK {alert.risk_score ? alert.risk_score.toFixed(1) : '—'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 truncate">
                        {alert.classification_label ?? 'Thermal Anomaly'}
                      </p>
                      {alert.station_available && (
                        <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 truncate">
                          {alert.nearest_station_name} · {alert.station_distance_km?.toFixed(1)} km
                        </p>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="flex flex-col items-center justify-center text-center h-full min-h-[220px] px-5 py-6 rounded-xl border border-dashed border-slate-200 dark:border-white/[0.08] bg-slate-50/60 dark:bg-slate-950/30">
                <div className="relative mb-3">
                  <div className="absolute inset-0 rounded-full bg-emerald-400/30 blur-xl" />
                  <div className="relative w-11 h-11 rounded-full bg-gradient-to-br from-emerald-400/20 to-emerald-600/[0.06] dark:from-emerald-400/15 dark:to-emerald-600/[0.04] border border-emerald-400/30 dark:border-emerald-400/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shadow-[0_0_18px_-4px_rgba(16,185,129,0.5)]">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                  </div>
                </div>
                <p className="text-xs font-bold text-slate-600 dark:text-slate-300">
                  No active priority alerts
                </p>
                <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1.5 max-w-[230px] leading-relaxed">
                  All detections are currently triaged below CRITICAL / HIGH. New escalations will surface here in real time.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Priority Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/90 dark:border-white/[0.07] bg-white dark:bg-slate-900/70 dark:backdrop-blur-xl shadow-[0_1px_2px_rgba(15,23,42,0.05),0_16px_40px_-18px_rgba(15,23,42,0.22)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_24px_60px_-30px_rgba(0,0,0,0.85)]">
        <ClusterTable
          selectedClusterId={selectedEvent?.cluster_id ?? null}
          onSelectCluster={handleSelectCluster}
        />
      </div>

      {/* Event Detail Panel (Right panel or mobile drawer modal) */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
