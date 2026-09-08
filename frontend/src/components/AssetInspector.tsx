import type { Asset } from '../types'
import AlarmBadge from './AlarmBadge'
import MetricCard from './MetricCard'
export default function AssetInspector({ asset }: { asset?: Asset }) {
  if (!asset) {
    return (
      <aside className="asset-inspector">
        <div className="panel-kicker">ASSET INSPECTOR</div>
        <div className="empty-state" style={{ padding: '24px 0', textAlign: 'center' }}>
          No asset selected or telemetry stream is empty.
        </div>
      </aside>
    )
  }
  const timestamp = asset.updated_at
    ? new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(asset.updated_at))
    : 'N/A'
  return (
    <aside className="asset-inspector">
      <div className="panel-kicker">ASSET INSPECTOR</div>
      <div className="inspector-title">
        <div>
          <h2>{asset.asset_name}</h2>
          <span>{asset.asset_id}</span>
        </div>
        <AlarmBadge level={asset.alarm_level ?? 'normal'} />
      </div>
      <div className="inspector-metrics">
        <MetricCard label="TEMPERATURE" value={asset.temperature_c ?? 0} unit="°C" />
        <MetricCard label="PRESSURE" value={asset.pressure_bar ?? 0} unit="bar" />
        <MetricCard label="LIQUID LEVEL" value={asset.level_percent ?? 0} unit="%" />
        <MetricCard label="FLOW RATE" value={asset.flow_m3h ?? 0} unit="m³/h" />
        <MetricCard label="GAS" value={asset.gas_ppm ?? 0} unit="ppm" />
        <MetricCard
          label="VALVE STATE"
          value={asset.valve_open ? 'OPEN' : 'CLOSED'}
          accent={asset.valve_open ? 'green' : 'amber'}
        />
      </div>
      <footer>Last updated {timestamp}</footer>
    </aside>
  )
}

