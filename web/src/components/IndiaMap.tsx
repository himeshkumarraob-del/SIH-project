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
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapFlyTo target={flyTarget} />
        <MapFocus selectedEvent={selectedEvent} />

        {/* Movement vector lines */}
        {movements.map((mv) => (
          <Polyline
            key={`mv-${mv.cluster_id}`}
            positions={[
              [mv.start_latitude, mv.start_longitude],
              [mv.end_latitude, mv.end_longitude],
            ]}
            pathOptions={{
              color: '#d97706',
              weight: 2.5,
              opacity: 0.85,
              dashArray: '8 5',
            }}
          />
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
                  color: isSelected ? '#1e40af' : color,
                  fillColor: color,
                  fillOpacity: isSelected ? 0.9 : 0.7,
                  weight: isSelected ? 3 : 1.5,
                }}
                eventHandlers={{
                  click: () => onSelectEvent(event),
                }}
              >
                <Popup>
                  <div style={{ padding: '8px', fontSize: '12px', fontFamily: 'sans-serif', minWidth: '180px' }}>
                    <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: '4px' }}>
                      Cluster #{event.cluster_id}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: color, display: 'inline-block' }} />
                      <span style={{ fontWeight: 500, color }}>{event.abnormality_level}</span>
                    </div>
                    <div style={{ color: '#64748b', lineHeight: '1.6' }}>
                      <div>FRP: {event.frp.toFixed(1)} MW</div>
                      <div>Bright TI4: {event.bright_ti4.toFixed(1)} K</div>
                      <div>Date: {event.acq_date}</div>
                      <div>{formatCoordinate(event.latitude, event.longitude)}</div>
                    </div>
                    {mv && (
                      <div style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid #e2e8f0', color: '#b45309' }}>
                        Movement: {mv.movement_direction} ({mv.total_movement_distance_km.toFixed(2)} km)
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Location Search — positioned top-right over the map */}
      <div ref={searchRef} style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 1000 }}>
        {/* Search Input */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onFocus={() => { if (searchResults.length > 0) setShowResults(true); }}
            placeholder="Search location..."
            style={{
              width: '240px',
              padding: '8px 32px 8px 10px',
              fontSize: '13px',
              fontFamily: 'sans-serif',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              outline: 'none',
              boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
              background: 'white',
            }}
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
            style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        {/* Search Results Dropdown */}
        {showResults && searchResults.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: '4px',
              background: 'white',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
              maxHeight: '200px',
              overflowY: 'auto',
              zIndex: 1001,
            }}
          >
            {searchResults.slice(0, 8).map((loc, i) => (
              <div
                key={`${loc.name}-${i}`}
                onClick={() => handleSelectLocation(loc)}
                style={{
                  padding: '8px 10px',
                  fontSize: '13px',
                  fontFamily: 'sans-serif',
                  cursor: 'pointer',
                  borderBottom: i < searchResults.length - 1 ? '1px solid #f1f5f9' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.backgroundColor = '#f8fafc'; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.backgroundColor = 'white'; }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                <span>{loc.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Locations — positioned below search */}
      <div
        style={{
          position: 'absolute',
          top: '52px',
          right: '12px',
          zIndex: 1000,
          display: 'flex',
          gap: '4px',
          flexWrap: 'wrap',
          justifyContent: 'flex-end',
          maxWidth: '240px',
        }}>
        {QUICK_LOCATIONS.map((loc) => (
          <button
            key={loc.name}
            onClick={() => handleSelectLocation(loc)}
            style={{
              padding: '3px 8px',
              fontSize: '11px',
              fontFamily: 'sans-serif',
              fontWeight: 500,
              color: '#475569',
              background: 'rgba(255,255,255,0.92)',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => {
              (e.target as HTMLElement).style.backgroundColor = '#0f172a';
              (e.target as HTMLElement).style.color = 'white';
              (e.target as HTMLElement).style.borderColor = '#0f172a';
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLElement).style.backgroundColor = 'rgba(255,255,255,0.92)';
              (e.target as HTMLElement).style.color = '#475569';
              (e.target as HTMLElement).style.borderColor = '#d1d5db';
            }}
          >
            {loc.name}
          </button>
        ))}
      </div>

      {/* Map Legend — positioned absolutely over the map */}
      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          zIndex: 1000,
          background: 'rgba(255,255,255,0.95)',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          padding: '10px 12px',
          fontSize: '12px',
          fontFamily: 'sans-serif',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        }}
      >
        <div style={{ fontWeight: 600, color: '#0f172a', marginBottom: '6px' }}>Thermal Abnormality</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#dc2626', display: 'inline-block' }} />
          <span>HIGH Anomaly</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#d97706', display: 'inline-block' }} />
          <span>ELEVATED Event</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#16a34a', display: 'inline-block' }} />
          <span>NORMAL Event</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #e2e8f0' }}>
          <svg width="14" height="14" viewBox="0 0 14 14">
            <line x1="0" y1="7" x2="14" y2="7" stroke="#d97706" strokeWidth="2" strokeDasharray="5 3" />
          </svg>
          <span>Movement Vector</span>
        </div>
        <div style={{ color: '#94a3b8', marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #f1f5f9', fontSize: '11px' }}>
          Total: {events.length.toLocaleString()} detections
        </div>
      </div>
    </div>
  );
}
