import { useEffect, useMemo, useState } from 'react'
import type { Asset, PlantState } from './types'
import Header, { type AppView } from './components/Header'
import { fetchPlantState, API_BASE_URL } from './services/api'
import DigitalTwin from './pages/DigitalTwin'
import Overview from './pages/Overview'
import Analytics from './pages/Analytics'
import Alerts from './pages/Alerts'
import Assets from './pages/Assets'

const stamp = () => new Date().toISOString()
const demoState: PlantState = {
  source_kind: 'SIMULATED_INTEGRATION_BASELINE',
  source_notice: 'Demonstration telemetry is shown until the API connects.',
  generated_at: stamp(),
  assets: [
    { asset_id: 'TK-101', asset_name: 'Feed Tank', temperature_c: 45.7, pressure_bar: 4.12, level_percent: 66.4, flow_m3h: 81.9, valve_open: true, gas_ppm: 4, risk_score: .18, alarm_level: 'normal', updated_at: stamp() },
    { asset_id: 'RX-201', asset_name: 'Reactor', temperature_c: 65.1, pressure_bar: 31.05, level_percent: 62.38, flow_m3h: 46.99, valve_open: true, gas_ppm: 11, risk_score: .72, alarm_level: 'critical', updated_at: stamp() },
    { asset_id: 'TK-301', asset_name: 'Buffer Tank', temperature_c: 54, pressure_bar: 3.4, level_percent: 42, flow_m3h: 55, valve_open: false, gas_ppm: 3, risk_score: .42, alarm_level: 'warning', updated_at: stamp() },
  ],
}

function isValidAsset(item: unknown): item is Asset {
  if (!item || typeof item !== 'object') return false
  const a = item as Record<string, unknown>
  return typeof a.asset_id === 'string' && typeof a.asset_name === 'string'
}

function sanitizePlantState(data: unknown, fallback: PlantState): PlantState {
  if (!data || typeof data !== 'object') return fallback
  const d = data as Record<string, unknown>
  if (!Array.isArray(d.assets)) return fallback
  const validAssets = d.assets.filter(isValidAsset)
  return {
    source_kind: d.source_kind === 'SIMULATED_INTEGRATION_BASELINE' ? 'SIMULATED_INTEGRATION_BASELINE' : fallback.source_kind,
    source_notice: typeof d.source_notice === 'string' ? d.source_notice : fallback.source_notice,
    generated_at: typeof d.generated_at === 'string' ? d.generated_at : new Date().toISOString(),
    assets: validAssets,
  }
}

export default function App() {
  const [state, setState] = useState<PlantState>(demoState)
  const [selectedId, setSelectedId] = useState('RX-201')
  const [view, setView] = useState<AppView>('twin')
  const [connection, setConnection] = useState('DEMO MODE')

  useEffect(() => {
    let isCancelled = false

    fetchPlantState()
      .then(data => {
        if (!isCancelled) {
          setState(prev => sanitizePlantState(data, prev))
        }
      })
      .catch(() => {
        if (!isCancelled) setConnection('DEMO MODE')
      })

    const wsUrl = `${API_BASE_URL.replace(/^http/, 'ws')}/ws/telemetry`
    const socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      if (!isCancelled) setConnection('LIVE')
    }

    socket.onmessage = event => {
      if (isCancelled) return
      try {
        const raw = JSON.parse(event.data)
        setState(prev => sanitizePlantState(raw, prev))
        setConnection('LIVE')
      } catch (err) {
        console.warn('Failed to parse WebSocket telemetry JSON:', err)
      }
    }

    socket.onerror = () => {
      if (!isCancelled) setConnection('DEMO MODE')
    }

    socket.onclose = () => {
      if (!isCancelled) setConnection('DEMO MODE')
    }

    return () => {
      isCancelled = true
      if (socket.readyState === WebSocket.OPEN) {
        socket.close()
      } else if (socket.readyState === WebSocket.CONNECTING) {
        socket.onopen = () => socket.close()
      }
    }
  }, [])

  const safeAssets = state?.assets ?? []
  const selected = useMemo(
    () => safeAssets.find(asset => asset.asset_id === selectedId) ?? safeAssets[0],
    [selectedId, safeAssets]
  )

  const selectAsset = (asset: Asset) => {
    setSelectedId(asset.asset_id)
    setView('twin')
  }

  const selectInTwin = (asset: Asset) => setSelectedId(asset.asset_id)

  const content =
    view === 'twin' ? (
      <DigitalTwin assets={safeAssets} selected={selected} onSelect={selectInTwin} />
    ) : view === 'overview' ? (
      <Overview assets={safeAssets} onSelect={selectAsset} />
    ) : view === 'analytics' ? (
      <Analytics assets={safeAssets} />
    ) : view === 'alerts' ? (
      <Alerts assets={safeAssets} />
    ) : (
      <Assets assets={safeAssets} onSelect={selectAsset} />
    )

  return (
    <div className="app-shell">
      <Header view={view} setView={setView} connection={connection} />
      <div className="source-banner">
        {(state?.source_kind || '').replace(/_/g, ' ')} · {state?.source_notice || ''}
      </div>
      {content}
    </div>
  )
}

