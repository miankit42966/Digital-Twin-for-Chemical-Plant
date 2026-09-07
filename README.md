# SentinelTwin — Chemical Plant Safety Digital Twin

An academic, local-first digital-twin platform for chemical-process safety monitoring.

## Status and data honesty

This repository is at **Phase 0 (environment setup)**. The running interface deliberately uses a **synthetic integration baseline**, not plant telemetry, TEP data, or ML inference. Its purpose is to prove the frontend/backend connection and the scene interaction before Phases 1–4 introduce audited datasets and trained models. Do not use its values as safety advice or model results.

## Architecture

```text
React + TypeScript + Three.js scene  <-- REST / WebSocket -->  FastAPI
                                                            |
                                              dataset adapters / model registry (planned)
```

## Run locally

Open two terminals from the repository root.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r backend\requirements.txt
py -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Visit the URL printed by Vite (normally `http://localhost:5173`). The backend API documentation is at `http://localhost:8000/docs`.

## Planned sources and limits

* Tennessee Eastman Process (TEP) will be the process/fault source after acquisition and schema verification.
* AI4I 2020 will be the predictive-maintenance source after acquisition and schema verification.
* No model has been trained and there are no evaluation metrics yet.
* Safety thresholds in the baseline are visual demonstration values only; they are not operating limits.

See [docs/PROGRESS_LOG.md](docs/PROGRESS_LOG.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

