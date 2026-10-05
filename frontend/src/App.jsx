import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import LiveMonitoring from './pages/LiveMonitoring'
import ViolationsHistory from './pages/ViolationsHistory'
import ModelSettings from './pages/ModelSettings'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/monitoring" element={<LiveMonitoring />} />
            <Route path="/violations" element={<ViolationsHistory />} />
            <Route path="/settings"   element={<ModelSettings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
