# Progress Log

## Current phase

**Phase 1 — Dataset sourcing, ingestion & EDA (in progress).**

## 2026-09-07 — Phase 1

### Completed

* Verified and documented the official Harvard Dataverse TEP v1.0 source (DOI `10.7910/DVN/6C3JR1`) and the official UCI AI4I 2020 source (dataset 601, DOI `10.24432/C5HS5C`).
* Added reproducible source-specific download scripts, schema-validating ingestion scripts, versioned Parquet/manifest output, and EDA scripts. The single-command Windows entry point is `scripts/data/ingest_all.ps1 -Fetch`.
* Downloaded the unmodified AI4I UCI CSV, validated its 10,000-row documented schema, and wrote `data/processed/ai4i/uci-601/ai4i.parquet` plus manifest. Its raw CSV SHA-256 is `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`.
* Ran AI4I EDA and generated three figures, summary statistics, class counts, and `docs/eda/AI4I_summary.md`. The summary is generated from the local processed file and excludes failure-mode label leakage from its operational-predictor correlation view.

### Blocked / remaining

* Harvard Dataverse returned HTTP 403 to this environment for the official TEP datafile API, including a retry with an explicit academic User-Agent. No TEP stand-in has been created.
* Manually download the four exact v1.0 RData files named in `docs/datasets/TEP.md` from the DOI landing page into `data/raw/tep/`, then run `py -m ml.ingestion.ingest_tep` and `py -m ml.eda.tep_eda`. This will create the TEP Parquet, manifest, figures, and computed summary.
* Phase 1 is **not complete** until those TEP steps run successfully and are verified.

### Repository handoff

* Current scaffold, AI4I pipeline/docs/EDA assets, and this progress record were published to the project GitHub `main` branch on 2026-09-07. Raw datasets and Parquet files remain local by design; the tracked AI4I manifest records source provenance.

## 2026-09-07

### Completed this session

* Created the monorepo layout: `backend`, `frontend`, `ml`, `data`, and `docs`.
* Added a FastAPI service with health, state, incident, report, and WebSocket interfaces.
* Added a React/TypeScript/Three.js client with an inspectable plant scene and live WebSocket connection.
* The integration feed is explicitly marked `SIMULATED_INTEGRATION_BASELINE`. It is deterministic synthetic UI plumbing only, not TEP data or a prediction.
* Added local run instructions and baseline architecture documentation.

### Verified

* Installed the backend requirements in `.venv`; Python compilation and the telemetry-contract import check passed.
* Started FastAPI on port 8010 and verified `/health` (`ok`) plus `/api/v1/plant/state` (three assets, labeled baseline); stopped the test server afterward.
* Installed frontend dependencies and ran `npm run build` successfully. Vite produced the production bundle.
* Vite reports a 1.1 MB uncompressed JavaScript bundle, primarily from the initial Three.js stack. This is a performance follow-up, not a failed build.

### Next steps

1. Acquire TEP and AI4I only from their documented public sources; retain source metadata and licenses.
2. Implement reproducible ingestion with schema checks and EDA, then update Phase 1 status only after it runs.
3. Replace the baseline feed only with a clearly labeled replay adapter once TEP schema is verified.

### Open decisions

* NASA C-MAPSS is deferred until Phase 3 capacity is confirmed.
* Historical incident source selection is deferred; any candidate must be publicly citable and summarized without claiming causal matching.
