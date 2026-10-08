import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import ProcessMap from './ProcessMap'
import PressureChart from './PressureChart'
import SnapshotReport from './SnapshotReport'
import RtfExplorer from './RtfExplorer'
import PrognosisLab from './PrognosisLab'
import './playback.css'
import type { Ai4iFrame, Ai4iRecord, Ai4iSummary, DashboardMode, DatasetFrame, PlantState, ReplaySeries, SnapshotData } from './types'

// Three.js is only needed for the optional 3D topology view. Loading it on
// demand keeps the dataset explorer responsive, including the AI4I-only view.
const PlantScene = lazy(() => import('./PlantScene'))

const api = ''
const faultNumbers = Array.from({ length: 21 }, (_, index) => index)
const runNumbers = Array.from({ length: 500 }, (_, index) => index + 1)

function DatasetJourney({ playing }: { playing: boolean }) {
  const stages = [
    ['01', 'Published dataset', 'Local TEP Parquet, not a plant connection'],
    ['02', 'Selected trajectory', 'Partition, fault scenario and run'],
    ['03', 'Measured variables', '52 TEP process variables per sample'],
    ['04', 'Equipment view', 'Mapped sensors on three measured units'],
    ['05', 'Research models', 'Current fault score and +20 min pressure'],
  ]
  return <section className={`dataset-journey ${playing ? 'is-playing' : ''}`} aria-label="How the data reaches this dashboard">{stages.map(([number, label, detail], index) => <div key={number} style={{ animationDelay: `${index * .35}s` }}><b>{number}</b><strong>{label}</strong><span>{detail}</span></div>)}</section>
}

