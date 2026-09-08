export default function MetricCard({ label, value, unit, accent }: { label: string; value: string | number; unit?: string; accent?: 'green' | 'amber' | 'red' }) {
  return <div className={`metric-card ${accent ?? ''}`}><span>{label}</span><strong>{value}{unit && <em>{unit}</em>}</strong></div>
}
