import { useEffect, useState } from 'react'
import './evaluation.css'

interface RtfCard {
  model_name: string
  created_utc: string
  source_doi: string
  source_sha256: string
  task: string
  split: string
  evaluation_sampling: string
  history_samples: number
  features: string[]
  run_counts: Record<'train' | 'validation' | 'test', number>
  sample_counts: Record<'train' | 'validation' | 'test', number>
  test: { mae_minutes: number; rmse_minutes: number; p90_absolute_error_minutes: number; last_4h_support: number; last_4h_mae_minutes: number | null }
  warning_horizon_minutes: number
  next_unit_status: string
  next_unit_confusion_matrix: Record<string, unknown> | null
  next_unit_per_equipment_precision_recall: Record<string, unknown> | null
  warning_performance: Record<string, unknown> | null
  abstention_rate: number
  limitations: string[]
}

export default function RtfEvaluation() {
  const [card, setCard] = useState<RtfCard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    document.title = 'Run-to-failure model evaluation | SentinelTwin'
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    fetch('/api/v1/models/tep-rtf-prognosis', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Model card API ${response.status}`)
      return response.json() as Promise<RtfCard>
    }).then(value => {
      if (controller.signal.aborted) return
      if (!value.model_name || !Number.isFinite(value.test?.mae_minutes) || !Array.isArray(value.limitations)) throw new Error('Incomplete model card')
      setCard(value); setError(null)
    }).catch(value => { if (!controller.signal.aborted || controller.signal.reason === 'Request timeout') setError(`Evaluation unavailable: ${String(value)}`) }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [retry])
  return <main className="dashboard dataset-dashboard evaluation-page"><header className="site-header"><a className="brand evaluation-brand" href="/"><span className="brand-mark" aria-hidden="true">◇</span><span><span className="brand-name">SENTINELTWIN</span><span className="brand-sub">MODEL EVALUATION</span></span></a><a className="evaluation-back" href="/">← Back to dashboard</a></header><section className="dataset-heading"><div><span className="eyebrow">PUBLISHED SIMULATION / HELD-OUT RUNS</span><h1>Run-to-failure prognosis evaluation</h1><p>What the remaining-time model estimates—and why no component forecast is claimed without verified labels.</p></div><div className="dataset-source-indicator"><strong>TEP RTF</strong><span>Research benchmark only</span></div></section>
    {error && <div className="error-banner" role="alert"><span>{error} No substitute scores are shown.</span><button type="button" className="control-button" onClick={() => setRetry(value => value + 1)}>Retry evaluation</button></div>}
    {!card && !error && <section className="explanation-card" role="status">Loading saved evaluation evidence…</section>}
    {card && <><div className="source-banner"><span className="source-badge">SIMULATED SHUTDOWN TARGET</span><span>{card.task}</span></div><section className="evaluation-metrics" aria-label="Held-out model metrics"><div><span className="tiny-heading">TIME MAE</span><strong>{card.test.mae_minutes.toFixed(1)} min</strong><p>Average absolute remaining-time error on sampled held-out-run points.</p></div><div><span className="tiny-heading">90TH-PERCENTILE ERROR</span><strong>{card.test.p90_absolute_error_minutes.toFixed(1)} min</strong><p>90% of evaluated absolute time errors are at or below this value.</p></div><div><span className="tiny-heading">LAST FOUR HOURS MAE</span><strong>{card.test.last_4h_mae_minutes?.toFixed(1) ?? 'N/A'} min</strong><p>{card.test.last_4h_support.toLocaleString()} evaluated samples near shutdown.</p></div><div><span className="tiny-heading">NEXT UNIT</span><strong>{card.next_unit_status === 'ready' ? 'Evaluated' : 'Unassessed'}</strong><p>{card.next_unit_status === 'ready' ? 'See the technical model card for per-unit results.' : 'No verified terminal-equipment labels; no unit prediction or highlight.'}</p></div></section><section className="evaluation-grid"><article className="explanation-card"><span className="tiny-heading">NO FUTURE-DATA LEAKAGE</span><h2>Training and testing</h2><p>{card.split}</p><p>{card.evaluation_sampling}</p><dl className="evaluation-facts"><div><dt>Training runs</dt><dd>{card.run_counts.train}</dd></div><div><dt>Validation runs</dt><dd>{card.run_counts.validation}</dd></div><div><dt>Held-out test runs</dt><dd>{card.run_counts.test}</dd></div><div><dt>Observed history</dt><dd>{card.history_samples} samples</dd></div></dl><p>Current and previous process readings form the input. The actual shutdown time is used only as the training/evaluation target.</p></article><article className="explanation-card"><span className="tiny-heading">EQUIPMENT-WARNING EVIDENCE</span><h2>Fail-closed component status</h2><p>{card.next_unit_status === 'ready' ? 'The model can name a unit only after verified run-level labels and held-out evaluation.' : 'The source CSVs have no terminal equipment label. The application does not infer one from case names, so equipment warnings remain disabled.'}</p><p>Selected warning window: {card.warning_horizon_minutes} simulated minutes. Per-unit metrics and warning performance are {card.warning_performance ? 'available in the technical card' : 'not available without verified labels'}.</p><p>Abstention rate: {(card.abstention_rate * 100).toFixed(1)}%.</p></article></section><section className="explanation-card evaluation-limitations"><span className="tiny-heading">SOURCE AND LIMITS</span><h2>Research result, not plant protection</h2><p>Source DOI: <a href={`https://doi.org/${card.source_doi}`} target="_blank" rel="noreferrer">{card.source_doi}</a></p><ul>{card.limitations.map(item => <li key={item}>{item}</li>)}</ul><details className="evaluation-details"><summary>View model features and raw card</summary><pre>{JSON.stringify(card, null, 2)}</pre></details></section></>}
    <footer><span>SentinelTwin · TEP RTF evaluation</span><span>Simulated process shutdown is not physical equipment failure</span></footer>
  </main>
}
