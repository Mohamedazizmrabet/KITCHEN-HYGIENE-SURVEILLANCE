import { useEffect, useState, useRef } from 'react'
import { laravelApi, inferenceApi } from '../api/axios'
import SnapshotCard from '../components/SnapshotCard'

const INFERENCE_BASE = import.meta.env.VITE_INFERENCE_URL || 'http://localhost:8001'

const VIOLATION_TYPES = [
  'no_gloves', 'no_hairnet', 'no_mask', 'incorrect_mask', 'all'
]

export default function ViolationsHistory() {
  const [violations, setViolations] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const PER_PAGE = 20

  const [viewTab, setViewTab] = useState('logs') // 'logs' | 'snapshots'
  
  // States for live snapshots
  const [snapshots, setSnapshots] = useState([])
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const snapshotsInterval = useRef(null)

  useEffect(() => {
    // Fetch DB logs
    const fetchViolations = async () => {
      setLoading(true)
      try {
        const res = await laravelApi.get('/violations')
        const data = res.data?.data || res.data || []
        setViolations(Array.isArray(data) ? data : [])
      } catch (_) {
        setViolations([])
      } finally {
        setLoading(false)
      }
    }
    fetchViolations()
    const interval = setInterval(fetchViolations, 10000)
    
    return () => clearInterval(interval)
  }, [])

  // Fetch live snapshots for the 'snapshots' tab
  useEffect(() => {
    if (viewTab === 'snapshots') {
      const fetchLiveSnapshots = async () => {
        try {
          const health = await inferenceApi.get('/health')
          const sessions = health.data.active_sessions
          if (sessions && sessions.length > 0) {
            const sid = sessions[0]
            const res = await inferenceApi.get(`/session/${sid}/snapshots/full`)
            setSnapshots(res.data.snapshots || [])
          } else {
            setSnapshots([])
          }
        } catch (_) {}
      }
      fetchLiveSnapshots()
      snapshotsInterval.current = setInterval(fetchLiveSnapshots, 2000)
    } else {
      clearInterval(snapshotsInterval.current)
    }
    return () => clearInterval(snapshotsInterval.current)
  }, [viewTab])

  const downloadSnapshot = (snapshotId) => {
    const a = document.createElement('a')
    a.href = `${INFERENCE_BASE}/snapshot/${snapshotId}/download`
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const downloadAllSnapshots = () => {
    snapshots.forEach((s, i) => {
      setTimeout(() => downloadSnapshot(s.snapshot_id), i * 300)
    })
  }

  // Group snapshots by person ID
  const groupedSnapshots = snapshots.reduce((acc, snap) => {
    if (!acc[snap.track_id]) acc[snap.track_id] = []
    acc[snap.track_id].push(snap)
    return acc
  }, {})

  const filtered = filter === 'all'
    ? violations
    : violations.filter((v) => v.violation_type === filter)

  const totalPages = Math.ceil(filtered.length / PER_PAGE)
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const violationCounts = VIOLATION_TYPES.reduce((acc, type) => {
    acc[type] = violations.filter((v) => v.violation_type === type).length
    return acc
  }, {})

  return (
    <div>
      {/* Full-screen Snapshot Modal */}
      {selectedSnapshot && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.85)', zIndex: 9999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: 24
        }} onClick={() => setSelectedSnapshot(null)}>
          <div style={{ maxWidth: '90%', maxHeight: '90%', position: 'relative' }} onClick={(e) => e.stopPropagation()}>
            <img 
              src={`data:image/jpeg;base64,${selectedSnapshot.image_b64}`} 
              alt="Snapshot" 
              style={{ maxWidth: '100%', maxHeight: '80vh', objectFit: 'contain', border: '2px solid var(--danger)', borderRadius: 8 }} 
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
              <div style={{ color: '#fff', fontSize: '1.2rem', fontWeight: 600 }}>
                Person #{selectedSnapshot.track_id} — {new Date(selectedSnapshot.timestamp).toLocaleString()}
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button className="btn btn-primary" onClick={() => downloadSnapshot(selectedSnapshot.snapshot_id)}>
                  Download
                </button>
                <button className="btn btn-ghost" style={{ color: '#fff' }} onClick={() => setSelectedSnapshot(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <h1>Violations History</h1>
        <p>All recorded PPE compliance violations & live snapshots</p>
      </div>

      {/* Main Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {[
          { key: 'logs', label: 'Database Logs' },
          { key: 'snapshots', label: 'Live Session Snapshots' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setViewTab(key)}
            style={{
              padding: '10px 24px',
              background: 'none',
              border: 'none',
              borderBottom: viewTab === key ? '2px solid var(--accent)' : '2px solid transparent',
              color: viewTab === key ? 'var(--accent)' : 'var(--text-secondary)',
              fontWeight: viewTab === key ? 700 : 500,
              fontSize: '0.9rem',
              cursor: 'pointer',
              transition: 'all 0.2s',
              marginBottom: -1,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {viewTab === 'logs' ? (
        <>
          {/* Summary cards */}
      <div className="grid-metrics" style={{ marginBottom: 24 }}>
        {VIOLATION_TYPES.filter((t) => t !== 'all').map((type) => (
          <div
            key={type}
            className="metric-card"
            style={{ cursor: 'pointer', borderColor: filter === type ? 'var(--danger)' : undefined }}
            onClick={() => { setFilter(type); setPage(1) }}
          >
            <div className="metric-value" style={{ color: 'var(--danger)' }}>
              {violationCounts[type] || 0}
            </div>
            <div className="metric-label">{type.replace(/_/g, ' ')}</div>
          </div>
        ))}
      </div>

      <div className="card">
        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          {['all', ...VIOLATION_TYPES.filter((t) => t !== 'all')].map((type) => (
            <button
              key={type}
              onClick={() => { setFilter(type); setPage(1) }}
              className="btn btn-ghost"
              style={{
                padding: '6px 14px',
                fontSize: '0.8rem',
                borderColor: filter === type ? 'var(--accent)' : undefined,
                color: filter === type ? 'var(--accent)' : undefined,
              }}
            >
              {type === 'all' ? `All (${violations.length})` : type.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        {/* Table */}
        {loading ? (
          <div className="empty-state"><div className="spinner" /></div>
        ) : paginated.length === 0 ? (
          <div className="empty-state">
            <p>No violations found</p>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Session</th>
                  <th>Person</th>
                  <th>Violation</th>
                  <th>Confidence</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((v) => (
                  <tr key={v.id}>
                    <td className="font-mono text-muted" style={{ fontSize: '0.75rem' }}>
                      #{v.id}
                    </td>
                    <td className="font-mono text-muted" style={{ fontSize: '0.75rem' }}>
                      {v.session_id ? String(v.session_id).slice(0, 8) + '…' : '—'}
                    </td>
                    <td>#{v.person_id}</td>
                    <td>
                      <span style={{
                        background: 'var(--danger-bg)',
                        color: 'var(--danger)',
                        padding: '3px 10px',
                        borderRadius: 4,
                        fontSize: '0.8rem',
                        fontWeight: 600,
                      }}>
                        {v.violation_type}
                      </span>
                    </td>
                    <td className="font-mono">
                      {v.confidence ? `${(v.confidence * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                      {v.timestamp
                        ? new Date(v.timestamp).toLocaleString()
                        : new Date(v.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 20 }}>
                <button
                  className="btn btn-ghost"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                  style={{ padding: '6px 14px' }}
                >
                  Prev
                </button>
                <span style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  {page} / {totalPages}
                </span>
                <button
                  className="btn btn-ghost"
                  disabled={page === totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  style={{ padding: '6px 14px' }}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
      </>
      ) : (
        /* Snapshots Tab */
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 style={{ margin: 0 }}>Active Session Snapshots</h3>
            {snapshots.length > 0 && (
              <button className="btn btn-ghost" onClick={downloadAllSnapshots}>
                Download All
              </button>
            )}
          </div>
          
          {snapshots.length === 0 ? (
            <div className="empty-state">
              <p>No snapshots found for the current active session.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
              {Object.entries(groupedSnapshots)
                .sort(([idA], [idB]) => Number(idA) - Number(idB))
                .map(([personId, snaps]) => (
                <div key={personId} style={{ 
                  background: 'rgba(0,0,0,0.1)', 
                  padding: 12, 
                  borderRadius: 8,
                  border: '1px solid var(--border)' 
                }}>
                  <h4 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: 'var(--accent)' }}>
                    👤 Person #{personId} <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 6 }}>({snaps.length} violations)</span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {[...snaps].reverse().map((snap) => (
                      <SnapshotCard
                        key={snap.snapshot_id}
                        snapshot={snap}
                        onDownload={downloadSnapshot}
                        onClickImage={() => setSelectedSnapshot(snap)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
