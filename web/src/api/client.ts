/**
 * API client — starts in MOCK mode. Toggle USE_MOCK to false when
 * FastAPI backend is available. The dev server proxies /api → localhost:8000.
 */

import type { ThermalEvent, ClusterSummary, MovementVector, DashboardStats, FilterState, ClassificationData } from '../types';
import { MOCK_EVENTS, MOCK_CLUSTERS, MOCK_MOVEMENTS, MOCK_STATISTICS } from '../data/mockData';
import { MOCK_CLASSIFICATIONS } from '../data/classifications';

const USE_MOCK = true;

function applyFilters<T extends object>(
  items: T[],
  filters: FilterState,
  fieldMap: Partial<Record<keyof FilterState, keyof T>>,
): T[] {
  return items.filter((item) => {
    for (const [filterKey, fieldKey] of Object.entries(fieldMap)) {
      const filterValues = filters[filterKey as keyof FilterState];
      if (Array.isArray(filterValues) && filterValues.length > 0) {
        const itemValue = String((item as Record<string, unknown>)[fieldKey as string] ?? '');
        if (!filterValues.includes(itemValue)) return false;
      }
    }
    if (filters.dateRange && filters.dateRange.start && filters.dateRange.end) {
      const dateVal = String((item as Record<string, unknown>)['acq_date'] ?? '');
      if (dateVal && (dateVal < filters.dateRange.start || dateVal > filters.dateRange.end)) {
        return false;
      }
    }
    return true;
  });
}

export async function fetchEvents(filters: FilterState): Promise<ThermalEvent[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_EVENTS, filters, {
      abnormalityLevel: 'abnormality_level',
      persistenceCategory: 'persistence_category',
      satellite: 'source_satellite',
    });
  }
  const params = new URLSearchParams();
  if (filters.abnormalityLevel.length) params.set('abnormality_level', filters.abnormalityLevel.join(','));
  if (filters.persistenceCategory.length) params.set('persistence_category', filters.persistenceCategory.join(','));
  if (filters.satellite.length) params.set('satellite', filters.satellite.join(','));
  if (filters.dateRange?.start) params.set('start_date', filters.dateRange.start);
  if (filters.dateRange?.end) params.set('end_date', filters.dateRange.end);
  const res = await fetch(`/api/v1/events?${params}`);
  return res.json();
}

export async function fetchClusters(filters: FilterState): Promise<ClusterSummary[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_CLUSTERS, filters, {
      riskLevel: 'risk_level',
      abnormalityLevel: 'abnormality_level',
      falseAlarmConcern: 'false_alarm_indicator',
      persistenceCategory: 'persistence_category',
    });
  }
  const params = new URLSearchParams();
  if (filters.riskLevel.length) params.set('risk_level', filters.riskLevel.join(','));
  if (filters.abnormalityLevel.length) params.set('abnormality_level', filters.abnormalityLevel.join(','));
  if (filters.falseAlarmConcern.length) params.set('false_alarm_indicator', filters.falseAlarmConcern.join(','));
  const res = await fetch(`/api/v1/clusters?${params}`);
  return res.json();
}

export async function fetchMovement(filters: FilterState): Promise<MovementVector[]> {
  if (USE_MOCK) {
    return applyFilters(MOCK_MOVEMENTS, filters, {
      movementStatus: 'movement_status',
    });
  }
  const params = new URLSearchParams();
  if (filters.movementStatus.length) params.set('movement_status', filters.movementStatus.join(','));
  const res = await fetch(`/api/v1/movement?${params}`);
  return res.json();
}

export async function fetchStatistics(): Promise<DashboardStats> {
  if (USE_MOCK) {
    return MOCK_STATISTICS;
  }
  const res = await fetch('/api/v1/statistics');
  return res.json();
}

/** Merge cluster summary data into events for the detail panel */
export function findClusterSummary(clusterId: number): ClusterSummary | undefined {
  return MOCK_CLUSTERS.find((c) => c.cluster_id === clusterId);
}

export function findMovement(clusterId: number): MovementVector | undefined {
  return MOCK_MOVEMENTS.find((m) => m.cluster_id === clusterId);
}

export function findClassification(clusterId: number): ClassificationData | undefined {
  return MOCK_CLASSIFICATIONS[clusterId];
}
