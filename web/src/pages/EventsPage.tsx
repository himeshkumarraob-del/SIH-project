import { useState, useEffect, useMemo } from 'react';
import { fetchClusters } from '../api/client';
import EventDetailPanel from '../components/EventDetailPanel';
import { formatNumber, formatCoordinate } from '../utils/formatters';
import type { ClusterSummary, ThermalEvent, FilterState } from '../types';

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

const LEVEL_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, ELEVATED: 2, NORMAL: 1 };

export default function EventsPage() {
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedRisk, setSelectedRisk] = useState<string[]>([]);
  const [selectedAbnormality, setSelectedAbnormality] = useState<string[]>([]);
  const [sortKey, setSortKey] = useState<keyof ClusterSummary>('risk_score');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null);
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const pageSize = 25;

  // Load the full cluster catalog from /api/v1/clusters whenever the risk/
  // abnormality filter pills change or the user hits Retry. Unlike the old
  // code, a failed request surfaces an explicit error state instead of
  // silently leaving the queue empty.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const filters: FilterState = {
      riskLevel: selectedRisk,
      abnormalityLevel: selectedAbnormality,
      falseAlarmConcern: [],
      movementStatus: [],
      persistenceCategory: [],
      satellite: [],
      dateRange: null,
    };

    fetchClusters(filters, { throwOnError: true })
      .then((data) => {
        if (cancelled) return;
        setClusters(data);
        setLoading(false);
        setPage(1);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        console.error('Failed to load clusters catalog:', err);
        setClusters([]);
        setLoading(false);
        setError(err?.message || 'Unable to reach the thermal intelligence API.');
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRisk, selectedAbnormality, reloadKey]);

  // Restart at page 1 whenever the search query changes so a narrowed result
  // set can never leave the user stranded on an out-of-range page.
  useEffect(() => {
    setPage(1);
  }, [search]);

  const toggleRisk = (r: string) => {
    setSelectedRisk((prev) => (prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]));
  };

  const toggleAbnormality = (a: string) => {
    setSelectedAbnormality((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]));
  };

  const filtered = useMemo(() => {
    let result = clusters;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          String(c.cluster_id).includes(q) ||
          c.anomaly_characterization?.toLowerCase().includes(q) ||
          c.risk_factors?.toLowerCase().includes(q) ||
          c.explanation?.toLowerCase().includes(q),
      );
    }

    result = [...result].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortAsc ? av - bv : bv - av;
      }
      const aOrd = LEVEL_ORDER[String(av)] ?? 0;
      const bOrd = LEVEL_ORDER[String(bv)] ?? 0;
      if (aOrd !== bOrd) return sortAsc ? aOrd - bOrd : bOrd - aOrd;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });

    return result;
  }, [clusters, search, sortKey, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  // Clamp to the last valid page so an out-of-range page (from sorting or a
  // result set that shrank) can never render as an empty table.
  const safePage = Math.min(Math.max(1, page), totalPages);
  const paginatedRows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const handleSort = (key: keyof ClusterSummary) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const handleSelectCluster = (cluster: ClusterSummary) => {
    setSelectedEvent(
      makeClusterEvent(
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
      ),
    );
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 bg-ambient p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Title */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100 tracking-tight">
            Thermal Events & Clusters Catalog
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            Search, sort, filter, and inspect detailed intelligence for all {clusters.length} tracked thermal clusters.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="panel rounded-xl p-3 sm:p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Quick Risk Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mr-1">
              Risk Level:
            </span>
            {['HIGH', 'MEDIUM', 'LOW'].map((r) => (
              <button
                key={r}
                onClick={() => toggleRisk(r)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                  selectedRisk.includes(r)
                    ? r === 'HIGH'
                      ? 'bg-red-600 text-white shadow-xs'
                      : r === 'MEDIUM'
                      ? 'bg-amber-500 text-white shadow-xs'
                      : 'bg-green-600 text-white shadow-xs'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Quick Abnormality Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mr-1">
              AI Anomaly:
            </span>
            {['HIGH', 'ELEVATED', 'NORMAL'].map((a) => (
              <button
                key={a}
                onClick={() => toggleAbnormality(a)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                  selectedAbnormality.includes(a)
                    ? 'bg-navy-900 text-white dark:bg-blue-600 dark:text-white shadow-xs'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                {a}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="w-full sm:w-72">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search cluster ID, factors, explanation..."
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-navy-600"
            />
          </div>
        </div>
      </div>

      {/* Events Table Card */}
      <div className="panel rounded-xl overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="min-w-[800px] w-full text-xs">
            <thead className="bg-slate-50 dark:bg-slate-950/80 sticky top-0 border-b border-slate-200 dark:border-slate-800">
              <tr className="text-left text-slate-500 dark:text-slate-400">
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('cluster_id')}>
                  Cluster ID {sortKey === 'cluster_id' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('risk_score')}>
                  Risk Score {sortKey === 'risk_score' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('abnormality_level')}>
                  AI Anomaly {sortKey === 'abnormality_level' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('false_alarm_indicator')}>
                  False Alarm {sortKey === 'false_alarm_indicator' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('max_frp')}>
                  Max FRP {sortKey === 'max_frp' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('observation_count')}>
                  Observations {sortKey === 'observation_count' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('active_days')}>
                  Days {sortKey === 'active_days' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold cursor-pointer" onClick={() => handleSort('persistence_category')}>
                  Persistence {sortKey === 'persistence_category' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="px-3.5 py-2.5 font-bold">Coordinates / Detection</th>
                <th className="px-3.5 py-2.5 font-bold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={10} className="text-center py-16">
                    <div className="inline-flex flex-col items-center gap-2">
                      <div className="w-7 h-7 border-2 border-navy-800 dark:border-blue-500 border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 animate-pulse">
                        Loading cluster catalog…
                      </span>
                    </div>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={10} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-2 max-w-md">
                      <div className="w-9 h-9 rounded-full bg-red-100 dark:bg-red-950/70 text-red-600 dark:text-red-400 flex items-center justify-center">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                      </div>
                      <p className="text-sm font-bold text-navy-900 dark:text-slate-200">
                        Unable to Load Cluster Catalog
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{error}</p>
                      <button
                        type="button"
                        onClick={() => setReloadKey((k) => k + 1)}
                        className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 transition-colors shadow-xs"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5M20 20v-5h-5M4.5 9A7.5 7.5 0 0119 7.5M19.5 15A7.5 7.5 0 015 16.5" />
                        </svg>
                        Retry Fetch
                      </button>
                    </div>
                  </td>
                </tr>
              ) : paginatedRows.length > 0 ? (
                paginatedRows.map((cluster) => (
                  <tr
                    key={cluster.cluster_id}
                    onClick={() => handleSelectCluster(cluster)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
                  >
                    <td className="px-3.5 py-2.5 font-bold text-navy-900 dark:text-slate-100">
                      #{cluster.cluster_id}
                    </td>
                    <td className="px-3.5 py-2.5">
                      <span
                        className={`font-bold ${
                          cluster.risk_level === 'HIGH'
                            ? 'text-red-600 dark:text-red-400'
                            : cluster.risk_level === 'MEDIUM'
                            ? 'text-amber-600 dark:text-amber-400'
                            : 'text-green-600 dark:text-green-400'
                        }`}
                      >
                        {cluster.risk_score ? cluster.risk_score.toFixed(1) : '—'}
                      </span>
                      <span className="ml-1 text-[10px] text-slate-400">({cluster.risk_level})</span>
                    </td>
                    <td className="px-3.5 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          cluster.abnormality_level === 'HIGH'
                            ? 'bg-red-100 text-red-700 dark:bg-red-950/80 dark:text-red-300'
                            : cluster.abnormality_level === 'ELEVATED'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-300'
                            : 'bg-green-100 text-green-700 dark:bg-green-950/80 dark:text-green-300'
                        }`}
                      >
                        {cluster.abnormality_level}
                      </span>
                    </td>
                    <td className="px-3.5 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          cluster.false_alarm_indicator === 'HIGH'
                            ? 'bg-green-100 text-green-700 dark:bg-green-950/80 dark:text-green-300'
                            : cluster.false_alarm_indicator === 'MEDIUM'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {cluster.false_alarm_indicator}
                      </span>
                    </td>
                    <td className="px-3.5 py-2.5 font-mono text-slate-800 dark:text-slate-200">
                      {cluster.max_frp ? `${cluster.max_frp.toFixed(1)} MW` : '—'}
                    </td>
                    <td className="px-3.5 py-2.5 text-slate-700 dark:text-slate-300">
                      {cluster.observation_count} pts
                    </td>
                    <td className="px-3.5 py-2.5 text-slate-700 dark:text-slate-300">
                      {cluster.active_days}d
                    </td>
                    <td className="px-3.5 py-2.5 text-slate-600 dark:text-slate-400 capitalize">
                      {cluster.persistence_category?.replace(/_/g, ' ') ?? '—'}
                    </td>
                    <td className="px-3.5 py-2.5 text-slate-500 font-mono text-[11px]">
                      {formatCoordinate(cluster.latitude ?? 0, cluster.longitude ?? 0)}
                    </td>
                    <td className="px-3.5 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectCluster(cluster);
                        }}
                        className="px-2 py-1 rounded text-[11px] font-semibold bg-navy-900 text-white dark:bg-blue-600 hover:bg-navy-800 transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="text-center py-16 text-slate-400 dark:text-slate-500">
                    No clusters match current filters or search query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <div>
            Showing {(safePage - 1) * pageSize + 1} to {Math.min(safePage * pageSize, filtered.length)} of {filtered.length} clusters
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, Math.min(p, totalPages) - 1))}
              className="px-2.5 py-1 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 transition-colors"
            >
              Previous
            </button>
            <span className="px-2 font-bold text-slate-700 dark:text-slate-200">
              {safePage} / {totalPages}
            </span>
            <button
              type="button"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="px-2.5 py-1 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Event Detail Intelligence Dossier */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
