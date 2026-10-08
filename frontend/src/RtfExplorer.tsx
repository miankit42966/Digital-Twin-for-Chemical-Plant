import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import ProcessMap from './ProcessMap'
import PressureChart from './PressureChart'
import type { Asset, DashboardMode, RtfFrame, RtfOptions, RtfSnapshot } from './types'
import './rtf.css'
import './snapshot.css'

const PlantScene = lazy(() => import('./PlantScene'))

function RtfSnapshotReport({ report, onClose }: { report: RtfSnapshot; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const node = dialog.current!
    node.showModal()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { node.close(); document.body.style.overflow = previous }
  }, [])
  const { state } = report
  const filename = `tep-rtf-${state.case_id}-run-${state.simulation_id}-sample-${state.sample_index}`
  function downloadJson() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url; link.download = `${filename}.json`; link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  function printReport() {
    const title = document.title
    document.title = filename
    try { window.print() } finally { document.title = title }
  }
  return <dialog ref={dialog} className="snapshot-dialog" aria-labelledby="rtf-snapshot-title" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <article className="snapshot-report" data-source="TEP_RTF" data-sample={state.sample_index}>
      <div className="snapshot-toolbar"><span>SIMULATED RUN-TO-FAILURE SNAPSHOT</span><div><button type="button" className="control-button" onClick={printReport}>Print / Save as PDF</button><button type="button" className="snapshot-close" onClick={onClose}>Close report</button></div></div>
      <header className="snapshot-heading"><span className="tiny-heading">SENTINELTWIN / RESEARCH DATA</span><h1 id="rtf-snapshot-title">{state.case_id} · Run {state.simulation_id} · Sample {state.sample_index}</h1><p>Fixed sample captured from published simulation. This report is not live telemetry or a safety alert.</p></header>
      <section className="snapshot-section"><h2>Trajectory and forecast</h2><dl className="snapshot-facts"><div><dt>Simulated time</dt><dd>{state.time_hours.toFixed(2)} h</dd></div><div><dt>Estimated time to shutdown</dt><dd>{state.prognosis.remaining_minutes == null ? 'Unavailable' : `${state.prognosis.remaining_minutes.toFixed(1)} min`}</dd></div><div><dt>Next equipment</dt><dd>{state.prognosis.next_unit_id ?? 'Unassessed'}</dd></div><div><dt>Equipment warning</dt><dd>{state.prognosis.highlight_unit_id ?? 'None'}</dd></div></dl><p>{state.prognosis.notice}</p></section>
      <section className="snapshot-section"><h2>Measured process units</h2><div className="snapshot-table-wrap"><table><thead><tr><th>Unit</th><th>Temperature °C</th><th>Pressure bar(g)</th><th>Level %</th><th>Flow (source unit)</th></tr></thead><tbody>{state.assets.map(asset => <tr key={asset.asset_id}><th scope="row">{asset.asset_name}<small>{asset.asset_id}</small></th><td>{asset.temperature_c.toFixed(2)}</td><td>{asset.pressure_bar.toFixed(3)}</td><td>{asset.level_percent.toFixed(2)}</td><td>{asset.flow_value?.toFixed(3) ?? 'N/A'}</td></tr>)}</tbody></table></div></section>
      <section className="snapshot-section snapshot-limits"><h2>Interpretation limit</h2><p>Predicted remaining time refers to a simulated process shutdown condition. No component is named unless a verified terminal-unit label supports its model. Neither result establishes physical equipment failure or proves a flow-caused failure.</p></section>
      <details className="snapshot-technical"><summary>Technical export</summary><button type="button" className="control-button" onClick={downloadJson}>Download JSON</button></details>
      <footer className="snapshot-footer">SentinelTwin · TEP_RTF · research simulation only</footer>
    </article>
  </dialog>
}

