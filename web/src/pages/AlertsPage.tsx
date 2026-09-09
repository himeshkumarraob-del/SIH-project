import { useState, useEffect } from 'react';
import { fetchAllAlerts, postAcknowledgeAlert, postResolveAlert } from '../api/client';
import EventDetailPanel from '../components/EventDetailPanel';
import { formatNumber } from '../utils/formatters';
import type { ThermalAlert, ThermalEvent } from '../types';

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

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<ThermalAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadAlerts = () => {
    setLoading(true);
    fetchAllAlerts({
      severity: severityFilter !== 'ALL' ? severityFilter : undefined,
      status: statusFilter !== 'ALL' ? statusFilter : undefined,
    })
      .then((data) => {
        setAlerts(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load alerts:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadAlerts();
  }, [severityFilter, statusFilter]);

  const handleAcknowledge = async (alertId: string) => {
    try {
      await postAcknowledgeAlert(alertId);
      setActionMessage(`Alert ${alertId} acknowledged successfully.`);
      setTimeout(() => setActionMessage(null), 3000);
      loadAlerts();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const handleResolve = async (alertId: string) => {
    try {
      await postResolveAlert(alertId);
      setActionMessage(`Alert ${alertId} resolved successfully.`);
      setTimeout(() => setActionMessage(null), 3000);
      loadAlerts();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      a.alert_id.toLowerCase().includes(q) ||
      String(a.cluster_id).includes(q) ||
      (a.classification_label && a.classification_label.toLowerCase().includes(q)) ||
      (a.nearest_station_name && a.nearest_station_name.toLowerCase().includes(q)) ||
      (a.reasons && a.reasons.toLowerCase().includes(q))
    );
  });

  const criticalCount = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = alerts.filter((a) => a.severity === 'HIGH').length;
  const activeCount = alerts.filter((a) => a.status === 'ACTIVE').length;
  const acknowledgedCount = alerts.filter((a) => a.status === 'ACKNOWLEDGED').length;
  const resolvedCount = alerts.filter((a) => a.status === 'RESOLVED').length;

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 bg-ambient p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Title & Action Notification */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100 tracking-tight">
            Decision-Support Thermal Alerts
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            Algorithmic anomaly alerts generated from processed NASA VIIRS satellite evidence and CNN classification.
          </p>
        </div>
        {actionMessage && (
          <div className="px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200 text-xs font-semibold animate-fadeIn">
            ✓ {actionMessage}
          </div>
        )}
      </div>

      {/* Summary KPI Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-3">
        {[
          { label: 'Total Alerts', value: String(alerts.length), valueClass: 'text-slate-900 dark:text-slate-100', bar: 'bg-slate-400', chip: 'text-slate-500 dark:text-slate-400' },
          { label: 'Critical', value: String(criticalCount), valueClass: 'text-red-600 dark:text-red-400', bar: 'bg-red-500', chip: 'text-red-600 dark:text-red-400' },
          { label: 'High', value: String(highCount), valueClass: 'text-orange-600 dark:text-orange-500', bar: 'bg-orange-500', chip: 'text-orange-600 dark:text-orange-500' },
          { label: 'Active', value: String(activeCount), valueClass: 'text-blue-600 dark:text-blue-400', bar: 'bg-blue-500', chip: 'text-blue-600 dark:text-blue-400' },
          { label: 'Resolved / Ack', value: `${resolvedCount} / ${acknowledgedCount}`, valueClass: 'text-slate-700 dark:text-slate-300', bar: 'bg-emerald-500', chip: 'text-slate-500 dark:text-slate-400' },
        ].map((item, idx) => (
          <div
            key={item.label}
            className={`relative overflow-hidden rounded-xl panel p-3 ${
              idx === 4 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            <div className={`absolute inset-x-0 top-0 h-0.5 opacity-80 ${item.bar}`} />
            <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
              {item.label}
            </div>
            <div className={`mt-1 text-xl sm:text-2xl font-extrabold tabular-nums leading-none ${item.valueClass}`}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Filter and Search Bar */}
      <div className="panel rounded-xl p-3 sm:p-4 flex flex-wrap items-center justify-between gap-3">
        {/* Severity filter pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mr-1">
            Severity:
          </span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                severityFilter === sev
                  ? 'bg-navy-900 text-white dark:bg-blue-600 dark:text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        {/* Status filter pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mr-1">
            Status:
          </span>
          {['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                statusFilter === st
                  ? 'bg-navy-900 text-white dark:bg-blue-600 dark:text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="w-full sm:w-64">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by ID, station, reasons..."
            className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-navy-600"
          />
        </div>
      </div>

      {/* Alerts Grid / List */}
      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-16 text-sm text-slate-400 dark:text-slate-500 animate-pulse">
            Loading decision-support alerts...
          </div>
        ) : filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert) => {
            const reasons = (alert.reasons ?? '').split('|').map((r) => r.trim()).filter(Boolean);
            return (
              <div
                key={alert.alert_id}
                className={`panel rounded-xl border-l-[3px] p-3.5 sm:p-4 hover:shadow-md transition-all space-y-3 ${
                  alert.severity === 'CRITICAL'
                    ? 'border-l-red-600'
                    : alert.severity === 'HIGH'
                    ? 'border-l-orange-500'
                    : alert.severity === 'MEDIUM'
                    ? 'border-l-amber-400'
                    : 'border-l-slate-300 dark:border-l-slate-600'
                }`}
              >
                {/* Header Row */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold text-white shadow-2xs ${
                        alert.severity === 'CRITICAL'
                          ? 'bg-red-600'
                          : alert.severity === 'HIGH'
                          ? 'bg-orange-500'
                          : alert.severity === 'MEDIUM'
                          ? 'bg-amber-500'
                          : 'bg-slate-500'
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">
                      {alert.alert_id} (Cluster #{alert.cluster_id})
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                        alert.status === 'ACTIVE'
                          ? 'bg-red-100 text-red-700 dark:bg-red-950/80 dark:text-red-300'
                          : alert.status === 'ACKNOWLEDGED'
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-300'
                          : 'bg-green-100 text-green-700 dark:bg-green-950/80 dark:text-green-300'
                      }`}
                    >
                      {alert.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5 ml-auto">
                    <span className="flex items-baseline gap-1.5">
                      <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
                        Risk
                      </span>
                      <span className={`font-mono text-sm font-extrabold leading-none ${
                        alert.severity === 'CRITICAL'
                          ? 'text-red-600 dark:text-red-400'
                          : alert.severity === 'HIGH'
                          ? 'text-orange-600 dark:text-orange-400'
                          : alert.severity === 'MEDIUM'
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-slate-700 dark:text-slate-200'
                      }`}>
                        {alert.risk_score != null ? formatNumber(alert.risk_score) : '—'}
                      </span>
                    </span>
                    <span className="hidden sm:inline text-slate-300 dark:text-slate-600">|</span>
                    <span
                      className={`hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                        alert.evidence_confidence === 'HIGH'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300'
                          : alert.evidence_confidence === 'MODERATE'
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300'
                          : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                      }`}
                    >
                      Evidence {alert.evidence_confidence ?? 'INSUFFICIENT'}
                    </span>
                  </div>
                </div>

                {/* Details & Metadata Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-2">
                  <div className="min-w-0">
                    <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500 block mb-0.5">Classification</span>
                    <span className="text-[11px] font-semibold text-slate-800 dark:text-slate-200 leading-snug">
                      {alert.classification_label ?? 'Unknown'}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500 block mb-0.5">Persistence</span>
                    <span className="text-[11px] font-semibold text-slate-800 dark:text-slate-200 capitalize leading-snug">
                      {alert.persistence_category?.replace(/_/g, ' ') ?? '—'}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500 block mb-0.5">Station</span>
                    <span className="text-[11px] font-semibold text-slate-800 dark:text-slate-200 leading-snug">
                      {alert.station_available
                        ? `${alert.nearest_station_name} · ${alert.station_distance_km?.toFixed(1)} km`
                        : 'No station nearby'}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-400 dark:text-slate-500 block mb-0.5">Max FRP / Brightness</span>
                    <span className="text-[11px] font-semibold font-mono text-slate-800 dark:text-slate-200 leading-snug">
                      {alert.max_frp ? `${alert.max_frp.toFixed(1)} MW` : '—'} /{' '}
                      {alert.max_bright_ti4 ? `${alert.max_bright_ti4.toFixed(1)} K` : '—'}
                    </span>
                  </div>
                </div>

                {/* Trigger Reasons */}
                {reasons.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40">
                    <span className="inline-flex items-center gap-1.5 text-[9px] font-bold text-amber-700 dark:text-amber-400 uppercase tracking-[0.12em] block mb-1.5">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Alert Trigger Rationale
                    </span>
                    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-slate-700 dark:text-slate-300">
                      {reasons.map((r, i) => (
                        <div key={i} className="flex items-center gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-amber-500" />
                          <span>{r}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions Row */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <div className="text-[11px] text-slate-400 dark:text-slate-500">
                    Decision-support advisory only. Does not replace ground truth verification.
                  </div>
                  <div className="flex items-center gap-2 ml-auto">
                    {alert.status === 'ACTIVE' && (
                      <button
                        type="button"
                        onClick={() => handleAcknowledge(alert.alert_id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 hover:bg-amber-100 dark:hover:bg-amber-900/60 border border-amber-200 dark:border-amber-800 transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                    {alert.status !== 'RESOLVED' && (
                      <button
                        type="button"
                        onClick={() => handleResolve(alert.alert_id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-950/60 hover:bg-green-100 dark:hover:bg-green-900/60 border border-green-200 dark:border-green-800 transition-colors"
                      >
                        Resolve
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() =>
                        setSelectedEvent(
                          makeClusterEvent(
                            alert.cluster_id,
                            alert.latitude ?? DEFAULT_VIEW.lat,
                            alert.longitude ?? DEFAULT_VIEW.lon,
                          ),
                        )
                      }
                      className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 transition-colors shadow-2xs"
                    >
                      View Intelligence Dossier
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="text-center py-16 panel rounded-xl p-8">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-200">No Alerts Match Current Filters</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Try switching severity or status filter to see other alerts.
            </p>
          </div>
        )}
      </div>

      {/* Event Detail Panel for Selected Event */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
