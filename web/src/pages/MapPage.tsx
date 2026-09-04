import { useState, useCallback } from 'react';
import IndiaMap from '../components/IndiaMap';
import FilterPanel from '../components/FilterPanel';
import EventDetailPanel from '../components/EventDetailPanel';
import { useFilters } from '../hooks/useFilters';
import type { ThermalEvent, ClusterSummary } from '../types';

const DEFAULT_VIEW = { lat: 20.5937, lon: 78.9629 };

function makeClusterEvent(
  clusterId: number,
  latitude: number,
  longitude: number,
  extras?: Partial<ThermalEvent>,
): ThermalEvent {
  return {
    detection_id: `cluster-${clusterId}`,
    latitude,
    longitude,
    acq_date: '',
    cluster_id: clusterId,
    persistence_category: 'unknown',
    anomaly_score: 0,
    anomaly_flag: 0,
    abnormality_level: 'NORMAL',
    anomaly_characterization: '',
    explanation: '',
    contributing_factors: '',
    bright_ti4: 0,
    bright_ti5: 0,
    frp: 0,
    confidence: '',
    satellite: '',
    scan: 0,
    track: 0,
    acq_time: '',
    instrument: 'VIIRS',
    source_satellite: '',
    source_file: '',
    acquisition_datetime: '',
    ...extras,
  };
}

export default function MapPage() {
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null);
  const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false);
  const { activeFilterCount } = useFilters();

  const openCluster = useCallback(
    (clusterId: number, latitude: number, longitude: number, extras?: Partial<ThermalEvent>) => {
      setSelectedEvent(makeClusterEvent(clusterId, latitude, longitude, extras));
    },
    [],
  );

  const handleSelectEvent = useCallback((event: ThermalEvent) => {
    setSelectedEvent(event);
  }, []);

  return (
    <div className="flex-1 flex min-h-0 relative w-full overflow-hidden">
      {/* Left: Mission Control Filter Panel */}
      <FilterPanel
        isMobileOpen={isMobileFiltersOpen}
        onCloseMobile={() => setIsMobileFiltersOpen(false)}
      />

      {/* Center: Full-Screen GIS Map */}
      <div className="flex-1 flex flex-col min-w-0 w-full relative">
        {/* Floating Mobile Filter Trigger Button on Map */}
        <div className="lg:hidden absolute top-2.5 left-28 z-[1000]">
          <button
            type="button"
            onClick={() => setIsMobileFiltersOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-navy-900 dark:bg-slate-900 text-white shadow-md border border-slate-700 hover:bg-navy-800 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <span className="w-4 h-4 rounded-full bg-red-600 text-[10px] font-bold text-white flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>

        {/* Map Container (takes all available screen space) */}
        <div className="flex-1 relative w-full" style={{ minHeight: 0 }}>
          <IndiaMap selectedEvent={selectedEvent} onSelectEvent={handleSelectEvent} />
        </div>
      </div>

      {/* Right: Event Detail Intelligence Dossier */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
