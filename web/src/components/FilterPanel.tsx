import { useFilters } from '../hooks/useFilters';

interface FilterGroupProps {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}

function FilterGroup({ label, options, selected, onToggle }: FilterGroupProps) {
  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
        {label}
      </h3>
      <div className="space-y-1">
        {options.map((opt) => {
          const isActive = selected.includes(opt);
          return (
            <label
              key={opt}
              className={`flex items-center gap-2 px-2 py-1 rounded text-sm cursor-pointer transition-colors ${
                isActive
                  ? 'bg-navy-800 text-white'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              <input
                type="checkbox"
                checked={isActive}
                onChange={() => onToggle(opt)}
                className="sr-only"
              />
              <span
                className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                  isActive
                    ? 'bg-white border-white'
                    : 'border-slate-300 bg-white'
                }`}
              >
                {isActive && (
                  <svg className="w-2.5 h-2.5 text-navy-800" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </span>
              <span className="truncate">{opt.replace(/_/g, ' ')}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

export default function FilterPanel() {
  const { filters, toggleFilterValue, clearAllFilters, activeFilterCount } = useFilters();

  return (
    <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-200 overflow-y-auto">
      <div className="px-3 py-3 border-b border-slate-100">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm font-semibold text-navy-900">Filters</h2>
          {activeFilterCount > 0 && (
            <button
              onClick={clearAllFilters}
              className="text-xs text-navy-600 hover:text-navy-800 font-medium"
            >
              Clear all ({activeFilterCount})
            </button>
          )}
        </div>
      </div>

      <div className="px-3 py-3">
        <FilterGroup
          label="Risk Level"
          options={['HIGH', 'MEDIUM', 'LOW']}
          selected={filters.riskLevel}
          onToggle={(v) => toggleFilterValue('riskLevel', v)}
        />

        <FilterGroup
          label="AI Abnormality"
          options={['HIGH', 'ELEVATED', 'NORMAL']}
          selected={filters.abnormalityLevel}
          onToggle={(v) => toggleFilterValue('abnormalityLevel', v)}
        />

        <FilterGroup
          label="False Alarm Concern"
          options={['LOW', 'MEDIUM', 'HIGH']}
          selected={filters.falseAlarmConcern}
          onToggle={(v) => toggleFilterValue('falseAlarmConcern', v)}
        />

        <FilterGroup
          label="Thermal Movement"
          options={['MOVING', 'STATIONARY', 'INSUFFICIENT_DATA']}
          selected={filters.movementStatus}
          onToggle={(v) => toggleFilterValue('movementStatus', v)}
        />

        <FilterGroup
          label="Persistence"
          options={['persistent', 'short_lived_repeated', 'isolated']}
          selected={filters.persistenceCategory}
          onToggle={(v) => toggleFilterValue('persistenceCategory', v)}
        />

        <FilterGroup
          label="Satellite"
          options={['NOAA-20', 'NOAA-21']}
          selected={filters.satellite}
          onToggle={(v) => toggleFilterValue('satellite', v)}
        />

        {/* Date Range */}
        <div className="mb-4">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Date Range
          </h3>
          <div className="space-y-1.5">
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
              className="w-full px-2 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-navy-500"
            />
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
              className="w-full px-2 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-navy-500"
            />
          </div>
        </div>

        {/* Coming Soon Section */}
        <div className="mt-6 pt-4 border-t border-slate-100">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Future Modules
          </h3>
          <div className="space-y-1 text-xs text-slate-400">
            <div className="px-2 py-1 bg-slate-50 rounded">Vulnerability-Aware Risk</div>
            <div className="px-2 py-1 bg-slate-50 rounded">CloudShield</div>
            <div className="px-2 py-1 bg-slate-50 rounded">Station Alerting</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
