import { useEffect, useState } from 'react'
import { laravelApi, inferenceApi } from '../api/axios'

const ALL_PPE_CLASSES = [
  { key: 'gloves',         label: 'Gloves',          type: 'compliance' },
  { key: 'hairnet',        label: 'Hairnet',          type: 'compliance' },
  { key: 'mask',           label: 'Mask',             type: 'compliance' },
  { key: 'no_gloves',      label: 'No Gloves',        type: 'violation'  },
  { key: 'no_hairnet',     label: 'No Hairnet',       type: 'violation'  },
  { key: 'no_mask',        label: 'No Mask',          type: 'violation'  },
  { key: 'incorrect_mask', label: 'Incorrect Mask',   type: 'violation'  },
]

const MODEL_OPTIONS = [
  { value: 'YOLO',   label: 'YOLO11',           desc: 'Fast, high-throughput detection' },
  { value: 'RTDETR', label: 'RT-DETR-L',         desc: 'COCO pretrained; fine-tune for PPE classes' },
  { value: 'BOTH',   label: 'Compare Both',      desc: 'Side-by-side benchmark mode'       },
]

export default function ModelSettings() {
  const [settings, setSettings] = useState({
    model: 'YOLO',
    confidence_threshold: 0.5,
    enabled_classes: ['gloves', 'hairnet', 'mask', 'no_gloves', 'no_hairnet'],
    stream_fps: 30,
    device: 'auto',
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    // Load saved settings from Laravel
    laravelApi.get('/settings').then((res) => {
      if (res.data) {
        setSettings((prev) => ({ ...prev, ...res.data }))
      }
    }).catch(() => {})

    // Load current inference service health
    inferenceApi.get('/health').then((res) => setHealth(res.data)).catch(() => {})
  }, [])

  const toggleClass = (key) => {
    setSettings((prev) => ({
      ...prev,
      enabled_classes: prev.enabled_classes.includes(key)
        ? prev.enabled_classes.filter((c) => c !== key)
        : [...prev.enabled_classes, key],
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      // Save to Laravel
      await laravelApi.put('/settings', settings)

      // Apply model selection immediately to inference service
      await inferenceApi.post('/model/select', { model: settings.model }).catch(() => {})

      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Model Settings</h1>
        <p>Configure detection models and PPE class selection</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>
        {/* Left: model + threshold */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Model selection */}
          <div className="card">
            <h3 style={{ marginBottom: 16 }}>Detection Model</h3>
            <div className="radio-group">
              {MODEL_OPTIONS.map(({ value, label, desc }) => (
                <label
                  key={value}
                  className={`radio-option ${settings.model === value ? 'selected' : ''}`}
                  onClick={() => setSettings((prev) => ({ ...prev, model: value }))}
                >
                  <input
                    type="radio"
                    name="model"
                    value={value}
                    checked={settings.model === value}
                    onChange={() => setSettings((prev) => ({ ...prev, model: value }))}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{label}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>{desc}</div>
                  </div>

                  {/* Weight status indicator */}
                  <div style={{ marginLeft: 'auto', fontSize: '0.75rem' }}>
                    {value === 'YOLO' && (
                      <span style={{ color: health?.yolo_loaded ? 'var(--success)' : 'var(--danger)' }}>
                        {health?.yolo_loaded ? 'Loaded' : 'Missing'}
                      </span>
                    )}
                    {value === 'RTDETR' && (
                      <span style={{ color: health?.rtdetr_loaded ? 'var(--success)' : 'var(--danger)' }}>
                        {health?.rtdetr_loaded ? 'Loaded' : 'Missing'}
                      </span>
                    )}
                  </div>
                </label>
              ))}
            </div>

            {/* Weight file instructions */}
            <div style={{
              marginTop: 16,
              padding: '12px 14px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              borderLeft: '3px solid var(--accent)',
            }}>
              <strong style={{ color: 'var(--accent)' }}>Model weights</strong><br />
              Place weight files in <code style={{ color: 'var(--warning)', background: 'rgba(245,158,11,0.1)', padding: '1px 5px', borderRadius: 3 }}>inference-service/models/</code>:<br />
              <code style={{ display: 'block', marginTop: 6 }}>khawla_v6.pt · khawla_mask_vest.pt · yolov8n.pt</code>
              <code style={{ display: 'block' }}>rtdetr-l.pt</code>
            </div>
          </div>

          {/* Thresholds */}
          <div className="card">
            <h3 style={{ marginBottom: 16 }}>Detection Parameters</h3>

            <div className="form-group">
              <label className="form-label">
                Confidence Threshold — {(settings.confidence_threshold * 100).toFixed(0)}%
              </label>
              <input
                type="range" min="0.1" max="0.99" step="0.01"
                value={settings.confidence_threshold}
                onChange={(e) => setSettings((p) => ({ ...p, confidence_threshold: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                <span>Sensitive (10%)</span>
                <span>Strict (99%)</span>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Stream FPS Target</label>
              <input
                type="number" min="1" max="60"
                className="form-input"
                value={settings.stream_fps}
                onChange={(e) => setSettings((p) => ({ ...p, stream_fps: parseInt(e.target.value) }))}
              />
            </div>
          </div>
        </div>

        {/* Right: PPE class selection */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="card">
            <h3 style={{ marginBottom: 4 }}>PPE Class Selection</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
              Choose which classes to detect. These must match your model's training classes.
            </p>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Compliance Classes
              </div>
              <div className="checkbox-group">
                {ALL_PPE_CLASSES.filter((c) => c.type === 'compliance').map(({ key, label }) => (
                  <label key={key} className="checkbox-option">
                    <input
                      type="checkbox"
                      checked={settings.enabled_classes.includes(key)}
                      onChange={() => toggleClass(key)}
                    />
                    <span style={{ fontSize: '0.875rem' }}>{label}</span>
                    <span style={{
                      marginLeft: 'auto',
                      fontSize: '0.7rem',
                      color: 'var(--success)',
                      background: 'var(--success-bg)',
                      padding: '2px 8px', borderRadius: 4,
                    }}>
                      PPE
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--danger)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Violation Classes
              </div>
              <div className="checkbox-group">
                {ALL_PPE_CLASSES.filter((c) => c.type === 'violation').map(({ key, label }) => (
                  <label key={key} className="checkbox-option">
                    <input
                      type="checkbox"
                      checked={settings.enabled_classes.includes(key)}
                      onChange={() => toggleClass(key)}
                    />
                    <span style={{ fontSize: '0.875rem' }}>{label}</span>
                    <span style={{
                      marginLeft: 'auto',
                      fontSize: '0.7rem',
                      color: 'var(--danger)',
                      background: 'var(--danger-bg)',
                      padding: '2px 8px', borderRadius: 4,
                    }}>
                      Violation
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Save button */}
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{ justifyContent: 'center' }}
          >
            {saving ? (
              <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> Saving…</>
            ) : saved ? (
              'Settings Saved'
            ) : (
              'Save Settings'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
