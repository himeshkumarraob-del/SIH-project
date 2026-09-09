import { useEffect, useState, useMemo } from 'react';
import { useFilters } from '../hooks/useFilters';
import { fetchClusters } from '../api/client';
import { formatCoordinate } from '../utils/formatters';
import type { ClusterSummary } from '../types';
import { triggerIncidentReportDownload } from '../utils/reportGenerator';


interface ClusterTableProps {
  selectedClusterId: number | null;
  onSelectCluster: (cluster: ClusterSummary) => void;
}

type SortKey = 'risk_score' | 'cluster_id' | 'abnormality_level' | 'false_alarm_indicator' | 'detection_reliability' | 'persistence_category';

const LEVEL_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, ELEVATED: 2, NORMAL: 1 };

export default function ClusterTable({ selectedClusterId, onSelectCluster }: ClusterTableProps) {
  const { filters } = useFilters();
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('risk_score');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    fetchClusters(filters).then(setClusters);
  }, [filters]);

  const filtered = useMemo(() => {
    let result = clusters;

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          String(c.cluster_id).includes(q) ||
          c.anomaly_characterization?.toLowerCase().includes(q) ||
          c.risk_factors?.toLowerCase().includes(q)
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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ col }: { col: SortKey }) => (
    <span className="ml-1 text-slate-300 dark:text-slate-600">
      {sortKey === col ? (sortAsc ? '↑' : '↓') : '↕'}
    </span>
  );

  return (
    <div className="bg-transparent border-t border-slate-200/90 dark:border-white/[0.06] flex flex-col flex-shrink-0 transition-colors duration-200 h-[170px] sm:h-[190px]">
      {/* Table header bar */}
      <div className="px-3.5 sm:px-4 py-2 sm:py-2.5 border-b border-slate-100 dark:border-white/[0.06] flex flex-wrap items-center justify-between gap-2 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-gradient-to-br from-navy-700 to-navy-900 dark:from-slate-700 dark:to-slate-800 text-white flex items-center justify-center shadow-sm ring-1 ring-inset ring-white/15">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </div>
          <h2 className="text-xs sm:text-sm font-bold text-navy-900 dark:text-slate-100">High-Priority Events</h2>
          <span className="text-[10px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.06] px-2 py-0.5 rounded-full border border-slate-200/80 dark:border-white/[0.06]">
            {filtered.length} clusters
          </span>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search cluster ID or factors..."
          className="px-2 py-1 text-xs border border-slate-200 dark:border-slate-700 rounded w-full xs:w-44 sm:w-48 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-navy-500 dark:focus:ring-blue-500"
        />
      </div>

      {/* Scrollable table container */}
      <div className="flex-1 overflow-x-auto overflow-y-auto">
        <table className="min-w-[640px] w-full text-xs">
          <thead className="bg-slate-50/90 dark:bg-slate-950/70 backdrop-blur-sm sticky top-0 border-b border-slate-200/90 dark:border-white/[0.06]">
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('cluster_id')}>
                Cluster ID <SortIcon col="cluster_id" />
              </th>
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('risk_score')}>
                Risk Score <SortIcon col="risk_score" />
              </th>
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('abnormality_level')}>
                AI Abnormality <SortIcon col="abnormality_level" />
              </th>
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('false_alarm_indicator')}>
                False Alarm <SortIcon col="false_alarm_indicator" />
              </th>
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('detection_reliability')}>
                Reliability <SortIcon col="detection_reliability" />
              </th>
              <th className="px-3 py-1.5 font-medium cursor-pointer" onClick={() => handleSort('persistence_category')}>
                Persistence <SortIcon col="persistence_category" />
              </th>
              <th className="px-3 py-1.5 font-medium">Characterization</th>
              <th className="px-3 py-1.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
            {filtered.map((cluster) => (
              <tr
                key={cluster.cluster_id}
                className={`cursor-pointer transition-colors border-l-2 ${
                  selectedClusterId === cluster.cluster_id
                    ? 'bg-navy-50 dark:bg-slate-800/80 border-l-navy-600 dark:border-l-blue-500'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/50 border-l-transparent'
                }`}
                onClick={() => onSelectCluster(cluster)}
              >
                <td className="px-3 py-1.5 font-medium text-navy-800 dark:text-slate-200">
                  #{cluster.cluster_id}
                </td>
                <td className="px-3 py-1.5">
                  <span className={`font-semibold ${
                    cluster.risk_level === 'HIGH' ? 'text-red-600 dark:text-red-400' :
                    cluster.risk_level === 'MEDIUM' ? 'text-amber-600 dark:text-amber-400' :
                    'text-green-600 dark:text-green-400'
                  }`}>
                    {cluster.risk_score}
                  </span>
                  <span className="ml-1 text-slate-400 dark:text-slate-500">{cluster.risk_level}</span>
                </td>
                <td className="px-3 py-1.5">
                  <LevelBadge level={cluster.abnormality_level} />
                </td>
                <td className="px-3 py-1.5">
                  <LevelBadge level={cluster.false_alarm_indicator} invert />
                </td>
                <td className="px-3 py-1.5">
                  <LevelBadge level={cluster.detection_reliability} />
                </td>
                <td className="px-3 py-1.5 text-slate-600 dark:text-slate-400 capitalize">
                  {cluster.persistence_category?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td className="px-3 py-1.5 text-slate-600 dark:text-slate-400 truncate max-w-[160px]">
                  {cluster.anomaly_characterization?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    onClick={() => triggerIncidentReportDownload(cluster.cluster_id)}
                    className="px-2 py-0.5 rounded text-[10px] font-bold text-navy-900 dark:text-sky-400 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700"
                    title="Download PDF Incident Report"
                  >
                    📄 Report
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-slate-400 dark:text-slate-500">
                  No clusters match current filters
                </td>
              </tr>
            )}

          </tbody>
        </table>
      </div>
    </div>
  );
}

function LevelBadge({ level, invert = false }: { level: string; invert?: boolean }) {
  let cls = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400';
  if (level === 'HIGH') cls = invert ? 'bg-green-50 dark:bg-green-950/60 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800';
  else if (level === 'MEDIUM') cls = 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800';
  else if (level === 'LOW') cls = invert ? 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800' : 'bg-green-50 dark:bg-green-950/60 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800';
  else if (level === 'ELEVATED') cls = 'bg-orange-50 dark:bg-orange-950/60 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-800';
  else if (level === 'NORMAL') cls = 'bg-green-50 dark:bg-green-950/60 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800';

  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {level}
    </span>
  );
}
