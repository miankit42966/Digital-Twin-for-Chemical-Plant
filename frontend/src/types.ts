export type AlarmLevel = 'normal' | 'warning' | 'critical' | 'emergency_shutdown'
export interface Asset { asset_id: string; asset_name: string; temperature_c: number; pressure_bar: number; level_percent: number; flow_m3h: number; valve_open: boolean; gas_ppm: number; risk_score: number; alarm_level: AlarmLevel; updated_at: string }
export interface PlantState { source_kind: 'SIMULATED_INTEGRATION_BASELINE'; source_notice: string; generated_at: string; assets: Asset[] }

