import { useState, useEffect, useRef } from 'react'
import { inferenceApi, laravelApi, streamUrl, benchmarkStreamUrl } from '../api/axios'
import StreamPlayer from '../components/StreamPlayer'
import MetricCard from '../components/MetricCard'
import ViolationBadge from '../components/ViolationBadge'
import SnapshotCard from '../components/SnapshotCard'

const MODEL_OPTIONS = ['YOLO', 'RT']

const INFERENCE_BASE = import.meta.env.VITE_INFERENCE_URL || 'http://localhost:8001'

// Available PPE items. key = compliance class, violation = violation class
const ALL_PPE_ITEMS = [
  { key: 'mask',    label: 'Mask',    violation: 'no_mask',    icon: '😷' },
  { key: 'gloves',  label: 'Gloves',  violation: 'no_gloves',  icon: '🧤' },
  { key: 'hairnet', label: 'Hairnet', violation: 'no_hairnet', icon: '👒' },
]

export default function LiveMonitoring() {
  const [sessionId, setSessionId] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isBenchmark, setIsBenchmark] = useState(false)
  const [metrics, setMetrics] = useState(null)
  const [source, setSource] = useState('0')
  const [selectedModel, setSelectedModel] = useState('YOLO')
  const [trackStates, setTrackStates] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('tracks') // 'tracks' | 'snapshots'
  const [selectedSnapshot, setSelectedSnapshot] = useState(null) // For full-screen modal

  // PPE toggle state — which items are being tracked
  const [activeItems, setActiveItems] = useState(
    () => new Set(ALL_PPE_ITEMS.map((p) => p.key))
  )

  const metricsInterval = useRef(null)
  const tracksInterval = useRef(null)
  const snapshotsInterval = useRef(null)

  // On mount, load initial PPE config and check for active sessions to prevent reset
  useEffect(() => {
    inferenceApi.get('/config/ppe').then((res) => {
      setActiveItems(new Set(res.data.active_compliance))
    }).catch(() => {})

    inferenceApi.get('/health').then((res) => {
      const activeSessions = res.data.active_sessions
      if (activeSessions && activeSessions.length > 0) {
        setSessionId(activeSessions[0])
        setIsRunning(true)
        if (res.data.active_model) {
          setSelectedModel(res.data.active_model)
        }
      }
    }).catch(() => {})
  }, [])

  // When activeItems changes, push to backend
  const updatePpeConfig = async (newActiveItems) => {
    const compliance = [...newActiveItems]
    const violations = ALL_PPE_ITEMS
      .filter((p) => newActiveItems.has(p.key))
      .map((p) => p.violation)
    try {
      await inferenceApi.post('/config/ppe', { compliance, violations })
    } catch (_) {}
  }

  const toggleItem = (itemKey) => {
    setActiveItems((prev) => {
      const next = new Set(prev)
      if (next.has(itemKey)) {
        next.delete(itemKey)
      } else {
        next.add(itemKey)
      }
      updatePpeConfig(next)
      return next
    })
  }

  // Poll metrics while session is active
  useEffect(() => {
    if (isRunning) {
      metricsInterval.current = setInterval(async () => {
        try {
          const res = await inferenceApi.get('/metrics')
          setMetrics(res.data)
        } catch (_) {}
      }, 1500)
    } else {
      clearInterval(metricsInterval.current)
    }
    return () => clearInterval(metricsInterval.current)
  }, [isRunning])

  // Poll track states
  useEffect(() => {
    if (isRunning && sessionId && !isBenchmark) {
      tracksInterval.current = setInterval(async () => {
        try {
          const res = await inferenceApi.get(`/session/${sessionId}/tracks`)
          setTrackStates(res.data.tracks || [])
        } catch (_) {}
      }, 1000)
    } else {
      clearInterval(tracksInterval.current)
      if (!isRunning) setTrackStates([])
    }
    return () => clearInterval(tracksInterval.current)
  }, [isRunning, sessionId, isBenchmark])

  // Poll violation snapshots (with image data)
  useEffect(() => {
    if (isRunning && sessionId && !isBenchmark) {
      snapshotsInterval.current = setInterval(async () => {
        try {
          const res = await inferenceApi.get(`/session/${sessionId}/snapshots/full`)
          setSnapshots(res.data.snapshots || [])
        } catch (_) {}
      }, 2000)
    } else {
      clearInterval(snapshotsInterval.current)
      if (!isRunning) setSnapshots([])
    }
    return () => clearInterval(snapshotsInterval.current)
  }, [isRunning, sessionId, isBenchmark])

  const startSession = async () => {
    setError('')
    try {
      if (selectedModel === 'BOTH') {
        await inferenceApi.post('/benchmark/start', { source })
        setIsBenchmark(true)
        setIsRunning(true)
        await laravelApi.post('/sessions', { source, model_used: 'BOTH', status: 'active' }).catch(() => {})
      } else {
        await inferenceApi.post('/model/select', { model: selectedModel })
        const res = await inferenceApi.post('/session/start', { source, model: selectedModel })
        setSessionId(res.data.session_id)
        setIsBenchmark(false)
        setIsRunning(true)
        await laravelApi.post('/sessions', { source, model_used: selectedModel, status: 'active' }).catch(() => {})
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const stopSession = async () => {
    try {
      if (isBenchmark) {
        await inferenceApi.post('/benchmark/stop')
      } else if (sessionId) {
        await inferenceApi.post('/session/stop', { session_id: sessionId })
      }
    } catch (_) {}
    setIsRunning(false)
    setSessionId(null)
    setIsBenchmark(false)
    setMetrics(null)
  }

  // Download a single snapshot
  const downloadSnapshot = (snapshotId) => {
    const a = document.createElement('a')
    a.href = `${INFERENCE_BASE}/snapshot/${snapshotId}/download`
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // Download all snapshots
  const downloadAll = () => {
    snapshots.forEach((s, i) => {
      setTimeout(() => downloadSnapshot(s.snapshot_id), i * 300)
    })
  }

  const sessionMetrics = metrics?.sessions?.[sessionId] || null
  const benchmarkMetrics = metrics?.benchmark || null

  const streamSrc = isRunning
    ? (isBenchmark ? benchmarkStreamUrl() : streamUrl(sessionId))
    : null

  const violationCount = snapshots.length

  // Group snapshots by person ID
  const groupedSnapshots = snapshots.reduce((acc, snap) => {
    if (!acc[snap.track_id]) acc[snap.track_id] = []
    acc[snap.track_id].push(snap)
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
        <h1>Live Monitoring</h1>
        <p>Real-time PPE compliance detection with person tracking</p>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>

          {/* Video source */}
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 300px' }}>
            <label className="form-label">Video Source</label>
            <input
              className="form-input"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="e.g. 0, C:/videos/kitchen.mp4, or rtsp://cam-ip/stream"
              disabled={isRunning}
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.6 }}>
              Supported sources:<br />
              • Webcam: <span className="font-mono">0</span>, <span className="font-mono">1</span><br />
              • Local Video: <span className="font-mono">C:/path/to/video.mp4</span><br />
              • Network Stream: <span className="font-mono">rtsp://...</span> or <span className="font-mono">http://.../stream.m3u8</span><br />
              • Embed URL: <span className="font-mono">https://open.ivideon.com/embed/...</span> (uses browser capture)
            </div>
          </div>

          {/* Model */}
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Model</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {MODEL_OPTIONS.map((m) => (
                <button
                  key={m}
                  className={`btn ${selectedModel === m ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setSelectedModel(m)}
                  disabled={isRunning}
                  style={{ padding: '8px 16px' }}
                >
                  {m === 'BOTH' ? 'Compare Both' : m}
                </button>
              ))}
            </div>
          </div>

          {/* Start/Stop */}
          <div>
            {!isRunning ? (
              <button className="btn btn-primary" onClick={startSession}>
                Start Session
              </button>
            ) : (
              <button className="btn btn-danger" onClick={stopSession}>
                Stop
              </button>
            )}
          </div>
        </div>

        {error && (
          <div style={{
            marginTop: 12, padding: '10px 14px',
            background: 'var(--danger-bg)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--danger)', fontSize: '0.875rem',
          }}>
            {error}
          </div>
        )}

        {/* PPE Parameter Toggles */}
        <div style={{
          marginTop: 16, padding: '12px 16px',
          background: 'var(--bg-elevated)',
          borderRadius: 'var(--radius-sm)',
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10 }}>
            PPE Parameters to Track
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {ALL_PPE_ITEMS.map((item) => {
              const isActive = activeItems.has(item.key)
              return (
                <label key={item.key} style={{
                  display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                  padding: '7px 16px', borderRadius: 24,
                  border: `1.5px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
                  background: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
                  transition: 'all 0.2s', userSelect: 'none',
                }}>
                  <input type="checkbox" checked={isActive} onChange={() => toggleItem(item.key)} style={{ display: 'none' }} />
                  <span style={{ fontSize: '1.1rem' }}>{item.icon}</span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: isActive ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {item.label}
                  </span>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: isActive ? 'var(--accent)' : 'var(--border)', flexShrink: 0,
                  }} />
                </label>
              )
            })}
          </div>
          <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)', marginTop: 8 }}>
            Untick an item to stop tracking it — violations for that PPE will be ignored.
          </div>
        </div>
      </div>

      {/* Main layout: stream + sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24 }}>

        {/* Stream + Metrics */}
        <div>
          <StreamPlayer
            src={streamSrc}
            label={isBenchmark ? 'Benchmark — Both Models' : selectedModel}
            isLive={isRunning}
          />

          {isRunning && (
            <div className="grid-metrics" style={{ marginTop: 16 }}>
              <MetricCard
                value={sessionMetrics?.fps ?? benchmarkMetrics?.YOLO?.fps ?? '—'}
                label="FPS"
                unit=""
                accent="var(--accent)"
              />
              <MetricCard
                value={sessionMetrics?.latency_ms ?? '—'}
                label="Latency"
                unit="ms"
                accent="var(--warning)"
              />
              <MetricCard
                value={sessionMetrics?.total_detections ?? '—'}
                label="Detections"
                accent="var(--success)"
              />
              <MetricCard
                value={sessionMetrics?.active_violations ?? '—'}
                label="Violations"
                accent="var(--danger)"
              />
            </div>
          )}

          {/* Benchmark dual metrics */}
          {isBenchmark && benchmarkMetrics && (
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {Object.entries(benchmarkMetrics).map(([modelName, data]) => (
                <div key={modelName} className="card">
                  <h3 style={{ marginBottom: 12, color: modelName === 'YOLO' ? 'var(--accent)' : 'var(--warning)' }}>
                    {modelName}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <div>
                      <div className="metric-value" style={{ fontSize: '1.5rem' }}>{data.fps}</div>
                      <div className="metric-label">FPS</div>
                    </div>
                    <div>
                      <div className="metric-value" style={{ fontSize: '1.5rem' }}>{data.latency_ms}<span style={{ fontSize: '0.8rem' }}>ms</span></div>
                      <div className="metric-label">Latency</div>
                    </div>
                    <div>
                      <div className="metric-value" style={{ fontSize: '1.5rem' }}>{data.avg_detections}</div>
                      <div className="metric-label">Avg Dets</div>
                    </div>
                    <div>
                      <div className="metric-value" style={{ fontSize: '1.5rem' }}>{data.frame_count}</div>
                      <div className="metric-label">Frames</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar: Tracks + Snapshots */}
        <div>
          <div className="card" style={{ position: 'sticky', top: 24 }}>

            {/* Tab header */}
            <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid var(--border)' }}>
              {[
                { key: 'tracks', label: 'Active Tracks' },
                { key: 'snapshots', label: `Snapshots${violationCount > 0 ? ` (${violationCount})` : ''}` },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  style={{
                    flex: 1,
                    padding: '8px 0',
                    background: 'none',
                    border: 'none',
                    borderBottom: activeTab === key ? '2px solid var(--accent)' : '2px solid transparent',
                    color: activeTab === key ? 'var(--accent)' : 'var(--text-secondary)',
                    fontWeight: activeTab === key ? 700 : 400,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    marginBottom: -1,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Active Tracks tab */}
            {activeTab === 'tracks' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {isRunning && <span className="status-pill compliant" style={{ fontSize: '0.65rem', alignSelf: 'flex-start', marginBottom: 4 }}>Live</span>}
                {trackStates.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <p style={{ fontSize: '0.8rem' }}>
                      {isRunning ? 'No persons detected yet' : 'Start a session to track persons'}
                    </p>
                  </div>
                ) : (
                  trackStates.map((state) => (
                    <ViolationBadge
                      key={state.track_id}
                      personId={state.track_id}
                      detectedPpe={state.detected_ppe || []}
                      missingPpe={state.missing_ppe || []}
                      isCompliant={state.status === 'COMPLIANT'}
                      activeItems={activeItems}
                      allPpeItems={ALL_PPE_ITEMS}
                    />
                  ))
                )}
              </div>
            )}

            {/* Snapshots tab */}
            {activeTab === 'snapshots' && (
              <div>
                {snapshots.length > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: '0.75rem', padding: '5px 12px' }}
                      onClick={downloadAll}
                    >
                      Download All
                    </button>
                  </div>
                )}
                {snapshots.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <p style={{ fontSize: '0.8rem' }}>
                      {isRunning ? 'No violations detected yet' : 'Start a session to capture violations'}
                    </p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxHeight: 520, overflowY: 'auto', paddingRight: 8 }}>
                    {Object.entries(groupedSnapshots)
                      .sort(([idA], [idB]) => Number(idA) - Number(idB))
                      .map(([personId, snaps]) => (
                      <div key={personId} style={{ 
                        background: 'rgba(0,0,0,0.1)', 
                        padding: 12, 
                        borderRadius: 8,
                        border: '1px solid var(--border)' 
                      }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '0.85rem', color: 'var(--accent)' }}>
                          👤 Person #{personId} ({snaps.length} violations)
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

            {/* Session info footer */}
            <div style={{
              marginTop: 16, padding: '10px 12px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Model</span>
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                  {isBenchmark ? 'Both (Compare)' : selectedModel}
                </span>
              </div>
              {sessionId && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                  <span>Session</span>
                  <span className="font-mono" style={{ fontSize: '0.7rem' }}>
                    {sessionId.slice(0, 8)}…
                  </span>
                </div>
              )}

              {/* Bounding box colour legend */}
              <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                  Bounding Box Legend
                </div>
                {[
                  { color: '#32dc32', label: 'Compliant' },
                  { color: '#f03030', label: 'Violation' },
                  { color: '#ffa51e', label: 'Low confidence' },
                ].map(({ color, label }) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{
                      display: 'inline-block', width: 12, height: 12,
                      borderRadius: 2, background: color, flexShrink: 0,
                    }} />
                    <span style={{ fontSize: '0.75rem' }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
