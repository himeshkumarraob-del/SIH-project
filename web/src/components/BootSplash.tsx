import { useEffect, useRef, useState } from 'react';
import brandLogo from '../assets/logo-transparent.png';
import { INDIA_OUTLINE, INDIA_INTERIOR, ix, iy } from '../data/indiaOutline';
import './BootSplash.css';

/* ---------------------------------------------------------------------------
   ThermalWatch boot splash — “India being observed from space”.
   A choreographed, cinematic system-initialization sequence:
   near-black → atmosphere → real India geography → graticule → satellite
   scan → thermal anomalies → FLAREX identity → THERMALWATCH → progress →
   SYSTEM READY → dissolve into the application.

   No chrome, no interactivity — it exists only while the app initializes.

   The India geometry is real (GADM-derived country boundary + coastline,
   full J&K/Ladakh, all Northeastern states, island territories). Thermal
   points sit at actual fire-prone / industrial locations and are struck by
   the scanning beam in geographic order (per-site CSS delay mirrors the
   beam's travel), so each detection reads as: SATELLITE → DETECTION →
   ANALYSIS.
   --------------------------------------------------------------------------- */

const STATUSES = [
  'INITIALIZING THERMAL INTELLIGENCE',
  'CONNECTING SATELLITE DATA',
  'LOADING THERMAL EVENTS',
  'ANALYZING THERMAL ANOMALIES',
  'CALCULATING RISK INTELLIGENCE',
  'PREPARING RESPONSE INTELLIGENCE',
  'SYSTEM READY',
] as const;

/* Graticule — every 4°, with sparse labels (classic India framing) */
const LONS = [68, 72, 76, 80, 84, 88, 92, 96];
const LATS = [8, 12, 16, 20, 24, 28, 32];
const LON_LABELS = [70, 80, 90];
const LAT_LABELS = [10, 20, 30];

/* Thermal anomalies at real, plausible geospatial positions (°E, °N, heat).
   heat: 1 amber · 2 orange · 3 red — intensity tiers of a thermal signature. */
const THERMAL_SITES: {
  lon: number;
  lat: number;
  heat: 1 | 2 | 3;
  ring?: boolean;
}[] = [
  { lon: 79.1, lat: 29.9, heat: 2 }, // Uttarakhand foothills — forest fire zone
  { lon: 75.4, lat: 27.1, heat: 1 }, // Rajasthan / Aravalli
  { lon: 71.1, lat: 22.3, heat: 1 }, // Saurashtra (Gujarat)
  { lon: 78.4, lat: 22.9, heat: 1 }, // Satpura (Madhya Pradesh)
  { lon: 80.0, lat: 20.2, heat: 3, ring: true }, // Gadchiroli (Maharashtra)
  { lon: 81.6, lat: 19.2, heat: 3, ring: true }, // Bastar (Chhattisgarh)
  { lon: 86.2, lat: 23.9, heat: 2 }, // Jharkhand coal belt
  { lon: 84.7, lat: 19.9, heat: 1 }, // Ganjam (Odisha)
  { lon: 75.3, lat: 13.9, heat: 2 }, // Western Ghats (Karnataka)
  { lon: 77.0, lat: 11.0, heat: 1 }, // Nilgiri / Tamil Nadu
  { lon: 92.7, lat: 26.4, heat: 2 }, // Assam valley
  { lon: 92.8, lat: 23.3, heat: 3, ring: true }, // Mizoram jhum belt
];

const HEAT_COLOR: Record<number, string> = {
  1: '#fbbf24', // amber
  2: '#fb923c', // orange
  3: '#ef4444', // red
};

/* Choreography timing (ms) — trimmed by `reduced` for prefers-reduced-motion */
const TIMING = {
  statusStart: 2150,
  statusStep: 430,
  fillDuration: 2500,
  readyHold: 650,
  fadeDuration: 800,
  reducedScale: 0.55,
};

