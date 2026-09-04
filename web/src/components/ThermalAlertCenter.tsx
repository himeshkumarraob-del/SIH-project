import type { ThermalAlert } from '../types';
import { formatNumber } from '../utils/formatters';

/**
 * Bell button + compact notification center for active decision-support
 * thermal alerts. Lives in the dashboard header. Opening the list never
 * changes the backend alert lifecycle — only a future explicit
 * acknowledge/resolve action would.
 */

interface CenterProps {
  eligibleAlerts: ThermalAlert[];
  totalCritical: number;
  totalHigh: number;
  apiAvailable: boolean;
  lastUpdated: string | null;
  centerOpen: boolean;
  setCenterOpen: (open: boolean) => void;
  onView: (alert: ThermalAlert) => void;
}

const severityChip: Record<string, string> = {
  CRITICAL: 'bg-red-600',
  HIGH: 'bg-orange-500',
  MEDIUM: 'bg-amber-500',
  LOW: 'bg-slate-400',
};

const severityText: Record<string, string> = {
  CRITICAL: 'text-red-700',
  HIGH: 'text-orange-700',
  MEDIUM: 'text-amber-700',
  LOW: 'text-slate-500',
};

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

export default function ThermalAlertCenter({
  eligibleAlerts,
  totalCritical,
  totalHigh,
  apiAvailable,
  lastUpdated,
  centerOpen,
  setCenterOpen,
  onView,
}: CenterProps) {
  const count = totalCritical + totalHigh;
  const hasEligible = eligibleAlerts.length > 0;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Open thermal alert list (${count} active high or critical ${count === 1 ? 'alert' : 'alerts'})`}
        aria-haspopup="dialog"
        aria-expanded={centerOpen}
        onClick={() => setCenterOpen(!centerOpen)}
        className="relative inline-flex items-center justify-center rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-red-300"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
          />
        </svg>
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white shadow-sm shadow-red-500/50">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {centerOpen && (
        <div
          role="dialog"
          aria-label="Active thermal alerts"
          // Fixed under the header's title row on the right — never over the
          // map's top-left zoom controls. Dismissible and keyboard operable.
          className="fixed top-36 right-3 z-[1300] w-[380px] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-2xl ring-1 ring-black/5 dark:border-slate-800 dark:bg-slate-900 dark:ring-white/10"
        >
          <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-800/80">
            <div>
              <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                Thermal Alerts
                <span className="ml-2 inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
                  <span className={`w-1.5 h-1.5 rounded-full ${apiAvailable ? 'bg-green-500' : 'bg-amber-500'}`} />
                  {apiAvailable ? 'Live API' : 'API unavailable'}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 dark:text-slate-500">
                {hasEligible
                  ? `${totalCritical} critical · ${totalHigh} high · updated ${formatTimestamp(lastUpdated)}`
                  : 'No active HIGH/CRITICAL alerts'}
              </div>
            </div>
            <button
              type="button"
              aria-label="Close alert list"
              onClick={() => setCenterOpen(false)}
              className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-300"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="max-h-[60vh] overflow-y-auto">
            {!apiAvailable && !hasEligible && (
              <div className="px-3 py-4 text-xs text-slate-500 dark:text-slate-400">
                Alert API is currently unavailable. Last known data is retained;
                polling will resume automatically.
              </div>
            )}

            {hasEligible ? (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {eligibleAlerts.map((alert) => {
                  const classification = alert.classification_label ?? 'Unknown';
                  return (
                    <li
                      key={alert.alert_id}
                      className={alert.severity === 'CRITICAL' ? 'border-l-2 border-l-red-600' : ''}
                    >
                      <button
                        type="button"
                        onClick={() => onView(alert)}
                        className="w-full px-3 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-800/60 focus:outline-none focus:bg-slate-50 dark:focus:bg-slate-800/60 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold text-white ${severityChip[alert.severity] ?? 'bg-slate-400'}`}
                          >
                            {alert.severity}
                          </span>
                          <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                            Cluster #{alert.cluster_id}
                          </span>
                          <span className="ml-auto text-[11px] text-slate-400 dark:text-slate-500">
                            {formatTimestamp(alert.updated_at)}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                          <span>
                            Risk{' '}
                            <span className="font-semibold text-slate-700 dark:text-slate-300">
                              {alert.risk_score != null ? formatNumber(alert.risk_score) : '—'}
                            </span>
                          </span>
                          <span className="truncate max-w-[160px]">{classification}</span>
                          <span className={severityText[alert.severity] ?? 'text-slate-500'}>
                            Evidence {alert.evidence_confidence ?? 'INSUFFICIENT'}
                          </span>
                          <span>Status {alert.status}</span>
                        </div>
                        {alert.station_available && (
                          <div className="mt-0.5 truncate text-[11px] text-slate-400 dark:text-slate-500">
                            {alert.nearest_station_name}
                            {alert.station_distance_km != null
                              ? ` (${formatNumber(alert.station_distance_km)} km)`
                              : ''}
                          </div>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="px-3 py-5 text-center text-xs text-slate-500 dark:text-slate-400">
                No active unsuppressed HIGH/CRITICAL alerts right now.
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 bg-slate-50 px-3 py-1.5 text-[10px] leading-snug text-slate-400 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-500">
            Decision-support alerts from processed satellite evidence — not
            confirmed fire declarations. No automatic dispatch.
          </div>
        </div>
      )}
    </div>
  );
}
