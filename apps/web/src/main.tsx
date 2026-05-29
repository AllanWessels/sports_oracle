import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import { App } from './App'
import { EvalDashboard } from './components/dashboards/EvalDashboard'
import { RoutingDashboard } from './components/dashboards/RoutingDashboard'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/dashboard/routing" element={<RoutingDashboard />} />
        <Route path="/dashboard/eval" element={<EvalDashboard />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
