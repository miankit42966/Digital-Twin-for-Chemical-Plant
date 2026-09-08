import type { Asset } from '../types'
import TrendChart, { type TrendPoint } from '../components/TrendChart'
const makeTrend = (value: number, wave: number): TrendPoint[] => Array.from({ length: 12 }, (_, index) => ({ time: `${String(index).padStart(2, '0')}:00`, value: value + Math.sin(index * .76 + wave) * Math.max(value * .045, 1.5) + (index - 6) * .12 }))
export default function Analytics({ assets = [] }: { assets: Asset[] }) {
  const source = assets[1] ?? assets[0]
  const normal = assets.filter(asset => asset.alarm_level === 'normal').length
  const warning = assets.filter(asset => asset.alarm_level === 'warning').length
  const critical = Math.max(0, assets.length - normal - warning)
  return (
    <div className="page-grid analytics-page">
      <section className="page-title">
        <span>HISTORICAL ANALYTICS</span>
        <h1>Telemetry trends</h1>
        <p>Mock history derived from the current integration telemetry stream. It is not a predictive model.</p>
      </section>
      <section className="chart-grid">
        <TrendChart title="Temperature" unit="°C" data={makeTrend(source?.temperature_c ?? 45, 0)} color="#45d696" />
        <TrendChart title="Pressure" unit="bar" data={makeTrend(source?.pressure_bar ?? 4, 1)} color="#6ca7ff" />
        <TrendChart title="Flow rate" unit="m³/h" data={makeTrend(source?.flow_m3h ?? 50, 2)} color="#d9ab54" />
        <TrendChart title="Liquid level" unit="%" data={makeTrend(source?.level_percent ?? 50, 3)} color="#b27aff" />
        <TrendChart title="Gas concentration" unit="ppm" data={makeTrend(source?.gas_ppm ?? 5, 4)} color="#f27979" />
      </section>
      <section className="panel distribution-panel">
        <div className="panel-heading">
          <div><span>ALARM DISTRIBUTION</span><h2>Current asset status</h2></div>
        </div>
        <div className="distribution">
          <div><i className="normal" /><b>{normal}</b><span>Normal</span></div>
          <div><i className="warning" /><b>{warning}</b><span>Warning</span></div>
          <div><i className="critical" /><b>{critical}</b><span>Critical / shutdown</span></div>
        </div>
      </section>
    </div>
  )
}

