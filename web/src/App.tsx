import { useState, useCallback } from 'react';
import { FilterContext, useFilterState } from './hooks/useFilters';
import { useThermalAlerts } from './hooks/useThermalAlerts';
import DashboardHeader from './components/DashboardHeader';
import FilterPanel from './components/FilterPanel';
import IndiaMap from './components/IndiaMap';
import EventDetailPanel from './components/EventDetailPanel';
import ClusterTable from './components/ClusterTable';
import ThermalAlertToasts from './components/ThermalAlertToasts';
import ThermalAlertCenter from './components/ThermalAlertCenter';
import type { ThermalEvent, ClusterSummary, ThermalAlert } from './types';

const DEFAULT_VIEW = { lat: 20.5937, lon: 78.9629 };

/** Build a lightweight event context used to drive selection + detail fetches. */
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

  const openCluster = useCallback(
    (clusterId: number, latitude: number, longitude: number, extras?: Partial<ThermalEvent>) => {
      setSelectedEvent(makeClusterEvent(clusterId, latitude, longitude, extras));
    },
    [],
  );

  const handleSelectEvent = useCallback((event: ThermalEvent) => {
    setSelectedEvent(event);
  }, []);

  const handleSelectCluster = useCallback(
    (cluster: ClusterSummary) => {
      // Build a lightweight event context from the real cluster summary; the detail
      // panel fetches the full per-cluster intelligence from the API.
      openCluster(
        cluster.cluster_id,
        cluster.latitude ?? DEFAULT_VIEW.lat,
        cluster.longitude ?? DEFAULT_VIEW.lon,
        {
          acq_date: cluster.first_detection,
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
        },
      );
    },
    [openCluster],
  );

  const handleCloseDetail = useCallback(() => {
    setSelectedEvent(null);
  }, []);

  // Thermal alert notification layer: polls the real /api/v1/alerts API and
  // surfaces popups only for NEWLY seen ACTIVE unsuppressed HIGH/CRITICAL
  // alerts. VIEW EVENT routes into the existing cluster selection + detail
  // panel + map fly-to.
  const alertLayer = useThermalAlerts(
    useCallback(
      (alert: ThermalAlert) => {
        openCluster(
          alert.cluster_id,
          alert.latitude ?? DEFAULT_VIEW.lat,
          alert.longitude ?? DEFAULT_VIEW.lon,
        );
      },
      [openCluster],
    ),
  );

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      {/* Top: Operational Metrics Header */}
      <DashboardHeader
        actions={
          <ThermalAlertCenter
            eligibleAlerts={alertLayer.eligibleAlerts}
            totalCritical={alertLayer.totalCritical}
            totalHigh={alertLayer.totalHigh}
            apiAvailable={alertLayer.apiAvailable}
            lastUpdated={alertLayer.lastUpdated}
            centerOpen={alertLayer.centerOpen}
            setCenterOpen={alertLayer.setCenterOpen}
            onView={alertLayer.viewAlert}
          />
        }
      />

      {/* Thermal alert popups — new ACTIVE unsuppressed HIGH/CRITICAL only */}
      <ThermalAlertToasts
        popups={alertLayer.popups}
        onView={alertLayer.viewAlert}
        onDismiss={alertLayer.dismissPopup}
      />

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
