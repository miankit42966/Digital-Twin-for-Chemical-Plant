# Project integration audit — 2026-10-03

Scope: application source/configuration, backend contracts, frontend views and playback, dataset/ML/EDA pipelines, manifests and model cards, dependency installation, local servers and current GitHub revision. Generated dependencies were checked by package tooling; every binary was not manually inspected. Existing worktree changes were preserved. No push or deployment was performed.

## Issues corrected

| Area | Correction |
| --- | --- |
| Data synchronization | TEP state/history are one atomic frame from the same trajectory. AI4I summary/record/neighbors likewise use one captured dataset revision; separate requests cannot clear each other's error state. |
| Source identity | `/api/v1/plant/state` and `/ws/telemetry` now expose selected TEP measurements. The synthetic baseline is explicitly isolated under testing endpoints. UI sources and benchmark labels remain separate. |
| Model inference | Dataset and legacy replay share one feature contract/loader. Model/card fingerprints, dimensions and features are validated; missing/corrupt models preserve measured equipment/history with explicit notices. Pressure features match training float32 arithmetic exactly. |
| Hosting connections | Relative API requests work with Vite dev/preview proxies and the API-hosted production build. Model evaluation links use the same origin. |
| Reports | The placeholder report is replaced by a readable fixed-sample preview and Print / Save as PDF, with optional technical JSON. Source switching aborts pending exports, duplicate requests are guarded, and old responses cannot overwrite the newer request's busy state. No control action is implied. |
| Concurrency | Bounded single-flight caches prevent repeated cold loads for the same key. Per-client cursors, atomic frames and superseded-request cancellation preserve source/run/sample identity. |
| Windows disconnects | Historical WinError 10054 tracebacks originated in the Proactor socket-shutdown callback after peer resets. The new selector-loop launcher avoids that callback and passed deliberate peer-reset checks; the old log is preserved, not overwritten. |
| Dataset reliability | Downloads validate before replacement. CSV/Parquet/replay/manifest writes use temporary files and atomic replacement. TEP ingestion processes individual source tables rather than concatenating 15.33M rows, validates exact feature names and complete run/sample identities. |
| Windows pipeline | Uses the project's Python environment, resolves the repository independently of working directory and stops on failed native commands. AI4I plots use a headless renderer. |
| Dependencies and documentation | Vite updated to 6.4.3; package lock updated. Outdated starter/ML/API architecture text corrected. Explicit 3D loading/WebGL-unavailable messages added. |

## Verification results

- 23 Python unit/integration tests: atomic frames, valid/invalid boundaries, model degradation, source separation, exact training/inference features, snapshot identity, REST/WebSocket agreement/end closure, atomic ingestion, legacy replay, explicit I/O degradation, single-flight/bounded caching, concurrent mixed-source requests and deterministic parallel predictions.
- 12 browser playback checks passed: slow-network no-flicker, 3D movement between samples, pause cancellation/frozen frames, early missing forecast, seek/end/restart, speed, disconnect/retry, selected-run readings, mobile layout and 2D play/pause; no browser exceptions.
- 18 browser integration checks passed: API-hosted build, preview/dev proxies, separate dataset reports, source/error recovery, missing-model measured-data retention, mobile layout, native keyboard focus/Escape, readable report/PDF/print layout and delayed/duplicate export races. Desktop 3D and mobile report screenshots visually reviewed.
- 10 model-evaluation browser checks passed: readable pages on dev/built origins, metrics matching saved cards, confusion matrix, safety/provenance text, unchanged JSON APIs, mobile layout and failure/retry. No browser runtime exceptions in any of the three suites.
- Live bounded concurrency regression passed: **128 HTTP requests at concurrency 16**, **8 independently ordered WebSocket clients**, normal final-sample closure, and **8 deliberate abrupt peer resets**. Model readiness and source/sample/chart agreement held. Median HTTP latency **563 ms**, p95 **1,688 ms** for this local mixed-load run. Fresh backend runtime log contains no callback traceback; this does not establish a production capacity SLA.
- Full read-only data audit passed, not just a sample: **15,330,000 TEP rows, 21,000 complete trajectories, all 52 feature columns finite**, no duplicate/missing/out-of-range sample identities. All raw-source hashes match manifests; both model-card dataset hashes match current TEP Parquet.
- AI4I: **10,000 complete UDI records, no nulls, 339 published failure labels**; raw-source hash and manifest agree.
- TypeScript compilation, Vite production build, Python compilation and `pip check` passed. `npm audit` reports **0 known vulnerabilities** at audit time.
- `git fetch origin` succeeded; `HEAD...origin/main` reports **0 ahead / 0 behind**. Local ongoing changes are uncommitted; this does not mean those local edits have been uploaded.
- API health: `ok`; both datasets available, both TEP models ready. Local development dashboard: `http://127.0.0.1:5173/`; built dashboard: `http://127.0.0.1:8000/`.

Reproduce with the repository `.venv`: `python -m unittest discover -s tests -p "test_*.py" -v`, `python -m scripts.verify_data`, `python scripts/concurrency_check.py` (running backend required), and the three browser scripts `tests/dashboard_playback_check.py`, `tests/dashboard_integration_check.py`, `tests/model_evaluation_check.py` (running app/API and QA Chrome CDP on 9225 required). Run browser scripts sequentially because they share a QA page; build before starting them. Build/audit from `frontend/` with `npm.cmd run build` and `npm.cmd audit`. Test dependency setup is in `backend/requirements-dev.txt`. Start the backend with `python backend/run_server.py`.

## Remaining boundaries

This is a verified local research prototype, **not an industry-certified live plant twin**. Physical sensor ingestion, authenticated industrial access, historian/audit infrastructure, validated event-time labels, calibrated failure/leak probabilities, approved safety limits and independent safety review are not present. No real valve actuation occurs. The fault detector's held-out recall remains approximately 0.546; it must not be represented as a dependable operational hazard detector.

The build emits a non-blocking large Three.js bundle warning (~1.17 MB uncompressed). The installed Starlette test client emits a non-blocking `httpx` deprecation warning; tests pass. TEP's largest RData source still requires substantial RAM despite reduced ingestion memory use. Backend model binaries are trusted local artifacts, not arbitrary uploaded pickles. Re-ingesting a different Parquet file requires retraining and repeating the fingerprint audit. Stop serving during ingestion/retraining: replacing individual files is not a transactional hot deployment of the complete dataset/model/card set. The local Windows selector-loop server has platform socket limits; no unlimited concurrency or industrial deployment certification is claimed.

Checks establish the tested paths and current artifacts; they do not guarantee absence of every possible future defect or validate real-world process safety.
