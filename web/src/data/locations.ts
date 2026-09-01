/**
 * Predefined Indian locations for map search and navigation.
 * Structured so a geocoding API (Nominatim, etc.) can replace this later.
 */

export interface MapLocation {
  name: string;
  aliases: string[];
  lat: number;
  lon: number;
  zoom: number;
  region?: string;
}

export const LOCATIONS: MapLocation[] = [
  // === Country ===
  { name: 'India', aliases: ['india', 'bharat'], lat: 20.5937, lon: 78.9629, zoom: 5 },

  // === States / Regions ===
  { name: 'Tamil Nadu', aliases: ['tamil nadu', 'tamilnadu', 'tn'], lat: 11.1271, lon: 78.6569, zoom: 7 },
  { name: 'Kerala', aliases: ['kerala', 'keral'], lat: 10.8505, lon: 76.2711, zoom: 7 },
  { name: 'Karnataka', aliases: ['karnataka'], lat: 15.3173, lon: 75.7139, zoom: 7 },
  { name: 'Andhra Pradesh', aliases: ['andhra pradesh', 'andhra', 'ap'], lat: 15.9129, lon: 79.7400, zoom: 7 },
  { name: 'Telangana', aliases: ['telangana', 'ts'], lat: 18.1124, lon: 79.0193, zoom: 7 },
  { name: 'Maharashtra', aliases: ['maharashtra', 'mh'], lat: 19.7515, lon: 75.7139, zoom: 7 },
  { name: 'Gujarat', aliases: ['gujarat', 'gj'], lat: 22.2587, lon: 71.1924, zoom: 7 },
  { name: 'Rajasthan', aliases: ['rajasthan', 'rj'], lat: 27.0238, lon: 74.2179, zoom: 7 },
  { name: 'Madhya Pradesh', aliases: ['madhya pradesh', 'mp'], lat: 22.9734, lon: 78.6569, zoom: 7 },
  { name: 'Uttar Pradesh', aliases: ['uttar pradesh', 'up'], lat: 26.8467, lon: 80.9462, zoom: 7 },
  { name: 'Bihar', aliases: ['bihar'], lat: 25.0961, lon: 85.3131, zoom: 7 },
  { name: 'West Bengal', aliases: ['west bengal', 'wb'], lat: 22.9873, lon: 87.8550, zoom: 7 },
  { name: 'Odisha', aliases: ['odisha', 'orissa'], lat: 20.9517, lon: 85.0985, zoom: 7 },
  { name: 'Chhattisgarh', aliases: ['chhattisgarh', 'cg'], lat: 21.2787, lon: 81.8661, zoom: 7 },
  { name: 'Jharkhand', aliases: ['jharkhand', 'jh'], lat: 23.6102, lon: 85.2799, zoom: 7 },
  { name: 'Punjab', aliases: ['punjab'], lat: 31.1471, lon: 75.3412, zoom: 7 },
  { name: 'Haryana', aliases: ['haryana'], lat: 29.0588, lon: 76.0856, zoom: 7 },
  { name: 'Delhi NCR', aliases: ['delhi', 'new delhi', 'ncr'], lat: 28.7041, lon: 77.1025, zoom: 10 },

  // === Major Cities ===
  { name: 'Chennai', aliases: ['chennai', 'madras'], lat: 13.0827, lon: 80.2707, zoom: 11 },
  { name: 'Mumbai', aliases: ['mumbai', 'bombay'], lat: 19.0760, lon: 72.8777, zoom: 11 },
  { name: 'Bengaluru', aliases: ['bengaluru', 'bangalore', 'blore'], lat: 12.9716, lon: 77.5946, zoom: 11 },
  { name: 'Hyderabad', aliases: ['hyderabad'], lat: 17.3850, lon: 78.4867, zoom: 11 },
  { name: 'Kolkata', aliases: ['kolkata', 'calcutta'], lat: 22.5726, lon: 88.3639, zoom: 11 },
  { name: 'Pune', aliases: ['pune', 'poona'], lat: 18.5204, lon: 73.8567, zoom: 11 },
  { name: 'Ahmedabad', aliases: ['ahmedabad', 'amdavad'], lat: 23.0225, lon: 72.5714, zoom: 11 },
  { name: 'Jaipur', aliases: ['jaipur'], lat: 26.9124, lon: 75.7873, zoom: 11 },
  { name: 'Lucknow', aliases: ['lucknow'], lat: 26.8467, lon: 80.9462, zoom: 11 },
  { name: 'Bhopal', aliases: ['bhopal'], lat: 23.2599, lon: 77.4126, zoom: 11 },
  { name: 'Patna', aliases: ['patna'], lat: 25.6093, lon: 85.1376, zoom: 11 },
  { name: 'Indore', aliases: ['indore'], lat: 22.7196, lon: 75.8577, zoom: 11 },
  { name: 'Coimbatore', aliases: ['coimbatore', 'kovai'], lat: 11.0168, lon: 76.9558, zoom: 11 },
  { name: 'Madurai', aliases: ['madurai'], lat: 9.9252, lon: 78.1198, zoom: 11 },
  { name: 'Visakhapatnam', aliases: ['visakhapatnam', 'vizag'], lat: 17.6868, lon: 83.2185, zoom: 11 },
  { name: 'Nagpur', aliases: ['nagpur'], lat: 21.1458, lon: 79.0882, zoom: 11 },
  { name: 'Varanasi', aliases: ['varanasi', 'benaras', 'kashi'], lat: 25.3176, lon: 82.9739, zoom: 11 },
  { name: 'Thiruvananthapuram', aliases: ['thiruvananthapuram', 'trivandrum'], lat: 8.5241, lon: 76.9366, zoom: 11 },
  { name: 'Guwahati', aliases: ['guwahati', 'gauhati'], lat: 26.1445, lon: 91.7362, zoom: 11 },
  { name: 'Chandigarh', aliases: ['chandigarh'], lat: 30.7333, lon: 76.7794, zoom: 11 },

  // === Avadi and nearby ===
  { name: 'Avadi', aliases: ['avadi'], lat: 13.1067, lon: 80.0970, zoom: 13 },
  { name: 'Ambattur', aliases: ['ambattur'], lat: 13.1143, lon: 80.1548, zoom: 13 },
  { name: 'Tiruvallur', aliases: ['tiruvallur', 'thiruvallur'], lat: 13.1444, lon: 79.9071, zoom: 12 },
  { name: 'Kanchipuram', aliases: ['kanchipuram', 'kancheepuram'], lat: 12.8342, lon: 79.7036, zoom: 12 },

  // === Industrial / Thermal Zones ===
  { name: 'Jharia', aliases: ['jharia'], lat: 23.7492, lon: 86.4147, zoom: 13 },
  { name: 'Raniganj', aliases: ['raniganj'], lat: 23.6375, lon: 87.1333, zoom: 13 },
];

/**
 * Search locations by name or alias. Returns matches sorted by relevance.
 */
export function searchLocations(query: string): MapLocation[] {
  if (!query || query.trim().length === 0) return [];
  const q = query.toLowerCase().trim();
  return LOCATIONS.filter(
    (loc) =>
      loc.name.toLowerCase().includes(q) ||
      loc.aliases.some((alias) => alias.toLowerCase().includes(q))
  ).sort((a, b) => {
    // Exact name match first
    const aExact = a.name.toLowerCase() === q;
    const bExact = b.name.toLowerCase() === q;
    if (aExact && !bExact) return -1;
    if (!aExact && bExact) return 1;
    // Then alias exact match
    const aAlias = a.aliases.some((al) => al.toLowerCase() === q);
    const bAlias = b.aliases.some((al) => al.toLowerCase() === q);
    if (aAlias && !bAlias) return -1;
    if (!aAlias && bAlias) return 1;
    // Then starts-with
    const aStarts = a.name.toLowerCase().startsWith(q);
    const bStarts = b.name.toLowerCase().startsWith(q);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return 0;
  });
}
