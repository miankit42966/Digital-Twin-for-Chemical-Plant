import type { Asset } from '../types'
import AlarmBadge from './AlarmBadge'
export default function AssetCard({ asset, selected, onSelect }: { asset: Asset; selected?: boolean; onSelect: () => void }) {
  return <button className={`asset-card ${selected ? 'selected' : ''}`} onClick={onSelect}><div><span>{asset.asset_id}</span><b>{asset.asset_name}</b></div><AlarmBadge level={asset.alarm_level} /><small>{asset.temperature_c} °C · {asset.pressure_bar} bar · {asset.level_percent}% level</small></button>
}
