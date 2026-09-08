import type { Asset } from '../types'
import AssetCard from '../components/AssetCard'
import AssetInspector from '../components/AssetInspector'
import KpiBar from '../components/KpiBar'
import PlantScene from '../PlantScene'
export default function DigitalTwin({ assets = [], selected, onSelect }: { assets: Asset[]; selected?: Asset; onSelect: (asset: Asset) => void }) {
  return (
    <div className="twin-page">
      <KpiBar assets={assets} />
      <section className="twin-workspace">
        <PlantScene assets={assets} select={onSelect} selected={selected} />
        <AssetInspector asset={selected} />
      </section>
      <section className="asset-card-row">
        {assets.map(asset => (
          <AssetCard
            key={asset.asset_id}
            asset={asset}
            selected={asset.asset_id === selected?.asset_id}
            onSelect={() => onSelect(asset)}
          />
        ))}
      </section>
    </div>
  )
}

