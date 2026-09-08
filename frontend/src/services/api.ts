import type { PlantState } from '../types'

export const API_BASE_URL = 'http://localhost:8000'

export async function fetchPlantState(): Promise<PlantState> {
  const response = await fetch(`${API_BASE_URL}/api/v1/plant/state`)
  if (!response.ok) throw new Error(`Plant state request failed: ${response.status}`)
  return response.json() as Promise<PlantState>
}

export async function fetchIncidents() {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents`)
  if (!response.ok) throw new Error(`Incidents request failed: ${response.status}`)
  return response.json() as Promise<unknown[]>
}
