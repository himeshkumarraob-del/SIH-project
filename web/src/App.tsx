import { useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { FilterContext, useFilterState } from './hooks/useFilters';
import { useThermalAlerts } from './hooks/useThermalAlerts';
import { ThemeProvider } from './hooks/useTheme';
import AppNavbar from './components/AppNavbar';
import ThermalAlertCenter from './components/ThermalAlertCenter';
import ThermalAlertToasts from './components/ThermalAlertToasts';
import OverviewPage from './pages/OverviewPage';
import MapPage from './pages/MapPage';
import AlertsPage from './pages/AlertsPage';
import EventsPage from './pages/EventsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SystemPage from './pages/SystemPage';
import type { ThermalAlert } from './types';

export default function App() {
  return (
    <ThemeProvider>
      <FilterProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </FilterProvider>
    </ThemeProvider>
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

function AppShell() {
  const navigate = useNavigate();

  const handleAlertClick = useCallback(
    (alert: ThermalAlert) => {
      // Navigate to /alerts or /map when viewing an alert from global bell / toast
      navigate('/alerts');
    },
    [navigate],
  );

  const alertLayer = useThermalAlerts(handleAlertClick);

  const activeAlertCount = alertLayer.totalCritical + alertLayer.totalHigh;

  return (
    <div className="h-screen w-full flex flex-col bg-slate-50 dark:bg-slate-950 overflow-hidden transition-colors duration-200">
      {/* Global Multi-Page Top Navigation Bar */}
      <AppNavbar
        activeAlertCount={activeAlertCount}
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

      {/* Global Thermal alert popups for new active unsuppressed HIGH/CRITICAL anomalies */}
      <ThermalAlertToasts
        popups={alertLayer.popups}
        onView={alertLayer.viewAlert}
        onDismiss={alertLayer.dismissPopup}
      />

      {/* Page Content Routes */}
      <main className="flex-1 flex min-h-0 relative w-full overflow-hidden">
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
