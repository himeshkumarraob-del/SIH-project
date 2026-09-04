import { useEffect, useMemo, useState } from 'react';
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import { fetchEmergencyResponseStations, fetchPrototypeNotificationHistory, postPrototypeNotification } from '../api/client';
import type { EmergencyResponseSearchResult, FireStationCandidate, PrototypeNotificationHistoryEntry } from '../types';

interface EmergencyResponseModalProps {
  clusterId: number;
  onClose: () => void;
}

type SearchStage = 'LOCATING EVENT' | 'SEARCHING NEARBY STATIONS' | 'STATIONS FOUND' | 'NO VERIFIED FIRE STATION FOUND WITHIN 50 KM';

const stageOrder: SearchStage[] = ['LOCATING EVENT', 'SEARCHING NEARBY STATIONS', 'STATIONS FOUND'];

export default function EmergencyResponseModal({ clusterId, onClose }: EmergencyResponseModalProps) {
  const [data, setData] = useState<EmergencyResponseSearchResult | null>(null);
  const [stage, setStage] = useState<SearchStage>('LOCATING EVENT');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStation, setSelectedStation] = useState<FireStationCandidate | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [history, setHistory] = useState<PrototypeNotificationHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setStage('LOCATING EVENT');

    const timers = [
      window.setTimeout(() => !cancelled && setStage('SEARCHING NEARBY STATIONS'), 650),
    ];

    fetchEmergencyResponseStations(clusterId)
      .then((result) => {
        if (cancelled) return;
        timers.push(window.setTimeout(() => {
          if (cancelled) return;
          setData(result);
          setSelectedStation(result.nearest_station);
          setStage(result.station_available ? 'STATIONS FOUND' : 'NO VERIFIED FIRE STATION FOUND WITHIN 50 KM');
          setLoading(false);
        }, 1050));
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });

    fetchPrototypeNotificationHistory(clusterId)
      .then((rows) => {
        if (cancelled) return;
        setHistory(rows);
        setHistoryLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setHistory([]);
        setHistoryLoading(false);
      });

    return () => {
      cancelled = true;
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [clusterId]);

  const mapCenter = useMemo<[number, number]>(() => {
    if (!data) return [20.5937, 78.9629];
    return [data.event.latitude, data.event.longitude];
  }, [data]);

  const canSend = Boolean(data?.notification_eligible && selectedStation && !sending && !sendResult);

  const handleSend = async () => {
    if (!data || !selectedStation) return;
    setSending(true);
    setSendError(null);
    try {
      const result = await postPrototypeNotification(data.cluster_id, selectedStation.station_id);
      setSendResult(`${result.detail} Recipient ${result.recipient_masked}.`);
      setConfirming(false);
      fetchPrototypeNotificationHistory(data.cluster_id)
        .then((rows) => setHistory(rows))
        .catch(() => undefined);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Prototype notification failed.');
    } finally {
      setSending(false);
    }
  };

  const stageIndex = Math.max(0, stageOrder.indexOf(stage));

  return (
    <div className="fixed inset-0 z-[1800] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-2 sm:p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-6xl max-h-[94vh] overflow-hidden rounded-xl border border-slate-700 bg-slate-950 text-slate-100 shadow-2xl flex flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-[0.14em] text-white">
                Prototype / Decision-Support Notification
              </span>
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Emergency Response Module</span>
            </div>
            <h2 className="mt-1 text-lg font-extrabold tracking-tight text-white sm:text-xl">Thermal Event Response</h2>
            <p className="text-xs text-slate-400">Operator-confirmed advisory workflow. ThermalWatch does not declare confirmed emergencies or official dispatch.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-bold text-slate-200 hover:bg-slate-700" title="Close emergency response">
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
          {error && (
            <div className="rounded-lg border border-red-900 bg-red-950/60 p-4 text-sm text-red-200">{error}</div>
          )}

          {!error && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.05fr_0.95fr]">
              <section className="space-y-3 min-w-0">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {stageOrder.map((item, idx) => (
                    <div key={item} className={`rounded-lg border px-3 py-2 ${idx <= stageIndex || stage === 'NO VERIFIED FIRE STATION FOUND WITHIN 50 KM' ? 'border-blue-500/60 bg-blue-950/30' : 'border-slate-800 bg-slate-900/70'}`}>
                      <div className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Step {idx + 1}</div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-[0.08em] text-slate-100">
                        <span className={`h-2 w-2 rounded-full ${idx <= stageIndex && loading ? 'animate-pulse bg-blue-400' : idx <= stageIndex ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        {item}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="relative h-[340px] overflow-hidden rounded-lg border border-slate-800 bg-slate-900 sm:h-[430px]">
                  {data ? (
                    <MapContainer center={mapCenter} zoom={9} scrollWheelZoom className="h-full w-full">
                      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                      <Circle center={mapCenter} radius={data.search_radius_km * 1000} pathOptions={{ color: '#38bdf8', fillColor: '#0ea5e9', fillOpacity: 0.08, weight: 1 }} />
                      <CircleMarker center={mapCenter} radius={9} pathOptions={{ color: '#ffffff', fillColor: '#ef4444', fillOpacity: 0.95, weight: 2 }}>
                        <Popup>Thermal event cluster #{data.cluster_id}</Popup>
                      </CircleMarker>
                      {data.stations.map((station) => {
                        const selected = selectedStation?.station_id === station.station_id;
                        return (
                          <CircleMarker key={station.station_id} center={[station.station_latitude, station.station_longitude]} radius={selected ? 8 : 5} pathOptions={{ color: selected ? '#fde68a' : '#22c55e', fillColor: selected ? '#f59e0b' : '#16a34a', fillOpacity: 0.9, weight: selected ? 3 : 1.5 }} eventHandlers={{ click: () => setSelectedStation(station) }}>
                            <Popup>{station.station_name}<br />{station.distance_km.toFixed(1)} km</Popup>
                          </CircleMarker>
                        );
                      })}
                    </MapContainer>
                  ) : (
                    <div className="flex h-full items-center justify-center text-center">
                      <div>
                        <div className="mx-auto mb-3 h-9 w-9 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                        <div className="text-xs font-extrabold uppercase tracking-[0.16em] text-blue-300">{stage}</div>
                      </div>
                    </div>
                  )}
                  {data && (
                    <div className="absolute left-3 top-3 rounded-md border border-slate-700 bg-slate-950/85 px-3 py-2 text-xs shadow-lg">
                      <div className="font-extrabold text-white">Search radius {data.search_radius_km.toFixed(0)} km</div>
                      <div className={data.station_available ? 'text-emerald-300' : 'text-amber-300'}>{data.status_message}</div>
                    </div>
                  )}
                </div>
              </section>

              <section className="space-y-3 min-w-0">
                {data ? (
                  <>
                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                        <Metric label="Cluster" value={`#${data.event.cluster_id}`} />
                        <Metric label="Severity" value={data.event.severity} tone={data.event.severity === 'CRITICAL' ? 'text-red-300' : 'text-orange-300'} />
                        <Metric label="Risk" value={`${Math.round(data.event.risk_score)}/100`} />
                        <Metric label="Class" value={data.event.classification_label} wide />
                        <Metric label="Evidence" value={data.event.evidence_confidence} />
                        <Metric label="False Alarm" value={`${data.event.false_alarm_indicator} concern`} />
                        <Metric label="Coordinates" value={`${data.event.latitude.toFixed(5)}, ${data.event.longitude.toFixed(5)}`} wide />
                        <Metric label="Detections" value={`${data.event.observation_count} obs / ${data.event.active_days} days`} />
                      </div>
                    </div>

                    {!data.station_available && (
                      <div className="rounded-lg border border-amber-700 bg-amber-950/40 p-3 text-sm font-bold text-amber-200">NO VERIFIED FIRE STATION FOUND WITHIN 50 KM</div>
                    )}

                    {data.nearest_station && (
                      <div className="rounded-lg border border-amber-500/70 bg-amber-950/30 p-3">
                        <div className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-amber-300">Nearest Verified Station</div>
                        <div className="mt-1 flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-extrabold text-white">{data.nearest_station.station_name}</div>
                            <div className="text-xs text-slate-400">{data.nearest_station.distance_km.toFixed(1)} km from event</div>
                          </div>
                          <button type="button" onClick={() => setSelectedStation(data.nearest_station)} className="rounded-md bg-amber-500 px-2.5 py-1 text-[10px] font-extrabold uppercase text-slate-950">Selected</button>
                        </div>
                      </div>
                    )}

                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <h3 className="text-xs font-extrabold uppercase tracking-[0.14em] text-slate-300">Ranked Nearby Stations</h3>
                        <span className="text-[10px] text-slate-500">Verified dataset only</span>
                      </div>
                      <div className="space-y-2">
                        {data.stations.map((station, idx) => (
                          <button key={station.station_id} type="button" onClick={() => setSelectedStation(station)} className={`w-full rounded-lg border p-2.5 text-left transition ${selectedStation?.station_id === station.station_id ? 'border-blue-500 bg-blue-950/40' : 'border-slate-800 bg-slate-950/60 hover:border-slate-600'}`}>
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Rank {idx + 1}</div>
                                <div className="truncate text-sm font-bold text-white">{station.station_name}</div>
                                <div className="text-[11px] text-slate-400">Contact: {station.contact_phone ? station.contact_phone : 'No verified contact in dataset'}</div>
                              </div>
                              <div className="shrink-0 text-right text-xs font-mono font-extrabold text-slate-100">{station.distance_km.toFixed(1)} km</div>
                            </div>
                            <a href={`https://www.openstreetmap.org/?mlat=${station.station_latitude}&mlon=${station.station_longitude}#map=15/${station.station_latitude}/${station.station_longitude}`} target="_blank" rel="noreferrer" className="mt-2 inline-flex rounded border border-slate-700 px-2 py-1 text-[10px] font-extrabold uppercase tracking-[0.08em] text-blue-300 hover:bg-slate-800">
                              View on Map
                            </a>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                      <div className={`mb-3 rounded-md border px-3 py-2 text-xs ${data.notification_eligible ? 'border-emerald-700 bg-emerald-950/30 text-emerald-200' : 'border-amber-700 bg-amber-950/30 text-amber-200'}`}>
                        {data.eligibility_reason}
                      </div>
                      {!confirming ? (
                        <button type="button" disabled={!canSend} onClick={() => setConfirming(true)} className="w-full rounded-lg bg-red-600 px-4 py-2.5 text-xs font-extrabold uppercase tracking-[0.1em] text-white shadow-lg disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400">
                          Send Prototype Alert
                        </button>
                      ) : (
                        <div className="space-y-2">
                          <p className="text-xs text-slate-300">Confirm sending one backend-configured prototype SMS recipient. This is decision-support only and does not dispatch emergency services.</p>
                          <div className="grid grid-cols-2 gap-2">
                            <button type="button" onClick={() => setConfirming(false)} className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800">Cancel</button>
                            <button type="button" onClick={handleSend} disabled={sending} className="rounded-lg bg-red-600 px-3 py-2 text-xs font-extrabold uppercase text-white disabled:bg-slate-700">{sending ? 'Sending...' : 'Confirm Send'}</button>
                          </div>
                        </div>
                      )}
                      {sendResult && <div className="mt-3 rounded-md border border-emerald-700 bg-emerald-950/30 p-2 text-xs text-emerald-200">{sendResult}</div>}
                      {sendError && <div className="mt-3 rounded-md border border-red-800 bg-red-950/40 p-2 text-xs text-red-200">{sendError}</div>}
                    </div>
                  </>
                ) : (
                  <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-center text-sm text-slate-400">{stage}</div>
                )}

                {/* Prototype Notification History (masked, no provider secrets) */}
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h3 className="text-xs font-extrabold uppercase tracking-[0.14em] text-slate-300">Prototype Notification History</h3>
                    <span className="text-[10px] text-slate-500">Cluster #{clusterId} · masked</span>
                  </div>
                  {historyLoading ? (
                    <div className="py-3 text-center text-[11px] text-slate-500">Loading attempts…</div>
                  ) : history.length === 0 ? (
                    <div className="py-3 text-center text-[11px] text-slate-500">No prototype notification attempts recorded for this cluster.</div>
                  ) : (
                    <div className="space-y-2">
                      {history.slice(0, 5).map((entry, idx) => {
                        const tone =
                          entry.send_status === 'SENT'
                            ? 'border-emerald-700 bg-emerald-950/30 text-emerald-200'
                            : entry.send_status === 'REJECTED'
                            ? 'border-amber-700 bg-amber-950/30 text-amber-200'
                            : 'border-red-800 bg-red-950/40 text-red-200';
                        return (
                          <div key={`${entry.timestamp}-${idx}`} className={`rounded-md border px-2.5 py-2 text-[11px] ${tone}`}>
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-extrabold uppercase tracking-[0.08em]">{entry.send_status}</span>
                              <span className="font-mono text-slate-400">{entry.timestamp.replace('T', ' ').slice(0, 16)}</span>
                            </div>
                            <div className="mt-1 space-y-0.5 text-slate-300">
                              {entry.selected_station && (
                                <div>Station: {entry.selected_station}{entry.distance_km != null ? ` · ${entry.distance_km.toFixed(1)} km` : ''}</div>
                              )}
                              {entry.recipient_masked && <div>Recipient: {entry.recipient_masked}</div>}
                              {entry.failure_reason && <div className="text-red-300/90">Reason: {entry.failure_reason}</div>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, tone = 'text-slate-100', wide = false }: { label: string; value: string; tone?: string; wide?: boolean }) {
  return (
    <div className={`min-w-0 rounded-md border border-slate-800 bg-slate-950/60 p-2 ${wide ? 'sm:col-span-2' : ''}`}>
      <div className="text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className={`mt-1 truncate text-xs font-bold ${tone}`}>{value || '-'}</div>
    </div>
  );
}
