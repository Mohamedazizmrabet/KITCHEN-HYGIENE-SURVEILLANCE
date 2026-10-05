import axios from 'axios'

// Laravel API instance — routed through Vite proxy
const laravelApi = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
  withCredentials: true,
})

// Python inference service — direct connection for non-stream calls
const inferenceApi = axios.create({
  baseURL: 'http://localhost:8001',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// Global response interceptor for error normalisation
const attachInterceptors = (instance) => {
  instance.interceptors.response.use(
    (res) => res,
    (err) => {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Unknown error'
      console.error(`[API Error] ${message}`)
      return Promise.reject(new Error(message))
    }
  )
}

attachInterceptors(laravelApi)
attachInterceptors(inferenceApi)

export { laravelApi, inferenceApi }

// ---------------------------------------------------------------------------
// Convenience helpers
// ---------------------------------------------------------------------------

/** MJPEG stream URL for a given session ID (direct FastAPI) */
export const streamUrl = (sessionId) =>
  `http://localhost:8001/stream/${sessionId}`

/** Benchmark stream URL (direct FastAPI) */
export const benchmarkStreamUrl = () =>
  `http://localhost:8001/benchmark/stream`
