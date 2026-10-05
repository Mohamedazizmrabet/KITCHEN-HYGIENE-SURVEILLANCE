import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { laravelApi, inferenceApi } from '../api/axios'
import MetricCard from '../components/MetricCard'

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [sessions, setSessions] = useState([])
  const [violations, setViolations] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthRes, sessionsRes, violationsRes] = await Promise.allSettled([
          inferenceApi.get('/health'),
          laravelApi.get('/sessions'),
          laravelApi.get('/violations'),
        ])

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data)
        if (sessionsRes.status === 'fulfilled') setSessions(sessionsRes.value.data?.data || sessionsRes.value.data || [])
        if (violationsRes.status === 'fulfilled') setViolations(violationsRes.value.data?.data || violationsRes.value.data || [])
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const recentViolations = Array.isArray(violations) ? violations.slice(0, 5) : []

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Kitchen hygiene surveillance overview</p>
      </div>

      {/* Metric cards */}
      <div className="grid-metrics">
        <MetricCard
          value={health?.active_sessions?.length ?? 0}
          label="Active Sessions"
          accent="var(--accent)"
        />
        <MetricCard
          value={recentViolations.length}
          label="Recent Violations"
          accent="var(--danger)"
        />
        <MetricCard
          value={health?.active_model ?? '—'}
          label="Active Model"
          accent="var(--warning)"
        />
        <MetricCard
          value={health?.device?.toUpperCase() ?? '—'}
          label="Compute Device"
          accent="var(--success)"
        />
      </div>

      <div className="grid-2">
        {/* Service status */}
        <div className="card">
          <div className="card-header">
            <h3>Inference Service</h3>
            <span className={`status-pill ${health ? 'compliant' : 'violation'}`}>
              {health ? 'Online' : 'Offline'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'YOLO11 weights', ok: health?.yolo_loaded, note: health?.yolo_loaded ? 'Loaded' : 'Missing — place in models/' },
              { label: 'RT-DETR-L weights', ok: health?.rtdetr_loaded, note: health?.rtdetr_loaded ? 'Loaded' : 'Missing — place rtdetr-l.pt in models/' },
              { label: 'Device', ok: true, note: health?.device ?? '…' },
            ].map(({ label, ok, note }) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px',
                background: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <span style={{ fontSize: '0.875rem' }}>{label}</span>
                <span style={{ fontSize: '0.8rem', color: ok ? 'var(--success)' : 'var(--danger)' }}>
                  {note}
                </span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16 }}>
            <Link to="/monitoring" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
              Start Monitoring
            </Link>
          </div>
        </div>

        {/* Recent violations */}
        <div className="card">
          <div className="card-header">
            <h3>Recent Violations</h3>
            <Link to="/violations" style={{ color: 'var(--accent)', fontSize: '0.8rem', textDecoration: 'none' }}>
              View all
            </Link>
          </div>

          {loading ? (
            <div className="empty-state"><div className="spinner" /></div>
          ) : recentViolations.length === 0 ? (
            <div className="empty-state">
              <p>No violations recorded</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Type</th>
                  <th>Confidence</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentViolations.map((v) => (
                  <tr key={v.id}>
                    <td>#{v.person_id}</td>
                    <td style={{ color: 'var(--danger)' }}>{v.violation_type}</td>
                    <td className="font-mono">{(v.confidence * 100).toFixed(0)}%</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                      {new Date(v.created_at || v.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
