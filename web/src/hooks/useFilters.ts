import { useState, useCallback, createContext, useContext } from 'react';
import type { FilterState } from '../types';
import { EMPTY_FILTERS } from '../types';

interface FilterContextValue {
  filters: FilterState;
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  toggleFilterValue: (key: keyof FilterState, value: string) => void;
  clearAllFilters: () => void;
  activeFilterCount: number;
}

export const FilterContext = createContext<FilterContextValue | null>(null);

export function useFilterState() {
  const [filters, setFilters] = useState<FilterState>({ ...EMPTY_FILTERS });

  const setFilter = useCallback(<K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const toggleFilterValue = useCallback((key: keyof FilterState, value: string) => {
    setFilters((prev) => {
      const current = prev[key];
      if (!Array.isArray(current)) return prev;
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [key]: next };
    });
  }, []);

  const clearAllFilters = useCallback(() => {
    setFilters({ ...EMPTY_FILTERS });
  }, []);

  const activeFilterCount = [
    ...filters.riskLevel,
    ...filters.abnormalityLevel,
    ...filters.falseAlarmConcern,
    ...filters.movementStatus,
    ...filters.persistenceCategory,
    ...filters.satellite,
    ...(filters.dateRange ? ['dateRange'] : []),
  ].length;

  return { filters, setFilter, toggleFilterValue, clearAllFilters, activeFilterCount };
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
}
