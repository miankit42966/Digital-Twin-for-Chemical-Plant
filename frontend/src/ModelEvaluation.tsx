import { useEffect, useState } from 'react'
import './evaluation.css'

export type EvaluationKind = 'tep-detector' | 'tep-pressure-20m'
interface ModelCard {
  model_name: string; created_utc: string; task: string; dataset: string; dataset_sha256: string;
  features: string[]; split: string; n_train: number; n_test: number; limitations: string[];
  label_rule?: string; target?: string; threshold?: number;
  precision?: number; recall?: number; average_precision?: number; roc_auc?: number;
  confusion_matrix?: { tn: number; fp: number; fn: number; tp: number };
  calibration_evidence?: { brier_score: number; expected_calibration_error: number; method: string; bins: { lower: number; upper: number; count: number; mean_score: number | null; observed_positive_rate: number | null }[] };
  per_fault_recall?: Record<string, { recall: number; support: number; true_positive: number }>;
  mae_kpa_gauge?: number; rmse_kpa_gauge?: number; r2?: number; p95_absolute_error_kpa_gauge?: number;
}
const percent = (value: number) => `${(value * 100).toFixed(2)}%`
const count = (value: number) => value.toLocaleString('en-US')

function validateCard(value: ModelCard, kind: EvaluationKind): ModelCard {
  if (!value || typeof value.model_name !== 'string' || typeof value.task !== 'string'
    || typeof value.split !== 'string' || typeof value.dataset !== 'string' || typeof value.dataset_sha256 !== 'string'
    || !Array.isArray(value.features) || !value.features.every(feature => typeof feature === 'string')
    || !Array.isArray(value.limitations) || !value.limitations.every(item => typeof item === 'string')
    || !Number.isFinite(value.n_train) || !Number.isFinite(value.n_test)) throw new Error('Evaluation card is incomplete')
  const metrics = kind === 'tep-detector'
    ? [value.precision, value.recall, value.average_precision, value.roc_auc, value.threshold, ...Object.values(value.confusion_matrix ?? {})]
    : [value.mae_kpa_gauge, value.rmse_kpa_gauge, value.r2, value.p95_absolute_error_kpa_gauge]
  if (metrics.some(metric => typeof metric !== 'number' || !Number.isFinite(metric))
    || (kind === 'tep-detector' && (!value.confusion_matrix || ['tn', 'fp', 'fn', 'tp'].some(key => !Number.isFinite(value.confusion_matrix![key as keyof NonNullable<ModelCard['confusion_matrix']>]))))) throw new Error('Evaluation metrics are incomplete')
  return value
}

