export type AlarmLevel = 'normal' | 'warning' | 'critical' | 'emergency_shutdown' | 'unassessed'
export type DashboardMode = 'tep' | 'ai4i' | 'rtf' | 'prognosis_lab'
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
export interface DetectorSensitivityFactor {
  feature: string
  observed_value: number
  reference_median: number
  score_delta: number
}
export interface DetectorExplanation {
  method: 'one_feature_at_a_time_median_replacement'
  ensemble_tree_std: number
  top_positive_factors: DetectorSensitivityFactor[]
  top_negative_factors: DetectorSensitivityFactor[]
  disclaimer: string
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
  detector_explanation: DetectorExplanation | null
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
export interface RtfPrognosis {
  status: 'ready' | 'missing' | 'invalid' | 'needs_history'
  remaining_minutes: number | null
  next_unit_id: 'RX-201' | 'SP-201' | 'ST-301' | null
  highlight_unit_id: 'RX-201' | 'SP-201' | 'ST-301' | null
  unit_status: 'unavailable_no_verified_labels' | 'abstained' | 'ready'
  warning_horizon_minutes: number
  notice: string
}
export interface RtfState {
  source_kind: 'TEP_RTF'
  source_notice: string
  generated_at: string
  case_id: string
  simulation_id: number
  sample_index: number
  total_samples: number
  time_hours: number
  assets: Asset[]
  prognosis: RtfPrognosis
}
export interface RtfHistoryPoint { sample_index: number; time_hours: number; reactor_pressure_bar_g: number }
export interface RtfHistory { source_kind: 'TEP_RTF'; case_id: string; simulation_id: number; end_sample: number; total_samples: number; points: RtfHistoryPoint[] }
export interface RtfFrame { state: RtfState; history: RtfHistory }
export interface RtfOptionRun { id: number; samples: number }
export interface RtfOptionCase { id: string; documented_scenario: boolean; run_count: number; runs: RtfOptionRun[] }
export interface RtfOptions { source_kind: 'TEP_RTF'; source_notice: string; cases: RtfOptionCase[] }
export interface RtfSnapshot extends RtfFrame { source_kind: 'TEP_RTF'; status: 'ready'; report_kind: 'rtf_snapshot'; model_card: Record<string, unknown> }
export type LabEquipmentId = 'RX-201' | 'CD-201' | 'SP-201' | 'ST-301' | 'CP-201'
export interface LabAsset {
  asset_id: LabEquipmentId
  asset_name: string
  temperature_c: number | null
  pressure_bar: number | null
  level_percent: number | null
  flow_value: number | null
  flow_unit: string | null
  performance_percent: number | null
  work_kw: number | null
  alarm_level: 'unassessed'
  updated_at: string
}
export interface LabPrognosis {
  status: 'ready' | 'missing' | 'invalid' | 'needs_history'
  failure_within_horizon_probability: number | null
  remaining_minutes: number | null
  predicted_equipment_id: LabEquipmentId | null
  predicted_failure_mode: string | null
  confidence: number | null
  unit_status: 'unassessed' | 'abstained' | 'ready'
  warning_horizon_minutes: number
  highlight_equipment_id: LabEquipmentId | null
  notice: string
}
export interface LabOutcome { censored: boolean; failed_equipment_id: LabEquipmentId | null; failure_mode: string | null; shutdown_reason: string }
export interface LabState {
  source_kind: 'SYNTHETIC_EQUIPMENT_PROGNOSIS'; source_notice: string; generated_at: string
  run_id: number; sample_index: number; total_samples: number; time_minutes: number
  assets: LabAsset[]; prognosis: LabPrognosis; observed_outcome: LabOutcome | null
}
export interface LabHistoryPoint { sample_index: number; time_minutes: number; reactor_pressure_bar: number }
export interface LabHistory { source_kind: 'SYNTHETIC_EQUIPMENT_PROGNOSIS'; run_id: number; end_sample: number; total_samples: number; points: LabHistoryPoint[] }
export interface LabFrame { state: LabState; history: LabHistory }
export interface LabOptions { source_kind: 'SYNTHETIC_EQUIPMENT_PROGNOSIS'; source_notice: string; sample_period_minutes: number; runs: { id: number; samples: number }[] }
export interface LabSnapshot extends LabFrame { status: 'ready'; report_kind: 'equipment_prognosis_snapshot'; model_card: Record<string, unknown> }
export interface Ai4iFrame { source_kind: 'AI4I_DATASET'; summary: Ai4iSummary; record: Ai4iRecord; neighbors: Ai4iRecords }
export type SnapshotData = ({ status: 'ready'; report_kind: 'dataset_snapshot'; source_kind: 'TEP_DATASET'; model_cards: Record<string, unknown> } & DatasetFrame)
  | ({ status: 'ready'; report_kind: 'dataset_snapshot' } & Ai4iFrame)

