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
          color: 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900',
          textColor: 'text-slate-900 dark:text-slate-100',
          icon: (
            <svg className="w-5 h-5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          ),
        },
        {
          label: 'Active Clusters',
          value: stats.active_clusters,
          color: 'border-blue-300 dark:border-blue-900/60 bg-white dark:bg-slate-900',
          textColor: 'text-blue-900 dark:text-blue-400',
          icon: (
            <svg className="w-5 h-5 text-blue-400 dark:text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          ),
        },
        {
          label: 'High-Risk Events',
          value: stats.high_risk_count,
          color: 'border-red-300 dark:border-red-900/60 bg-white dark:bg-slate-900',
          textColor: 'text-red-700 dark:text-red-400',
          icon: (
            <svg className="w-5 h-5 text-red-500 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          ),
        },
        {
          label: 'Moving Clusters',
          value: stats.moving_count,
          color: 'border-amber-300 dark:border-amber-900/60 bg-white dark:bg-slate-900',
          textColor: 'text-amber-700 dark:text-amber-400',
          icon: (
            <svg className="w-5 h-5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          ),
        },
        {
          label: 'High False Alarm Concern',
          value: stats.high_false_alarm_count,
          color: 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900',
          textColor: 'text-slate-700 dark:text-slate-300',
          icon: (
            <svg className="w-5 h-5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ]
    : [];

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Top Welcome & KPI Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100 tracking-tight">
            Operational Intelligence Overview
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            Real-time thermal anomaly surveillance, risk assessment & decision-support intelligence across India.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/map')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 text-white shadow-xs transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
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
            className={`flex items-center gap-2.5 sm:gap-3 p-3 rounded-xl border ${card.color} shadow-2xs transition-colors ${
              idx === 4 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/80 flex-shrink-0">{card.icon}</div>
            <div className="min-w-0 flex-1">
              <div className={`text-lg sm:text-xl font-bold leading-tight ${card.textColor}`}>
                {formatNumber(card.value)}
              </div>
              <div className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 truncate">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Map & Active Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left 2 Cols: Main Key Map */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs flex flex-col h-[400px] sm:h-[460px]">
          <div className="px-3.5 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/40">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <h2 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">
                Active Thermal Signatures & Propagation
              </h2>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500">Live Satellite Ingestion</span>
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
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <h3 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">
                Priority Alerts Queue
              </h3>
            </div>
            <button
              type="button"
              onClick={() => navigate('/alerts')}
              className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
            >
              View All ({criticalAlerts.length})
            </button>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto max-h-[380px]">
            {criticalAlerts.length > 0 ? (
              criticalAlerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  onClick={() => openCluster(alert.cluster_id, alert.latitude ?? DEFAULT_VIEW.lat, alert.longitude ?? DEFAULT_VIEW.lon)}
                  className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-slate-50/60 dark:bg-slate-800/40 hover:bg-white dark:hover:bg-slate-800 transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-bold text-white ${
                        alert.severity === 'CRITICAL' ? 'bg-red-600' : 'bg-orange-500'
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-xs font-bold text-navy-900 dark:text-slate-200">
                      Cluster #{alert.cluster_id}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400 ml-auto">
                      Risk {alert.risk_score ? alert.risk_score.toFixed(1) : '—'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 truncate">
                    {alert.classification_label ?? 'Thermal Anomaly'}
                  </p>
                  {alert.station_available && (
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5 truncate">
                      Station: {alert.nearest_station_name} ({alert.station_distance_km?.toFixed(1)} km)
                    </p>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-xs text-slate-400 dark:text-slate-500">
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
