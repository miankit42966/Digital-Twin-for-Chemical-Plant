import { useEffect, useRef } from 'react'
import PressureChart from './PressureChart'
import type { SnapshotData } from './types'
import './snapshot.css'

export default function SnapshotReport({ report, onClose }: { report: SnapshotData; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    closeButton.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { element.close(); document.body.style.overflow = previousOverflow }
  }, [])
  const tep = report.source_kind === 'TEP_DATASET' ? report : null
  const ai = report.source_kind === 'AI4I_DATASET' ? report : null
  const title = tep ? `TEP snapshot · Sample ${tep.state.sample_index}` : `AI4I snapshot · UDI ${ai!.record.udi}`
  const filename = tep ? `tep-${tep.state.dataset_partition}-fault-${tep.state.fault_number}-run-${tep.state.simulation_run}-sample-${tep.state.sample_index}` : `ai4i-udi-${ai!.record.udi}`
  const observed = tep?.history.points.map(point => ({ minute: point.elapsed_minutes, pressure: point.reactor_pressure_bar_g })) ?? []
  const last = observed[observed.length - 1]
  const projected = last && tep?.state.reactor_pressure_20m_bar_g != null ? [last, { minute: last.minute + 20, pressure: tep.state.reactor_pressure_20m_bar_g }] : []
  function downloadJson() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = `${filename}.json`; link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  function printReport() {
    const previousTitle = document.title
    document.title = filename
    try { window.print() } finally { document.title = previousTitle }
  }
  return <dialog ref={dialog} className="snapshot-dialog" aria-labelledby="snapshot-title" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <article className="snapshot-report" data-source={report.source_kind} data-sample={tep?.state.sample_index ?? ai?.record.udi}>
      <div className="snapshot-toolbar"><span>READABLE SNAPSHOT REPORT</span><div><button type="button" className="control-button" onClick={printReport}>Print / Save as PDF</button><button ref={closeButton} type="button" className="snapshot-close" onClick={onClose}>Close report</button></div></div>
      <header className="snapshot-heading"><span className="tiny-heading">SENTINELTWIN / PUBLISHED BENCHMARK DATA</span><h1 id="snapshot-title">{title}</h1><p>This report is fixed to the displayed sample captured when you clicked Export. It does not update with playback.</p></header>
      {tep && <>
        <section className="snapshot-section"><h2>Selected process sample</h2><dl className="snapshot-facts"><div><dt>Partition / run</dt><dd>{tep.state.dataset_partition} / {tep.state.simulation_run}</dd></div><div><dt>Published fault scenario</dt><dd>{tep.state.fault_number}</dd></div><div><dt>Sample / total</dt><dd>{tep.state.sample_index} / {tep.state.total_samples}</dd></div><div><dt>Simulation time</dt><dd>{tep.state.elapsed_minutes} min</dd></div></dl><p>{tep.state.source_notice}</p><p>Report generated: {new Date(tep.state.generated_at).toLocaleString()} · {tep.state.sample_period_minutes} simulated min per sample.</p></section>
        <section className="snapshot-section"><h2>Measured equipment readings</h2><div className="snapshot-table-wrap"><table><caption>Published TEP measurements; all equipment status is unassessed.</caption><thead><tr><th>Equipment</th><th>Temperature °C</th><th>Pressure bar(g)</th><th>Level %</th><th>Flow (source unit)</th></tr></thead><tbody>{tep.state.assets.map(asset => <tr key={asset.asset_id}><th scope="row">{asset.asset_name}<small>{asset.asset_id}</small></th><td>{asset.temperature_c.toFixed(1)}</td><td>{asset.pressure_bar.toFixed(3)}</td><td>{asset.level_percent.toFixed(1)}</td><td>{asset.flow_value?.toFixed(3) ?? 'Unavailable'} {asset.flow_unit}</td></tr>)}</tbody></table></div></section>
        <section className="snapshot-section"><h2>Research model outputs</h2><dl className="snapshot-facts"><div><dt>Current fault score</dt><dd>{tep.state.detector_score == null ? 'Unavailable' : `${(tep.state.detector_score * 100).toFixed(1)}%`}</dd></div><div><dt>Reactor pressure +20 min</dt><dd>{tep.state.reactor_pressure_20m_bar_g == null ? 'Unavailable' : `${tep.state.reactor_pressure_20m_bar_g.toFixed(3)} bar(g)`}</dd></div></dl><p>The fault score describes the current simulated sample, not a calibrated failure probability. The pressure value is a regression estimate at +20 simulated minutes, not a leak or over-pressure alert.</p>{Object.entries(tep.state.model_notices).map(([kind, notice]) => <p key={kind}>{kind === 'pressure' ? 'Pressure model' : 'Fault detector'}: {notice}</p>)}</section>
        {tep.state.detector_explanation && <section className="snapshot-section"><h2>Current-sample detector sensitivity</h2><p>One feature at a time was replaced with its training-set median. The resulting score changes are not causal explanations or calibrated uncertainty.</p><dl className="snapshot-facts">{tep.state.detector_explanation.top_positive_factors.map(factor => <div key={`positive-${factor.feature}`}><dt>{factor.feature} raises score</dt><dd>+{(factor.score_delta * 100).toFixed(1)} points</dd></div>)}{tep.state.detector_explanation.top_negative_factors.map(factor => <div key={`negative-${factor.feature}`}><dt>{factor.feature} lowers score</dt><dd>{(factor.score_delta * 100).toFixed(1)} points</dd></div>)}</dl><p>{tep.state.detector_explanation.disclaimer}</p></section>}
        {observed.length > 0 && <PressureChart title="Recorded reactor pressure history" caption="Solid: published samples ending at this snapshot. Dashed: one +20 simulated-minute estimate. No site-approved safety threshold is applied." observed={observed} projected={projected} />}
      </>}
      {ai && <>
        <section className="snapshot-section"><h2>Selected maintenance record</h2><dl className="snapshot-facts"><div><dt>UDI / product</dt><dd>{ai.record.udi} / {ai.record.product_id}</dd></div><div><dt>Product type</dt><dd>{ai.record.type}</dd></div><div><dt>Published failure label</dt><dd>{ai.record.machine_failure ? 'Yes' : 'No'}</dd></div><div><dt>Dataset records</dt><dd>{ai.summary.total_records.toLocaleString()}</dd></div></dl><p>{ai.summary.notice}</p></section>
        <section className="snapshot-section"><h2>Published measurements</h2><dl className="snapshot-facts"><div><dt>Air temperature</dt><dd>{ai.record.air_temperature_k} K</dd></div><div><dt>Process temperature</dt><dd>{ai.record.process_temperature_k} K</dd></div><div><dt>Rotational speed</dt><dd>{ai.record.rotational_speed_rpm} rpm</dd></div><div><dt>Torque</dt><dd>{ai.record.torque_nm} Nm</dd></div><div><dt>Tool wear</dt><dd>{ai.record.tool_wear_min} min</dd></div></dl><p>Published failure-mode indicators: TWF {ai.record.twf} · HDF {ai.record.hdf} · PWF {ai.record.pwf} · OSF {ai.record.osf} · RNF {ai.record.rnf}.</p><p>These are benchmark labels, not model predictions. AI4I machining records are separate from TEP chemical-process simulation.</p></section>
      </>}
      <section className="snapshot-section snapshot-limits"><h2>Source and safety limits</h2><p>This is recorded simulation/benchmark data, not live plant telemetry. No operational safety guarantee, validated future-failure probability or real actuator control is provided. Unsupported gas and binary valve readings are not invented.</p></section>
      <details className="snapshot-technical"><summary>Technical data export (optional)</summary><p>JSON is intended for analysis and software integration, not the readable report.</p><button type="button" className="control-button" onClick={downloadJson}>Download technical JSON</button></details>
      <footer className="snapshot-footer">SentinelTwin · {report.source_kind} · fixed benchmark snapshot</footer>
    </article>
  </dialog>
}
