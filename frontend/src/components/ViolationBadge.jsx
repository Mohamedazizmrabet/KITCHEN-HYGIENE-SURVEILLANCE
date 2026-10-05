/**
 * ViolationBadge — displays a single tracked person's compliance state.
 *
 * Props:
 *   personId     number    — track ID
 *   detectedPpe  string[]  — compliance PPE items present (e.g. ['mask'])
 *   missingPpe   string[]  — compliance PPE items absent (e.g. ['gloves'])
 *   isCompliant  boolean
 *   activeItems  Set<string> — which PPE items are being tracked
 *   allPpeItems  array     — full list of { key, label, icon, violation }
 */
export default function ViolationBadge({
  personId,
  detectedPpe = [],
  missingPpe = [],
  isCompliant,
  activeItems = new Set(),
  allPpeItems = [],
}) {
  // Filter to only items that are currently being tracked
  const trackedItems = allPpeItems.filter((p) => activeItems.has(p.key))

  return (
    <div className={`violation-badge ${isCompliant ? 'compliant' : ''}`}>
      <div className="violation-avatar">
        #{personId}
      </div>

      <div className="violation-body">
        <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
          <span className="violation-title">Person #{personId}</span>
          <span className={`status-pill ${isCompliant ? 'compliant' : 'violation'}`}>
            {isCompliant ? 'Compliant' : 'Violation'}
          </span>
        </div>

        {/* Per-item status rows */}
        {trackedItems.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {trackedItems.map((item) => {
              const hasItem = detectedPpe.includes(item.key)
              const isMissing = missingPpe.includes(item.violation)
              // If neither detected nor missing, we just show as unknown
              const status = hasItem ? 'ok' : isMissing ? 'missing' : 'unknown'

              return (
                <div key={item.key} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '4px 8px', borderRadius: 6,
                  background: status === 'ok'
                    ? 'rgba(34,197,94,0.08)'
                    : status === 'missing'
                      ? 'rgba(239,68,68,0.08)'
                      : 'rgba(100,100,100,0.06)',
                  border: `1px solid ${
                    status === 'ok'
                      ? 'rgba(34,197,94,0.2)'
                      : status === 'missing'
                        ? 'rgba(239,68,68,0.2)'
                        : 'rgba(100,100,100,0.12)'
                  }`,
                }}>
                  <span style={{ fontSize: '0.9rem' }}>{item.icon}</span>
                  <span style={{
                    flex: 1, fontSize: '0.75rem', fontWeight: 600,
                    color: status === 'ok'
                      ? 'var(--success)'
                      : status === 'missing'
                        ? 'var(--danger)'
                        : 'var(--text-muted)',
                  }}>
                    {item.label}
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>
                    {status === 'ok' ? '✅' : status === 'missing' ? '❌' : '—'}
                  </span>
                </div>
              )
            })}
          </div>
        ) : (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            No PPE items being tracked
          </div>
        )}
      </div>
    </div>
  )
}
