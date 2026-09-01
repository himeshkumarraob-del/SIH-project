export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatCoordinate(lat: number, lon: number): string {
  const latDir = lat >= 0 ? 'N' : 'S';
  const lonDir = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(3)}°${latDir}, ${Math.abs(lon).toFixed(3)}°${lonDir}`;
}

export function formatDistance(km: number): string {
  return `${km.toFixed(2)} km`;
}

export function formatRate(kmPerDay: number): string {
  return `${kmPerDay.toFixed(2)} km/day`;
}

export function formatDegrees(deg: number): string {
  return `${deg.toFixed(1)}°`;
}

export function riskLevelColor(level: string): string {
  switch (level) {
    case 'HIGH': return 'text-red-600 bg-red-50 border-red-200';
    case 'MEDIUM': return 'text-amber-600 bg-amber-50 border-amber-200';
    case 'LOW': return 'text-green-600 bg-green-50 border-green-200';
    default: return 'text-slate-500 bg-slate-50 border-slate-200';
  }
}

export function riskLevelBg(level: string): string {
  switch (level) {
    case 'HIGH': return 'bg-red-600';
    case 'MEDIUM': return 'bg-amber-500';
    case 'LOW': return 'bg-green-600';
    default: return 'bg-slate-400';
  }
}

export function abnormalityColor(level: string): string {
  switch (level) {
    case 'HIGH': return 'text-red-600 bg-red-50 border-red-200';
    case 'ELEVATED': return 'text-orange-600 bg-orange-50 border-orange-200';
    case 'NORMAL': return 'text-green-600 bg-green-50 border-green-200';
    default: return 'text-slate-500 bg-slate-50 border-slate-200';
  }
}

export function markerColor(level: string): string {
  switch (level) {
    case 'HIGH': return '#dc2626';
    case 'ELEVATED': return '#d97706';
    case 'NORMAL': return '#16a34a';
    default: return '#6b7280';
  }
}

export function riskGaugeGradient(score: number): string {
  if (score >= 60) return 'from-red-500 to-red-600';
  if (score >= 30) return 'from-amber-400 to-amber-500';
  return 'from-green-400 to-green-500';
}
