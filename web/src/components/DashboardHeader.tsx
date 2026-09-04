import { useEffect, useState, type ReactNode } from 'react';
import { fetchStatistics } from '../api/client';
import { formatNumber } from '../utils/formatters';
import type { DashboardStats } from '../types';
import { useTheme } from '../hooks/useTheme';

interface DashboardHeaderProps {
  /** Optional right-side header actions (e.g. thermal alert bell). */
  actions?: ReactNode;
  /** Mobile filter drawer toggle */
  onToggleFilters?: () => void;
  /** Active filter count for mobile badge */
  activeFilterCount?: number;
}

export default function DashboardHeader({
  actions,
  onToggleFilters,
  activeFilterCount = 0,
}: DashboardHeaderProps) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const { isDark, toggleTheme } = useTheme();

  useEffect(() => {
    fetchStatistics().then(setStats);
  }, []);

  if (!stats) return null;

  const cards = [
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
      badge: true,
      badgeColor: 'bg-red-100 text-red-700 dark:bg-red-950/80 dark:text-red-300',
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
      label: 'High False-Alarm Concern',
      value: stats.high_false_alarm_count,
      color: 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900',
      textColor: 'text-slate-700 dark:text-slate-300',
      icon: (
        <svg className="w-5 h-5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ];

  return (
    <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-3 sm:px-4 py-2.5 transition-colors duration-200 flex-shrink-0">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-7 h-7 sm:w-8 sm:h-8 bg-navy-800 dark:bg-navy-700 rounded-lg flex items-center justify-center shadow-xs flex-shrink-0">
            <svg className="w-4 h-4 sm:w-5 sm:h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-sm sm:text-base font-bold text-navy-900 dark:text-slate-100 leading-tight truncate">
              Thermal Intelligence
            </h1>
            <p className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 truncate hidden xs:block">
              Operational Dashboard — India VIIRS Anomaly Monitoring
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap ml-auto">
          {/* Mobile Filter Drawer Toggle Button */}
          {onToggleFilters && (
            <button
              onClick={onToggleFilters}
              className="lg:hidden flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-navy-900 dark:bg-navy-700 text-white shadow-2xs hover:bg-navy-800 dark:hover:bg-navy-600 transition-colors"
              title="Open filters"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <span>FILTERS</span>
              {activeFilterCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
          )}

          {actions}

          {/* Theme Switcher Button */}
          <button
            onClick={toggleTheme}
            className="flex items-center gap-1 px-2 sm:px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors shadow-2xs"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {isDark ? (
              <>
                <svg className="w-3.5 h-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                <span className="hidden xs:inline">LIGHT</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
                <span className="hidden xs:inline">DARK</span>
              </>
            )}
          </button>

          <span className="inline-flex items-center px-1.5 sm:px-2 py-0.5 rounded text-[11px] sm:text-xs font-medium bg-green-50 dark:bg-green-950/60 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1 sm:mr-1.5 animate-pulse" />
            <span className="hidden xs:inline">LIVE DATA</span>
            <span className="xs:hidden">LIVE</span>
          </span>
          <span className="text-[11px] sm:text-xs text-slate-400 dark:text-slate-500 hidden sm:inline">
            Aug 2026
          </span>
        </div>
      </div>

      {/* Responsive KPI Grid: 2 columns on mobile, 3 columns on tablet, 5 columns on desktop */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-1.5 sm:gap-2">
        {cards.map((card, idx) => (
          <div
            key={card.label}
            className={`flex items-center gap-2 sm:gap-2.5 px-2.5 py-1.5 sm:px-3 sm:py-2 rounded-lg border ${card.color} transition-colors duration-200 ${idx === 4 ? 'col-span-2 sm:col-span-1' : ''}`}
          >
            <div className="flex-shrink-0">{card.icon}</div>
            <div className="min-w-0 flex-1">
              <div className={`text-base sm:text-lg font-bold leading-tight ${card.textColor}`}>
                {formatNumber(card.value)}
              </div>
              <div className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 truncate">{card.label}</div>
            </div>
          </div>
        ))}
      </div>
    </header>
  );
}

