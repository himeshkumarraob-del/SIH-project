import { useEffect, useState, useMemo } from 'react';
import { useFilters } from '../hooks/useFilters';
import { fetchClusters } from '../api/client';
import { formatCoordinate } from '../utils/formatters';
import type { ClusterSummary } from '../types';

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
    <span className="ml-1 text-slate-300">
      {sortKey === col ? (sortAsc ? '↑' : '↓') : '↕'}
    </span>
  );

  return (
    <div className="bg-white border-t border-slate-200 flex flex-col flex-shrink-0" style={{ height: '180px' }}>
      {/* Table header bar */}
      <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-navy-900">High-Priority Events</h2>
          <span className="text-xs text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
            {filtered.length} clusters
          </span>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search cluster ID or factors..."
          className="px-2 py-1 text-xs border border-slate-200 rounded w-48 focus:outline-none focus:ring-1 focus:ring-navy-500"
        />
      </div>

      {/* Scrollable table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 sticky top-0">
            <tr className="text-left text-slate-500">
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
            </tr>
          </thead>
          <tbody>
            {filtered.map((cluster) => (
              <tr
                key={cluster.cluster_id}
                className={`cursor-pointer transition-colors border-l-2 ${
                  selectedClusterId === cluster.cluster_id
                    ? 'bg-navy-50 border-l-navy-600'
                    : 'hover:bg-slate-50 border-l-transparent'
                }`}
                onClick={() => onSelectCluster(cluster)}
              >
                <td className="px-3 py-1.5 font-medium text-navy-800">
                  #{cluster.cluster_id}
                </td>
                <td className="px-3 py-1.5">
                  <span className={`font-semibold ${
                    cluster.risk_level === 'HIGH' ? 'text-red-600' :
                    cluster.risk_level === 'MEDIUM' ? 'text-amber-600' :
                    'text-green-600'
                  }`}>
                    {cluster.risk_score}
                  </span>
                  <span className="ml-1 text-slate-400">{cluster.risk_level}</span>
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
                <td className="px-3 py-1.5 text-slate-600 capitalize">
                  {cluster.persistence_category?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td className="px-3 py-1.5 text-slate-600 truncate max-w-[160px]">
                  {cluster.anomaly_characterization?.replace(/_/g, ' ') ?? '—'}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-400">
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
  let cls = 'bg-slate-100 text-slate-600';
  if (level === 'HIGH') cls = invert ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200';
  else if (level === 'MEDIUM') cls = 'bg-amber-50 text-amber-700 border border-amber-200';
  else if (level === 'LOW') cls = invert ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200';
  else if (level === 'ELEVATED') cls = 'bg-orange-50 text-orange-700 border border-orange-200';
  else if (level === 'NORMAL') cls = 'bg-green-50 text-green-700 border border-green-200';

  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {level}
    </span>
  );
}
