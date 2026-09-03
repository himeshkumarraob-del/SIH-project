import { useEffect, useState, type ReactNode } from 'react';
import { fetchStatistics } from '../api/client';
import { formatNumber } from '../utils/formatters';
import type { DashboardStats } from '../types';

interface DashboardHeaderProps {
  /** Optional right-side header actions (e.g. thermal alert bell). */
  actions?: ReactNode;
}

export default function DashboardHeader({ actions }: DashboardHeaderProps) {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    fetchStatistics().then(setStats);
  }, []);

  if (!stats) return null;

  const cards = [
    {
      label: 'Total Detections',
      value: stats.total_detections,
      color: 'border-slate-300',
      textColor: 'text-slate-900',
      icon: (
        <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      ),
    },
    {
      label: 'Active Clusters',
      value: stats.active_clusters,
      color: 'border-blue-300',
      textColor: 'text-blue-900',
      icon: (
        <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
    {
      label: 'High-Risk Events',
      value: stats.high_risk_count,
      color: 'border-red-300',
      textColor: 'text-red-700',
      badge: true,
      badgeColor: 'bg-red-100 text-red-700',
      icon: (
        <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      ),
    },
    {
      label: 'Moving Clusters',
      value: stats.moving_count,
      color: 'border-amber-300',
      textColor: 'text-amber-700',
      icon: (
        <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
      ),
    },
    {
      label: 'High False-Alarm Concern',
      value: stats.high_false_alarm_count,
      color: 'border-slate-300',
      textColor: 'text-slate-700',
      icon: (
        <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ];

  return (
    <header className="bg-white border-b border-slate-200 px-4 py-2.5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-navy-800 rounded flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-semibold text-navy-900 leading-tight">
              Thermal Intelligence
            </h1>
            <p className="text-xs text-slate-500">
              Operational Dashboard — India VIIRS Anomaly Monitoring
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse" />
            LIVE DATA
          </span>
          <span className="text-xs text-slate-400">
            Aug 2026
          </span>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {cards.map((card) => (
          <div
            key={card.label}
            className={`flex items-center gap-2.5 px-3 py-2 rounded border ${card.color} bg-white`}
          >
            <div className="flex-shrink-0">{card.icon}</div>
            <div className="min-w-0">
              <div className={`text-lg font-bold leading-tight ${card.textColor}`}>
                {formatNumber(card.value)}
              </div>
              <div className="text-xs text-slate-500 truncate">{card.label}</div>
            </div>
          </div>
        ))}
      </div>
    </header>
  );
}
