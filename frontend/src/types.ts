export type AlarmLevel = 'normal' | 'warning' | 'critical' | 'emergency_shutdown' | 'unassessed'
export type DashboardMode = 'tep' | 'ai4i'
export interface Asset {
  asset_id: string
  asset_name: string
  temperature_c: number
  pressure_bar: number
  level_percent: number
  flow_m3h: number | null
  flow_value: number | null
  flow_unit: string | null
  valve_open: boolean | null
  gas_ppm: number | null
  risk_score: number | null
  alarm_level: AlarmLevel
  updated_at: string
}
export interface PlantState {
  source_kind: 'SIMULATED_INTEGRATION_BASELINE' | 'TEP_REPLAY' | 'TEP_DATASET'
  source_notice: string
  generated_at: string
  assets: Asset[]
  sample_index: number | null
  elapsed_minutes: number | null
  fault_number: number | null
  simulation_run: number | null
  dataset_partition: 'training' | 'testing' | null
  total_samples: number | null
  sample_period_minutes: number | null
  detector_score: number | null
  reactor_pressure_20m_bar_g: number | null
  model_status: Record<string, 'ready' | 'missing' | 'invalid'>
  model_notices: Record<string, string>
}
export interface ReplayPoint {
  sample_index: number
  elapsed_minutes: number
  reactor_pressure_bar_g: number
  reactor_temperature_c: number
  reactor_level_percent: number
  separator_pressure_bar_g: number
  stripper_pressure_bar_g: number
}
export interface ReplaySeries {
  source_kind: 'TEP_REPLAY' | 'TEP_DATASET'
  simulation_run: number
  fault_number: number
  dataset_partition: 'training' | 'testing' | null
  sample_period_minutes: number
  end_sample: number
  total_samples: number | null
  points: ReplayPoint[]
}
export interface Ai4iSummary {
  source_kind: 'AI4I_DATASET'
  notice: string
  total_records: number
  failure_records: number
  product_types: Record<'L' | 'M' | 'H', number>
  failure_modes: Record<'TWF' | 'HDF' | 'PWF' | 'OSF' | 'RNF', number>
}
export interface Ai4iRecord {
  source_kind: 'AI4I_DATASET'
  notice: string
  udi: number
  product_id: string
  type: 'L' | 'M' | 'H'
  air_temperature_k: number
  process_temperature_k: number
  rotational_speed_rpm: number
  torque_nm: number
  tool_wear_min: number
  machine_failure: number
  twf: number
  hdf: number
  pwf: number
  osf: number
  rnf: number
}
export interface Ai4iRecords { source_kind: 'AI4I_DATASET'; start: number; records: Ai4iRecord[] }
export interface DatasetFrame { state: PlantState; history: ReplaySeries }
export interface Ai4iFrame { source_kind: 'AI4I_DATASET'; summary: Ai4iSummary; record: Ai4iRecord; neighbors: Ai4iRecords }
export type SnapshotData = ({ status: 'ready'; report_kind: 'dataset_snapshot'; source_kind: 'TEP_DATASET'; model_cards: Record<string, unknown> } & DatasetFrame)
  | ({ status: 'ready'; report_kind: 'dataset_snapshot' } & Ai4iFrame)

