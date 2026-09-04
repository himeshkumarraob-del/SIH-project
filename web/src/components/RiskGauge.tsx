interface RiskGaugeProps {
  score: number;
  level: string;
  size?: number;
}

export default function RiskGauge({ score, level, size = 140 }: RiskGaugeProps) {
  const radius = (size - 24) / 2;
  const circumference = Math.PI * radius; // semi-circle
  const clampedScore = Math.min(Math.max(score, 0), 100);
  const progress = clampedScore / 100;
  const offset = circumference - progress * circumference;

  let color = '#16a34a';
  let gradientId = 'risk-low-grad';
  let badgeBg = 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
  let displayLevel = 'LOW';

  if (clampedScore >= 60 || level === 'HIGH') {
    color = '#dc2626';
    gradientId = 'risk-high-grad';
    badgeBg = 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800';
    displayLevel = 'HIGH';
  } else if (clampedScore >= 30 || level === 'MEDIUM') {
    color = '#d97706';
    gradientId = 'risk-med-grad';
    badgeBg = 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800';
    displayLevel = 'MEDIUM';
  }

  const cx = size / 2;
  const cy = size * 0.58;

  return (
    <div className="flex flex-col items-center select-none">
      <div className="relative">
        <svg width={size} height={size * 0.62} viewBox={`0 0 ${size} ${size * 0.62}`} className="overflow-visible">
          <defs>
            <linearGradient id="risk-low-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="100%" stopColor="#16a34a" />
            </linearGradient>
            <linearGradient id="risk-med-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#fbbf24" />
              <stop offset="100%" stopColor="#d97706" />
            </linearGradient>
            <linearGradient id="risk-high-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f87171" />
              <stop offset="100%" stopColor="#dc2626" />
            </linearGradient>
            <filter id="gauge-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor={color} floodOpacity="0.25" />
            </filter>
          </defs>

          {/* Background Track Arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            className="stroke-slate-200 dark:stroke-slate-700 transition-colors"
            strokeWidth={10}
            strokeLinecap="round"
          />

          {/* Inner Accent Track */}
          <path
            d={`M ${cx - radius + 8} ${cy} A ${radius - 8} ${radius - 8} 0 0 1 ${cx + radius - 8} ${cy}`}
            fill="none"
            className="stroke-slate-100 dark:stroke-slate-800/80 transition-colors"
            strokeWidth={2}
            strokeDasharray="2,4"
          />

          {/* Progress Arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            filter="url(#gauge-glow)"
            style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.3s ease' }}
          />

          {/* Tick marks */}
          {[0, 25, 50, 75, 100].map((tick) => {
            const angle = Math.PI - (tick / 100) * Math.PI;
            const rOuter = radius + 8;
            const rInner = radius + 4;
            const x1 = cx + rOuter * Math.cos(angle);
            const y1 = cy - rOuter * Math.sin(angle);
            const x2 = cx + rInner * Math.cos(angle);
            const y2 = cy - rInner * Math.sin(angle);
            return (
              <line
                key={tick}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                className="stroke-slate-300 dark:stroke-slate-600 transition-colors"
                strokeWidth={1.5}
                strokeLinecap="round"
              />
            );
          })}

          {/* Score Text */}
          <text
            x={cx}
            y={cy - 8}
            textAnchor="middle"
            className="font-bold tracking-tight fill-slate-900 dark:fill-slate-100"
            style={{ fontSize: size * 0.24, fontWeight: 800, fontFamily: 'ui-monospace, monospace' }}
          >
            {Math.round(clampedScore)}
          </text>
          <text
            x={cx}
            y={cy + 6}
            textAnchor="middle"
            className="font-medium fill-slate-400 dark:fill-slate-500"
            style={{ fontSize: size * 0.08, letterSpacing: '0.05em' }}
          >
            INDEX SCORE / 100
          </text>
        </svg>
      </div>

      {/* Level Badge */}
      <div className={`mt-0.5 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border shadow-xs ${badgeBg}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
        <span>{displayLevel} RISK</span>
      </div>
    </div>
  );
}


