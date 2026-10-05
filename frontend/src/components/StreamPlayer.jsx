import { useState } from 'react'

/**
 * StreamPlayer — renders a live MJPEG stream as an <img> element.
 *
 * Props:
 *   src          string   — MJPEG stream URL (FastAPI /stream/{id})
 *   label        string   — overlay label (e.g. model name)
 *   isLive       boolean  — whether the stream is active
 *   onError      function — called when the stream fails to load
 */
export default function StreamPlayer({ src, label = 'Stream', isLive = false, onError }) {
  const [hasError, setHasError] = useState(false)

  const handleError = () => {
    setHasError(true)
    onError?.()
  }

  const handleLoad = () => {
    setHasError(false)
  }

  return (
    <div className="stream-container">
      {/* MJPEG stream — browser handles multipart/x-mixed-replace natively */}
      {isLive && src && !hasError ? (
        <img
          className="stream-img"
          src={src}
          alt="Live surveillance stream"
          onError={handleError}
          onLoad={handleLoad}
        />
      ) : (
        <div className="stream-offline">
          <div className="icon">📷</div>
          <p>
            {hasError
              ? 'Stream connection lost'
              : 'No active stream — start a session to begin'}
          </p>
          {hasError && (
            <button
              className="btn btn-ghost"
              style={{ marginTop: 8, fontSize: '0.8rem', padding: '6px 14px' }}
              onClick={() => setHasError(false)}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* Live badge */}
      {isLive && !hasError && (
        <div className="stream-badge">
          <span className="live-dot" />
          LIVE · {label}
        </div>
      )}
    </div>
  )
}
