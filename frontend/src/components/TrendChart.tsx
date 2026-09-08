export type TrendPoint = { time: string; value: number }
export default function TrendChart({ title, unit, data, color }: { title: string; unit: string; data: TrendPoint[]; color: string }) {
  const width = 340, height = 132, pad = 18, values = data.map(point => point.value), min = Math.min(...values), max = Math.max(...values), range = max - min || 1
  const points = data.map((point, index) => `${pad + index / Math.max(data.length - 1, 1) * (width - pad * 2)},${height - pad - (point.value - min) / range * (height - pad * 2)}`).join(' ')
  return <article className="trend-chart"><header><b>{title}</b><span>{data[data.length - 1]?.value.toFixed(1)} {unit}</span></header><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} historical trend`}><path d={`M ${pad} ${height - pad} H ${width - pad} M ${pad} ${height / 2} H ${width - pad} M ${pad} ${pad} H ${width - pad}`} /><polyline points={points} stroke={color} /></svg><footer><span>{data[0]?.time}</span><span>{data[data.length - 1]?.time}</span></footer></article>
}
