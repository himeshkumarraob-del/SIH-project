import React, { useEffect, useMemo, useState, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, Polygon, useMap } from 'react-leaflet';
import L from 'leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { useFilters } from '../hooks/useFilters';
import { fetchEvents, fetchMovement } from '../api/client';
import type { ThermalEvent, MovementVector } from '../types';
import type { MapLocation } from '../data/locations';
import { searchLocations } from '../data/locations';
import { formatCoordinate, markerColor } from '../utils/formatters';
import { triggerIncidentReportDownload } from '../utils/reportGenerator';


const INDIA_CENTER: [number, number] = [20.5937, 78.9629];

// Movement direction arrows are shown only for clusters whose direction of
// detected thermal activity movement is considered reliable (MODERATE/HIGH).
// Arrows represent the direction of detected thermal activity, NOT confirmed
// physical fire-front propagation.
const RELIABLE_DIRECTION_CONFIDENCE = ['MODERATE', 'HIGH'];

/** Approximate destination lat/lon after moving `distKm` at `bearingDeg` from a point. */
function destinationPoint(lat: number, lon: number, bearingDeg: number, distKm: number): [number, number] {
  const R = 6371.0088;
  const d = distKm / R;
  const brng = (bearingDeg * Math.PI) / 180;
  const lat1 = (lat * Math.PI) / 180;
  const lon1 = (lon * Math.PI) / 180;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(brng),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brng) * Math.sin(d) * Math.cos(lat1),
      Math.cos(d) - Math.sin(lat1) * Math.sin(lat2),
    );
  return [(lat2 * 180) / Math.PI, (lon2 * 180) / Math.PI];
}

/**
 * Arrowhead wing endpoints at the tip of a direction arrow.
 * Wing length scales with displacement but is clamped to a sensible visual
 * range so arrows never become huge misleading vectors.
 */
function arrowHeadWings(mv: MovementVector): { tip: [number, number]; wing1: [number, number]; wing2: [number, number] } {
  const tip: [number, number] = [mv.end_latitude, mv.end_longitude];
  const disp = Math.max(mv.total_movement_distance_km, 0);
  const wingKm = Math.min(Math.max(disp * 0.35, 0.9), 4.0);
  const spreadDeg = 26;
  const back1 = (mv.movement_bearing_degrees + 180 - spreadDeg + 360) % 360;
  const back2 = (mv.movement_bearing_degrees + 180 + spreadDeg) % 360;
  return {
    tip,
    wing1: destinationPoint(tip[0], tip[1], back1, wingKm),
    wing2: destinationPoint(tip[0], tip[1], back2, wingKm),
  };
}

/**
 * Draw a direction arrow as a thin shaft (start->end centroid) plus a filled
 * arrowhead at the end centroid. A soft glow underlay keeps the arrow legible
 * over both basemaps, and a slow dash-flow implies the direction of travel.
 * The shaft is the real recorded displacement of detected thermal activity;
 * the head marks its direction.
 */
function MovementDirectionArrow({ mv }: { mv: MovementVector }) {
  const { tip, wing1, wing2 } = arrowHeadWings(mv);
  const color = mv.direction_confidence === 'HIGH' ? '#ea580c' : '#d97706';
  const shaft: [number, number][] = [
    [mv.start_latitude, mv.start_longitude],
    [mv.end_latitude, mv.end_longitude],
  ];
  return (
    <>
      {/* Soft glow underlay shaft */}
      <Polyline
        positions={shaft}
        pathOptions={{ color, weight: 5, opacity: 0.14 }}
      />
      {/* Clean animated shaft */}
      <Polyline
        positions={shaft}
        pathOptions={{
          color,
          weight: 1.6,
          opacity: 0.9,
          dashArray: '4 5',
          className: 'direction-shaft',
        }}
      />
      {/* Filled arrowhead */}
      <Polygon
        positions={[tip, wing1, wing2]}
        pathOptions={{
          fillColor: color,
          fillOpacity: 0.95,
          color,
          weight: 1,
          opacity: 0.9,
        }}
      />
    </>
  );
}

function createClusterIcon(cluster: { getChildCount(): number }) {
  const count = cluster.getChildCount();
  const size = count < 100 ? 'small' : count < 1000 ? 'medium' : 'large';
  const cls = `marker-cluster marker-cluster-${size}`;
  return L.divIcon({
    html: `<div><span>${count}</span></div>`,
    className: cls,
    iconSize: L.point(42, 42),
  });
}

function MapFlyTo({ target }: { target: MapLocation | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) {
      map.flyTo([target.lat, target.lon], target.zoom, { duration: 1.0 });
    }
  }, [target, map]);
  return null;
}

