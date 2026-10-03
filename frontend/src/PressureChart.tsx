type Point = { minute: number; pressure: number }
type Props = { observed: Point[]; projected?: Point[]; response?: Point[]; threshold?: number; title: string; caption: string; observedLabel?: string; projectedLabel?: string }

export default function PressureChart({ observed, projected = [], response = [], threshold, title, caption, observedLabel = 'Recorded samples', projectedLabel = 'Pressure estimate' }: Props) {
  const all = [...observed, ...projected, ...response]
  const xMin = Math.min(...all.map(point => point.minute))
  const xMax = Math.max(...all.map(point => point.minute), xMin + 1)
  const yMin = Math.floor(Math.min(...all.map(point => point.pressure), threshold ?? Infinity) - 1)
  const yMax = Math.ceil(Math.max(...all.map(point => point.pressure), threshold ?? -Infinity) + 1)
  const x = (value: number) => 50 + (value - xMin) / (xMax - xMin) * 610
  const y = (value: number) => 210 - (value - yMin) / (yMax - yMin) * 160
  const path = (points: Point[]) => points.map((point, index) => `${index ? 'L' : 'M'} ${x(point.minute).toFixed(1)} ${y(point.pressure).toFixed(1)}`).join(' ')
  const last = observed[observed.length - 1]

  return <section className="chart-panel" aria-label={title}>
    <div className="panel-heading"><div><span className="tiny-heading">PRESSURE TREND</span><h3>{title}</h3></div><span className="chart-unit">bar(g) / simulated minutes</span></div>
    <svg className="pressure-chart" viewBox="0 0 700 250" role="img" aria-label={`${title}. ${caption}`}>
      {[0, 1, 2, 3, 4].map(index => { const value = yMin + (yMax - yMin) * index / 4; return <g key={index}><line x1="50" x2="660" y1={y(value)} y2={y(value)} className="chart-gridline" /><text x="42" y={y(value) + 4} textAnchor="end" className="chart-axis">{value.toFixed(1)}</text></g> })}
      <line x1="50" x2="660" y1="210" y2="210" className="chart-axis-line" />
      {threshold != null && <g><line x1="50" x2="660" y1={y(threshold)} y2={y(threshold)} className="chart-threshold" /><text x="655" y={y(threshold) - 7} textAnchor="end" className="chart-threshold-label">TRAINING THRESHOLD</text></g>}
      {observed.length > 1 && <path d={path(observed)} className="chart-observed" />}
      {projected.length > 1 && <path d={path(projected)} className="chart-projected" />}
      {response.length > 1 && <path d={path(response)} className="chart-response" />}
      {last && <circle cx={x(last.minute)} cy={y(last.pressure)} r="5" className="chart-point" />}
      <text x="50" y="237" className="chart-axis">{xMin} min</text><text x="660" y="237" textAnchor="end" className="chart-axis">{xMax} min</text>
    </svg>
    <div className="chart-legend"><span><i className="line observed" />{observedLabel}</span>{projected.length > 1 && <span><i className="line projected" />{projectedLabel}</span>}{response.length > 1 && <span><i className="line response" />Scripted response</span>}</div>
    <p className="panel-caption">{caption}</p>
  </section>
}
