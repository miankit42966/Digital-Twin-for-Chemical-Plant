import type { Asset } from '../types'
import MetricCard from './MetricCard'
export default function KpiBar({ assets = [] }: { assets: Asset[] }) {
  const alarms = assets.filter(asset => asset.alarm_level !== 'normal').length
  const critical = assets.filter(asset => asset.alarm_level === 'critical' || asset.alarm_level === 'emergency_shutdown').length
  const health = assets.length > 0
    ? Math.round((1 - assets.reduce((sum, asset) => sum + (asset.risk_score ?? 0), 0) / assets.length) * 100)
    : 100
  return (
    <section className="kpi-bar">
      <MetricCard label="PLANT STATUS" value={critical ? 'ATTENTION' : 'STABLE'} accent={critical ? 'red' : 'green'} />
      <MetricCard label="ACTIVE ALARMS" value={alarms} accent={alarms ? 'amber' : 'green'} />
      <MetricCard label="ONLINE ASSETS" value={`${assets.length}/${assets.length}`} accent="green" />
      <MetricCard label="PLANT HEALTH" value={health} unit="%" accent={health < 60 ? 'amber' : 'green'} />
    </section>
  )
}

