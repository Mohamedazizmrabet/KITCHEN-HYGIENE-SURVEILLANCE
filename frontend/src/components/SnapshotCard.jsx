/**
 * SnapshotCard.jsx
 * Displays a single violation snapshot with thumbnail, metadata, reason badges, and download button.
 */

// Map raw class names to human-readable reasons
const VIOLATION_LABELS = {
  no_mask:    { label: 'Missing Mask',    icon: '😷', color: '#ef4444' },
  no_gloves:  { label: 'Missing Gloves',  icon: '🧤', color: '#f97316' },
  no_hairnet: { label: 'Bare Hair',       icon: '👒', color: '#a855f7' },
}

function ViolationReason({ violation }) {
  const info = VIOLATION_LABELS[violation] || { label: violation, icon: '⚠️', color: '#ef4444' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: `${info.color}1a`,
      color: info.color,
      fontSize: '0.72rem',
      fontWeight: 700,
      padding: '3px 10px',
      borderRadius: 12,
      border: `1px solid ${info.color}44`,
    }}>
      {info.icon} {info.label}
    </span>
  )
}

export default function SnapshotCard({ snapshot, onDownload, onClickImage }) {
  const { snapshot_id, track_id, timestamp, violations, image_b64 } = snapshot

  const formatted = new Date(timestamp).toLocaleString()

  return (
    <div style={{
      background: 'var(--bg-elevated)',
      border: '1px solid rgba(239,68,68,0.25)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Thumbnail */}
      {image_b64 && (
        <div 
          style={{ position: 'relative', background: '#000', cursor: onClickImage ? 'pointer' : 'default' }}
          onClick={onClickImage}
        >
          <img
            src={`data:image/jpeg;base64,${image_b64}`}
            alt={`Violation Person #${track_id}`}
            style={{ width: '100%', display: 'block', maxHeight: 180, objectFit: 'cover' }}
          />
          <span style={{
            position: 'absolute', top: 6, left: 6,
            background: 'var(--danger)', color: '#fff',
            fontSize: '0.65rem', fontWeight: 700,
            padding: '2px 8px', borderRadius: 20, letterSpacing: '0.05em',
          }}>
            VIOLATION
          </span>
        </div>
      )}

      {/* Info */}
      <div style={{ padding: '10px 12px', flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: '0.85rem' }}>
            Person #{track_id}
          </span>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            {formatted}
          </span>
        </div>

        {/* Violation reasons */}
        {violations && violations.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 10 }}>
            {violations.map((v) => (
              <ViolationReason key={v} violation={v} />
            ))}
          </div>
        )}

        {/* Download */}
        <button
          className="btn btn-ghost"
          style={{ width: '100%', fontSize: '0.75rem', padding: '6px 0' }}
          onClick={() => onDownload(snapshot_id)}
        >
          Download
        </button>
      </div>
    </div>
  )
}