/* Satellite scan pacing — one full left→right pass over the geography.
   The beam is 24vw wide (hairline on its leading edge) and travels 124vw
   total; the flare delay below mirrors that exactly so each detection
   spike lands ~0.2 s after the hairline crosses the site. */
const SCAN_START = 0.8; // s — matches CSS scan delay
const SCAN_PERIOD = 14; // s — matches CSS scan duration
const SCAN_BEAM_VW = 24; // vw — matches CSS .boot-scan width
const SCAN_TRAVEL_VW = 100 + SCAN_BEAM_VW; // vw swept per cycle
const FLARE_LAG = 0.2; // s — detection→analysis latency after the beam

interface BootSplashProps {
  onFinish: () => void;
}

export default function BootSplash({ onFinish }: BootSplashProps) {
  const [progress, setProgress] = useState(0);
  const [statusIdx, setStatusIdx] = useState(-1);
  const [statusLeaving, setStatusLeaving] = useState(false);
  const [exiting, setExiting] = useState(false);
  const [reduced, setReduced] = useState(false);

  const statusRef = useRef(-1);
  const leavingRef = useRef(false);
  const exitingRef = useRef(false);
  const doneRef = useRef(false);
  const swapTimer = useRef<number | null>(null);
  const rafRef = useRef(0);

  /* Detect / react to reduced-motion preference */
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  /* Timeline driver: progress, status sequence, exit, finish */
  useEffect(() => {
    const scale = reduced ? TIMING.reducedScale : 1;
    const start = TIMING.statusStart * scale;
    const step = TIMING.statusStep * scale;
    const fillDur = TIMING.fillDuration * scale;
    const fadeStart = start + (STATUSES.length - 1) * step + TIMING.readyHold * scale;
    const total = fadeStart + TIMING.fadeDuration;

    let t0: number | null = null;

    const swapStatus = (target: number) => {
      if (target <= statusRef.current) return;
      if (leavingRef.current) return;
      if (reduced) {
        statusRef.current = target;
        setStatusIdx(target);
        return;
      }
      leavingRef.current = true;
      setStatusLeaving(true);
      swapTimer.current = window.setTimeout(() => {
        statusRef.current = target;
        leavingRef.current = false;
        setStatusLeaving(false);
        setStatusIdx(target);
      }, 130);
    };

    const tick = (now: number) => {
      if (t0 === null) t0 = now;
      const t = now - t0;

      const p = Math.min(1, Math.max(0, (t - 2000 * scale) / fillDur));
      setProgress(p);

      if (t >= start) {
        const target = Math.min(
          Math.floor((t - start) / step),
          STATUSES.length - 1,
        );
        if (target !== statusRef.current && !leavingRef.current) {
          swapStatus(target);
        }
      }

      if (t >= fadeStart && !exitingRef.current) {
        exitingRef.current = true;
        setExiting(true);
      }

      if (t >= total) {
        if (!doneRef.current) {
          doneRef.current = true;
          onFinish();
        }
        return;
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(rafRef.current);
      if (swapTimer.current !== null) window.clearTimeout(swapTimer.current);
    };
  }, [reduced, onFinish]);

  return (
    <div
      className={`boot ${exiting ? 'boot--exiting' : ''} ${reduced ? 'boot--reduced' : ''}`}
      role="status"
      aria-label="ThermalWatch initializing"
    >
      {/* Layer 1 — deep navy/black atmosphere */}
      <div className="boot-layer boot-bg" aria-hidden="true" />

      {/* Layer 2 — faint satellite/Earth texture + atmospheric haze */}
      <div className="boot-layer boot-earth" aria-hidden="true" />
      <div className="boot-layer boot-noise" aria-hidden="true" />
      <div className="boot-layer boot-cloud" aria-hidden="true" />

      {/* Layer 3 — real India geography, framed by the graticule */}
      <svg
        className="boot-layer boot-map"
        viewBox="0 0 1020 1000"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <g className="boot-grid">
          {LONS.map((lon) => (
            <line key={`v${lon}`} x1={ix(lon)} y1="0" x2={ix(lon)} y2="1000" />
          ))}
          {LATS.map((lat) => (
            <line key={`h${lat}`} x1="0" y1={iy(lat)} x2="1020" y2={iy(lat)} />
          ))}
        </g>
        <g className="boot-grid-labels">
          {LON_LABELS.map((lon) => (
            <text key={`lv${lon}`} x={ix(lon)} y="992" textAnchor="middle">
              {lon}°E
            </text>
          ))}
          {LAT_LABELS.map((lat) => (
            <text key={`lh${lat}`} x="6" y={iy(lat) + 4} textAnchor="start">
              {lat}°N
            </text>
          ))}
        </g>

        {/* Country outline + coastline (mainland & island territories) */}
        <g className="boot-geo">
          <path className="boot-geo-fill" d={INDIA_OUTLINE} />
          <path className="boot-geo-line" d={INDIA_OUTLINE} />
          <path className="boot-geo-inner" d={INDIA_INTERIOR} />
        </g>

        {/* Thermal anomalies + detection rings (struck by the scan in order) */}
        <g className="boot-thermal">
          {THERMAL_SITES.map((site, i) => {
            const x = ix(site.lon);
            const color = HEAT_COLOR[site.heat];
            const frac = x / 1020;
            const delay =
              SCAN_START + (frac * SCAN_TRAVEL_VW * SCAN_PERIOD) / 100 + FLARE_LAG;
            const fade = ((i % 3) + 1) * 0.14; // natural stagger of emergence
            return (
              <g key={`site${i}`} style={{ '--fade': fade } as React.CSSProperties}>
                {site.ring && (
                  <circle
                    className="tp-ring"
                    cx={x}
                    cy={iy(site.lat)}
                    r="8"
                    style={{ '--t': `${delay}s` } as React.CSSProperties}
                  />
                )}
                <circle
                  className="tp-halo"
                  cx={x}
                  cy={iy(site.lat)}
                  r="6.5"
                  fill={color}
                  style={{ '--t': `${delay}s`, '--c': color } as React.CSSProperties}
                />
                <circle
                  className="tp-core"
                  cx={x}
                  cy={iy(site.lat)}
                  r="2"
                  fill={color}
                  style={{ '--t': `${delay}s`, '--c': color } as React.CSSProperties}
                />
              </g>
            );
          })}
        </g>
      </svg>

      {/* Layer 4 — one elegant satellite scanning beam */}
      <div className="boot-layer boot-scan" aria-hidden="true" />

      {/* Layer 5 — focal vignette so the identity always dominates */}
      <div className="boot-layer boot-focus" aria-hidden="true" />

      {/* Layer 6 — centerpiece identity */}
      <div className="boot-center">
        <div className="boot-mark">
          <span className="boot-aura" aria-hidden="true" />
          <img
            src={brandLogo}
            alt="FLAREX"
            draggable={false}
            className="boot-logo"
          />
        </div>

        <div className="boot-name">THERMALWATCH</div>
        <div className="boot-tag">AI FIRE INTELLIGENCE</div>

        <div className="boot-progress">
          <div className="boot-progress-track">
            <div
              className="boot-progress-fill"
              style={{ width: `${Math.round(progress * 1000) / 10}%` }}
            >
              <span className="boot-progress-tip" aria-hidden="true" />
            </div>
          </div>
        </div>

        <div
          className={`boot-status ${statusIdx >= 0 ? 'boot-status--on' : ''}`}
          aria-live="polite"
        >
          {statusIdx >= 0 && (
            <span
              key={statusIdx}
              className={`boot-status-text ${
                statusLeaving
                  ? 'boot-status-text--leave'
                  : 'boot-status-text--enter'
              }`}
            >
              {STATUSES[statusIdx]}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}