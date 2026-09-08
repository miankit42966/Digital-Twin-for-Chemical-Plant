export type AppView = 'twin' | 'overview' | 'analytics' | 'alerts' | 'assets'
const links: Array<[AppView, string]> = [['twin', 'Digital Twin'], ['overview', 'Overview'], ['analytics', 'Analytics'], ['alerts', 'Alerts'], ['assets', 'Assets']]
export default function Header({ view, setView, connection }: { view: AppView; setView: (view: AppView) => void; connection: string }) {
  return <header className="app-header"><div className="brand"><span>ST</span><div><b>SENTINELTWIN</b><small>CHEMICAL PROCESS CONTROL</small></div></div><nav>{links.map(([key, label]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}>{label}</button>)}</nav><div className={`connection-status ${connection === 'LIVE' ? 'live' : ''}`}><i />{connection}</div></header>
}
