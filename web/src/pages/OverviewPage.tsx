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
          tint: 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400',
          bar: 'bg-slate-300 dark:bg-slate-600',
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
          tint: 'bg-blue-100/80 dark:bg-blue-950/70 text-blue-600 dark:text-blue-400',
          bar: 'bg-blue-500',
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
          tint: 'bg-red-100/80 dark:bg-red-950/70 text-red-600 dark:text-red-400',
          bar: 'bg-red-500',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          ),
        },
        {
          label: 'Moving Clusters',
          value: stats.moving_count,
          valueClass: 'text-amber-600 dark:text-amber-400',
          tint: 'bg-amber-100/80 dark:bg-amber-950/70 text-amber-600 dark:text-amber-400',
          bar: 'bg-amber-500',
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
          tint: 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400',
          bar: 'bg-slate-400 dark:bg-slate-500',
          icon: (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ]
    : [];

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Top Welcome & KPI Header */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-900 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-[0.14em]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live Surveillance
            </span>
          </div>
          <h1 className="text-lg sm:text-2xl font-extrabold text-navy-900 dark:text-slate-100 tracking-tight">
            Thermal Operations Overview
          </h1>
          <p className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Satellite anomaly surveillance · risk assessment · decision-support across India
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/map')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 text-white shadow-xs ring-1 ring-white/10 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <span>Full Map View</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
        {cards.map((card, idx) => (
          <div
            key={card.label}
            className={`relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3 shadow-xs transition-all hover:shadow-sm ${
              idx === 4 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            <div className={`absolute inset-x-0 top-0 h-0.5 ${card.bar} opacity-80`} />
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className={`text-lg sm:text-2xl font-extrabold tabular-nums leading-none ${card.valueClass}`}>
                  {formatNumber(card.value)}
                </div>
                <div className="mt-1.5 text-[10px] sm:text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500 truncate">
                  {card.label}
                </div>
              </div>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${card.tint}`}>
                {card.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Map & Active Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left 2 Cols: Main Key Map */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs flex flex-col h-[400px] sm:h-[460px]">
          <div className="px-3.5 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2 bg-slate-50/50 dark:bg-slate-950/40">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-md bg-red-100 dark:bg-red-950/80 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                </svg>
              </div>
              <h2 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100 truncate">
                Active Thermal Signatures & Propagation
              </h2>
            </div>
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-900 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider flex-shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              VIIRS · LIVE
            </span>
          </div>
          <div className="flex-1 relative">
            <IndiaMap selectedEvent={selectedEvent} onSelectEvent={(e) => setSelectedEvent(e)} />
          </div>
        </div>

        {/* Right 1 Col: Latest Critical & High Alerts Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-red-100 dark:bg-red-950/80 text-red-600 dark:text-red-400 flex items-center justify-center">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <h3 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">
                Priority Alert Queue
              </h3>
            </div>
            <button
              type="button"
              onClick={() => navigate('/alerts')}
              className="text-[11px] font-bold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            >
              View all ({criticalAlerts.length}) →
            </button>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto max-h-[380px]">
            {criticalAlerts.length > 0 ? (
              criticalAlerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  onClick={() => openCluster(alert.cluster_id, alert.latitude ?? DEFAULT_VIEW.lat, alert.longitude ?? DEFAULT_VIEW.lon)}
                  className={`p-2.5 rounded-lg border transition-all cursor-pointer group ${
                    alert.severity === 'CRITICAL'
                      ? 'bg-red-50/50 dark:bg-red-950/20 border-l-2 border-l-red-600 dark:border-l-red-500 border-red-100 dark:border-slate-800 hover:bg-red-50 dark:hover:bg-red-950/40'
                      : 'bg-orange-50/40 dark:bg-orange-950/10 border-l-2 border-l-orange-500 dark:border-l-orange-500 border-orange-100 dark:border-slate-800 hover:bg-orange-50 dark:hover:bg-orange-950/25'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold tracking-wider text-white ${
                          alert.severity === 'CRITICAL' ? 'bg-red-600' : 'bg-orange-500'
                        }`}
                      >
                        {alert.severity}
                      </span>
                      <span className="text-xs font-bold text-navy-900 dark:text-slate-200 truncate">
                        Cluster #{alert.cluster_id}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-slate-400 ml-auto flex-shrink-0">
                      RISK {alert.risk_score ? alert.risk_score.toFixed(1) : '—'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 dark:text-slate-300 truncate">
                    {alert.classification_label ?? 'Thermal Anomaly'}
                  </p>
                  {alert.station_available && (
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5 truncate">
                      {alert.nearest_station_name} · {alert.station_distance_km?.toFixed(1)} km
                    </p>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-10 text-xs text-slate-400 dark:text-slate-500">
                No critical or high alerts active at this moment.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Priority Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs">
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
