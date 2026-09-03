import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchActiveAlerts } from '../api/client';
import type { ThermalAlert } from '../types';

// This notification layer polls the alert API. It does not itself make
// upstream FIRMS ingestion real-time — it is a dashboard polling layer on
// top of the already-processed (non-real-time) thermal alert dataset.
const POLL_INTERVAL_MS = 15000;

// How many CRITICAL/HIGH toasts may be visible at once (avoid overwhelming).
const MAX_VISIBLE_POPUPS = 3;

// On first load we surface a small number of the most severe currently-active
// alerts (an operator opening the dashboard sees the top criticals), while
// seeding the dedup set with everything else so we never spam dozens of
// popups for pre-existing alerts. Only NEW alerts detected on later polls
// produce additional popups.
const INITIAL_POPUP_LIMIT = 2;

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

/**
 * A notification is only eligible to pop up when it is ACTIVE, NOT suppressed
 * (never an operator alarm) and HIGH or CRITICAL severity. MEDIUM/LOW alerts
 * never produce a disruptive popup.
 */
export function isPopupEligible(alert: ThermalAlert): boolean {
  return (
    alert.status === 'ACTIVE' &&
    !alert.suppressed &&
    (alert.severity === 'HIGH' || alert.severity === 'CRITICAL')
  );
}

/** Stable severity ordering: CRITICAL first, then HIGH (used for popups/center). */
export function compareAlertSeverity(a: ThermalAlert, b: ThermalAlert): number {
  const rankDiff = (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0);
  if (rankDiff !== 0) return rankDiff;
  return String(b.updated_at).localeCompare(String(a.updated_at));
}

export interface UseThermalAlertsResult {
  /** Currently ACTIVE unsuppressed HIGH/CRITICAL alerts (drives bell + center list). */
  eligibleAlerts: ThermalAlert[];
  /** Popup queue — only NEWLY detected alerts land here. */
  popups: ThermalAlert[];
  totalCritical: number;
  totalHigh: number;
  apiAvailable: boolean;
  lastUpdated: string | null;
  centerOpen: boolean;
  setCenterOpen: (open: boolean) => void;
  dismissPopup: (alertId: string) => void;
  viewAlert: (alert: ThermalAlert) => void;
}

export function useThermalAlerts(onViewAlert?: (alert: ThermalAlert) => void): UseThermalAlertsResult {
  const [eligibleAlerts, setEligibleAlerts] = useState<ThermalAlert[]>([]);
  const [popups, setPopups] = useState<ThermalAlert[]>([]);
  const [apiAvailable, setApiAvailable] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [centerOpen, setCenterOpen] = useState(false);

  // Local dedup state: alert_ids we have already surfaced (or seeded) this
  // session. Same alert across polls never pops twice.
  const seenIdsRef = useRef<Set<string>>(new Set());
  const firstPollDoneRef = useRef(false);
  const onViewAlertRef = useRef(onViewAlert);
  onViewAlertRef.current = onViewAlert;

  const dismissPopup = useCallback((alertId: string) => {
    setPopups((prev) => prev.filter((p) => p.alert_id !== alertId));
  }, []);

  // Auto-dismiss popups after a few seconds (visual only — never touches the
  // backend alert lifecycle).
  useEffect(() => {
    if (popups.length === 0) return;
    const timers = popups.map((p) =>
      setTimeout(() => dismissPopup(p.alert_id), 20000),
    );
    return () => timers.forEach((t) => clearTimeout(t));
  }, [popups, dismissPopup]);

  const ingestAlerts = useCallback(
    (alerts: ThermalAlert[]) => {
      const activeAlerts = alerts
        .filter((a) => a.status === 'ACTIVE' && !a.suppressed)
        .sort(compareAlertSeverity);

      const eligible = activeAlerts.filter((a) => a.severity === 'HIGH' || a.severity === 'CRITICAL');
      setEligibleAlerts(eligible);

      const newlySeen: ThermalAlert[] = [];
      for (const alert of eligible) {
        if (!seenIdsRef.current.has(alert.alert_id)) {
          newlySeen.push(alert);
        }
      }

      if (!firstPollDoneRef.current) {
        // First poll: surface the top INITIAL_POPUP_LIMIT CRITICAL/HIGH as a
        // visible "here's what is currently active" notification, then seed the
        // dedup set with all eligible ids so pre-existing alerts never spam.
        firstPollDoneRef.current = true;
        const initial = newlySeen.slice(0, INITIAL_POPUP_LIMIT);
        newlySeen.forEach((a) => seenIdsRef.current.add(a.alert_id));
        if (initial.length > 0) {
          setPopups(initial);
        }
        return;
      }

      // Subsequent polls: every genuinely new alert becomes a popup.
      if (newlySeen.length > 0) {
        newlySeen.forEach((a) => seenIdsRef.current.add(a.alert_id));
        setPopups((prev) => {
          const merged = [...prev, ...newlySeen];
          const unique = merged.filter(
            (a, idx, arr) => arr.findIndex((x) => x.alert_id === a.alert_id) === idx,
          );
          // Keep the most severe ones within the visible cap.
          return unique.sort(compareAlertSeverity).slice(0, MAX_VISIBLE_POPUPS);
        });
      }
    },
    [],
  );

  const poll = useCallback(async () => {
    try {
      const alerts = await fetchActiveAlerts();
      setApiAvailable(true);
      setLastUpdated(new Date().toISOString());
      ingestAlerts(alerts);
    } catch (err) {
      // Network/API failure: keep the last known-good data, surface an honest
      // "unavailable" state, and never fabricate alerts.
      console.error('Alert API unavailable during poll:', err);
      setApiAvailable(false);
    }
  }, [ingestAlerts]);

  useEffect(() => {
    // Immediate poll on mount.
    poll();
    const intervalId = window.setInterval(() => {
      // Skip polling while the tab is hidden (battery/network friendly).
      if (!document.hidden) {
        poll();
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [poll]);

  const totalCritical = useMemo(
    () => eligibleAlerts.filter((a) => a.severity === 'CRITICAL').length,
    [eligibleAlerts],
  );
  const totalHigh = useMemo(
    () => eligibleAlerts.filter((a) => a.severity === 'HIGH').length,
    [eligibleAlerts],
  );

  const viewAlert = useCallback(
    (alert: ThermalAlert) => {
      // Close popup/center and route to the existing event detail panel.
      dismissPopup(alert.alert_id);
      setCenterOpen(false);
      onViewAlertRef.current?.(alert);
    },
    [dismissPopup],
  );

  return {
    eligibleAlerts,
    popups,
    totalCritical,
    totalHigh,
    apiAvailable,
    lastUpdated,
    centerOpen,
    setCenterOpen,
    dismissPopup,
    viewAlert,
  };
}
