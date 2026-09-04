import type { ThermalAlert } from '../types';
import { formatNumber } from '../utils/formatters';

/**
 * Visual popup for a decision-support THERMAL ALERT.
 *
 * Wording guardrails: these are "thermal anomaly alerts" produced by the
 * alert engine from processed satellite evidence — never a claim of
 * "confirmed fire". is_decision_support_only is always true for these alerts.
 */

interface ToastProps {
  alert: ThermalAlert;
  onView: (alert: ThermalAlert) => void;
  onDismiss: (alertId: string) => void;
}

function severityChip(severity: string): string {
  return severity === 'CRITICAL'
    ? 'bg-red-600'
    : 'bg-orange-500';
}

function severityAccent(severity: string): string {
  return severity === 'CRITICAL'
    ? 'border-l-red-600'
    : 'border-l-orange-500';
}

function ThermalAlertToast({ alert, onView, onDismiss }: ToastProps) {
  const label = alert.severity === 'CRITICAL' ? 'CRITICAL THERMAL ALERT' : 'HIGH THERMAL ALERT';
  const classification = alert.classification_label ?? 'Unknown / Insufficient Evidence';
  const reasons = (alert.reasons ?? '')
    .split('|')
    .map((r) => r.trim())
    .filter(Boolean)
    .slice(0, 2);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`thermal-toast-enter w-[360px] max-w-[calc(100vw-1.5rem)] rounded-md border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 shadow-xl border-l-4 ${severityAccent(alert.severity)} overflow-hidden`}
    >
      <div className="px-3 pt-2.5 pb-2">
        {/* Header */}
        <div className="flex items-start gap-2">
          <span
            aria-hidden="true"
            className={`mt-0.5 w-6 h-6 flex-shrink-0 rounded ${severityChip(alert.severity)} flex items-center justify-center`}
          >
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <div className={`text-sm font-bold tracking-wide ${alert.severity === 'CRITICAL' ? 'text-red-700 dark:text-red-400' : 'text-orange-700 dark:text-orange-400'}`}>
              {label}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Thermal anomaly detected — decision-support alert
            </div>
          </div>
          <button
            type="button"
            aria-label={`Dismiss alert for cluster ${alert.cluster_id}`}
            onClick={() => onDismiss(alert.alert_id)}
            className="flex-shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <div>
            <dt className="text-slate-400 dark:text-slate-500">Cluster</dt>
            <dd className="font-semibold text-slate-800 dark:text-slate-200">#{alert.cluster_id}</dd>
          </div>
          <div>
            <dt className="text-slate-400 dark:text-slate-500">Risk Score</dt>
            <dd className="font-semibold text-slate-800 dark:text-slate-200">
              {alert.risk_score != null ? formatNumber(alert.risk_score) : '—'}
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-slate-400 dark:text-slate-500">Classification</dt>
            <dd className="font-medium text-slate-800 dark:text-slate-200 truncate">
              {classification}
              {alert.classification_score != null ? ` (${(alert.classification_score * 100).toFixed(0)}%)` : ''}
            </dd>
          </div>
          <div>
            <dt className="text-slate-400 dark:text-slate-500">Evidence</dt>
            <dd className="font-semibold text-slate-800 dark:text-slate-200">{alert.evidence_confidence ?? 'INSUFFICIENT'}</dd>
          </div>
          <div>
            <dt className="text-slate-400 dark:text-slate-500">Status</dt>
            <dd className="font-semibold text-slate-800 dark:text-slate-200">{alert.status}</dd>
          </div>
        </dl>

        {reasons.length > 0 && (
          <div className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
            {reasons.map((r, i) => (
              <div key={i} className="flex gap-1">
                <span aria-hidden="true" className="text-slate-300 dark:text-slate-600">•</span>
                <span className="truncate">{r}</span>
              </div>
            ))}
          </div>
        )}

        {alert.station_available && (
          <div className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400 truncate">
            Fire station: {alert.nearest_station_name}
            {alert.station_distance_km != null ? ` (${formatNumber(alert.station_distance_km)} km)` : ''}
          </div>
        )}

        {/* Actions */}
        <div className="mt-2.5 flex items-center gap-2 border-t border-slate-100 dark:border-slate-800 pt-2">
          <button
            type="button"
            onClick={() => onView(alert)}
            className={`flex-1 rounded px-3 py-1.5 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-offset-1 ${severityChip(alert.severity)} hover:opacity-90 focus:ring-red-400`}
          >
            VIEW EVENT
          </button>
          <button
            type="button"
            onClick={() => onDismiss(alert.alert_id)}
            className="rounded px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            DISMISS
          </button>
        </div>
      </div>
    </div>
  );
}

interface ToastsProps {
  popups: ThermalAlert[];
  onView: (alert: ThermalAlert) => void;
  onDismiss: (alertId: string) => void;
}

export default function ThermalAlertToasts({ popups, onView, onDismiss }: ToastsProps) {
  if (popups.length === 0) return null;

  return (
    // Fixed stack in the bottom-right corner of the viewport (the map's zoom
    // control is top-left, so critical map controls are never permanently
    // covered). Toasts auto-dismiss and are individually dismissible.
    <div className="fixed bottom-4 right-3 z-[1200] flex flex-col gap-2">
      {popups.map((alert) => (
        <ThermalAlertToast
          key={alert.alert_id}
          alert={alert}
          onView={onView}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  );
}
