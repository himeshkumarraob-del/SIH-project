interface RiskGaugeProps {
  score: number;
  level: string;
  size?: number;
}

export default function RiskGauge({ score, level, size = 120 }: RiskGaugeProps) {
  const radius = (size - 16) / 2;
  const circumference = Math.PI * radius; // half circle
  const progress = Math.min(Math.max(score, 0), 100) / 100;

  let color = '#16a34a';
  let bgColor = '#dcfce7';
  let label = 'LOW';
  if (score >= 60) {
    color = '#dc2626';
    bgColor = '#fef2f2';
    label = 'HIGH';
  } else if (score >= 30) {
    color = '#d97706';
    bgColor = '#fffbeb';
    label = 'MEDIUM';
  }

  const offset = circumference - progress * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
        {/* Background arc */}
        <path
          d={`M ${size / 2 - radius} ${size * 0.6} A ${radius} ${radius} 0 0 1 ${size / 2 + radius} ${size * 0.6}`}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Progress arc */}
        <path
          d={`M ${size / 2 - radius} ${size * 0.6} A ${radius} ${radius} 0 0 1 ${size / 2 + radius} ${size * 0.6}`}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.3s ease' }}
        />
        {/* Score text */}
        <text
          x={size / 2}
          y={size * 0.5}
          textAnchor="middle"
          className="text-2xl font-bold"
          fill={color}
          style={{ fontSize: size * 0.22, fontWeight: 700 }}
        >
          {Math.round(score)}
        </text>
        <text
          x={size / 2}
          y={size * 0.62}
          textAnchor="middle"
          fill="#94a3b8"
          style={{ fontSize: size * 0.1, fontWeight: 500 }}
        >
          / 100
        </text>
      </svg>
      <div
        className="mt-0.5 px-2 py-0.5 rounded text-xs font-semibold"
        style={{ color, backgroundColor: bgColor, border: `1px solid ${color}20` }}
      >
        {label} RISK
      </div>
    </div>
  );
}
