# SentinelTwin — Chemical Plant Safety Digital Twin

An academic, local-first digital-twin platform for chemical-process safety monitoring.

## Status and data honesty

The project is at **Phase 1 (dataset sourcing, ingestion & EDA)**. The interactive dashboard uses a clearly labeled **synthetic integration baseline**—not plant telemetry, TEP replay data, or ML inference. AI4I 2020 ingestion and EDA have been run on the official UCI file. TEP acquisition remains blocked by Harvard Dataverse access in this environment; see the progress log. No values in the UI are safety advice or model results.

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

Visit the URL printed by Vite (normally `http://localhost:5173`). API documentation is at `http://localhost:8000/docs`.

## Data pipeline

```powershell
py -m pip install -r ml\requirements.txt
py -m ml.ingestion.fetch_ai4i
py -m ml.ingestion.ingest_ai4i
py -m ml.eda.ai4i_eda
```

Raw datasets and large Parquet files are intentionally not committed. The processed AI4I manifest and generated EDA assets are tracked for provenance. See [docs/PROGRESS_LOG.md](docs/PROGRESS_LOG.md), [docs/datasets/AI4I.md](docs/datasets/AI4I.md), and [docs/datasets/TEP.md](docs/datasets/TEP.md).

## Limits

* No ML model has been trained and there are no evaluation metrics.
* Demonstration risk thresholds are not operating limits.
* TEP is a simulation; AI4I is synthetic-but-realistic industrial data.

