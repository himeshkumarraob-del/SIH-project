import { useState, useEffect } from 'react';
import { fetchStatistics, fetchClusters, fetchMovement } from '../api/client';
import { formatNumber } from '../utils/formatters';
import type { DashboardStats, ClusterSummary, MovementVector, FilterState } from '../types';

export default function AnalyticsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [movements, setMovements] = useState<MovementVector[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const emptyFilters: FilterState = {
      riskLevel: [],
      abnormalityLevel: [],
      falseAlarmConcern: [],
      movementStatus: [],
      persistenceCategory: [],
      satellite: [],
      dateRange: null,
    };
    Promise.all([
      fetchStatistics(),
      fetchClusters(emptyFilters),
      fetchMovement(emptyFilters),
    ])
      .then(([s, c, m]) => {
        setStats(s);
        setClusters(c);
        setMovements(m);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load analytics:', err);
        setLoading(false);
      });
  }, []);

  const totalClusters = stats?.active_clusters || clusters.length || 1;

  // Derive persistence categories
  const persistenceCounts: Record<string, number> = {};
  let totalFrp = 0;
  let maxObservedFrp = 0;
  clusters.forEach((c) => {
    const cat = c.persistence_category || 'isolated';
    persistenceCounts[cat] = (persistenceCounts[cat] || 0) + 1;
    totalFrp += c.max_frp || 0;
    if ((c.max_frp || 0) > maxObservedFrp) maxObservedFrp = c.max_frp;
  });
  const avgFrp = clusters.length > 0 ? totalFrp / clusters.length : 0;

  // Derive movement stats
  const movingCount = movements.filter((m) => m.movement_status === 'MOVING').length;
  const stationaryCount = movements.filter((m) => m.movement_status === 'STATIONARY').length;
  const insufficientCount = movements.filter((m) => m.movement_status === 'INSUFFICIENT_DATA').length;
  const movingVectors = movements.filter((m) => m.movement_status === 'MOVING');
  const avgMovingRate =
    movingVectors.length > 0
      ? movingVectors.reduce((acc, m) => acc + m.movement_rate_km_per_day, 0) / movingVectors.length
      : 0;

  if (loading || !stats) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50 dark:bg-slate-950 bg-ambient">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-navy-800 dark:border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-500 dark:text-slate-400">Loading Intelligence Analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 bg-ambient p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Title */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100 tracking-tight">
          Thermal & Risk Intelligence Analytics
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
          Distribution metrics, propagation dynamics, false alarm validation, and persistence profiles.
        </p>
      </div>

      {/* Top 4 Highlight Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 panel rounded-xl">
          <span className="text-xs text-slate-400 dark:text-slate-500">Tracked Detections</span>
          <div className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100">
            {formatNumber(stats.total_detections)}
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Across {stats.active_clusters} spatial clusters</span>
        </div>
        <div className="p-3.5 bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/50 rounded-xl shadow-2xs">
          <span className="text-xs text-red-600 dark:text-red-400 font-semibold">High-Risk Ratio</span>
          <div className="text-xl sm:text-2xl font-bold text-red-600 dark:text-red-400">
            {((stats.high_risk_count / totalClusters) * 100).toFixed(1)}%
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">{stats.high_risk_count} critical/high events</span>
        </div>
        <div className="p-3.5 bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 rounded-xl shadow-2xs">
          <span className="text-xs text-amber-600 dark:text-amber-400 font-semibold">Moving Thermal Events</span>
          <div className="text-xl sm:text-2xl font-bold text-amber-600 dark:text-amber-400">
            {movingCount}
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Avg {avgMovingRate.toFixed(2)} km/day velocity</span>
        </div>
        <div className="p-3.5 bg-white dark:bg-slate-900 border border-blue-200 dark:border-blue-900/50 rounded-xl shadow-2xs">
          <span className="text-xs text-blue-600 dark:text-blue-400 font-semibold">Peak FRP Recorded</span>
          <div className="text-xl sm:text-2xl font-bold text-blue-600 dark:text-blue-400">
            {maxObservedFrp.toFixed(1)} MW
          </div>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Average: {avgFrp.toFixed(1)} MW</span>
        </div>
      </div>

      {/* Main Analytical Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 1. Risk Score Distribution */}
        <div className="panel rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">Risk Level Distribution</h3>
            <span className="text-[11px] text-slate-400">Multi-factor score</span>
          </div>
          <div className="space-y-2.5">
            {[
              { level: 'HIGH', count: stats.risk_distribution.HIGH, color: 'bg-red-600', textColor: 'text-red-600 dark:text-red-400' },
              { level: 'MEDIUM', count: stats.risk_distribution.MEDIUM, color: 'bg-amber-500', textColor: 'text-amber-600 dark:text-amber-400' },
              { level: 'LOW', count: stats.risk_distribution.LOW, color: 'bg-green-600', textColor: 'text-green-600 dark:text-green-400' },
            ].map((item) => {
              const pct = ((item.count / totalClusters) * 100).toFixed(1);
              return (
                <div key={item.level} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-bold ${item.textColor}`}>{item.level} Risk</span>
                    <span className="font-mono text-slate-600 dark:text-slate-300">
                      {item.count} ({pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className={`h-full ${item.color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-slate-400 dark:text-slate-500 pt-1">
            Weighted synthesis of thermal anomaly severity, cluster persistence, FRP density, and proximity.
          </p>
        </div>

        {/* 2. AI Abnormality Levels */}
        <div className="panel rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">AI Anomaly Levels</h3>
            <span className="text-[11px] text-slate-400">Isolation Forest</span>
          </div>
          <div className="space-y-2.5">
            {[
              { level: 'HIGH', count: stats.anomaly_distribution.HIGH, color: 'bg-red-600', textColor: 'text-red-600 dark:text-red-400' },
              { level: 'ELEVATED', count: stats.anomaly_distribution.ELEVATED, color: 'bg-amber-500', textColor: 'text-amber-600 dark:text-amber-400' },
              { level: 'NORMAL', count: stats.anomaly_distribution.NORMAL, color: 'bg-green-600', textColor: 'text-green-600 dark:text-green-400' },
            ].map((item) => {
              const pct = ((item.count / totalClusters) * 100).toFixed(1);
              return (
                <div key={item.level} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-bold ${item.textColor}`}>{item.level} Anomaly</span>
                    <span className="font-mono text-slate-600 dark:text-slate-300">
                      {item.count} ({pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className={`h-full ${item.color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-slate-400 dark:text-slate-500 pt-1">
            Multivariate detection using band difference, FRP ratio, and cluster observation density.
          </p>
        </div>

        {/* 3. False Alarm Concern */}
        <div className="panel rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">False-Alarm Intelligence</h3>
            <span className="text-[11px] text-slate-400">Contextual Engine</span>
          </div>
          <div className="space-y-2.5">
            {[
              { level: 'HIGH CONCERN', count: stats.false_alarm_distribution.HIGH, color: 'bg-green-600', textColor: 'text-green-600 dark:text-green-400' },
              { level: 'MEDIUM CONCERN', count: stats.false_alarm_distribution.MEDIUM, color: 'bg-amber-500', textColor: 'text-amber-600 dark:text-amber-400' },
              { level: 'LOW CONCERN', count: stats.false_alarm_distribution.LOW, color: 'bg-slate-500', textColor: 'text-slate-600 dark:text-slate-300' },
            ].map((item) => {
              const pct = ((item.count / totalClusters) * 100).toFixed(1);
              return (
                <div key={item.level} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-bold ${item.textColor}`}>{item.level}</span>
                    <span className="font-mono text-slate-600 dark:text-slate-300">
                      {item.count} ({pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className={`h-full ${item.color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-slate-400 dark:text-slate-500 pt-1">
            Eliminates solar glint, water reflections, and persistent static industrial flares.
          </p>
        </div>

        {/* 4. Thermal Movement Dynamics */}
        <div className="panel rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">Thermal Propagation</h3>
            <span className="text-[11px] text-slate-400">Centroid Telemetry</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2.5 bg-slate-50 dark:bg-slate-800 rounded-lg">
              <div className="text-lg font-bold text-amber-600 dark:text-amber-400">{movingCount}</div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">Moving</div>
            </div>
            <div className="p-2.5 bg-slate-50 dark:bg-slate-800 rounded-lg">
              <div className="text-lg font-bold text-green-600 dark:text-green-400">{stationaryCount}</div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">Stationary</div>
            </div>
            <div className="p-2.5 bg-slate-50 dark:bg-slate-800 rounded-lg">
              <div className="text-lg font-bold text-slate-500 dark:text-slate-400">{insufficientCount}</div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">Single Day</div>
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-amber-50/60 dark:bg-amber-950/40 border border-amber-200/60 dark:border-amber-900/40 text-xs text-amber-800 dark:text-amber-300">
            <strong>Average Propagation Velocity:</strong> {avgMovingRate.toFixed(2)} km/day for detected moving clusters.
          </div>
        </div>

        {/* 5. Persistence Spectrum Breakdown */}
        <div className="panel rounded-xl p-4 space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">Cluster Persistence Breakdown</h3>
            <span className="text-[11px] text-slate-400">Temporal Duration</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {Object.entries(persistenceCounts).map(([cat, count]) => (
              <div key={cat} className="p-3 bg-slate-50 dark:bg-slate-800/80 rounded-xl border border-slate-100 dark:border-slate-700">
                <div className="text-xs font-bold text-slate-500 dark:text-slate-400 capitalize">
                  {cat.replace(/_/g, ' ')}
                </div>
                <div className="text-xl font-bold text-navy-900 dark:text-slate-100 mt-1">{count}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  {((count / totalClusters) * 100).toFixed(1)}% of clusters
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