function MapFocus({ selectedEvent }: { selectedEvent: ThermalEvent | null }) {
  const map = useMap();
  useEffect(() => {
    if (selectedEvent && selectedEvent.latitude !== 20.5937) {
      map.flyTo([selectedEvent.latitude, selectedEvent.longitude], 10, {
        duration: 0.8,
      });
    }
  }, [selectedEvent, map]);
  return null;
}

interface IndiaMapProps {
  selectedEvent: ThermalEvent | null;
  onSelectEvent: (event: ThermalEvent) => void;
}

const QUICK_LOCATIONS: MapLocation[] = [
  { name: 'India', aliases: [], lat: 20.5937, lon: 78.9629, zoom: 5 },
  { name: 'Tamil Nadu', aliases: [], lat: 11.1271, lon: 78.6569, zoom: 7 },
  { name: 'Chennai', aliases: [], lat: 13.0827, lon: 80.2707, zoom: 11 },
  { name: 'Avadi', aliases: [], lat: 13.1067, lon: 80.0970, zoom: 13 },
];

const CONTROL_BTN =
  'flex items-center justify-center w-7 h-7 rounded-md border shadow-sm backdrop-blur-sm transition-all focus:outline-none';

export default function IndiaMap({ selectedEvent, onSelectEvent }: IndiaMapProps) {
  const { filters } = useFilters();
  const [events, setEvents] = React.useState<ThermalEvent[]>([]);
  const [movements, setMovements] = React.useState<MovementVector[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MapLocation[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [flyTarget, setFlyTarget] = useState<MapLocation | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchEvents(filters).then(setEvents);
    fetchMovement(filters).then(setMovements);
  }, [filters]);

  const movementMap = useMemo(() => {
    const m = new Map<number, MovementVector>();
    movements.forEach((mv) => m.set(mv.cluster_id, mv));
    return m;
  }, [movements]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (value.trim().length > 0) {
      const results = searchLocations(value);
      setSearchResults(results);
      setShowResults(results.length > 0);
    } else {
      setSearchResults([]);
      setShowResults(false);
    }
  };

  const handleSelectLocation = (loc: MapLocation) => {
    setSearchQuery(loc.name);
    setShowResults(false);
    setFlyTarget(loc);
  };

  const [basemapLayer, setBasemapLayer] = useState<'osm' | 'satellite'>('osm');

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <MapContainer
        center={INDIA_CENTER}
        zoom={5}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
        scrollWheelZoom={true}
      >
        <TileLayer
          key={basemapLayer}
          attribution={
            basemapLayer === 'satellite'
              ? '&copy; Esri, Maxar, Earthstar Geographics'
              : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          }
          url={
            basemapLayer === 'satellite'
              ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
              : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
          }
        />

        <MapFlyTo target={flyTarget} />
        <MapFocus selectedEvent={selectedEvent} />

        {/* Thermal Activity Movement Direction arrows.
            Shown ONLY for clusters with a defensible direction of detected
            thermal activity (MODERATE/HIGH confidence). No arrow is drawn for
            stationary, erratic or insufficient-evidence clusters — absence of
            an arrow is NOT evidence of no movement direction. */}
        {movements
          .filter((mv) => mv.movement_status === 'MOVING' && mv.direction_available && RELIABLE_DIRECTION_CONFIDENCE.includes(mv.direction_confidence))
          .map((mv) => (
            <MovementDirectionArrow key={`dir-arrow-${mv.cluster_id}`} mv={mv} />
          ))}

        {/* Markers with clustering */}
        <MarkerClusterGroup
          chunkedLoading
          maxClusterRadius={50}
          iconCreateFunction={createClusterIcon}
        >
          {events.map((event) => {
            const color = markerColor(event.abnormality_level);
            const isSelected = selectedEvent?.detection_id === event.detection_id;
            const mv = movementMap.get(event.cluster_id);
            const baseRadius = isSelected ? 9 : event.abnormality_level === 'HIGH' ? 6.5 : 4.5;
            const dotClass =
              (isSelected ? 'dot-selected ' : '') +
              (event.abnormality_level === 'HIGH'
                ? 'dot-high'
                : event.abnormality_level === 'ELEVATED'
                ? 'dot-elevated'
                : 'dot-normal');

            return (
              <React.Fragment key={event.detection_id}>
                {/* Pulse halo underlay */}
                <CircleMarker
                  center={[event.latitude, event.longitude]}
                  radius={Math.max(baseRadius * 2.4, 10)}
                  pathOptions={{
                    color: 'transparent',
                    weight: 0,
                    fillColor: color,
                    fillOpacity: 0.5,
                    className: 'thermal-halo',
                    interactive: false,
                  }}
                />
                {/* Main marker */}
                <CircleMarker
                  center={[event.latitude, event.longitude]}
                  radius={baseRadius}
                  pathOptions={{
                    color: isSelected ? '#60a5fa' : color,
                    fillColor: isSelected ? '#3b82f6' : color,
                    fillOpacity: isSelected ? 1 : 0.9,
                    weight: isSelected ? 2.5 : 1.2,
                    className: `thermal-dot ${dotClass}`,
                  }}
                  eventHandlers={{
                    click: () => onSelectEvent(event),
                  }}
                >
                  <Popup>
                    <div style={{ padding: '10px 12px', fontSize: '12px', fontFamily: 'sans-serif', minWidth: '190px' }}>
                      <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                        Cluster #{event.cluster_id}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        <span style={{ width: '9px', height: '9px', borderRadius: '50%', backgroundColor: color, boxShadow: `0 0 6px ${color}`, display: 'inline-block' }} />
                        <span style={{ fontWeight: 600, color }}>{event.abnormality_level} ANOMALY</span>
                      </div>
                      <div style={{ color: '#475569', lineHeight: '1.7' }}>
                        <div>FRP: {event.frp.toFixed(1)} MW</div>
                        <div>Brightness: {event.bright_ti4.toFixed(1)} K</div>
                        <div>Coords: {formatCoordinate(event.latitude, event.longitude)}</div>
                        {event.acq_date && <div>Date: {event.acq_date}</div>}
                      </div>
                      <div style={{ marginTop: '8px', display: 'flex', gap: '4px' }}>
                        <button
                          type="button"
                          onClick={() => triggerIncidentReportDownload(event.cluster_id)}
                          style={{
                            width: '100%',
                            backgroundColor: '#0f172a',
                            color: '#ffffff',
                            border: 'none',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          📄 GENERATE REPORT
                        </button>
                      </div>
                      {mv && mv.movement_status === 'MOVING' && (

                        <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #e2e8f0', color: '#d97706' }}>
                          <div style={{ fontWeight: 600 }}>
                            ↗ Moving {mv.direction ?? ''} ({mv.movement_bearing_degrees.toFixed(0)}°)
                          </div>
                          <div>Rate: {mv.movement_rate_km_per_day.toFixed(2)} km/day</div>
                          <div>Total: {mv.total_movement_distance_km.toFixed(2)} km</div>
                          {mv.direction_available && (
                            <div>Confidence: {mv.direction_confidence}</div>
                          )}
                        </div>
                      )}
                      {mv && mv.movement_status === 'STATIONARY' && (
                        <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #e2e8f0', color: '#16a34a' }}>
                          Stationary (no net displacement)
                        </div>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              </React.Fragment>
            );
          })}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Vertical map control stack (basemap + extent) — sits under the
          native zoom control in the top-left corner. */}
      <div className="absolute top-[88px] left-2.5 z-[1000] flex flex-col gap-1">
        {/* Basemap: Streets */}
        <button
          type="button"
          aria-label="Streets basemap"
          title="Streets basemap"
          onClick={() => setBasemapLayer('osm')}
          className={`${CONTROL_BTN} ${
            basemapLayer === 'osm'
              ? 'bg-slate-900 text-white border-slate-700 dark:bg-blue-600 dark:border-blue-500'
              : 'bg-white/95 text-slate-600 border-slate-300 hover:text-slate-900 dark:bg-slate-900/95 dark:text-slate-300 dark:border-slate-700 dark:hover:text-white'
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 9h16M4 15h16M9 4v16" />
          </svg>
        </button>
        {/* Basemap: Satellite */}
        <button
          type="button"
          aria-label="Satellite basemap"
          title="Satellite basemap"
          onClick={() => setBasemapLayer('satellite')}
          className={`${CONTROL_BTN} ${
            basemapLayer === 'satellite'
              ? 'bg-slate-900 text-white border-slate-700 dark:bg-blue-600 dark:border-blue-500'
              : 'bg-white/95 text-slate-600 border-slate-300 hover:text-slate-900 dark:bg-slate-900/95 dark:text-slate-300 dark:border-slate-700 dark:hover:text-white'
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <circle cx="12" cy="12" r="7" />
            <path strokeLinecap="round" d="M12 2v3m0 14v3M2 12h3m14 0h3M5.6 5.6l2.1 2.1m8.6 8.6l2.1 2.1M5.6 18.4l2.1-2.1m8.6-8.6l2.1-2.1" />
            <circle cx="12" cy="12" r="2.2" />
          </svg>
        </button>
        {/* Reset to India extent */}
        <button
          type="button"
          aria-label="Reset view to India"
          title="Reset view to India"
          onClick={() => handleSelectLocation(QUICK_LOCATIONS[0])}
          className={`${CONTROL_BTN} bg-white/95 text-slate-600 border-slate-300 hover:text-slate-900 dark:bg-slate-900/95 dark:text-slate-300 dark:border-slate-700 dark:hover:text-white`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
          </svg>
        </button>
      </div>

      {/* Location Search — positioned top-right over the map */}
      <div ref={searchRef} className="absolute top-2.5 right-2.5 sm:top-3 sm:right-3 z-[1000] w-44 sm:w-56 max-w-[calc(100vw-5.5rem)]">
        {/* Search Input */}
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onFocus={() => { if (searchResults.length > 0) setShowResults(true); }}
            placeholder="Search location…"
            className="w-full px-2.5 pr-7 py-1.5 sm:py-1.5 text-xs font-sans rounded-md border border-slate-300 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 text-slate-900 dark:text-slate-100 shadow-sm outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-slate-400 backdrop-blur-sm"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchResults.length > 0) {
                handleSelectLocation(searchResults[0]);
              }
              if (e.key === 'Escape') {
                setShowResults(false);
              }
            }}
          />
          {/* Search icon */}
          <svg
            className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none w-3.5 h-3.5 text-slate-400"
            fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        {/* Search Results Dropdown */}
        {showResults && searchResults.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md shadow-xl max-h-52 overflow-y-auto z-[1001]">
            {searchResults.slice(0, 8).map((loc, i) => (
              <div
                key={`${loc.name}-${i}`}
                onClick={() => handleSelectLocation(loc)}
                className="px-2.5 py-1.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 last:border-b-0"
              >
                <svg className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                <span className="truncate">{loc.name}</span>
                {loc.region && <span className="text-[10px] text-slate-400 dark:text-slate-500 ml-auto flex-shrink-0">({loc.region})</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Locations — hidden on very small mobile to prevent map clutter */}
      <div
        className="hidden sm:flex absolute top-[52px] sm:top-[56px] right-2.5 sm:right-3 z-[1000] gap-1 flex-wrap justify-end max-w-[240px]"
      >
        {QUICK_LOCATIONS.map((loc) => (
          <button
            key={loc.name}
            onClick={() => handleSelectLocation(loc)}
            className="px-2 py-0.5 text-[11px] font-sans font-medium text-slate-700 dark:text-slate-200 bg-white/95 dark:bg-slate-900/95 hover:bg-slate-900 hover:text-white dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded shadow-sm cursor-pointer whitespace-nowrap transition-colors backdrop-blur-sm"
          >
            {loc.name}
          </button>
        ))}
      </div>

      {/* Map Legend — positioned bottom-left over the map with dark mode & responsive sizing */}
      <div
        className="absolute bottom-3 left-3 z-[1000] bg-white/95 dark:bg-slate-900/95 border border-slate-200/80 dark:border-slate-800 rounded-lg px-3 py-2.5 text-xs font-sans shadow-sm max-w-[calc(100vw-2rem)] sm:max-w-xs backdrop-blur-sm select-none"
      >
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <div className="font-bold text-slate-900 dark:text-slate-100 text-[10px] sm:text-[11px] uppercase tracking-[0.14em]">
            Thermal Legend
          </div>
          <span className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-emerald-700 dark:text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            LIVE
          </span>
        </div>
        <div className="space-y-1 text-[11px]">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block flex-shrink-0 shadow-[0_0_5px_rgba(220,38,38,0.8)]" />
            <span className="text-slate-700 dark:text-slate-300">HIGH Anomaly</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block flex-shrink-0 shadow-[0_0_5px_rgba(217,119,6,0.8)]" />
            <span className="text-slate-700 dark:text-slate-300">ELEVATED</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block flex-shrink-0 shadow-[0_0_5px_rgba(22,163,74,0.8)]" />
            <span className="text-slate-700 dark:text-slate-300">NORMAL Baseline</span>
          </div>
          <div className="flex items-center gap-2 pt-1 mt-1 border-t border-slate-200/70 dark:border-slate-800">
            <svg width="16" height="14" viewBox="0 0 16 14" className="flex-shrink-0">
              <line x1="1" y1="7" x2="10" y2="7" stroke="#d97706" strokeWidth="2" strokeDasharray="3 2" />
              <path d="M10 7 L6.5 3.8 L6.5 10.2 Z" fill="#ea580c" />
            </svg>
            <span className="text-slate-700 dark:text-slate-300">Thermal Movement</span>
          </div>
        </div>
        <div className="text-slate-400 dark:text-slate-500 mt-1.5 pt-1.5 border-t border-slate-100 dark:border-slate-800 text-[10px] font-mono">
          {events.length.toLocaleString()} detections on map
        </div>
      </div>
    </div>
  );
}