export default function RtfExplorer({ setMode }: { setMode: (mode: DashboardMode) => void }) {
  const [options, setOptions] = useState<RtfOptions | null>(null)
  const [caseId, setCaseId] = useState('')
  const [run, setRun] = useState(0)
  const [sample, setSample] = useState(21)
  const [frame, setFrame] = useState<RtfFrame | null>(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [view, setView] = useState<'3d' | 'map'>('3d')
  const [selectedId, setSelectedId] = useState('RX-201')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [snapshot, setSnapshot] = useState<RtfSnapshot | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const exportRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/tep/rtf/options', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Dataset API ${response.status}`)
      return response.json() as Promise<RtfOptions>
    }).then(value => {
      if (controller.signal.aborted) return
      if (value.source_kind !== 'TEP_RTF' || !value.cases.length) throw new Error('No RTF trajectories available')
      setOptions(value)
      const selected = value.cases.find(item => item.documented_scenario && item.runs.length) ?? value.cases.find(item => item.runs.length)
      if (!selected) throw new Error('No usable RTF run found')
      setCaseId(selected.id); setRun(selected.runs[0].id); setSample(Math.min(21, selected.runs[0].samples))
      setError(null)
    }).catch(value => { if (!controller.signal.aborted) setError(`Run-to-failure dataset unavailable: ${String(value)}`) })
    return () => controller.abort()
  }, [retry])

  useEffect(() => {
    exportRequest.current?.abort('Selection changed')
    exportRequest.current = null
    setExporting(false); setExportError(null); setSnapshot(null)
    return () => {
      exportRequest.current?.abort('Selection changed')
      exportRequest.current = null
    }
  }, [caseId, run, sample])

  const currentCase = options?.cases.find(item => item.id === caseId)
  const currentRun = currentCase?.runs.find(item => item.id === run)
  const totalSamples = currentRun?.samples ?? 1
  useEffect(() => {
    if (!caseId || !run || !currentRun) return
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    setLoading(true)
    fetch(`/api/v1/tep/rtf/frame?case=${encodeURIComponent(caseId)}&run=${run}&sample=${sample}&points=90`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Frame API ${response.status}`)
      return response.json() as Promise<RtfFrame>
    }).then(value => {
      if (controller.signal.aborted) return
      if (value.state.source_kind !== 'TEP_RTF' || value.history.source_kind !== 'TEP_RTF'
        || value.state.case_id !== caseId || value.state.simulation_id !== run || value.state.sample_index !== sample
        || value.history.case_id !== caseId || value.history.simulation_id !== run || value.history.end_sample !== sample) throw new Error('Unexpected trajectory frame')
      setFrame(value); setError(null); setLoading(false)
    }).catch(value => {
      if (!controller.signal.aborted || controller.signal.reason === 'Request timeout') {
        setError(`RTF frame unavailable: ${String(value)}`); setPlaying(false); setLoading(false)
      }
    }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [caseId, run, sample, currentRun, retry])

  const actual = frame?.state.case_id === caseId && frame.state.simulation_id === run ? frame : null
  const committed = actual?.state.sample_index === sample
  useEffect(() => {
    if (!playing || !committed || loading || error) return
    if (sample >= totalSamples) { setPlaying(false); return }
    const timer = window.setTimeout(() => setSample(value => value + 1), 2000 / speed)
    return () => window.clearTimeout(timer)
  }, [playing, committed, loading, error, sample, totalSamples, speed])

  function selectCase(value: string) {
    const next = options?.cases.find(item => item.id === value)
    if (!next?.runs.length) return
    setPlaying(false); setFrame(null); setSnapshot(null); setCaseId(value)
    setRun(next.runs[0].id); setSample(Math.min(21, next.runs[0].samples))
  }
  function selectRun(value: number) {
    const next = currentCase?.runs.find(item => item.id === value)
    if (!next) return
    setPlaying(false); setFrame(null); setSnapshot(null); setRun(value); setSample(Math.min(21, next.samples))
  }
  function togglePlayback() {
    if (playing) { setPlaying(false); if (actual) setSample(actual.state.sample_index) }
    else { if (sample >= totalSamples) setSample(1); setPlaying(true) }
  }
  async function exportSnapshot() {
    if (!actual || exporting || exportRequest.current) return
    setPlaying(false); setExporting(true)
    setExportError(null)
    const expected = actual.state
    const controller = new AbortController()
    exportRequest.current = controller
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    try {
      const response = await fetch(`/api/v1/report?source=rtf&case=${encodeURIComponent(expected.case_id)}&run=${expected.simulation_id}&sample=${expected.sample_index}`, { signal: controller.signal })
      if (!response.ok) throw new Error(`Report API ${response.status}`)
      const value = await response.json() as RtfSnapshot
      if (controller.signal.aborted || exportRequest.current !== controller) return
      if (value.source_kind !== 'TEP_RTF' || value.state.case_id !== expected.case_id || value.state.simulation_id !== expected.simulation_id || value.state.sample_index !== expected.sample_index) throw new Error('Report sample mismatch')
      setSnapshot(value)
    } catch (value) {
      if (exportRequest.current === controller && (!controller.signal.aborted || controller.signal.reason === 'Request timeout')) setExportError(`Snapshot unavailable: ${String(value)}`)
    } finally {
      window.clearTimeout(timeout)
      if (exportRequest.current === controller) { exportRequest.current = null; setExporting(false) }
    }
  }

  const state = actual?.state
  const assets = state?.assets ?? []
  const selected: Asset | undefined = assets.find(asset => asset.asset_id === selectedId) ?? assets[0]
  const forecast = state?.prognosis
  const observed = actual?.history.points.map(point => ({ minute: point.time_hours * 60, pressure: point.reactor_pressure_bar_g })) ?? []
  return <main className="dashboard dataset-dashboard rtf-dashboard">
    <header className="site-header"><div className="brand"><span className="brand-mark" aria-hidden="true">◇</span><div><span className="brand-name">SENTINELTWIN</span><span className="brand-sub">PROCESS DATA WORKBENCH</span></div></div><nav className="source-tabs" aria-label="Dataset"><button type="button" onClick={() => setMode('tep')}>TEP chemical process</button><button type="button" onClick={() => setMode('ai4i')}>AI4I maintenance</button><button type="button" className="active" aria-current="page">TEP run-to-failure</button><button type="button" onClick={() => setMode('prognosis_lab')}>Prognosis lab</button></nav><span className={`connection-pill ${error ? 'offline' : ''}`}><i />{error ? 'RTF dataset unavailable' : options ? 'RTF dataset ready' : 'Loading RTF dataset'}</span></header>
    <section className="dataset-heading"><div><span className="eyebrow">PUBLISHED SIMULATION / EQUIPMENT PROGNOSIS</span><h1>TEP run-to-failure</h1><p>Explore a recorded degradation trajectory. Estimated time means simulated process shutdown, not a real equipment breakdown.</p></div><div className="dataset-source-indicator"><strong>TEP RTF v1</strong><span>Research-only · no live plant connection</span></div></section>
    <div className="source-banner"><span className="source-badge">SEPARATE DATASET</span><span>{state?.source_notice ?? options?.source_notice ?? 'Loading official run-to-failure dataset.'}</span></div>
    {error && <div className="error-banner" role="alert"><span>{error}</span><button type="button" className="control-button" onClick={() => setRetry(value => value + 1)}>Retry</button></div>}
    <section className="dataset-controls" aria-label="Select a run-to-failure trajectory"><label>CASE<select value={caseId} onChange={event => selectCase(event.target.value)} disabled={!options}>{options?.cases.map(item => <option key={item.id} value={item.id}>{item.id}{item.documented_scenario ? '' : ' · undocumented case'}</option>)}</select></label><label>SIMULATION ID<select value={run || ''} onChange={event => selectRun(Number(event.target.value))} disabled={!currentCase}>{currentCase?.runs.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label><label>PLAYBACK SPEED<select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={.5}>0.5× slower</option><option value={1}>1× normal</option><option value={2}>2× faster</option></select></label><button type="button" className="control-button" onClick={togglePlayback} disabled={!actual || !!error}>{playing ? 'Pause stream' : sample >= totalSamples ? 'Restart stream' : 'Play stream'}</button><div className="sample-control"><label htmlFor="rtf-sample">SAMPLE <strong>{sample} / {totalSamples}</strong></label><input id="rtf-sample" type="range" min="1" max={totalSamples} value={Math.min(sample, totalSamples)} disabled={!currentRun} onChange={event => { setPlaying(false); setSample(Number(event.target.value)) }} /></div></section>
    <section className={`playback-status ${playing && committed && !loading ? 'is-playing' : ''}`} aria-label="RTF playback status" data-sample={state?.sample_index ?? ''} data-run={state?.simulation_id ?? ''} data-case={state?.case_id ?? ''}><div><i aria-hidden="true" /><strong>{playing ? 'Shutdown trajectory playback running' : 'Shutdown trajectory playback paused'}</strong><span>{state ? `${state.case_id} · Id ${state.simulation_id} · ${state.time_hours.toFixed(2)} simulated h` : 'Waiting for dataset'}</span></div><span>{loading && state ? `Loading sample ${sample}; last committed frame remains visible` : 'Recorded sample cadence · illustrative playback speed'}</span></section>
    <section className="summary-strip" aria-label="Run-to-failure result"><div><span>TRAJECTORY</span><strong>{caseId || '—'} · {run || '—'}</strong><small>{currentCase?.documented_scenario ? 'Documented scenario' : 'Scenario mapping unverified'}</small></div><div><span>SIMULATION TIME</span><strong>{state ? `${state.time_hours.toFixed(2)} h` : '—'}</strong><small>Recorded sample time</small></div><div><span>TIME TO SHUTDOWN</span><strong>{forecast?.remaining_minutes == null ? 'Unavailable' : `${forecast.remaining_minutes.toFixed(1)} min`}</strong><small>Model estimate · simulation only</small></div><div><span>NEXT EQUIPMENT</span><strong>{forecast?.next_unit_id ?? 'Unassessed'}</strong><small>No guessed component labels</small></div></section>
    {forecast && <div className={`rtf-forecast-note ${forecast.highlight_unit_id ? 'has-warning' : ''}`} role="status"><strong>{forecast.highlight_unit_id ? `${forecast.highlight_unit_id} predicted within 1 simulated hour` : 'Equipment warning not issued'}</strong><span>{forecast.notice}</span></div>}
    <div className="snapshot-actions"><a className="rtf-evaluation-link" href="/?evaluation=tep-rtf-prognosis" target="_blank" rel="noreferrer">Run-to-failure model evaluation ↗</a><button type="button" className="control-button" onClick={exportSnapshot} disabled={!actual || exporting}>{exporting ? 'Preparing snapshot…' : 'Export displayed snapshot'}</button>{exportError && <span role="alert">{exportError}</span>}</div>
    <section className="main-layout"><div className="visual-card"><div className="section-title"><div><span className="tiny-heading">PROCESS TOPOLOGY</span><h2>Recorded equipment and predicted warning</h2></div><div className="view-tabs" role="group" aria-label="Process view"><button type="button" className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')} aria-pressed={view === '3d'}>3D plant</button><button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')} aria-pressed={view === 'map'}>2D flow</button></div></div>{view === '3d' ? <Suspense fallback={<div className="scene scene-loading" role="status">Loading 3D view…</div>}><PlantScene assets={assets} selectedId={selected?.asset_id ?? null} select={asset => setSelectedId(asset.asset_id)} playing={playing && !!state && !loading} speed={speed} highlightUnitId={forecast?.highlight_unit_id ?? null} /></Suspense> : <ProcessMap assets={assets} selectedId={selected?.asset_id ?? null} onSelect={setSelectedId} pressureUnit="bar(g)" playing={playing && !!state && !loading} speed={speed} highlightUnitId={forecast?.highlight_unit_id ?? null} />}</div><aside className="inspector-card"><span className="tiny-heading">SELECTED PROCESS UNIT</span>{selected ? <><div className="inspector-head"><div><h2>{selected.asset_name}</h2><span>{selected.asset_id}</span></div><span className={`status-chip ${forecast?.highlight_unit_id === selected.asset_id ? 'forecast-warning' : ''}`}>{forecast?.highlight_unit_id === selected.asset_id ? 'PREDICTED ≤1 H' : 'UNASSESSED'}</span></div><div className="metric-grid"><div><span>TEMPERATURE</span><strong>{selected.temperature_c.toFixed(1)} <small>°C</small></strong></div><div><span>PRESSURE</span><strong>{selected.pressure_bar.toFixed(2)} <small>bar(g)</small></strong></div><div><span>LEVEL</span><strong>{selected.level_percent.toFixed(1)} <small>%</small></strong></div><div><span>FLOW</span><strong>{selected.flow_value?.toFixed(2) ?? 'N/A'} <small>{selected.flow_unit}</small></strong></div></div><div className="inspector-note"><strong>SOURCE AND LIMITS</strong><p>Measurements come from the separate run-to-failure simulation. Flow units and terminal equipment labels must be verified against source documentation.</p><p>Amber means a model forecast within one simulated hour, never an operational alarm. No physical failure cause is inferred.</p></div></> : <p className="empty-state">Loading a recorded process sample.</p>}</aside></section>
    <section className="analysis-layout">{observed.length ? <PressureChart title="Recorded reactor pressure" caption="Published run-to-failure simulation samples; no real plant threshold or future pressure value is claimed." observed={observed} projected={[]} /> : <section className="chart-panel empty-chart"><h3>Recorded pressure history</h3><p>Select a run and sample above.</p></section>}<section className="explanation-card"><span className="tiny-heading">READ THE FORECAST</span><h2>What “about to fail” means here</h2><p>The remaining-time model estimates when this simulated trajectory reaches its process shutdown endpoint. An equipment name is shown only if independent terminal-unit labels support a validated classifier.</p><p>Original TEP fault-score and +20-minute pressure models remain separate; they do not determine this warning.</p></section></section>
    <footer><span>SentinelTwin · TEP run-to-failure research view</span><span>Simulation evidence only · no plant control or safety guarantee</span></footer>
    {snapshot && <RtfSnapshotReport report={snapshot} onClose={() => setSnapshot(null)} />}
  </main>
}
