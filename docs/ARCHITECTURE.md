# Architecture notes

## Current integration boundary

The frontend obtains initial plant state via `GET /api/v1/plant/state` and then receives updates via `WS /ws/telemetry`. The FastAPI `BaselineTelemetry` service is deliberately isolated so a future `TepReplayTelemetry` adapter can use the same response contract.

Every payload contains `source_kind`. The only current value is `SIMULATED_INTEGRATION_BASELINE`; the UI renders it prominently. Future source kinds will distinguish `TEP_REPLAY` and `LIVE_SENSOR`.

## Alarm contract

`normal`, `warning`, `critical`, and `emergency_shutdown` are presentation states. Baseline transitions come from deterministic demonstration thresholds in `backend/app/services/baseline.py` and must not be treated as process safety limits. Phase 6 will replace or augment them with documented, traceable thresholds and model-output rules.

## Model boundary

No model endpoint currently exists. Models will be versioned with their model cards, training script hashes, dataset version identifiers, decision thresholds, and actual held-out evaluation results. The API must never label a heuristic or replay value as a trained prediction.

