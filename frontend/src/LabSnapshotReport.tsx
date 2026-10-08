import { useEffect, useRef } from 'react'
import type { LabSnapshot } from './types'
import './snapshot.css'

export default function LabSnapshotReport({ report, onClose }: { report: LabSnapshot; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close() }, [])
  const state = report.state
  function downloadJson() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = `synthetic-prognosis-run-${state.run_id}-sample-${state.sample_index}.json`; link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <dialog ref={dialog} className="snapshot-dialog" aria-labelledby="lab-snapshot-title" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <article className="snapshot-report" data-source={state.source_kind} data-sample={state.sample_index}>
      <div className="snapshot-toolbar"><span>SYNTHETIC PROGNOSIS SNAPSHOT</span><div><button type="button" className="control-button" onClick={() => window.print()}>Print / Save as PDF</button><button type="button" className="snapshot-close" onClick={onClose}>Close report</button></div></div>
      <header className="snapshot-heading"><span className="tiny-heading">SENTINELTWIN / LABELLED DYNAMIC SURROGATE</span><h1 id="lab-snapshot-title">Run {state.run_id} · Sample {state.sample_index}</h1><p>Fixed research snapshot. These are generated trajectories and labels, not official TEP RTF or physical-plant observations.</p></header>
      <section className="snapshot-section"><h2>Forecast</h2><dl className="snapshot-facts"><div><dt>Failure within 60 min</dt><dd>{state.prognosis.failure_within_horizon_probability == null ? 'Unavailable' : `${(state.prognosis.failure_within_horizon_probability * 100).toFixed(1)}%`}</dd></div><div><dt>Estimated RUL</dt><dd>{state.prognosis.remaining_minutes == null ? 'Abstained' : `${state.prognosis.remaining_minutes.toFixed(1)} min`}</dd></div><div><dt>Predicted equipment</dt><dd>{state.prognosis.predicted_equipment_id ?? 'Abstained'}</dd></div><div><dt>Predicted mode</dt><dd>{state.prognosis.predicted_failure_mode?.replace(/_/g, ' ') ?? 'Abstained'}</dd></div></dl><p>{state.prognosis.notice}</p></section>
      <section className="snapshot-section"><h2>Generated equipment readings</h2><div className="snapshot-table-wrap"><table><thead><tr><th>Equipment</th><th>Temperature</th><th>Pressure</th><th>Level</th><th>Flow / performance</th></tr></thead><tbody>{state.assets.map(asset => <tr key={asset.asset_id}><th>{asset.asset_name}<small>{asset.asset_id}</small></th><td>{asset.temperature_c?.toFixed(1) ?? 'N/A'} °C</td><td>{asset.pressure_bar?.toFixed(2) ?? 'N/A'} bar</td><td>{asset.level_percent?.toFixed(1) ?? 'N/A'}{asset.level_percent == null ? '' : '%'}</td><td>{asset.performance_percent != null ? `${asset.performance_percent.toFixed(1)}%` : asset.work_kw != null ? `${asset.work_kw.toFixed(1)} kW` : `${asset.flow_value?.toFixed(1) ?? 'N/A'} ${asset.flow_unit ?? ''}`}</td></tr>)}</tbody></table></div></section>
      {state.observed_outcome && <section className="snapshot-section"><h2>Observed synthetic outcome</h2><p>{state.observed_outcome.censored ? 'Healthy/censored run completed without an injected terminal failure.' : `${state.observed_outcome.failed_equipment_id} reached the generated ${state.observed_outcome.failure_mode?.replace(/_/g, ' ')} terminal condition.`}</p></section>}
      <section className="snapshot-section snapshot-limits"><h2>Safety boundary</h2><p>Amber is a synthetic benchmark forecast. It is not a real alarm and cannot authorize plant action.</p></section>
      <details className="snapshot-technical"><summary>Technical export</summary><button type="button" className="control-button" onClick={downloadJson}>Download JSON</button></details>
    </article>
  </dialog>
}
