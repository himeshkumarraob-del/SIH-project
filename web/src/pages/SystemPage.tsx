import { useState, useEffect } from 'react';
import { fetchStatistics } from '../api/client';
import { formatNumber } from '../utils/formatters';

interface EndpointStatus {
  name: string;
  path: string;
  method: string;
  status: 'ONLINE' | 'CHECKING' | 'OFFLINE';
  latencyMs?: number;
}

export default function SystemPage() {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [statsData, setStatsData] = useState<any>(null);

  const [endpoints, setEndpoints] = useState<EndpointStatus[]>([
    { name: 'Dashboard Statistics', path: '/api/v1/statistics', method: 'GET', status: 'CHECKING' },
    { name: 'Thermal Events', path: '/api/v1/events?limit=5', method: 'GET', status: 'CHECKING' },
    { name: 'Spatial Clusters', path: '/api/v1/clusters', method: 'GET', status: 'CHECKING' },
    { name: 'Decision Alerts', path: '/api/v1/alerts?status=ACTIVE', method: 'GET', status: 'CHECKING' },
    { name: 'Movement Telemetry', path: '/api/v1/movement', method: 'GET', status: 'CHECKING' },
  ]);

  const testEndpoints = async () => {
    const t0 = performance.now();
    try {
      const s = await fetchStatistics();
      const t1 = performance.now();
      setLatency(Math.round(t1 - t0));
      setApiOnline(true);
      setStatsData(s);
    } catch {
      setApiOnline(false);
      setLatency(null);
    }

    const tested = await Promise.all(
      endpoints.map(async (ep) => {
        const start = performance.now();
        try {
          const res = await fetch(ep.path);
          const end = performance.now();
          return {
            ...ep,
            status: res.ok ? ('ONLINE' as const) : ('OFFLINE' as const),
            latencyMs: Math.round(end - start),
          };
        } catch {
          return {
            ...ep,
            status: 'OFFLINE' as const,
          };
        }
      }),
    );
    setEndpoints(tested);
  };

  useEffect(() => {
    testEndpoints();
  }, []);

  const pipelines = [
    {
      name: 'NASA FIRMS VIIRS Ingestion',
      description: 'Ingests active thermal anomalies from 375m I-band (I4/I5) VIIRS sensors (Suomi NPP & NOAA-20).',
      status: 'ACTIVE',
      layer: 'Data Ingestion Layer',
    },
    {
      name: 'Spatial-Temporal DBSCAN Clusterer',
      description: 'Groups discrete pixel hotspots into coherent spatial clusters across time windows.',
      status: 'ACTIVE',
      layer: 'Geometry & Clustering',
    },
    {
      name: 'Isolation Forest AI Anomaly Detector',
      description: 'Scores multi-band spectral deviation, FRP ratios, and thermal brightness abnormality.',
      status: 'ACTIVE',
      layer: 'AI Intelligence Layer',
    },
    {
      name: 'Contextual False-Alarm Validator',
      description: 'Filters solar reflection, water boundaries, and persistent industrial flares using OSM context.',
      status: 'ACTIVE',
      layer: 'Validation Layer',
    },
    {
      name: 'Thermal Centroid Propagation Analyzer',
      description: 'Calculates displacement bearing degrees, rate (km/day), and direction vectors.',
      status: 'ACTIVE',
      layer: 'Kinematics & Telemetry',
    },
    {
      name: 'Decision-Support Thermal Alert Engine',
      description: 'State machine for active alerts, acknowledging, resolving, and emergency services routing.',
      status: 'ACTIVE',
      layer: 'Alert Store & Dispatch',
    },
  ];

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-3 sm:p-4 lg:p-6 space-y-4">
      {/* Title */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-navy-900 dark:text-slate-100 tracking-tight">
            System & Pipeline Architecture
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            Backend health diagnostics, FastAPI endpoint status, and intelligence pipeline subsystem statuses.
          </p>
        </div>
        <button
          type="button"
          onClick={testEndpoints}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-navy-900 hover:bg-navy-800 dark:bg-blue-600 dark:hover:bg-blue-500 transition-colors shadow-2xs"
        >
          Run Diagnostics Ping
        </button>
      </div>

      {/* Health Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-950/80 text-green-700 dark:text-green-400 flex items-center justify-center flex-shrink-0">
            <span className="w-3.5 h-3.5 rounded-full bg-green-500 animate-pulse" />
          </div>
          <div>
            <span className="text-xs text-slate-400 dark:text-slate-500">FastAPI REST Server</span>
            <div className="text-lg font-bold text-navy-900 dark:text-slate-100">
              {apiOnline === null ? 'Checking…' : apiOnline ? 'HEALTHY (200 OK)' : 'OFFLINE'}
            </div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {latency ? `${latency} ms round-trip` : 'Direct proxy connection'}
            </span>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7C5 4 4 5 4 7z" />
            </svg>
          </div>
          <div>
            <span className="text-xs text-slate-400 dark:text-slate-500">Master Dataset</span>
            <div className="text-lg font-bold text-navy-900 dark:text-slate-100">
              {statsData ? `${formatNumber(statsData.total_detections)} Detections` : 'Loaded'}
            </div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {statsData ? `${statsData.active_clusters} clusters indexed` : 'India VIIRS feed'}
            </span>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <span className="text-xs text-slate-400 dark:text-slate-500">Security & Integrity</span>
            <div className="text-lg font-bold text-navy-900 dark:text-slate-100">Operational</div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">Read-only intelligence mode</span>
          </div>
        </div>
      </div>

      {/* REST API Endpoints Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
        <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">Live API Endpoints</h3>
        <div className="overflow-x-auto">
          <table className="min-w-[600px] w-full text-xs">
            <thead className="bg-slate-50 dark:bg-slate-950/80 border-b border-slate-100 dark:border-slate-800">
              <tr className="text-left text-slate-500 dark:text-slate-400">
                <th className="px-3 py-2 font-bold">Service / Resource</th>
                <th className="px-3 py-2 font-bold">Method</th>
                <th className="px-3 py-2 font-bold">Endpoint Path</th>
                <th className="px-3 py-2 font-bold">Status</th>
                <th className="px-3 py-2 font-bold text-right">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
              {endpoints.map((ep) => (
                <tr key={ep.path} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="px-3 py-2 font-sans font-semibold text-slate-900 dark:text-slate-100">{ep.name}</td>
                  <td className="px-3 py-2">
                    <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 font-bold text-[10px]">
                      {ep.method}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{ep.path}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        ep.status === 'ONLINE'
                          ? 'bg-green-100 text-green-700 dark:bg-green-950/80 dark:text-green-300'
                          : ep.status === 'CHECKING'
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-300'
                          : 'bg-red-100 text-red-700 dark:bg-red-950/80 dark:text-red-300'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${ep.status === 'ONLINE' ? 'bg-green-500' : 'bg-red-500'}`} />
                      {ep.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-500 dark:text-slate-400">
                    {ep.latencyMs ? `${ep.latencyMs} ms` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI & Pipeline Subsystems */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
        <h3 className="text-sm font-bold text-navy-900 dark:text-slate-100">Pipeline Subsystems</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {pipelines.map((pipe) => (
            <div key={pipe.name} className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-navy-900 dark:text-slate-100">{pipe.name}</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-green-100 text-green-700 dark:bg-green-950/80 dark:text-green-300">
                  {pipe.status}
                </span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-400">{pipe.description}</p>
              <div className="text-[10px] text-slate-400 font-mono pt-1">{pipe.layer}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
