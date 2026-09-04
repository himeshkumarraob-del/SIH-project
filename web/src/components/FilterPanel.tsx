import { useState, useEffect } from 'react';
import { useFilters } from '../hooks/useFilters';
import { fetchClusters } from '../api/client';
import { formatNumber } from '../utils/formatters';

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  activeCount?: number;
  icon?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function CollapsibleSection({
  title,
  activeCount = 0,
  icon,
  defaultOpen = true,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-slate-100/90 dark:border-slate-800/80 py-2.5 last:border-b-0">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-left group py-0.5"
      >
        <div className="flex items-center gap-1.5 min-w-0">
          {icon && <span className="text-slate-400 dark:text-slate-500 group-hover:text-navy-700 dark:group-hover:text-slate-200 transition-colors flex-shrink-0">{icon}</span>}
          <span className="text-xs font-bold text-navy-900 dark:text-slate-200 group-hover:text-navy-700 dark:group-hover:text-white uppercase tracking-wider truncate">
            {title}
          </span>
          {activeCount > 0 && (
            <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-navy-800 dark:bg-navy-600 text-white shadow-2xs">
              {activeCount}
            </span>
          )}
        </div>
        <svg
          className={`w-3.5 h-3.5 text-slate-400 dark:text-slate-500 transition-transform duration-200 flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && <div className="mt-2 space-y-1.5 animate-fadeIn">{children}</div>}
    </div>
  );
}

interface FilterPanelProps {
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export default function FilterPanel({ isMobileOpen = false, onCloseMobile }: FilterPanelProps) {
  const { filters, toggleFilterValue, clearAllFilters, activeFilterCount } = useFilters();
  const [matchingCount, setMatchingCount] = useState<number | null>(null);
  const [loadingCount, setLoadingCount] = useState(false);

  // Dynamically derive matching cluster count from current filter state (no hardcoded count)
  useEffect(() => {
    let cancelled = false;
    setLoadingCount(true);
    fetchClusters(filters)
      .then((clusters) => {
        if (!cancelled) {
          setMatchingCount(clusters.length);
          setLoadingCount(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadingCount(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [filters]);

  const panelContent = (
    <div className="flex flex-col h-full overflow-hidden select-none">
      {/* Top Header: Mission Control & Clear Action */}
      <div className="px-3.5 py-3 border-b border-slate-200/90 dark:border-slate-800 bg-gradient-to-b from-white to-slate-50/80 dark:from-slate-900 dark:to-slate-950/60 flex-shrink-0">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-navy-800 to-navy-950 dark:from-blue-600 dark:to-blue-800 text-white flex items-center justify-center flex-shrink-0 shadow-xs ring-1 ring-white/10">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
            </div>
            <div className="min-w-0">
              <h2 className="text-[11px] font-extrabold text-navy-900 dark:text-slate-100 uppercase tracking-[0.14em] leading-none">
                Mission Filters
              </h2>
              <p className="mt-1 text-[9px] text-slate-400 dark:text-slate-500 uppercase tracking-[0.12em] font-semibold leading-none">
                Surveillance Scope
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {activeFilterCount > 0 ? (
              <button
                onClick={clearAllFilters}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 bg-red-50 dark:bg-red-950/60 hover:bg-red-100 dark:hover:bg-red-900/60 border border-red-200 dark:border-red-900 transition-colors"
                title="Reset all active filters"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5M20 20v-5h-5M4.5 9A7.5 7.5 0 0119 7.5M19.5 15A7.5 7.5 0 015 16.5" />
                </svg>
                Reset {activeFilterCount > 0 ? `· ${activeFilterCount}` : ''}
              </button>
            ) : (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider bg-slate-100 dark:bg-slate-800/80">
                All Active
              </span>
            )}

            {/* Close button for mobile drawer */}
            {onCloseMobile && (
              <button
                onClick={onCloseMobile}
                className="lg:hidden p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
                title="Close filter drawer"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Live Filtered Result Counter */}
        <div className="flex items-center justify-between rounded-md bg-slate-900 dark:bg-slate-950/80 border border-slate-800/60 dark:border-slate-800 px-2.5 py-1.5 text-[11px] shadow-inner">
          <span className="text-slate-400 dark:text-slate-500 font-semibold uppercase tracking-wider">
            Scope Match
          </span>
          <div className="flex items-center gap-1.5 font-mono font-bold">
            {loadingCount ? (
              <span className="text-slate-500 animate-pulse text-[10px] uppercase tracking-wider">Querying…</span>
            ) : (
              <>
                <span className="text-white dark:text-blue-300">{matchingCount !== null ? formatNumber(matchingCount) : '—'}</span>
                <span className="text-slate-500">clusters</span>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              </>
            )}
          </div>
        </div>
      </div>

      {/* Scrollable Filter Categories */}
      <div className="flex-1 overflow-y-auto px-3.5 py-2 space-y-1">
        {/* 1. Risk Level Filter (Pills) */}
        <CollapsibleSection
          title="Risk Level"
          activeCount={filters.riskLevel.length}
          icon={
            <svg className="w-3.5 h-3.5 text-red-500 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          }
        >
          <div className="grid grid-cols-3 gap-1.5">
            {[
              { id: 'HIGH', label: 'High', color: 'border-red-300 dark:border-red-900/80', active: 'bg-red-600 text-white border-red-700 shadow-xs', inactive: 'bg-red-50/70 dark:bg-red-950/40 text-red-700 dark:text-red-400 hover:bg-red-100/80 dark:hover:bg-red-900/40' },
              { id: 'MEDIUM', label: 'Medium', color: 'border-amber-300 dark:border-amber-900/80', active: 'bg-amber-600 text-white border-amber-700 shadow-xs', inactive: 'bg-amber-50/70 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 hover:bg-amber-100/80 dark:hover:bg-amber-900/40' },
              { id: 'LOW', label: 'Low', color: 'border-emerald-300 dark:border-emerald-900/80', active: 'bg-emerald-600 text-white border-emerald-700 shadow-xs', inactive: 'bg-emerald-50/70 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100/80 dark:hover:bg-emerald-900/40' },
            ].map((item) => {
              const isSelected = filters.riskLevel.includes(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => toggleFilterValue('riskLevel', item.id)}
                  className={`px-2 py-1 rounded-md text-xs font-bold border transition-all text-center flex items-center justify-center gap-1 ${
                    isSelected ? item.active : `${item.inactive} ${item.color}`
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-white' : 'bg-current'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 2. AI Abnormality Filter */}
        <CollapsibleSection
          title="AI Abnormality"
          activeCount={filters.abnormalityLevel.length}
          icon={
            <svg className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        >
          <div className="space-y-1">
            {[
              { id: 'HIGH', label: 'High Abnormality', activeClass: 'bg-red-600 text-white border-red-700', inactiveClass: 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800' },
              { id: 'ELEVATED', label: 'Elevated Abnormality', activeClass: 'bg-orange-600 text-white border-orange-700', inactiveClass: 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800' },
              { id: 'NORMAL', label: 'Normal Baseline', activeClass: 'bg-emerald-600 text-white border-emerald-700', inactiveClass: 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800' },
            ].map((item) => {
              const isSelected = filters.abnormalityLevel.includes(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => toggleFilterValue('abnormalityLevel', item.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-medium border transition-all ${
                    isSelected
                      ? `${item.activeClass} shadow-xs font-semibold`
                      : `${item.inactiveClass} border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/60`
                  }`}
                >
                  <span>{item.label}</span>
                  <span className={`w-3.5 h-3.5 rounded flex items-center justify-center ${isSelected ? 'bg-white/20' : 'border border-slate-300 dark:border-slate-600'}`}>
                    {isSelected && (
                      <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 3. False Alarm Concern Filter */}
        <CollapsibleSection
          title="False Alarm Concern"
          activeCount={filters.falseAlarmConcern.length}
          icon={
            <svg className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          }
        >
          <div className="grid grid-cols-3 gap-1">
            {[
              { id: 'LOW', label: 'Low', sub: 'Verified', active: 'bg-emerald-700 text-white border-emerald-800' },
              { id: 'MEDIUM', label: 'Med', sub: 'Uncertain', active: 'bg-amber-600 text-white border-amber-700' },
              { id: 'HIGH', label: 'High', sub: 'Concern', active: 'bg-red-600 text-white border-red-700' },
            ].map((item) => {
              const isSelected = filters.falseAlarmConcern.includes(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => toggleFilterValue('falseAlarmConcern', item.id)}
                  className={`p-1.5 rounded-md text-center border transition-all ${
                    isSelected
                      ? `${item.active} shadow-xs`
                      : 'bg-slate-50/70 dark:bg-slate-800/70 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/60'
                  }`}
                >
                  <div className={`text-xs font-bold leading-tight ${isSelected ? 'text-white' : 'text-slate-800 dark:text-slate-200'}`}>
                    {item.label}
                  </div>
                  <div className={`text-[9px] ${isSelected ? 'text-white/80' : 'text-slate-400 dark:text-slate-500'}`}>
                    {item.sub}
                  </div>
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 4. Thermal Movement Filter */}
        <CollapsibleSection
          title="Thermal Movement"
          activeCount={filters.movementStatus.length}
          icon={
            <svg className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          }
        >
          <div className="space-y-1">
            {[
              {
                id: 'MOVING',
                label: 'Moving Clusters',
                icon: (
                  <svg className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                ),
              },
              {
                id: 'STATIONARY',
                label: 'Stationary Clusters',
                icon: (
                  <svg className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
              {
                id: 'INSUFFICIENT_DATA',
                label: 'Insufficient Vector Data',
                icon: (
                  <svg className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
            ].map((item) => {
              const isSelected = filters.movementStatus.includes(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => toggleFilterValue('movementStatus', item.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs border transition-all ${
                    isSelected
                      ? 'bg-navy-900 dark:bg-navy-700 text-white border-navy-950 dark:border-navy-600 font-bold shadow-xs'
                      : 'bg-slate-50/70 dark:bg-slate-800/70 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/60 font-medium'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <span>{item.icon}</span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {isSelected && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 5. Persistence Footprint Filter */}
        <CollapsibleSection
          title="Persistence"
          activeCount={filters.persistenceCategory.length}
          icon={
            <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        >
          <div className="space-y-1">
            {[
              { id: 'persistent', label: 'Persistent Multi-Day' },
              { id: 'short_lived_repeated', label: 'Short-Lived Repeated' },
              { id: 'isolated', label: 'Isolated Single-Pass' },
            ].map((item) => {
              const isSelected = filters.persistenceCategory.includes(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => toggleFilterValue('persistenceCategory', item.id)}                  className={`w-full flex items-center justify-between px-2 py-1.5 rounded-md text-xs border transition-all ${
                    isSelected
                      ? 'bg-navy-800 dark:bg-navy-700 text-white border-navy-900 dark:border-navy-600 font-semibold shadow-xs'
                      : 'bg-slate-50/60 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/60'
                  }`}>
                  <span className="truncate">{item.label}</span>
                  <span className={`w-2 h-2 rounded-full border ${isSelected ? 'bg-emerald-400 border-white' : 'border-slate-300 dark:border-slate-600'}`} />
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 6. Satellite Constellation */}
        <CollapsibleSection
          title="Satellite Constellation"
          activeCount={filters.satellite.length}
          icon={
            <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
            </svg>
          }
        >
          <div className="grid grid-cols-2 gap-1.5">
            {['NOAA-20', 'NOAA-21'].map((sat) => {
              const isSelected = filters.satellite.includes(sat);
              return (
                <button
                  key={sat}
                  onClick={() => toggleFilterValue('satellite', sat)}
                  className={`px-2 py-1.5 rounded-md text-xs font-semibold border text-center transition-all ${
                    isSelected
                      ? 'bg-navy-900 dark:bg-navy-700 text-white border-navy-950 dark:border-navy-600 shadow-xs'
                      : 'bg-slate-50/70 dark:bg-slate-800/70 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/60'
                  }`}
                >
                  {sat}
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        {/* 7. Temporal Range */}
        <CollapsibleSection
          title="Acquisition Window"
          activeCount={filters.dateRange ? 1 : 0}
          icon={
            <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          }
        >
          <div className="space-y-1.5 bg-slate-50/80 dark:bg-slate-800/70 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
            <div>
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Start Date</span>
              <input
                type="date"
                value={filters.dateRange?.start ?? ''}
                onChange={(e) => {
                  const start = e.target.value;
                  const end = filters.dateRange?.end ?? '2026-08-30';
                  if (start) {
                    toggleFilterValue('dateRange', { start, end } as unknown as string);
                  }
                }}
                className="w-full px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-navy-600"
              />
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">End Date</span>
              <input
                type="date"
                value={filters.dateRange?.end ?? ''}
                onChange={(e) => {
                  const end = e.target.value;
                  const start = filters.dateRange?.start ?? '2026-08-01';
                  if (end) {
                    toggleFilterValue('dateRange', { start, end } as unknown as string);
                  }
                }}
                className="w-full px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-navy-600"
              />
            </div>
          </div>
        </CollapsibleSection>

      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sticky/Fixed Sidebar */}
      <aside className="hidden lg:flex w-60 lg:w-64 flex-shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex-col h-full overflow-hidden transition-colors duration-200">
        {panelContent}
      </aside>

      {/* Mobile / Tablet Slide-Over Drawer */}
      {isMobileOpen && (
        <div className="lg:hidden fixed inset-0 z-[1400] flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          {/* Slide-in Drawer */}
          <div className="relative w-[300px] max-w-[85vw] h-full bg-white dark:bg-slate-900 shadow-2xl flex flex-col overflow-hidden animate-slideRight z-10 border-r border-slate-200 dark:border-slate-800">
            {panelContent}
            {/* Mobile bottom Done action */}
            <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 flex-shrink-0">
              <button
                type="button"
                onClick={onCloseMobile}
                className="w-full py-2 px-3 rounded-lg text-xs font-bold text-white bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 transition-colors shadow-xs"
              >
                Apply & View ({matchingCount !== null ? formatNumber(matchingCount) : '—'} Clusters)
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

