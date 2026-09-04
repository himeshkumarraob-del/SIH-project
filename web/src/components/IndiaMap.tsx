import React, { useEffect, useMemo, useState, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { useFilters } from '../hooks/useFilters';
import { fetchEvents, fetchMovement } from '../api/client';
import type { ThermalEvent, MovementVector } from '../types';
import type { MapLocation } from '../data/locations';
import { searchLocations } from '../data/locations';
import { formatCoordinate, markerColor } from '../utils/formatters';

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
  const spreadDeg = 28;
  const back1 = (mv.movement_bearing_degrees + 180 - spreadDeg + 360) % 360;
  const back2 = (mv.movement_bearing_degrees + 180 + spreadDeg) % 360;
  return {
    tip,
    wing1: destinationPoint(tip[0], tip[1], back1, wingKm),
    wing2: destinationPoint(tip[0], tip[1], back2, wingKm),
  };
}

/**
 * Draw a direction arrow as a thin shaft (start->end centroid) plus an
 * arrowhead at the end centroid. The shaft is the real recorded displacement
 * of detected thermal activity; the head marks its direction.
 */
function MovementDirectionArrow({ mv }: { mv: MovementVector }) {
  const { tip, wing1, wing2 } = arrowHeadWings(mv);
  const color = mv.direction_confidence === 'HIGH' ? '#b45309' : '#d97706';
  return (
    <>
      <Polyline
        positions={[
          [mv.start_latitude, mv.start_longitude],
          [mv.end_latitude, mv.end_longitude],
        ]}
        pathOptions={{ color: '#d97706', weight: 1.5, opacity: 0.55, dashArray: '4 4' }}
      />
      <Polyline positions={[tip, wing1]} pathOptions={{ color, weight: 2.5, opacity: 0.95 }} />
      <Polyline positions={[tip, wing2]} pathOptions={{ color, weight: 2.5, opacity: 0.95 }} />
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
    iconSize: L.point(40, 40),
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

            return (
              <CircleMarker
                key={event.detection_id}
                center={[event.latitude, event.longitude]}
                radius={isSelected ? 10 : event.abnormality_level === 'HIGH' ? 7 : 5}
                pathOptions={{
                  color: isSelected ? '#3b82f6' : color,
                  fillColor: color,
                  fillOpacity: isSelected ? 0.95 : 0.75,
                  weight: isSelected ? 3 : 1.5,
                }}
                eventHandlers={{
                  click: () => onSelectEvent(event),
                }}
              >
                <Popup>
                  <div style={{ padding: '8px', fontSize: '12px', fontFamily: 'sans-serif', minWidth: '180px' }}>
                    <div style={{ fontWeight: 600, color: '#0f172a', marginBottom: '4px' }}>
                      Cluster #{event.cluster_id}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: color, display: 'inline-block' }} />
                      <span style={{ fontWeight: 500, color }}>{event.abnormality_level}</span>
                    </div>
                    <div style={{ color: '#475569', lineHeight: '1.6' }}>
                      <div>FRP: {event.frp.toFixed(1)} MW</div>
                      <div>Brightness: {event.bright_ti4.toFixed(1)} K</div>
                      <div>Coords: {formatCoordinate(event.latitude, event.longitude)}</div>
                      {event.acq_date && <div>Date: {event.acq_date}</div>}
                    </div>
                    {mv && mv.movement_status === 'MOVING' && (
                      <div style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid #e2e8f0', color: '#d97706' }}>
                        <div>Moving {mv.direction ?? ''} ({mv.movement_bearing_degrees.toFixed(0)}°)</div>
                        <div>Rate: {mv.movement_rate_km_per_day.toFixed(2)} km/day</div>
                        <div>Total: {mv.total_movement_distance_km.toFixed(2)} km</div>
                        {mv.direction_available && (
                          <div>Confidence: {mv.direction_confidence}</div>
                        )}
                      </div>
                    )}
                    {mv && mv.movement_status === 'STATIONARY' && (
                      <div style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid #e2e8f0', color: '#16a34a' }}>
                        Stationary (no net displacement)
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Basemap Switcher (OSM / Satellite) */}
      <div className="absolute top-2.5 left-14 sm:top-3 sm:left-14 z-[1000] flex items-center bg-white/95 dark:bg-slate-900/95 border border-slate-300 dark:border-slate-700 rounded-md shadow-md p-0.5 text-xs backdrop-blur-xs">
        <button
          type="button"
          onClick={() => setBasemapLayer('osm')}
          className={`px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-[11px] font-bold transition-colors ${
            basemapLayer === 'osm'
              ? 'bg-navy-900 dark:bg-blue-600 text-white shadow-2xs'
              : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          OSM
        </button>
        <button
          type="button"
          onClick={() => setBasemapLayer('satellite')}
          className={`px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-[11px] font-bold transition-colors ${
            basemapLayer === 'satellite'
              ? 'bg-navy-900 dark:bg-blue-600 text-white shadow-2xs'
              : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          SATELLITE
        </button>
      </div>

      {/* Location Search — positioned top-right over the map */}
      <div ref={searchRef} className="absolute top-2.5 right-2.5 sm:top-3 sm:right-3 z-[1000] w-44 sm:w-60 max-w-[calc(100vw-5.5rem)]">
        {/* Search Input */}
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onFocus={() => { if (searchResults.length > 0) setShowResults(true); }}
            placeholder="Search location..."
            className="w-full px-2.5 pr-7 py-1 sm:py-1.5 text-xs font-sans rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-md outline-none focus:ring-1 focus:ring-navy-600 dark:focus:ring-blue-500"
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
        className="hidden sm:flex absolute top-[48px] sm:top-[52px] right-2.5 sm:right-3 z-[1000] gap-1 flex-wrap justify-end max-w-[240px]"
      >
        {QUICK_LOCATIONS.map((loc) => (
          <button
            key={loc.name}
            onClick={() => handleSelectLocation(loc)}
            className="px-2 py-0.5 text-[11px] font-sans font-medium text-slate-700 dark:text-slate-200 bg-white/95 dark:bg-slate-900/95 hover:bg-slate-900 hover:text-white dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded shadow-xs cursor-pointer whitespace-nowrap transition-colors"
          >
            {loc.name}
          </button>
        ))}
      </div>

      {/* Map Legend — positioned bottom-left over the map with dark mode & responsive sizing */}
      <div
        className="absolute bottom-3 left-3 z-[1000] bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-xs font-sans shadow-md max-w-[calc(100vw-2rem)] sm:max-w-xs text-slate-800 dark:text-slate-200 backdrop-blur-xs"
      >
        <div className="font-semibold text-slate-900 dark:text-slate-100 mb-1 text-[11px] sm:text-xs">Thermal Abnormality</div>
        <div className="flex items-center gap-2 mb-1 text-[11px]">
          <span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block flex-shrink-0" />
          <span>HIGH Anomaly</span>
        </div>
        <div className="flex items-center gap-2 mb-1 text-[11px]">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block flex-shrink-0" />
          <span>ELEVATED Event</span>
        </div>
        <div className="flex items-center gap-2 mb-1 text-[11px]">
          <span className="w-2.5 h-2.5 rounded-full bg-green-600 inline-block flex-shrink-0" />
          <span>NORMAL Event</span>
        </div>
        <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-slate-200 dark:border-slate-800 text-[11px]">
          <svg width="14" height="14" viewBox="0 0 14 14" className="flex-shrink-0">
            <line x1="1" y1="7" x2="10" y2="7" stroke="#d97706" strokeWidth="2.5" />
            <line x1="10" y1="7" x2="6.5" y2="4.5" stroke="#d97706" strokeWidth="2.5" />
            <line x1="10" y1="7" x2="6.5" y2="9.5" stroke="#d97706" strokeWidth="2.5" />
          </svg>
          <span>Movement Direction</span>
        </div>
        <div className="text-slate-400 dark:text-slate-500 mt-1 pt-1 border-t border-slate-100 dark:border-slate-800 text-[10px] hidden xs:block">
          Total: {events.length.toLocaleString()} detections
        </div>
      </div>
    </div>
  );
}
