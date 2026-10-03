import type { Asset } from './types'

type Props = { assets: Asset[]; selectedId: string | null; onSelect: (id: string) => void; pressureUnit: string; playing: boolean; speed: number }

export default function ProcessMap({ assets, selectedId, onSelect, pressureUnit, playing, speed }: Props) {
  return <div className={`process-map ${playing ? 'is-playing' : ''}`}>
    <div className="map-topline"><span className="tiny-heading">PROCESS ROUTE / SIMPLIFIED VIEW</span><span className="map-key"><i /> Flow direction</span></div>
    <div className="process-route">
      <span className="route-boundary">FEED</span>
      {assets.map((asset, index) => <div className="route-unit" key={asset.asset_id}>
        {index > 0 && <div className={`route-connector ${index === 1 ? 'through-condenser' : ''}`} aria-hidden="true"><span className="flow-pulse" style={{ animationDuration: `${2 / speed}s`, animationPlayState: playing ? 'running' : 'paused' }} /><b>→</b>{index === 1 && <small>CONDENSER</small>}</div>}
        <button type="button" className={`equipment-node ${selectedId === asset.asset_id ? 'active' : ''} ${asset.alarm_level}`} onClick={() => onSelect(asset.asset_id)} aria-pressed={selectedId === asset.asset_id}>
          <span className="node-head"><span className="node-icon" aria-hidden="true"><span className="node-liquid" style={{ height: `${asset.level_percent}%` }} /></span><span><strong>{asset.asset_name}</strong><small>{asset.asset_id}</small></span></span>
          <span className="node-divider" />
          <span className="node-reading"><span>PRESSURE</span><b>{asset.pressure_bar.toFixed(2)} <small>{pressureUnit}</small></b></span>
          <span className="node-reading"><span>LEVEL</span><b>{asset.level_percent.toFixed(1)}<small>%</small></b></span>
          <span className="node-reading"><span>TEMPERATURE</span><b>{asset.temperature_c.toFixed(1)} <small>°C</small></b></span>
          <span className="node-reading"><span>FLOW</span><b>{asset.flow_value?.toFixed(2) ?? 'N/A'} <small>{asset.flow_unit}</small></b></span>
          <span className="node-state">{playing ? 'Following published samples' : 'Paused published sample'}</span>
        </button>
      </div>)}
      <span className="route-boundary">PRODUCT</span>
    </div>
    <div className="map-footer"><span>SEPARATOR VAPOR → COMPRESSOR → REACTOR RECYCLE</span><span>Select a measured unit · conceptual flow, not an engineering P&amp;ID</span></div>
  </div>
}