export default function ModelEvaluation({ kind }: { kind: EvaluationKind }) {
  const [card, setCard] = useState<ModelCard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const detector = kind === 'tep-detector'
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    setCard(null); setError(null)
    document.title = `${detector ? 'Fault detector' : 'Pressure model'} evaluation | SentinelTwin`
    fetch(`/api/v1/models/${kind}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Evaluation API ${response.status}`)
      return validateCard(await response.json(), kind)
    }).then(value => { if (!controller.signal.aborted) setCard(value) }).catch(value => {
      if (!controller.signal.aborted || controller.signal.reason === 'Request timeout') setError(controller.signal.reason === 'Request timeout' ? 'The API timed out. Check the local server and retry.' : `Evaluation unavailable: ${String(value)}`)
    }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [kind, retry, detector])

  const metrics = card ? detector ? [
    ['PRECISION', percent(card.precision!), 'Of samples flagged as faults, how many had a fault label.'],
    ['RECALL', percent(card.recall!), 'Of fault-labeled test samples, how many were detected.'],
    ['AVERAGE PRECISION', card.average_precision!.toFixed(3), 'Precision–recall ranking across thresholds; not overall accuracy.'],
    ['ROC AUC', card.roc_auc!.toFixed(3), 'Fault-vs-normal ranking across score thresholds.'],
  ] : [
    ['MEAN ABSOLUTE ERROR', `${card.mae_kpa_gauge!.toFixed(2)} kPa`, `${(card.mae_kpa_gauge! / 100).toFixed(3)} bar — average absolute pressure error.`],
    ['ROOT MEAN SQUARE ERROR', `${card.rmse_kpa_gauge!.toFixed(2)} kPa`, 'Penalizes larger pressure-estimation errors.'],
    ['R² SCORE', card.r2!.toFixed(3), 'Fit relative to a mean-pressure baseline; not a probability or accuracy percentage.'],
    ['95TH-PERCENTILE ERROR', `${card.p95_absolute_error_kpa_gauge!.toFixed(2)} kPa`, '95% of evaluated absolute errors were at or below this value.'],
  ] : []

  return <main className="dashboard dataset-dashboard evaluation-page" data-model={kind}>
    <header className="site-header"><a className="brand evaluation-brand" href="/" aria-label="SentinelTwin dashboard"><span className="brand-mark" aria-hidden="true">◇</span><span><span className="brand-name">SENTINELTWIN</span><span className="brand-sub">MODEL EVALUATION</span></span></a><a className="evaluation-back" href="/">← Back to dashboard</a></header>
    <section className="dataset-heading"><div><span className="eyebrow">RESEARCH MODEL / HELD-OUT BENCHMARK RESULTS</span><h1>{detector ? 'Fault detector evaluation' : 'Pressure model evaluation'}</h1><p>{detector ? 'How well the current-sample classifier detects injected TEP faults, and what its score does not mean.' : 'How well the model estimates reactor pressure at +20 simulated minutes, and where that estimate is limited.'}</p></div><div className="dataset-source-indicator"><strong>TEP simulation</strong><span>Research results · not safety certification</span></div></section>
    <nav className="source-tabs evaluation-tabs" aria-label="Model evaluation"><a className={detector ? 'active' : ''} aria-current={detector ? 'page' : undefined} href="/?evaluation=tep-detector">Fault detector</a><a className={!detector ? 'active' : ''} aria-current={!detector ? 'page' : undefined} href="/?evaluation=tep-pressure-20m">+20 min pressure</a></nav>
    {!card && !error && <section className="explanation-card evaluation-loading" role="status">Loading the model evaluation card…</section>}
    {error && <section className="error-banner" role="alert"><span>{error} No substitute results are shown.</span><button type="button" className="control-button" onClick={() => setRetry(value => value + 1)}>Retry evaluation</button></section>}
    {card && <>
      <div className="source-banner"><span className="source-badge">PUBLISHED SIMULATION / RESEARCH ONLY</span><span>{card.task}</span></div>
      {detector && card.calibration_evidence && card.per_fault_recall && <section className="evaluation-grid" aria-label="Detector calibration and per-fault results"><article className="explanation-card"><span className="tiny-heading">SCORE CALIBRATION / HELD-OUT TEP SAMPLES</span><h2>Score is not a plant failure probability</h2><dl className="evaluation-facts"><div><dt>Brier score</dt><dd>{card.calibration_evidence.brier_score.toFixed(3)}</dd></div><div><dt>Expected calibration error</dt><dd>{percent(card.calibration_evidence.expected_calibration_error)}</dd></div></dl><p>{card.calibration_evidence.method}</p><details className="evaluation-details"><summary>View score-bin evidence</summary><div className="evaluation-table-wrap"><table className="evaluation-matrix"><thead><tr><th>Score bin</th><th>Samples</th><th>Mean score</th><th>Fault-label rate</th></tr></thead><tbody>{card.calibration_evidence.bins.map(bin => <tr key={bin.lower}><th>{percent(bin.lower)}–{percent(bin.upper)}</th><td>{count(bin.count)}</td><td>{bin.mean_score == null ? 'N/A' : percent(bin.mean_score)}</td><td>{bin.observed_positive_rate == null ? 'N/A' : percent(bin.observed_positive_rate)}</td></tr>)}</tbody></table></div></details></article><article className="explanation-card"><span className="tiny-heading">SCENARIO-BY-SCENARIO ROBUSTNESS</span><h2>Faults the model misses</h2><p>Overall recall hides major differences across the 20 injected fault scenarios. Each row is held-out, fault-labeled simulation samples, not incidents.</p><div className="evaluation-table-wrap"><table className="evaluation-matrix"><thead><tr><th>Fault</th><th>Detected / total</th><th>Recall</th></tr></thead><tbody>{Object.entries(card.per_fault_recall).sort(([a], [b]) => Number(a) - Number(b)).map(([fault, result]) => <tr key={fault}><th>{fault}</th><td>{count(result.true_positive)} / {count(result.support)}</td><td className={result.recall < .5 ? 'evaluation-weak' : ''}>{percent(result.recall)}</td></tr>)}</tbody></table></div></article></section>}
      <section className="evaluation-metrics" aria-label="Held-out evaluation metrics">{metrics.map(([label, value, explanation]) => <div key={label}><span className="tiny-heading">{label}</span><strong>{value}</strong><p>{explanation}</p></div>)}</section>
      <section className="evaluation-grid">
        <article className="explanation-card"><span className="tiny-heading">HOW TO INTERPRET THIS</span><h2>{detector ? 'High precision does not mean every fault is found' : 'A pressure estimate is not a hazard alert'}</h2>{detector ? <><p>At the recorded score threshold of {card.threshold}, precision is {percent(card.precision!)} but recall is {percent(card.recall!)}. The model missed {count(card.confusion_matrix!.fn)} fault-labeled samples in this test set.</p><p>The dashboard score describes a <strong>current</strong> sample. It is not a calibrated chance of equipment failure in the next 20 minutes.</p></> : <><p>The target is reactor pressure in kPa gauge at +20 <strong>simulated</strong> minutes. The dashboard converts kPa to bar(g) by dividing by 100.</p><p>The estimate is evaluated against an interpolated target, not a directly observed measurement at exactly +20 minutes. It does not establish that a leak, breakdown or over-pressure event will occur.</p></>}</article>
        {detector ? <article className="explanation-card"><span className="tiny-heading">TEST OUTCOMES / SAMPLE COUNTS</span><h2>Detected vs. missed samples</h2><table className="evaluation-matrix"><caption>Rows are published labels; columns are model decisions at threshold {card.threshold}.</caption><thead><tr><th scope="col">Published label</th><th scope="col">Predicted normal</th><th scope="col">Predicted fault</th></tr></thead><tbody><tr><th scope="row">Normal</th><td>{count(card.confusion_matrix!.tn)}<small>Correct normal (TN)</small></td><td>{count(card.confusion_matrix!.fp)}<small>False positive (FP)</small></td></tr><tr><th scope="row">Fault</th><td>{count(card.confusion_matrix!.fn)}<small>Missed fault (FN)</small></td><td>{count(card.confusion_matrix!.tp)}<small>Detected fault (TP)</small></td></tr></tbody></table><p>Counts are simulation samples, not distinct incidents or operating hours.</p></article> : <article className="explanation-card"><span className="tiny-heading">TARGET CONSTRUCTION</span><h2>Where “+20 minutes” comes from</h2><ol className="evaluation-steps"><li>Read current and previous pressure/level/temperature measurements.</li><li>Predict one future reactor-pressure value using seven features.</li><li>Evaluate against interpolation between source samples at +18 and +21 simulated minutes.</li></ol><p>{card.target}</p></article>}
      </section>
      <section className="evaluation-grid"><article className="explanation-card"><span className="tiny-heading">REPRODUCIBLE EVALUATION</span><h2>Training and testing</h2><dl className="evaluation-facts"><div><dt>Training samples</dt><dd>{count(card.n_train)}</dd></div><div><dt>Held-out test samples</dt><dd>{count(card.n_test)}</dd></div><div><dt>Input features</dt><dd>{card.features.length}</dd></div><div><dt>Card generated</dt><dd>{card.created_utc && Number.isFinite(Date.parse(card.created_utc)) ? new Date(card.created_utc).toLocaleString() : 'Not recorded'}</dd></div></dl><p>{card.split}</p>{card.label_rule && <p><strong>Label rule:</strong> {card.label_rule}</p>}<details className="evaluation-details"><summary>View input features ({card.features.length})</summary><div className="evaluation-features">{card.features.map(feature => <code key={feature}>{feature}</code>)}</div></details></article>
      <article className="explanation-card"><span className="tiny-heading">DATA PROVENANCE</span><h2>Source and evaluation card</h2><p>{card.dataset}</p><p><strong>Model:</strong> {card.model_name}</p><details className="evaluation-details"><summary>Dataset SHA-256 fingerprint</summary><code className="evaluation-hash">{card.dataset_sha256}</code></details><details className="evaluation-details"><summary>View raw evaluation JSON (technical)</summary><pre>{JSON.stringify(card, null, 2)}</pre></details><p>Results are read directly from the backend's saved evaluation card; they are not illustrative dashboard values.</p></article></section>
      <section className="explanation-card evaluation-limitations"><span className="tiny-heading">SAFETY AND GENERALIZATION LIMITS</span><h2>Before using these results</h2><ul>{card.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>No live plant connection, approved safety thresholds, validated hazard probabilities or actuator control are provided by these models.</p></section>
    </>}
    <footer><span>SentinelTwin · model evaluation</span><span>Simulation evidence only · no operational safety guarantee</span></footer>
  </main>
}
