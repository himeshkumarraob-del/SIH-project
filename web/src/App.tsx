import { useState, useCallback } from 'react';
import { FilterContext, useFilterState } from './hooks/useFilters';
import DashboardHeader from './components/DashboardHeader';
import FilterPanel from './components/FilterPanel';
import IndiaMap from './components/IndiaMap';
import EventDetailPanel from './components/EventDetailPanel';
import ClusterTable from './components/ClusterTable';
import { findClusterSummary, findMovement } from './api/client';
import type { ThermalEvent, ClusterSummary } from './types';

export default function App() {
  return (
    <FilterProvider>
      <AppLayout />
    </FilterProvider>
  );
}

function FilterProvider({ children }: { children: React.ReactNode }) {
  const filterState = useFilterState();
  return (
    <FilterContext.Provider value={filterState}>
      {children}
    </FilterContext.Provider>
  );
}

function AppLayout() {
  const [selectedEvent, setSelectedEvent] = useState<ThermalEvent | null>(null);

  const handleSelectEvent = useCallback((event: ThermalEvent) => {
    setSelectedEvent(event);
  }, []);

  const handleSelectCluster = useCallback((cluster: ClusterSummary) => {
    // Find real coordinates from events that belong to this cluster
    // Use the cluster summary data + movement data for coordinates
    const movement = findMovement(cluster.cluster_id);

    // Use real coordinates from movement data or cluster's first detection coords
    // We store representative lat/lon in the mock cluster summaries
    const syntheticEvent: ThermalEvent = {
      detection_id: `cluster-${cluster.cluster_id}`,
      latitude: cluster.latitude ?? 20.5937,
      longitude: cluster.longitude ?? 78.9629,
      acq_date: cluster.first_detection,
      cluster_id: cluster.cluster_id,
      persistence_category: cluster.persistence_category,
      anomaly_score: cluster.anomaly_score,
      anomaly_flag: cluster.anomaly_flag,
      abnormality_level: cluster.abnormality_level,
      anomaly_characterization: cluster.anomaly_characterization,
      explanation: cluster.explanation,
      contributing_factors: cluster.contributing_factors,
      bright_ti4: cluster.max_bright_ti4,
      bright_ti5: cluster.max_bright_ti5,
      frp: cluster.max_frp,
      confidence: String(cluster.mean_confidence),
      satellite: '',
      scan: 0,
      track: 0,
      acq_time: '',
      instrument: 'VIIRS',
      source_satellite: '',
      source_file: '',
      acquisition_datetime: '',
    };
    setSelectedEvent(syntheticEvent);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedEvent(null);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      {/* Top: Operational Metrics Header */}
      <DashboardHeader />

      {/* Middle: Filter | Map | Detail */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Filter Panel */}
        <FilterPanel />

        {/* Center: Map + Table */}
        <div className="flex-1 flex flex-col min-w-0 relative">
          {/* Map (dominant — takes all available space) */}
          <div className="flex-1 relative" style={{ minHeight: 0 }}>
            <IndiaMap
              selectedEvent={selectedEvent}
              onSelectEvent={handleSelectEvent}
            />
          </div>

          {/* Bottom: High-Priority Table */}
          <ClusterTable
            selectedClusterId={selectedEvent?.cluster_id ?? null}
            onSelectCluster={handleSelectCluster}
          />
        </div>

        {/* Right: Event Detail Panel */}
        <EventDetailPanel
          event={selectedEvent}
          onClose={handleCloseDetail}
        />
      </div>
    </div>
  );
}
