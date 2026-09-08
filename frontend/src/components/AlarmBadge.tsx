import type { AlarmLevel } from '../types'

export default function AlarmBadge({ level }: { level: AlarmLevel }) {
  return <span className={`alarm-badge ${level}`}>{level.replace('_', ' ')}</span>
}
