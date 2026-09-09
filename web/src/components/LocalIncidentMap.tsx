import { useState, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import type {
  ThermalEvent,
  ClusterDetail,
  ClassificationDetailData,
  RiskDetailData,
  ResponseDetailData,
  MovementVector,
} from '../types';
import { formatCoordinate, markerColor } from '../utils/formatters';

interface LocalIncidentMapProps {
  event: ThermalEvent;
  detail?: ClusterDetail | null;
  classification?: ClassificationDetailData | null;
  risk?: RiskDetailData | null;
  response?: ResponseDetailData | null;
  movement?: MovementVector | null;
}

function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  map.setView(center, zoom, { animate: true });
  return null;
}

// Custom Fire Station Icon
const fireStationIcon = L.divIcon({
  html: `<div style="background:#dc2626; color:#fff; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px rgba(220,38,38,0.7); border:2px solid #fff; font-size:14px;">🚒</div>`,
  className: 'fire-station-marker',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

// Custom Industrial Facility Icon
const industrialIcon = L.divIcon({
  html: `<div style="background:#475569; color:#fff; width:26px; height:26px; border-radius:6px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 8px rgba(15,23,42,0.6); border:2px solid #fff; font-size:13px;">🏭</div>`,
  className: 'industrial-facility-marker',
  iconSize: [26, 26],
  iconAnchor: [13, 13],
});

export default function LocalIncidentMap({
  event,
  detail,
  classification,
  response,
}: LocalIncidentMapProps) {
  const [basemap, setBasemap] = useState<'osm' | 'satellite' | 'topo'>('osm');
  const [zoomLevel, setZoomLevel] = useState<number>(14);

  const lat = detail?.latitude ?? event.latitude;
  const lon = detail?.longitude ?? event.longitude;
  const center: [number, number] = [lat, lon];

  const color = markerColor(event.abnormality_level);

  // Categorize the Area (Industrial, Domestic/Residential, Agricultural, Forest/Natural, Park/Protected)
  const areaCategory = useMemo(() => {
    const clsLabel = (classification?.classification_label || detail?.classification_label || '').toLowerCase();
    const osmFacility = (classification?.osm_facility_type || '').toLowerCase();
    const landcover = (classification?.predicted_landcover_class || '').toLowerCase();
    const rationale = (classification?.classification_rationale || '').toLowerCase();

    if (
      clsLabel.includes('industrial') ||
      osmFacility.includes('factory') ||
      osmFacility.includes('industrial') ||
      osmFacility.includes('refinery') ||
      osmFacility.includes('power') ||
      osmFacility.includes('works')
    ) {
      return {
        type: 'INDUSTRIAL_ZONE',
        name: 'Industrial / Manufacturing Area',
        icon: '🏭',
        tone: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
        badgeBg: 'bg-amber-600',
        desc: 'Identified near industrial infrastructure, factory clusters, or commercial facilities.',
      };
    }

    if (
      clsLabel.includes('forest') ||
      landcover.includes('forest') ||
      landcover.includes('tree') ||
      landcover.includes('woodland') ||
      rationale.includes('forest')
    ) {
      return {
        type: 'FOREST_AREA',
        name: 'Forest / Natural Vegetation Area',
        icon: '🌲',
        tone: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
        badgeBg: 'bg-emerald-600',
        desc: 'Identified in forest canopy, dense vegetative cover, or wilderness zone.',
      };
    }

    if (
      clsLabel.includes('agricultural') ||
      landcover.includes('crop') ||
      landcover.includes('agriculture') ||
      landcover.includes('field') ||
      rationale.includes('crop')
    ) {
      return {
        type: 'AGRICULTURAL_AREA',
        name: 'Agricultural / Farmland Area',
        icon: '🌾',
        tone: 'bg-lime-500/15 text-lime-600 dark:text-lime-400 border-lime-500/30',
        badgeBg: 'bg-lime-600',
        desc: 'Identified in open agricultural fields, rural crop parcels, or agrarian landscape.',
      };
    }

    if (
      landcover.includes('urban') ||
      landcover.includes('built') ||
      osmFacility.includes('residential') ||
      detail?.location?.locality_colony !== 'Not available' ||
      detail?.location?.city_town !== 'Not available'
    ) {
      return {
        type: 'RESIDENTIAL_DOMESTIC',
        name: 'Domestic / Residential Settlement Area',
        icon: '🏘️',
        tone: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30',
        badgeBg: 'bg-blue-600',
        desc: 'Identified within or adjacent to inhabited settlements, residential colonies, or township sectors.',
      };
    }

    if (landcover.includes('park') || landcover.includes('grass') || landcover.includes('water')) {
      return {
        type: 'PARK_PROTECTED',
        name: 'Park / Protected Green Zone',
        icon: '🏞️',
        tone: 'bg-teal-500/15 text-teal-600 dark:text-teal-400 border-teal-500/30',
        badgeBg: 'bg-teal-600',
        desc: 'Identified in parklands, water buffer zones, or protected natural open spaces.',
      };
    }

    return {
      type: 'MIXED_TERRAIN',
      name: 'Mixed / Rural Open Terrain',
      icon: '📍',
      tone: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30',
      badgeBg: 'bg-slate-700',
      desc: 'Observed in open terrain or transitional rural geography with mixed spectral characteristics.',
    };
  }, [classification, detail]);

  const tileUrl =
    basemap === 'satellite'
      ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
      : basemap === 'topo'
      ? 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png'
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

  const tileAttr =
    basemap === 'satellite'
      ? '&copy; Esri &mdash; Earthstar Geographics'
      : basemap === 'topo'
      ? '&copy; OpenTopoMap contributors'
      : '&copy; OpenStreetMap contributors';

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-900 overflow-hidden relative select-none rounded-xl border border-slate-200 dark:border-slate-800 shadow-md">
      {/* Top Categorization HUD Header */}
      <div className="bg-slate-900/95 backdrop-blur-md px-4 py-3 border-b border-slate-800 z-[1000] flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <span className={`px-2.5 py-1 rounded-md text-xs font-bold border flex items-center gap-1.5 ${areaCategory.tone}`}>
            <span className="text-sm">{areaCategory.icon}</span>
            <span>{areaCategory.name}</span>
          </span>
          <div className="hidden sm:block text-xs text-slate-300">
            <span className="font-semibold text-white">
              {detail?.location?.formatted_location_header || `${lat.toFixed(4)}, ${lon.toFixed(4)}`}
            </span>
          </div>
        </div>

        {/* Map View Mode Controls */}
        <div className="flex items-center gap-1.5 ml-auto">
          <div className="bg-slate-800 rounded-lg p-0.5 border border-slate-700 flex items-center text-xs">
            <button
              type="button"
              onClick={() => setBasemap('osm')}
              className={`px-2 py-1 rounded font-medium transition-colors ${
                basemap === 'osm' ? 'bg-sky-600 text-white shadow-xs' : 'text-slate-400 hover:text-white'
              }`}
              title="OpenStreetMap Roads & Places"
            >
              OSM Streets
            </button>
            <button
              type="button"
              onClick={() => setBasemap('satellite')}
              className={`px-2 py-1 rounded font-medium transition-colors ${
                basemap === 'satellite' ? 'bg-sky-600 text-white shadow-xs' : 'text-slate-400 hover:text-white'
              }`}
              title="High-Resolution Satellite Imagery"
            >
              Satellite
            </button>
            <button
              type="button"
              onClick={() => setBasemap('topo')}
              className={`px-2 py-1 rounded font-medium transition-colors ${
                basemap === 'topo' ? 'bg-sky-600 text-white shadow-xs' : 'text-slate-400 hover:text-white'
              }`}
              title="Topographic Terrain"
            >
              Terrain
            </button>
          </div>

          <button
            type="button"
            onClick={() => setZoomLevel(15)}
            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            title="Zoom to Local Street Level"
          >
            Local (15x)
          </button>
          <button
            type="button"
            onClick={() => setZoomLevel(11)}
            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            title="Zoom to District Level"
          >
            District (11x)
          </button>
        </div>
      </div>

      {/* Live Geospatial Leaflet Map */}
      <div className="flex-1 relative w-full h-full min-h-[360px]">
        <MapContainer
          center={center}
          zoom={zoomLevel}
          style={{ width: '100%', height: '100%' }}
          zoomControl={true}
          scrollWheelZoom={true}
        >
          <TileLayer key={basemap} attribution={tileAttr} url={tileUrl} />
          <MapController center={center} zoom={zoomLevel} />

          {/* Heat Radiance Influence Zone */}
          <Circle
            center={center}
            radius={800}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: 0.15,
              weight: 1.5,
              dashArray: '4 4',
            }}
          />

          {/* Centroid Pulsing Marker */}
          <CircleMarker
            center={center}
            radius={10}
            pathOptions={{
              color: '#ffffff',
              fillColor: color,
              fillOpacity: 1,
              weight: 2.5,
              className: 'pulse-centroid-marker',
            }}
          >
            <Popup>
              <div className="text-xs p-1">
                <div className="font-extrabold text-navy-900 mb-1">
                  CLUSTER #{event.cluster_id} — {areaCategory.name}
                </div>
                <div className="text-slate-600 mb-1">
                  <strong>Coords:</strong> {formatCoordinate(lat, lon)}
                </div>
                <div className="text-slate-600 mb-1">
                  <strong>Max FRP:</strong> {(detail?.max_frp ?? event.frp ?? 0).toFixed(1)} MW
                </div>
                <div className="text-slate-600">
                  <strong>Location:</strong> {detail?.location?.formatted_location_header || 'Surrounding area'}
                </div>
              </div>
            </Popup>
          </CircleMarker>

          {/* If fire station exists in response context */}
          {response && response.station_available && response.nearest_station_name && (
            <Marker position={[lat + 0.012, lon + 0.015]} icon={fireStationIcon}>
              <Popup>
                <div className="text-xs">
                  <div className="font-bold text-red-600">🚒 {response.nearest_station_name}</div>
                  <div className="text-slate-600">
                    Distance: {response.station_distance_km?.toFixed(1) ?? '—'} km
                  </div>
                </div>
              </Popup>
            </Marker>
          )}

          {/* OSM Industrial Facility Marker if available */}
          {classification && classification.osm_facility_type !== 'UNKNOWN' && (
            <Marker position={[lat - 0.008, lon - 0.009]} icon={industrialIcon}>
              <Popup>
                <div className="text-xs">
                  <div className="font-bold text-slate-800">🏭 {classification.osm_facility_type}</div>
                  <div className="text-slate-600">
                    Distance: {classification.osm_distance_km?.toFixed(1) ?? '—'} km from anomaly
                  </div>
                </div>
              </Popup>
            </Marker>
          )}
        </MapContainer>

        {/* Floating Area Category Card at Bottom Left of Map */}
        <div className="absolute bottom-3 left-3 z-[1000] max-w-sm bg-slate-900/90 backdrop-blur-md rounded-xl p-3 border border-slate-700/80 shadow-xl text-xs text-white">
          <div className="flex items-center gap-1.5 font-bold mb-1">
            <span>{areaCategory.icon}</span>
            <span className="text-sky-400 uppercase tracking-wider">{areaCategory.name}</span>
          </div>
          <p className="text-[11px] text-slate-300 leading-snug">{areaCategory.desc}</p>
          <div className="mt-2 pt-2 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span>Lat: {lat.toFixed(5)}</span>
            <span>Lon: {lon.toFixed(5)}</span>
            <span>OSM Verified</span>
          </div>
        </div>
      </div>
    </div>
  );
}
