import { useState } from 'react';
import type {
  ThermalEvent,
  ClusterDetail,
  ClassificationDetailData,
  RiskDetailData,
  ResponseDetailData,
  MovementVector,
  RiskEvidenceComponent,
} from '../types';

interface EvidenceExplorerProps {
  event: ThermalEvent;
  detail: ClusterDetail | null;
  classification: ClassificationDetailData | null;
  risk: RiskDetailData | null;
  response: ResponseDetailData | null;
  movement: MovementVector | null;
}

/**
 * AI EVIDENCE EXPLORER
 *
 * Explains WHY the existing ThermalWatch pipeline prioritized this event.
 * Every value is drawn from evidence already produced by the pipeline:
 * - Risk contribution components come from the backend risk engine breakdown
 *   (risk_evidence) and always reconcile with the stored risk_score.
 * - Why-flagged factors, false-alarm concern, industrial-context rationale and
 *   satellite context reuse the existing API fields verbatim.
 * No risk score is ever recalculated in the frontend and no evidence is invented.
 */
export default function EvidenceExplorer({
  event,
  detail,
  classification,
  risk,
  response,
  movement,
}: EvidenceExplorerProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const toggle = (key: string) => setExpanded((prev) => (prev === key ? null : key));

  const riskScore = risk?.risk_score ?? detail?.risk_score ?? 0;
  const riskLevel = risk?.risk_level ?? detail?.risk_level ?? 'LOW';
  const evidence = risk?.risk_evidence;
  const components: RiskEvidenceComponent[] = evidence?.components ?? [];
  const multiplier = evidence?.reliability_multiplier ?? null;
  const baseScore = evidence?.base_score ?? null;
  const faConcern = (detail?.false_alarm_indicator ?? 'MEDIUM').toUpperCase();
  const abnormality = (event.abnormality_level || detail?.abnormality_level || 'NORMAL').toUpperCase();
  const detectionReliability = detail?.detection_reliability ?? '';

  // Satellite context (a land-cover CNN is contextual evidence, never a fire detector)
  const satClass = classification?.predicted_landcover_class ?? 'UNKNOWN';
  const satConf = classification?.prediction_confidence ?? 0;
  const hasSatellite = Boolean(satClass && satClass !== 'UNKNOWN' && satClass !== 'None' && satConf > 0);

  // Why flagged: risk factors (engine) + contributing indicators (AI explanation)
  const riskFactorList =
    risk?.risk_factors && risk.risk_factors !== 'Standard thermal baseline'
      ? risk.risk_factors.split(';').map((s) => s.trim()).filter(Boolean)
      : [];
  const contributingList = event.contributing_factors
    ? event.contributing_factors.split(';').map((s) => s.trim()).filter(Boolean)
    : [];
  const flaggedFactors = Array.from(
    new Map([...riskFactorList, ...contributingList].map((s) => [s.toLowerCase(), s])).values(),
  );
  const characterization =
    event.anomaly_characterization || detail?.anomaly_characterization || '';
  const explanationText = event.explanation || detail?.explanation || '';

  // False-alarm detector evidence (actual reasons recorded by the detector)
  const faReasons = detail?.false_alarm_reasons
    ? detail.false_alarm_reasons.split(';').map((s) => s.trim()).filter(Boolean)
    : [];

  // Industrial-context rationale (only when the classifier actually assigned it)
  const clsLabel = classification?.classification_label ?? '';
  const isIndustrial = clsLabel.includes('Industrial');
  const osmFacility = classification?.osm_facility_type ?? '';
  const hasOsm = Boolean(osmFacility && !['none', 'UNKNOWN'].includes(osmFacility));
  const rationaleLines = classification?.classification_rationale
    ? classification.classification_rationale
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.startsWith('- '))
        .map((l) => l.substring(2))
    : [];

  // Supporting vs limiting evidence — pipeline thresholds only, displayed when actually true
  const maxTi4 = detail?.max_bright_ti4 ?? 0;
  const btDiff = detail?.bt_diff_max ?? 0;
  const maxFrp = detail?.max_frp ?? event.frp ?? 0;
  const activeDays = detail?.active_days ?? 1;
  const persCat = (detail?.persistence_category ?? '').toLowerCase();
  const movementStatus = movement?.movement_status ?? detail?.movement_status ?? '';
  const clsScore = classification?.classification_score ?? 0;

  const supporting: { key: string; label: string; why: string }[] = [];
  if (maxTi4 >= 340 || btDiff >= 45) {
    supporting.push({
      key: 'intensity',
      label: 'High thermal intensity',
      why: `Peak brightness temperature ${maxTi4.toFixed(1)} K and/or spectral contrast ${btDiff.toFixed(1)} K exceed the anomaly-explainer thresholds.`,
    });
  }
  if (persCat === 'persistent' || activeDays >= 4) {
    supporting.push({
      key: 'persistence',
      label: 'Persistent thermal activity',
      why: `Activity spans ${activeDays} active day(s) with persistence category '${persCat || 'unknown'}'.`,
    });
  }
  if (maxFrp >= 15) {
    supporting.push({
      key: 'frp',
      label: 'Elevated FRP',
      why: `Peak Fire Radiative Power of ${maxFrp.toFixed(1)} MW meets the strong-FRP evidence threshold (>= 15 MW).`,
    });
  }
  if (abnormality === 'HIGH' || abnormality === 'ELEVATED') {
    supporting.push({
      key: 'abnormality',
      label: `${abnormality} statistical abnormality`,
      why: `The event was flagged ${abnormality} relative to the analyzed thermal baseline.`,
    });
  }
  if (detectionReliability === 'HIGH') {
    supporting.push({
      key: 'reliability',
      label: 'High detection reliability',
      why: 'The false-alarm detector assigned HIGH detection reliability to this cluster.',
    });
  }
  if (clsScore >= 0.6 && !clsLabel.includes('Unknown')) {
    supporting.push({
      key: 'context',
      label: 'Strong contextual evidence',
      why: `The source-classification model assigned a confidence of ${(clsScore * 100).toFixed(0)}% (${clsLabel}).`,
    });
  }

  const limiting: { key: string; label: string; why: string }[] = [];
  if (!hasSatellite) {
    limiting.push({
      key: 'satellite',
      label: 'Limited satellite imagery',
      why: 'No usable Sentinel-2 observation: imagery is unavailable or cloud-obscured. This is not negative evidence.',
    });
  }
  if (faConcern === 'HIGH') {
    limiting.push({
      key: 'fa',
      label: 'High false-alarm concern',
      why: 'The false-alarm detector flagged weak or single-pass evidence. HIGH concern is not a confirmed false alarm.',
    });
  }
  if (movementStatus === 'INSUFFICIENT_DATA') {
    limiting.push({
      key: 'movement',
      label: 'Insufficient movement observations',
      why: 'Too few satellite passes to infer a defensible direction for the detected thermal activity.',
    });
  }
  if (response && !response.station_available) {
    limiting.push({
      key: 'station',
      label: 'No nearby fire station',
      why: 'No verified fire station was found within the operational search radius.',
    });
  }

  const riskLevelTone =
    riskLevel === 'HIGH'
      ? 'bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900'
      : riskLevel === 'MEDIUM'
      ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900'
      : 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900';

  const faTone =
    faConcern === 'LOW'
      ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900'
      : faConcern === 'HIGH'
      ? 'bg-red-100 dark:bg-red-950/70 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900'
      : 'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900';

  const barTone = (points: number, max: number) => {
    const pct = max > 0 ? points / max : 0;
    return pct >= 0.8
      ? 'bg-gradient-to-r from-amber-500 to-red-500'
      : pct >= 0.5
      ? 'bg-gradient-to-r from-amber-500 to-orange-500'
      : 'bg-slate-400 dark:bg-slate-600';
  };

  const chevron = (open: boolean) => (
    <svg
      className={`w-3 h-3 text-slate-400 dark:text-slate-500 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );

  const sectionLabel = (dot: string, text: string) => (
    <div className="flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${dot} flex-shrink-0`} />
      <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
        {text}
      </span>
    </div>
  );

  return (
    <div className="bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-2xs overflow-hidden">
      {/* Header */}
      <div className="bg-slate-50/90 dark:bg-slate-900/80 px-3.5 py-2 border-b border-slate-100 dark:border-slate-700/60">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-500" />
            <h3 className="text-xs font-bold text-navy-900 dark:text-slate-100 uppercase tracking-wider">
              AI Evidence Explorer
            </h3>
          </div>
          <span className="text-[10px] font-mono font-semibold text-slate-400 dark:text-slate-500">
            EVIDENCE
          </span>
        </div>
        <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
          Why this event was prioritized
        </p>
      </div>

      <div className="p-3.5 space-y-3.5">
        {/* ================================================================ */}
        {/* 1. RISK EVIDENCE CONTRIBUTION                                   */}
        {/* ================================================================ */}
        <div className="space-y-2">
          {sectionLabel('bg-orange-500', 'Risk Evidence Contribution')}

          {/* Score hero */}
          <div className="flex items-center justify-between gap-2 rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-gradient-to-br from-slate-50 to-slate-100/60 dark:from-slate-900 dark:to-slate-900 px-3 py-2.5">
            <div>
              <span className="text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-[0.16em] block">
                Risk Score
              </span>
              <span className="text-2xl font-extrabold font-mono text-navy-900 dark:text-slate-100 leading-tight">
                {Math.round(riskScore)}
                <span className="text-xs font-bold text-slate-400 dark:text-slate-500 ml-0.5">/ 100</span>
              </span>
            </div>
            <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border shadow-2xs ${riskLevelTone}`}>
              {riskLevel}
            </span>
          </div>

          {/* Component bars */}
          {components.length > 0 ? (
            <div className="space-y-1.5">
              {components.map((comp) => {
                const open = expanded === `comp-${comp.key}`;
                const pct = comp.max_points > 0 ? (comp.points / comp.max_points) * 100 : 0;
                return (
                  <div
                    key={comp.key}
                    className="rounded-lg border border-slate-200/70 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-900/50 overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => toggle(`comp-${comp.key}`)}
                      className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-left hover:bg-slate-100/70 dark:hover:bg-slate-800/70 transition-colors"
                    >
                      <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-300">
                        {comp.label}
                      </span>
                      <span className="flex items-center gap-1.5 flex-shrink-0">
                        <span className="font-mono font-bold text-[11px] text-slate-800 dark:text-slate-200">
                          {comp.points.toFixed(0)} / {comp.max_points.toFixed(0)}
                        </span>
                        {chevron(open)}
                      </span>
                    </button>
                    <div className="px-2.5 pb-2">
                      <div className="w-full h-1.5 bg-slate-200/80 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${barTone(comp.points, comp.max_points)}`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                      {open && (
                        <div className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed mt-1.5">
                          <p>
                            <span className="font-bold text-slate-600 dark:text-slate-300">
                              Contribution:{' '}
                            </span>
                            {comp.points.toFixed(0)} / {comp.max_points.toFixed(0)} points
                          </p>
                          <p className="mt-0.5">
                            <span className="font-bold text-slate-600 dark:text-slate-300">Why: </span>
                            {comp.detail}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Reliability adjustment + reconciliation */}
              {baseScore != null && multiplier != null && (
                <div className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/70 rounded-lg px-2.5 py-2">
                  <p className="font-mono text-[11px] font-bold text-slate-700 dark:text-slate-300">
                    {baseScore.toFixed(0)} pts × {multiplier.toFixed(2)} reliability ={' '}
                    {evidence?.final_score != null ? evidence.final_score.toFixed(1) : riskScore.toFixed(1)}
                  </p>
                  <p className="mt-0.5">
                    Components are raw evidence points; the adjusted total is the existing risk score.
                    Reliability adjustment reflects {faConcern} false-alarm concern.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[10px] text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/70 rounded-lg px-2.5 py-2">
              Risk contribution breakdown unavailable for this event.
            </p>
          )}

          <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-relaxed">
            Risk score is an experimental decision-support index, not a calibrated probability of
            fire.
          </p>
        </div>

        {/* ================================================================ */}
        {/* 2. WHY THIS EVENT WAS FLAGGED                                    */}
        {/* ================================================================ */}
        <div className="space-y-2">
          {sectionLabel('bg-amber-500', 'Why this event was flagged')}

          {characterization && (
            <div className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/30 px-2.5 py-2">
              <span className="text-[9px] font-bold text-amber-700 dark:text-amber-400 uppercase tracking-[0.16em] block">
                Flagged as
              </span>
              <span className="text-[11px] font-bold text-amber-950 dark:text-amber-200 capitalize leading-snug block">
                {characterization.replace(/_/g, ' ')}
              </span>
              {explanationText && (
                <p className="text-[10px] text-amber-900/80 dark:text-amber-300/80 mt-1 leading-relaxed">
                  {explanationText}
                </p>
              )}
            </div>
          )}

          {flaggedFactors.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {flaggedFactors.map((f) => (
                <span
                  key={f}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 text-[10px] font-medium leading-tight"
                >
                  <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ================================================================ */}
        {/* 3. EVIDENCE RELIABILITY / FALSE-ALARM CONCERN                    */}
        {/* ================================================================ */}
        <div className="space-y-2">
          {sectionLabel('bg-emerald-500', 'Evidence Reliability')}

          <div className="rounded-lg border border-slate-200/70 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-900/50 p-2.5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                False-Alarm Concern
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border shadow-2xs ${faTone}`}>
                {faConcern}
              </span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Detection Reliability
              </span>
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-200">
                {detectionReliability || '—'}
              </span>
            </div>

            {faReasons.length > 0 && (
              <div className="pt-1.5 border-t border-slate-100 dark:border-slate-700/60 space-y-1">
                <span className="text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-[0.16em] block">
                  {faConcern === 'LOW' ? 'Supporting evidence' : 'Concern drivers'}
                </span>
                {faReasons.map((r) => (
                  <div key={r} className="flex items-start gap-1.5 text-[10px] text-slate-600 dark:text-slate-300 leading-tight">
                    <span className="text-emerald-500 dark:text-emerald-400 font-bold flex-shrink-0">✓</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            )}

            <p className="text-[9px] text-slate-400 dark:text-slate-500 leading-relaxed pt-0.5">
              A HIGH false-alarm concern reflects weak or single-pass evidence — it is not a
              confirmed false alarm.
            </p>
          </div>
        </div>

        {/* ================================================================ */}
        {/* 4. INDUSTRIAL-CONTEXT EXPLANATION (only when classified)         */}
        {/* ================================================================ */}
        {isIndustrial && (
          <div className="space-y-2">
            {sectionLabel('bg-amber-500', 'Why Industrial-Context?')}

            <div className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 p-2.5 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-bold text-amber-800 dark:text-amber-300 uppercase tracking-wider">
                  Industrial-Context
                </span>
                <span className="text-[10px] font-bold text-amber-900 dark:text-amber-200 capitalize">
                  {clsLabel}
                </span>
              </div>

              {hasOsm && classification && (
                <div className="flex items-center justify-between gap-2 text-[10px] text-amber-900/80 dark:text-amber-300/80">
                  <span>Nearest mapped facility (OSM)</span>
                  <span className="font-mono font-bold">
                    {osmFacility.replace(/_/g, ' ')}
                    {classification.osm_distance_km != null && isFinite(classification.osm_distance_km)
                      ? ` · ${classification.osm_distance_km.toFixed(2)} km`
                      : ''}
                  </span>
                </div>
              )}

              {rationaleLines.length > 0 && (
                <div className="space-y-1 pt-1 border-t border-amber-200/50 dark:border-amber-900/50">
                  {rationaleLines.map((line) => (
                    <div key={line} className="flex items-start gap-1.5 text-[10px] text-amber-900/80 dark:text-amber-300/80 leading-tight">
                      <span className="text-amber-600 dark:text-amber-400 font-bold flex-shrink-0">✓</span>
                      <span>{line}</span>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-[9px] text-amber-800/70 dark:text-amber-400/70 leading-relaxed">
                Contextual classification based on proximity, persistence, thermal signature and
                land-use context — not a confirmed industrial fire.
              </p>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* 5. SATELLITE CONTEXT (compact)                                   */}
        {/* ================================================================ */}
        <div className="space-y-2">
          {sectionLabel('bg-emerald-500', 'Satellite Context')}

          <div className="rounded-lg border border-slate-200/70 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-900/50 p-2.5 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <span className="text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-[0.16em] block">
                Sentinel-2 Land-Use Context
              </span>
              {hasSatellite ? (
                <span className="text-[11px] font-bold text-slate-700 dark:text-slate-200 capitalize block truncate">
                  {satClass.replace(/_/g, ' ')}
                </span>
              ) : (
                <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 block">
                  Unavailable / Cloud-obscured
                </span>
              )}
            </div>
            {hasSatellite ? (
              <div className="text-right flex-shrink-0">
                <span className="text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-[0.16em] block">
                  Confidence
                </span>
                <span className="text-[11px] font-mono font-bold text-emerald-700 dark:text-emerald-400">
                  {Math.round(satConf * 100)}%
                </span>
              </div>
            ) : (
              <svg className="w-4 h-4 text-slate-400 dark:text-slate-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z" />
              </svg>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* 6. SUPPORTING VS LIMITING EVIDENCE                               */}
        {/* ================================================================ */}
        <div className="space-y-2.5">
          <div className="space-y-1.5">
            {sectionLabel('bg-emerald-500', 'Supporting Evidence')}
            {supporting.length === 0 ? (
              <p className="text-[10px] text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/70 rounded-lg px-2.5 py-2">
                No supporting evidence recorded for this event.
              </p>
            ) : (
              <div className="space-y-1">
                {supporting.map((item) => {
                  const open = expanded === `sup-${item.key}`;
                  return (
                    <div key={item.key} className="rounded-md border border-slate-200/70 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                      <button
                        type="button"
                        onClick={() => toggle(`sup-${item.key}`)}
                        className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-left hover:bg-slate-100/70 dark:hover:bg-slate-800/70 transition-colors"
                      >
                        <span className="flex items-center gap-1.5 text-[11px] font-medium text-slate-700 dark:text-slate-300">
                          <span className="text-emerald-500 dark:text-emerald-400 font-bold flex-shrink-0">✓</span>
                          {item.label}
                        </span>
                        {chevron(open)}
                      </button>
                      {open && (
                        <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed px-2.5 pb-2">
                          {item.why}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            {sectionLabel('bg-slate-400', 'Limiting Evidence')}
            {limiting.length === 0 ? (
              <p className="text-[10px] text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/70 rounded-lg px-2.5 py-2">
                No limiting factors recorded for this event.
              </p>
            ) : (
              <div className="space-y-1">
                {limiting.map((item) => {
                  const open = expanded === `lim-${item.key}`;
                  return (
                    <div key={item.key} className="rounded-md border border-slate-200/70 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
                      <button
                        type="button"
                        onClick={() => toggle(`lim-${item.key}`)}
                        className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-left hover:bg-slate-100/70 dark:hover:bg-slate-800/70 transition-colors"
                      >
                        <span className="flex items-center gap-1.5 text-[11px] font-medium text-slate-600 dark:text-slate-400">
                          <span className="text-slate-400 dark:text-slate-500 flex-shrink-0">○</span>
                          {item.label}
                        </span>
                        {chevron(open)}
                      </button>
                      {open && (
                        <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed px-2.5 pb-2">
                          {item.why}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}