function Ai4iExplorer({ summary, record, neighbors, udi, setUdi, error, onRetry }: {
  summary: Ai4iSummary | null; record: Ai4iRecord | null; neighbors: Ai4iRecord[];
  udi: number; setUdi: (value: number) => void; error: string | null; onRetry: () => void;
}) {
  const failureRate = summary ? (summary.failure_records / summary.total_records * 100).toFixed(2) : '—'
  return <>
    <div className="source-banner"><span className="source-badge">AI4I 2020 DATASET</span><span>{summary?.notice ?? 'Loading local AI4I benchmark.'}</span></div>
    {error && <div className="error-banner" role="alert">{error}<button type="button" className="control-button" onClick={onRetry}>Retry dataset</button></div>}
    <section className="summary-strip" aria-label="AI4I dataset summary">
      <div><span>RECORDS</span><strong>{summary?.total_records.toLocaleString() ?? '—'}</strong><small>Published rows</small></div>
      <div><span>FAILURE LABELS</span><strong>{summary?.failure_records ?? '—'}</strong><small>Observed labels in benchmark</small></div>
      <div><span>FAILURE LABEL RATE</span><strong>{failureRate}%</strong><small>Not a predicted risk</small></div>
      <div><span>SELECTED UDI</span><strong>{record?.udi ?? '—'}</strong><small>{record?.product_id ?? 'Choose a record'}</small></div>
    </section>
    <section className="ai4i-layout"><div className="visual-card ai4i-main">
      <span className="tiny-heading">AI4I / ROW EXPLORER</span><h2>Machine observations</h2>
      <p className="dataset-intro">This is a machining predictive-maintenance benchmark. Its rows are shown exactly as published; they are not chemical-plant vessels or live sensor readings.</p>
      <div className="record-nav"><button type="button" onClick={() => setUdi(Math.max(1, udi - 1))} disabled={udi === 1}>Previous row</button><label htmlFor="udi-seek">UDI <strong>{udi}</strong></label><input id="udi-seek" type="range" min="1" max="10000" value={udi} onChange={event => setUdi(Number(event.target.value))} /><button type="button" onClick={() => setUdi(Math.min(10000, udi + 1))} disabled={udi === 10000}>Next row</button></div>
      <div className="ai4i-table-wrap"><table><thead><tr><th>UDI</th><th>Product</th><th>Type</th><th>Air K</th><th>Process K</th><th>RPM</th><th>Torque Nm</th><th>Failure label</th></tr></thead><tbody>{neighbors.map(row => <tr key={row.udi} className={row.udi === udi ? 'selected' : ''}><td><button type="button" className="record-link" onClick={() => setUdi(row.udi)} aria-label={`Inspect UDI ${row.udi}`} aria-current={row.udi === udi ? 'true' : undefined}>{row.udi}</button></td><td>{row.product_id}</td><td>{row.type}</td><td>{row.air_temperature_k}</td><td>{row.process_temperature_k}</td><td>{row.rotational_speed_rpm}</td><td>{row.torque_nm}</td><td>{row.machine_failure ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div>
    </div><aside className="inspector-card"><span className="tiny-heading">SELECTED PUBLISHED RECORD</span>{record ? <><div className="inspector-head"><div><h2>{record.product_id}</h2><span>UDI {record.udi} · Type {record.type}</span></div><span className={`status-chip ${record.machine_failure ? 'warning' : ''}`}>{record.machine_failure ? 'FAILURE LABEL' : 'NO FAILURE LABEL'}</span></div><div className="metric-grid"><div><span>AIR TEMPERATURE</span><strong>{record.air_temperature_k} <small>K</small></strong></div><div><span>PROCESS TEMPERATURE</span><strong>{record.process_temperature_k} <small>K</small></strong></div><div><span>ROTATIONAL SPEED</span><strong>{record.rotational_speed_rpm} <small>rpm</small></strong></div><div><span>TORQUE</span><strong>{record.torque_nm} <small>Nm</small></strong></div><div><span>TOOL WEAR</span><strong>{record.tool_wear_min} <small>min</small></strong></div></div><div className="inspector-note"><strong>PUBLISHED FAILURE-MODE LABELS</strong><p>TWF {record.twf} · HDF {record.hdf} · PWF {record.pwf} · OSF {record.osf} · RNF {record.rnf}</p><p>These are dataset labels, not a model's predictions or a safety alarm.</p></div></> : <p className="empty-state">Loading selected record…</p>}</aside></section>
    <section className="explanation-card ai4i-explanation"><span className="tiny-heading">DATASET BOUNDARY</span><h2>Why this is a separate view</h2><p>AI4I provides 10,000 machining equipment records and known failure labels. TEP provides chemical-process simulation trajectories. Their assets, units and targets differ, so this dashboard does not merge them into one fictional plant stream.</p>{summary && <p>Product types: L {summary.product_types.L.toLocaleString()}, M {summary.product_types.M.toLocaleString()}, H {summary.product_types.H.toLocaleString()}. Failure-mode counts can overlap; they are not additive equipment-failure counts.</p>}</section>
  </>
}

export default function App() {
  const [mode, setMode] = useState<DashboardMode>('tep')
  const [view, setView] = useState<'map' | '3d'>('3d')
  const [partition, setPartition] = useState<'training' | 'testing'>('testing')
  const [fault, setFault] = useState(6)
  const [run, setRun] = useState(401)
  const [sample, setSample] = useState(170)
  const [playing, setPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<PlantState | null>(null)
  const stateRef = useRef<PlantState | null>(null)
  const [previousState, setPreviousState] = useState<PlantState | null>(null)
  const [series, setSeries] = useState<ReplaySeries | null>(null)
  const [selectedId, setSelectedId] = useState('RX-201')
  const [ai4iSummary, setAi4iSummary] = useState<Ai4iSummary | null>(null)
  const [ai4iRecord, setAi4iRecord] = useState<Ai4iRecord | null>(null)
  const [ai4iNeighbors, setAi4iNeighbors] = useState<Ai4iRecord[]>([])
  const [udi, setUdi] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [snapshotReport, setSnapshotReport] = useState<SnapshotData | null>(null)
  const exportRequest = useRef<AbortController | null>(null)
  const [connection, setConnection] = useState('Loading local dataset…')
  const totalSamples = partition === 'testing' ? 960 : 500

  useEffect(() => {
    if (mode === 'tep') document.title = 'TEP chemical process | SentinelTwin'
    else if (mode === 'ai4i') document.title = 'AI4I maintenance | SentinelTwin'
    else if (mode === 'prognosis_lab') document.title = 'Equipment prognosis lab | SentinelTwin'
    else document.title = 'TEP run-to-failure | SentinelTwin'
  }, [mode])

  function cancelExport() {
    exportRequest.current?.abort('Selection changed')
    exportRequest.current = null
    setExporting(false); setExportError(null)
  }
  useEffect(() => {
    cancelExport()
    return () => { exportRequest.current?.abort('Selection changed'); exportRequest.current = null }
  }, [mode, partition, fault, run, udi])

  useEffect(() => {
    if (mode !== 'tep') return
    const cached = stateRef.current
    if (!error && cached?.dataset_partition === partition && cached.fault_number === fault && cached.simulation_run === run && cached.sample_index === sample) { setLoading(false); setConnection('TEP dataset ready'); return }
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    const query = `partition=${partition}&fault=${fault}&run=${run}`
    setLoading(true)
    fetch(`${api}/api/v1/tep/dataset/frame?sample=${sample}&points=90&${query}`, { signal: controller.signal })
    .then(async response => {
      if (!response.ok) throw new Error(`Dataset API ${response.status}`)
      return response.json() as Promise<DatasetFrame>
    }).then(({ state: snapshot, history }) => {
      if (controller.signal.aborted) return
      if (snapshot.source_kind !== 'TEP_DATASET' || history.source_kind !== 'TEP_DATASET'
        || snapshot.dataset_partition !== partition || snapshot.fault_number !== fault || snapshot.simulation_run !== run || snapshot.sample_index !== sample
        || history.dataset_partition !== partition || history.fault_number !== fault || history.simulation_run !== run || history.end_sample !== sample) throw new Error('Unexpected dataset sample')
      setPreviousState(stateRef.current); stateRef.current = snapshot
      setState(snapshot); setSeries(history); setError(null); setConnection('TEP dataset ready'); setLoading(false)
    }).catch(errorValue => {
      if (!controller.signal.aborted || controller.signal.reason === 'Request timeout') { setError(`TEP dataset could not be read: ${controller.signal.reason === 'Request timeout' ? 'Request timed out. Retry when the API is available.' : String(errorValue)}`); setConnection('Dataset unavailable'); setPlaying(false); setLoading(false) }
    }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [mode, partition, fault, run, sample, retry])

  useEffect(() => {
    if (mode !== 'tep' || !playing || loading || state?.sample_index !== sample) return
    if (sample >= totalSamples) { setPlaying(false); return }
    const timer = window.setTimeout(() => setSample(previous => previous + 1), 2000 / playbackSpeed)
    return () => window.clearTimeout(timer)
  }, [mode, playing, loading, state, sample, totalSamples, playbackSpeed])

  useEffect(() => {
    if (mode !== 'ai4i') return
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    fetch(`${api}/api/v1/ai4i/frame?udi=${udi}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`API ${response.status}`)
      return response.json() as Promise<Ai4iFrame>
    }).then(({ source_kind, summary, record, neighbors }) => {
      if (controller.signal.aborted) return
      if (source_kind !== 'AI4I_DATASET' || summary.source_kind !== 'AI4I_DATASET' || record.source_kind !== 'AI4I_DATASET' || neighbors.source_kind !== 'AI4I_DATASET' || record.udi !== udi) throw new Error('Unexpected AI4I source or UDI')
      setAi4iSummary(summary); setAi4iRecord(record); setAi4iNeighbors(neighbors.records); setError(null)
    }).catch(errorValue => {
      if (!controller.signal.aborted || controller.signal.reason === 'Request timeout') setError(`AI4I record unavailable: ${String(errorValue)}`)
    }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [mode, udi, retry])

  // Keep the last committed frame while the next sample is fetched. A new
  // trajectory still clears immediately, so readings never cross runs.
  const actual = state?.source_kind === 'TEP_DATASET' && state.dataset_partition === partition && state.fault_number === fault && state.simulation_run === run ? state : null
  const history = series?.source_kind === 'TEP_DATASET' && series.dataset_partition === partition && series.fault_number === fault && series.simulation_run === run && series.end_sample === actual?.sample_index ? series : null
  const previous = previousState?.dataset_partition === partition && previousState.fault_number === fault && previousState.simulation_run === run && previousState.sample_index === (actual?.sample_index ?? 0) - 1 ? previousState : null
  const assets = actual?.assets ?? []
  const selected = assets.find(asset => asset.asset_id === selectedId) ?? assets[0] ?? null
  const previousSelected = previous?.assets.find(asset => asset.asset_id === selected?.asset_id)
  const playbackActive = playing && !!actual && !error
  const measured = history?.points.map(point => ({ minute: point.elapsed_minutes, pressure: point.reactor_pressure_bar_g })) ?? []
  const last = measured[measured.length - 1]
  const estimate = last && actual?.reactor_pressure_20m_bar_g != null ? [last, { minute: last.minute + 20, pressure: actual.reactor_pressure_20m_bar_g }] : []
  const connectionText = error ? 'Dataset unavailable' : mode === 'tep' ? connection : ai4iRecord?.udi === udi ? 'AI4I dataset ready' : 'Loading AI4I record…'
  function togglePlayback() {
    cancelExport()
    if (playing) {
      if (actual?.sample_index != null && actual.sample_index !== sample) setSample(actual.sample_index)
      setPlaying(false)
    } else {
      if (sample === totalSamples) setSample(1)
      setPlaying(true)
    }
  }
  async function exportSnapshot() {
    if (exportRequest.current || exporting || (mode === 'tep' ? !actual : ai4iRecord?.udi !== udi)) return
    const expectedSource = mode === 'tep' ? 'TEP_DATASET' : 'AI4I_DATASET'
    const query = mode === 'tep' ? `source=tep&sample=${actual!.sample_index}&partition=${partition}&fault=${fault}&run=${run}` : `source=ai4i&udi=${udi}`
    setPlaying(false)
    if (mode === 'tep' && actual?.sample_index != null) setSample(actual.sample_index)
    setExporting(true); setExportError(null)
    const controller = new AbortController()
    exportRequest.current = controller
    const timeout = window.setTimeout(() => controller.abort('Request timeout'), 15000)
    try {
      const response = await fetch(`${api}/api/v1/report?${query}`, { signal: controller.signal })
      if (!response.ok) throw new Error(`Report API ${response.status}`)
      const report: SnapshotData = await response.json()
      if (controller.signal.aborted || exportRequest.current !== controller) return
      if (report.source_kind !== expectedSource) throw new Error('Unexpected report source')
      if (report.source_kind === 'TEP_DATASET' && (report.state.sample_index !== actual?.sample_index || report.history.end_sample !== actual?.sample_index || report.state.dataset_partition !== partition || report.state.fault_number !== fault || report.state.simulation_run !== run)) throw new Error('Unexpected snapshot trajectory or sample')
      if (report.source_kind === 'AI4I_DATASET' && report.record.udi !== udi) throw new Error('Unexpected snapshot UDI')
      setSnapshotReport(report)
    } catch (value) {
      if (exportRequest.current === controller && (!controller.signal.aborted || controller.signal.reason === 'Request timeout')) setExportError(`Snapshot export unavailable: ${String(value)}`)
    } finally {
      window.clearTimeout(timeout)
      if (exportRequest.current === controller) { exportRequest.current = null; setExporting(false) }
    }
  }

  if (mode === 'rtf') return <RtfExplorer setMode={setMode} />
  if (mode === 'prognosis_lab') return <PrognosisLab setMode={setMode} />

  return <main className="dashboard dataset-dashboard">
    <header className="site-header"><div className="brand"><span className="brand-mark" aria-hidden="true">◇</span><div><span className="brand-name">SENTINELTWIN</span><span className="brand-sub">PROCESS DATA WORKBENCH</span></div></div><nav className="source-tabs" aria-label="Dataset"><button type="button" className={mode === 'tep' ? 'active' : ''} onClick={() => { setMode('tep'); setError(null); setExportError(null) }}>TEP chemical process</button><button type="button" className={mode === 'ai4i' ? 'active' : ''} onClick={() => { setPlaying(false); setMode('ai4i'); setError(null); setExportError(null) }}>AI4I maintenance</button><button type="button" onClick={() => { setPlaying(false); setMode('rtf'); setError(null); setExportError(null) }}>TEP run-to-failure</button><button type="button" onClick={() => { setPlaying(false); setMode('prognosis_lab'); setError(null); setExportError(null) }}>Prognosis lab</button></nav><span className={`connection-pill ${error ? 'offline' : ''}`}><i />{connectionText}</span></header>
    <section className="dataset-heading"><div><span className="eyebrow">PUBLISHED BENCHMARK DATA / LOCAL DATASET</span><h1>{mode === 'tep' ? 'Chemical process dataset' : 'Machine maintenance dataset'}</h1><p>{mode === 'tep' ? 'Explore any published TEP run directly from the local Parquet dataset. The process view, chart and model outputs follow your selected sample.' : 'Inspect the published AI4I records separately. This machining dataset does not describe the TEP chemical plant.'}</p></div><div className="dataset-source-indicator"><strong>{mode === 'tep' ? 'TEP v1.0' : 'AI4I 2020'}</strong><span>Dataset-driven · no live plant connection</span></div></section>

    <div className="snapshot-actions"><button type="button" className="control-button" onClick={exportSnapshot} disabled={exporting || !!error || (mode === 'tep' ? !actual : ai4iRecord?.udi !== udi)}>{exporting ? 'Preparing snapshot…' : 'Export displayed snapshot'}</button>{exportError && <span role="alert">{exportError}</span>}</div>
    {mode === 'ai4i' ? <Ai4iExplorer summary={ai4iSummary} record={ai4iRecord?.udi === udi ? ai4iRecord : null} neighbors={ai4iRecord?.udi === udi ? ai4iNeighbors : []} udi={udi} setUdi={setUdi} error={error} onRetry={() => setRetry(value => value + 1)} /> : <>
      <div className="source-banner"><span className="source-badge">TEP DATASET / PUBLISHED SIMULATION</span><span>{actual?.source_notice ?? 'Selecting a trajectory from local Parquet. This is not live plant sensor data.'}</span></div>
      {error && <div className="error-banner" role="alert">{error}<button type="button" className="control-button" onClick={() => setRetry(value => value + 1)} disabled={loading}>Retry dataset</button></div>}
      <section className="dataset-controls" aria-label="Select a published TEP trajectory">
        <label>PARTITION<select value={partition} onChange={event => { const next = event.target.value as 'training' | 'testing'; setPartition(next); setSample(value => Math.min(value, next === 'testing' ? 960 : 500)); setPlaying(false) }}><option value="testing">Testing · 960 samples</option><option value="training">Training · 500 samples</option></select></label>
        <label>FAULT SCENARIO<select value={fault} onChange={event => { setFault(Number(event.target.value)); setPlaying(false) }}>{faultNumbers.map(number => <option value={number} key={number}>{number === 0 ? '0 · Fault-free' : `${number} · Published fault ${number}`}</option>)}</select></label>
        <label>SIMULATION RUN<select value={run} onChange={event => { setRun(Number(event.target.value)); setPlaying(false) }}>{runNumbers.map(number => <option value={number} key={number}>{number}</option>)}</select></label>
        <label>PLAYBACK SPEED<select value={playbackSpeed} onChange={event => setPlaybackSpeed(Number(event.target.value))}><option value={.5}>0.5× · slower</option><option value={1}>1× · normal</option><option value={2}>2× · faster</option></select></label>
        <button type="button" className="control-button" onClick={togglePlayback} disabled={!!error || !actual} aria-pressed={playing}>{playing ? 'Pause stream' : sample === totalSamples ? 'Restart stream' : 'Play stream'}</button>
        <div className="sample-control"><label htmlFor="sample-seek">SAMPLE <strong>{sample} / {totalSamples}</strong></label><input id="sample-seek" type="range" min="1" max={totalSamples} value={sample} onChange={event => { cancelExport(); setPlaying(false); setSample(Number(event.target.value)) }} /></div>
      </section>
      <section className={`playback-status ${playbackActive ? 'is-playing' : ''}`} aria-label="Playback status" data-sample={actual?.sample_index ?? ''} data-run={actual?.simulation_run ?? ''} data-fault={actual?.fault_number ?? ''} data-partition={actual?.dataset_partition ?? ''}>
        <div><i aria-hidden="true" /><strong>{error ? 'Playback stopped' : !actual ? 'Loading trajectory' : sample === totalSamples && !playing ? 'Run complete' : playbackActive ? 'Process playback running' : 'Process playback paused'}</strong><span>{actual ? `Showing sample ${actual.sample_index} · ${actual.elapsed_minutes} simulated min` : 'Waiting for dataset'}</span></div>
        <span>{loading && actual ? `Loading sample ${sample}… keeping the last frame visible` : `3 simulated min per sample · ${2 / playbackSpeed}s minimum between updates`}</span>
        <div className="playback-progress" aria-hidden="true"><span key={`${actual?.sample_index}-${playbackSpeed}`} style={{ animationDuration: `${2 / playbackSpeed}s`, animationPlayState: playbackActive && !loading ? 'running' : 'paused' }} /></div>
      </section>
      <section className="summary-strip" aria-label="Selected TEP data"><div><span>TRAJECTORY</span><strong>{partition} · {run}</strong><small>Published fault scenario {fault}</small></div><div><span>SIMULATION TIME</span><strong>{actual?.elapsed_minutes ?? '—'} min</strong><small>3 simulated min per sample</small></div><div><span>CURRENT FAULT SCORE</span><strong>{actual?.detector_score == null ? 'Unavailable' : `${Math.round(actual.detector_score * 100)}%`}</strong><small>Research classifier, not failure probability</small></div><div><span>REACTOR PRESSURE +20 MIN</span><strong>{actual?.reactor_pressure_20m_bar_g == null ? 'Unavailable' : `${actual.reactor_pressure_20m_bar_g.toFixed(2)} bar(g)`}</strong><small>Simulation regression estimate</small></div></section>
      {actual?.detector_explanation && <section className="explanation-card detector-evidence" aria-label="Current sample detector evidence"><span className="tiny-heading">CURRENT SAMPLE / MODEL SENSITIVITY</span><h2>What changes this fault score?</h2><p>Each feature was replaced separately with its training-set median. A positive delta means the observed value raises the score in this one-feature test; it does not prove a physical cause.</p><div className="detector-factor-groups"><div><strong>Raises score</strong>{actual.detector_explanation.top_positive_factors.length ? <ul>{actual.detector_explanation.top_positive_factors.map(factor => <li key={factor.feature}><code>{factor.feature}</code><span>+{(factor.score_delta * 100).toFixed(1)} points</span></li>)}</ul> : <p>No positive factor in this test.</p>}</div><div><strong>Lowers score</strong>{actual.detector_explanation.top_negative_factors.length ? <ul>{actual.detector_explanation.top_negative_factors.map(factor => <li key={factor.feature}><code>{factor.feature}</code><span>{(factor.score_delta * 100).toFixed(1)} points</span></li>)}</ul> : <p>No negative factor in this test.</p>}</div></div><small>{actual.detector_explanation.disclaimer} Tree-score spread: {(actual.detector_explanation.ensemble_tree_std * 100).toFixed(1)} percentage points; not calibrated uncertainty.</small></section>}
      {actual && Object.entries(actual.model_notices ?? {}).filter(([kind]) => actual.model_status?.[kind] !== 'ready' || (kind === 'pressure' && (actual.sample_index ?? 0) < 4)).map(([kind, notice]) => <p className="model-availability" key={kind}><strong>{kind === 'pressure' ? 'Pressure model' : 'Fault detector'}:</strong> {notice}</p>)}
      <section className="main-layout">
        <div className="visual-card">
          <div className="section-title"><div><span className="tiny-heading">PROCESS TOPOLOGY</span><h2>TEP equipment and flows</h2></div><div className="view-tabs" role="group" aria-label="Process view"><button type="button" className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')} aria-pressed={view === '3d'}>3D plant</button><button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')} aria-pressed={view === 'map'}>2D flow</button></div></div>
          {view === '3d' ? <Suspense fallback={<div className="scene scene-loading" role="status">Loading 3D process view…</div>}><PlantScene assets={assets} selectedId={selected?.asset_id ?? null} select={asset => setSelectedId(asset.asset_id)} playing={playbackActive} speed={playbackSpeed} /></Suspense> : <ProcessMap assets={assets} selectedId={selected?.asset_id ?? null} onSelect={setSelectedId} pressureUnit="bar(g)" playing={playbackActive} speed={playbackSpeed} />}
          <div className="asset-playback-cards" aria-label="Dataset readings by equipment">{assets.map(asset => <button key={asset.asset_id} type="button" onClick={() => setSelectedId(asset.asset_id)} aria-pressed={selected?.asset_id === asset.asset_id}><strong>{asset.asset_name}</strong><span>{asset.pressure_bar.toFixed(2)} bar(g) · {asset.temperature_c.toFixed(1)} °C</span><span>Level {asset.level_percent.toFixed(1)}% · Flow {asset.flow_value?.toFixed(2) ?? 'N/A'} {asset.flow_unit}</span><i className="asset-level-track" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, asset.level_percent))}%` }} /></i></button>)}</div>
        </div>
        <aside className="inspector-card"><span className="tiny-heading">SELECTED MEASURED UNIT</span>{selected ? <>
          <div className="inspector-head"><div><h2>{selected.asset_name}</h2><span>{selected.asset_id}</span></div><span className="status-chip">UNASSESSED</span></div>
          <div className="metric-grid"><div><span>TEMPERATURE</span><strong>{selected.temperature_c.toFixed(1)} <small>°C</small></strong></div><div><span>PRESSURE</span><strong>{selected.pressure_bar.toFixed(2)} <small>bar(g)</small></strong></div><div><span>LIQUID LEVEL</span><strong>{selected.level_percent.toFixed(1)} <small>%</small></strong></div><div><span>FLOW RATE</span><strong>{selected.flow_value?.toFixed(2) ?? 'N/A'} <small>{selected.flow_unit}</small></strong></div></div>
          <div className="sample-change"><strong>CHANGE FROM PREVIOUS SAMPLE</strong><span>{previousSelected ? `Pressure ${(selected.pressure_bar - previousSelected.pressure_bar) >= 0 ? '+' : ''}${(selected.pressure_bar - previousSelected.pressure_bar).toFixed(3)} bar · Level ${(selected.level_percent - previousSelected.level_percent) >= 0 ? '+' : ''}${(selected.level_percent - previousSelected.level_percent).toFixed(2)} percentage points` : 'Press Play to follow consecutive samples.'}</span></div>
          <div className="inspector-note"><strong>SOURCE AND LIMITS</strong><p>Values are mapped from XMEAS variables in the selected published TEP sample. Gas ppm, binary valve state, site limits and validated per-asset alarms are not present.</p><p>Fault number is dataset scenario metadata, never a model input or a live alarm.</p></div><div className="model-links"><a href="/?evaluation=tep-detector" target="_blank" rel="noreferrer">Fault detector evaluation ↗</a><a href="/?evaluation=tep-pressure-20m" target="_blank" rel="noreferrer">Pressure model evaluation ↗</a></div>
        </> : <p className="empty-state">Loading the selected sample. Check local dataset availability if this persists.</p>}</aside>
      </section>
      <section className="analysis-layout">{measured.length ? <PressureChart title="Reactor pressure by simulation time" caption="Solid: selected published trajectory. Dashed: a single +20 simulated-minute pressure estimate; it is not an over-pressure or leak alert." observed={measured} projected={estimate} observedLabel="Published samples" projectedLabel="Model pressure estimate" /> : <section className="chart-panel empty-chart"><span className="tiny-heading">PRESSURE HISTORY</span><h3>Loading selected trajectory</h3><p>Choose a run and sample above. History is drawn from that exact dataset trajectory.</p></section>}<section className="explanation-card"><span className="tiny-heading">READ THE RESULTS</span><h2>What the models actually do</h2><p>The 52-variable classifier scores whether the <em>current</em> TEP sample resembles an injected fault. It does not predict a real equipment failure. The separate model estimates reactor pressure at +20 simulated minutes.</p><div className="explanation-cue"><span>NO SAFETY CLAIM</span><p>Neither value is a calibrated plant hazard probability. Without physical sensors, event labels and approved operating limits, this dashboard cannot issue industrial safety alerts or control equipment.</p></div></section></section>
      <DatasetJourney playing={playbackActive} />
    </>}
    <footer><span>SentinelTwin · local dataset workbench</span><span>TEP and AI4I are distinct published benchmarks; no dummy plant feed is displayed.</span></footer>
    {snapshotReport && <SnapshotReport report={snapshotReport} onClose={() => setSnapshotReport(null)} />}
  </main>
}
