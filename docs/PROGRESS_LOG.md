# Progress Log

## Current phase

**Phase 2 — Full TEP dataset exploration, animated process playback, AI4I record exploration, benchmark fault detection, and 20-minute simulation-pressure regression (prototype).** Dataset sourcing, ingestion and EDA are complete. A validated 20-minute *failure-event* forecast and industrial validation remain future work.

## 2026-10-03 — Concurrency and final runtime audit

* Added bounded single-flight dataset/model caches; concurrent cold requests no longer repeat the same expensive load. Verified one load for 16 concurrent callers, bounded cache storage, mixed-source frame isolation and deterministic parallel inference.
* Fixed pending-export cancellation and stale completion/busy-state races. Browser regression deliberately releases old responses after a newer source request; duplicate exports are guarded immediately.
* Historical `backend-server-error.log` contains Windows Proactor peer-reset callback tracebacks. Preserved it as evidence; added the selector-loop server launcher and restarted the backend. Eight deliberately reset upgraded WebSocket peers produced no traceback in the new runtime log.
* Verified 128 live HTTP requests at concurrency 16, eight independently ordered WebSocket streams with normal end closure, and health after eight abrupt resets. Median latency 563 ms, p95 1,688 ms on this local mixed-load run; not a capacity guarantee.
* Full data integrity audit, dependency checks, TypeScript/build and browser suites rerun. Detailed current results and reproduction commands are in `docs/PROJECT_AUDIT.md`. Existing worktree edits preserved; no commit/push.

## 2026-10-03 — Readable snapshot export

* Replaced automatic JSON download with a fixed-sample report preview. Capture pauses playback, validates the selected source/run/sample, and shows measured equipment readings, research-model outputs, bounded pressure history and explicit safety limits. AI4I reports stay separate.
* Added Print / Save as PDF with report-only, unclipped print styling; technical JSON is an optional disclosure/action. The native modal supports keyboard focus, Escape and return to the dashboard.
* Expanded `tests/dashboard_integration_check.py` to check no automatic download, preview identity, print action/PDF rendering, report-only print layout, keyboard handling and mobile report layout.

## 2026-10-03 — Readable model evaluation reports

* Diagnosed inspector links opening raw JSON API responses. Replaced dashboard link targets with dedicated evaluation views, preserving the JSON API contract.
* Added actual saved metric cards with definitions, detector confusion matrix, pressure-target explanation, data splits, feature/provenance details and safety limitations. Loading, incomplete/unavailable-card errors and Retry are explicit; raw JSON is an optional technical disclosure.
* Verified production build and ten browser checks across development/built origins, real metric matching, source/limitation text, mobile expanded details and API failure recovery. Regression: `tests/model_evaluation_check.py`.

## 2026-10-03 — Cross-project synchronization audit

* Audited source/configuration, API/WebSocket/data/model contracts, ingestion, frontend, local hosting and current GitHub revision. Added atomic TEP and AI4I frames, source-correct plant/telemetry interfaces, shared validated model inference and source-specific snapshot export.
* Fixed dev/preview/production API origins, Windows ingestion environment/exit handling, interrupted-write reliability and large TEP ingestion concatenation. Updated Vite to 6.4.3 and refreshed outdated documentation.
* Verified 18 Python tests, 22 browser checks, production build, dependency consistency and a full scan of all 15,330,000 TEP rows/21,000 trajectories plus AI4I records. Source/model fingerprints match; `npm audit` reports zero known vulnerabilities. GitHub has no newer remote commit; ongoing local edits remain uncommitted.
* Detailed evidence, fixes, verification commands and honest remaining limits: `docs/PROJECT_AUDIT.md`.

## 2026-10-03 — Playback flicker and missing motion corrected

* Diagnosed repeated blank frames: requesting a new sample invalidated the currently rendered state and history, removing measured vessels and inspector/chart content until the next response arrived.
* Retained the last committed same-trajectory state/history while loading, validated response identity, and changed playback to advance after a completed request plus the selected dwell time. Pause aborts a pending advance, requests time out with Retry, and the last sample stops with an explicit Restart control.
* Added animated 3D flow markers, direction arrows, illustrative reactor mixing/compressor rotation, and smooth dataset-driven vessel/gauge levels. The 2D route follows the same Play/Pause state and speed. Added per-unit readings, sample-to-sample deltas and a visible playback status/progress indicator.
* The dashboard currently reads selectable TEP trajectories directly from the full local Parquet dataset, with AI4I in a separate record explorer. This supersedes the older default guided-demo and fixed-replay interfaces described in historical entries below.
* Verified production build and 12 browser checks: slow-network frame retention, motion between samples, in-flight pause cancellation, frozen paused frames, missing early pressure estimate, seeking/end/restart, 2× speed, disconnect/Retry recovery, selected-run readings matching the API dataset, mobile layout, 2D Play/Pause, and absence of browser exceptions. Regression script: `tests/dashboard_playback_check.py`.

## 2026-10-03 — Guided dashboard redesign

* Rebuilt the default dashboard as a five-step, video-inspired walkthrough with a clickable simplified 2D route, preserved 3D view, asset inspector, trend chart, training-only warning and simulated response.
* Added a separate TEP replay interface with play/pause, sample seeking, bounded recorded history and a visually distinct +20-minute pressure estimate. The original synthetic UI baseline remains selectable.
* Verified that demo warning/response content does not appear in TEP or baseline modes. All demo readings are labeled illustrative and no control writeback is implemented.

## 2026-10-03 — Replay and detector prototype

* Added a selectable dashboard TEP replay mode from a 960-sample official testing run, with source/run/sample metadata and mapped reactor, separator and stripper measurements.
* Trained a 52-variable CPU current-fault detector with held-out testing runs. Exact evaluation results and limitations are in `docs/models/TEP_fault_detector.json`.
* Added explicit `unassessed` status for replay measurements and left unsupported gas, valve and asset alarm fields unavailable.
* Trained a separate +20 simulated-minute reactor-pressure regression model on TEP runs and exposed its estimated pressure in the API/dashboard. The held-out testing-run metrics and limitations are in `docs/models/TEP_pressure_20m.json`; this is not a 20-minute failure forecast.
* Audited research claims and recorded source corrections and acceptance criteria in `docs/RESEARCH_GAPS.md`.

## 2026-10-03 — TEP completion

### Completed

* Downloaded the four official Harvard Dataverse TEP v1.0 RData files and verified their published MD5 checksums.
* Validated and combined the source tables into `data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet`: 15,330,000 rows, 52 sensor columns, no sensor null cells, and 21 published fault numbers.
* Generated local TEP EDA statistics, fault balance, time-series, correlation figures, and `docs/eda/TEP_summary.md`.
* Updated the EDA job to stream the large Parquet dataset in bounded batches and use Matplotlib's non-GUI renderer, so it runs reliably on a local development machine.

### Scope retained

* The dashboard/API remain explicitly labeled `SIMULATED_INTEGRATION_BASELINE`; TEP acquisition does not turn synthetic UI values into plant telemetry, TEP replay, or ML inference.

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
