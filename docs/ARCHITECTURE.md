# Architecture notes

## Current data path

The main React dashboard defaults to the TEP dataset tab. `GET /api/v1/tep/dataset/frame` returns one selected sample plus bounded contiguous history atomically from the same trajectory. The backend validates matching source, partition, fault, run, sample and cadence metadata. Individual state/series endpoints remain available. The backend filters local Parquet by partition, fault number and run; no fixed replay extraction limits the main view. Dataset caches invalidate when source file signatures change. A separate `TEP_RTF` mode serves one committed case/run/sample frame plus bounded history and a past-only remaining-time prognosis; unsupported or unlabeled outcomes fail closed without an equipment highlight. `SYNTHETIC_EQUIPMENT_PROGNOSIS` is a fourth, isolated lab source with five generated units, explicit terminal labels and a separately evaluated model bundle.

The published TEP/RTF 3D and 2D views map reactor, separator and stripper values from the same selected sample; condenser and compressor remain conceptual context there. In the synthetic lab all five units have generated equipment-appropriate telemetry and are selectable. The 3D scene is not a detailed plant engineering model or P&ID. A separate AI4I tab requests `/api/v1/ai4i/frame`, which captures one dataset revision for its summary, selected record and neighbors. AI4I's assets, units and failure labels are never merged into the TEP chemical-plant scene.

Every TEP dataset response has `source_kind=TEP_DATASET` plus partition/fault/run/sample metadata. AI4I responses have `source_kind=AI4I_DATASET`. The frontend checks source identities before display. The general plant-state and telemetry WebSocket APIs also use TEP; the latter closes when the selected trajectory ends. Synthetic testing is isolated at `/api/v1/testing/baseline` and `/ws/testing/baseline`. `TEP_REPLAY` remains a legacy adapter. There is no `LIVE_SENSOR` connector.

Relative API requests work through Vite dev/preview proxies or the FastAPI-served production build. `/api/v1/report` supplies source-specific read-only snapshot exports. Shared `tep_models` inference validates features, input dimensions, matching dataset fingerprints and the shared atomic artifact ID of each model/card pair; failures degrade only model output, not measured data. The RTF loader applies the same pair validation. A read-only full-data audit checks these bindings and verifies every processed RTF Parquet hash.

Playback retains the last committed state/history pair during a sample request and advances only after that request completes and the selected dwell time elapses. It does not discard a valid frame when the requested sample index changes. Pause restores the slider to the committed sample and aborts any pending advance. A different trajectory invalidates the old state immediately. Requests time out after 15 seconds with a Retry control; the final sample stops playback instead of looping silently.

React Three Fiber frame callbacks animate continuous shader-driven pipe cores and illustrative rotating parts while playback is active. Liquid meshes and gauges smoothly approach measured sample levels. Pipe geometry and the Canvas remain mounted across sample updates. The 2D route's directional pulses use the same play/pause and speed state. Motion provides process context; it does not solve physical dynamics or measure mechanical RPM.

## Concurrency and local runtime

Dataset/trajectory/model caches use bounded LRU storage plus 32 fixed reentrant lock stripes. Concurrent requests for the same cold key load it only once; inference and unrelated requests are not globally serialized. Each WebSocket maintains its own run/sample cursor. API frames and reports capture the selected rows once, keeping measurements and history aligned.

Frontend effects abort superseded requests and reject mismatched identities. Export additionally holds an immediate in-flight request guard, cancels when source/run/UDI/manual sample/playback selection changes, and ignores late responses and cleanup from old requests. Reports remain fixed snapshots, not live updates.

The documented `backend/run_server.py` entry point uses `asyncio.SelectorEventLoop` to avoid the Windows Proactor socket-shutdown callback traceback after abrupt peer resets. This is a local single-process setup, not an unlimited-concurrency configuration. Dataset replacement/retraining should run as maintenance with serving stopped: atomic individual files do not form a transaction across a whole dataset/model/card set.

## Model and safety boundary

`ml/train_tep_detector.py` trains a CPU current-fault classifier; its score describes resemblance to a fault-injected TEP sample, not a calibrated probability of a real plant failure. `ml/train_tep_pressure_forecast.py` trains a separate CPU regressor for reactor pressure at +20 **simulated** minutes; the target is interpolated from +18 and +21 minute TEP samples. Evaluations, splits and source hashes are recorded in the model cards under `docs/models/`.

TEP outputs use `unassessed` equipment status. There are no mapped gas ppm or binary valve sensors, approved site limits, validated leak alerts, hazard probabilities, or actuation. The frontend does not turn model scores or pressure estimates into warning/critical plant alarms. A real safety deployment would require live authenticated telemetry, documented sensor-to-equipment mapping, event labels, calibration, operational limits and an independent safety review.

The prognosis lab trains only on generated run families. It can issue an amber synthetic warning when its held-out release gates, probability threshold, equipment threshold and ≤60-minute RUL condition all pass. Outcome labels are withheld from API frames until the terminal sample. This demonstrates the required ML workflow but is not evidence of physical equipment-failure prediction.
