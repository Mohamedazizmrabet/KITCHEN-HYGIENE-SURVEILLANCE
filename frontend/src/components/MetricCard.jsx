/**
 * MetricCard — displays a single KPI with icon, value, and label.
 *
 * Props:
 *   icon    string  — emoji or icon character
 *   value   string|number
 *   label   string
 *   accent  string  — optional CSS colour override for top border
 *   unit    string  — optional unit suffix (e.g. "ms", "fps")
 */
export default function MetricCard({ value, label, accent, unit = '' }) {
  return (
    <div
      className="metric-card"
      style={{ '--card-accent': accent || 'var(--accent)' }}
    >
      <style>{`
        .metric-card::before { background: var(--card-accent, var(--accent)); }
      `}</style>

      <div className="metric-value">
        {value}
        {unit && (
          <span style={{ fontSize: '1rem', fontWeight: 500, color: 'var(--text-secondary)', marginLeft: 4 }}>
            {unit}
          </span>
        )}
      </div>

      <div className="metric-label">{label}</div>
    </div>
  )
}
