# SentinelTwin — process data workbench

SentinelTwin is a local research dashboard for two separate published benchmarks. The default TEP view reads the full Tennessee Eastman Process Parquet dataset directly: choose training/testing, fault scenario 0–20, run 1–500, and any sample in that trajectory. The AI4I tab explores the machining predictive-maintenance dataset without pretending it is part of the chemical plant.

This is **not a live physical-plant digital twin or a validated safety system**. TEP is published process simulation, AI4I is a synthetic-but-realistic machining benchmark, and the models are research models. No plant actuator is controlled.

## Start locally

From the repository root, install the backend and model dependencies, then run the API:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r ml\requirements.txt
.\.venv\Scripts\python.exe backend\run_server.py
```

In a second terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173/>. API documentation is at <http://127.0.0.1:8000/docs>.

`backend/run_server.py` uses a selector event loop to avoid Windows Proactor shutdown callback errors when a browser abruptly resets a WebSocket. Keep one backend listener on port 8000. For dataset replacement or model retraining, stop serving first, complete the pipeline, run the data audit, then restart; hot publishing a dataset/model/card set is not a transactional deployment.

For a production build, run `npm.cmd run build` in `frontend/`, then start/restart the API. It serves that build at <http://127.0.0.1:8000/>. `npm.cmd run preview` serves it at <http://127.0.0.1:4173/>. Dev and preview proxy API/WebSocket requests to the local backend; the production build uses the API's own origin.

The TEP tab needs `data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet`. The AI4I tab needs `data/processed/ai4i/uci-601/ai4i.parquet`. If these files are absent, obtain/ingest them using the repository's scripts:

```powershell
.\.venv\Scripts\python.exe -m ml.ingestion.fetch_tep
.\.venv\Scripts\python.exe -m ml.ingestion.ingest_tep
.\.venv\Scripts\python.exe -m ml.ingestion.fetch_ai4i
.\.venv\Scripts\python.exe -m ml.ingestion.ingest_ai4i
```

Model binaries under `models/` are generated locally and ignored by Git. To rebuild them from the ingested TEP data:

```powershell
.\.venv\Scripts\python.exe -m ml.train_tep_detector
.\.venv\Scripts\python.exe -m ml.train_tep_pressure_forecast
```

## What the dashboard shows

- The TEP selectors query any published trajectory directly from Parquet. Play advances after each loaded sample's dwell time (2 seconds at 1×, plus request time); 0.5× and 2× speeds are available. Each sample represents three **simulated** minutes. Pause cancels a pending advance, and a run stops at its final sample until Restart is pressed.
- During playback, 3D flow markers, reactor mixing and the compressor rotor illustrate the route. Vessel fills and gauges interpolate to the dataset's measured levels. Motion speed is visual, not a physical fluid-velocity or RPM measurement. The 2D route also follows Play/Pause.
- Current readings, equipment and pressure history stay visible while the next sample loads. A failed request stops playback with a Retry option; switching trajectory clears the old run's readings.
- The 3D view and 2D route show process topology. Reactor, separator and stripper values map to published XMEAS variables. Condenser/compressor shapes provide context only; this is not an engineering P&ID.
- The solid pressure line is measured in the selected simulation run. The dashed point is a single +20 simulated-minute reactor-pressure regression estimate.
- The fault detector scores the **current** sample's resemblance to an injected fault. It does not predict a future failure or produce a calibrated hazard probability.
- The AI4I tab shows published rows, failure labels and units separately; it does not merge AI4I records with the TEP plant scene.

The dashboard uses `/api/v1/tep/dataset/frame` for an atomic measured-state/history pair, and `/api/v1/ai4i/frame` for one coherent summary/record/neighbors response. Individual state/series/record endpoints remain available. `/api/v1/plant/state` and `/ws/telemetry` now use the selected TEP dataset, not a dummy plant feed. Synthetic testing is explicitly isolated at `/api/v1/testing/baseline` and `/ws/testing/baseline`; legacy `/api/v1/tep/replay` and `/ws/tep/replay` remain available.

Export displayed snapshot opens a readable, fixed-sample report from `/api/v1/report` for the displayed source and sample, including measured readings, model outputs and pressure history where applicable. Playback pauses when capturing. Print / Save as PDF opens the browser print dialog; choose Save as PDF to save the report. The print layout contains only the report, not the background dashboard. JSON remains an optional technical export inside the report; no file is downloaded automatically. Missing or incompatible model files leave measured values available with an explicit model-status message.

The inspector's evaluation links open readable reports at `/?evaluation=tep-detector` and `/?evaluation=tep-pressure-20m`. These show real saved metrics, explanations, data splits, features and limitations; raw JSON is available in an expandable technical section. `/api/v1/models/*` remains unchanged for API consumers. Browser regression checks are in `tests/model_evaluation_check.py`.

## Verification and limits

Install test dependencies with `.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt`, then run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` from the root and `npm.cmd run build` in `frontend/`. `.\.venv\Scripts\python.exe -m scripts.verify_data` scans every TEP sample/feature, checks trajectory completeness, source hashes and model-card freshness, and verifies AI4I sequence/labels. Model evaluations and source provenance are in [docs/models](docs/models), [TEP dataset notes](docs/datasets/TEP.md), [AI4I dataset notes](docs/datasets/AI4I.md) and the [research-gap audit](docs/RESEARCH_GAPS.md).

`tests/dashboard_playback_check.py` checks the running local UI through a QA Chrome CDP session on port 9225. It covers slow-response frame retention, animated/frozen 3D frames, in-flight cancellation, seeking, end/restart, speed, retry recovery, dataset run identity, and mobile 2D playback. It writes screenshots to a temporary QA directory.

There are no live sensors, site-approved thresholds, validated leak/over-pressure alerts, or safety-rated control actions. Do not use the displayed scores or estimates for operating decisions.

Current cross-project verification results and remaining limits are in [the project audit](docs/PROJECT_AUDIT.md).
