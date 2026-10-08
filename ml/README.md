# ML workspace

The local dashboard uses the complete TEP (15,330,000 rows) and AI4I (10,000 rows) published benchmarks. Raw downloads and generated Parquet/model binaries are ignored by Git; their provenance and schema are recorded in processed manifests.

Use the repository `.venv` and run modules from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ml.ingestion.fetch_tep
.\.venv\Scripts\python.exe -m ml.ingestion.ingest_tep
.\.venv\Scripts\python.exe -m ml.ingestion.fetch_ai4i
.\.venv\Scripts\python.exe -m ml.ingestion.ingest_ai4i
.\.venv\Scripts\python.exe -m ml.ingestion.fetch_tep_rtf
.\.venv\Scripts\python.exe -m ml.ingestion.ingest_tep_rtf
.\.venv\Scripts\python.exe -m ml.eda.tep_eda
.\.venv\Scripts\python.exe -m ml.eda.ai4i_eda
.\.venv\Scripts\python.exe -m ml.train_tep_detector
.\.venv\Scripts\python.exe -m ml.train_tep_pressure_forecast
.\.venv\Scripts\python.exe -m ml.train_tep_rtf
.\.venv\Scripts\python.exe -m ml.simulation.generate_equipment_prognosis
.\.venv\Scripts\python.exe -m ml.train_equipment_prognosis
.\.venv\Scripts\python.exe -m scripts.verify_data
```

Downloads are validated before replacement; processed outputs are published atomically. TEP ingestion processes one RData table at a time instead of concatenating the complete dataset in memory. RTF ingestion records a SHA-256 fingerprint for every generated Parquet and revalidates an existing ingestion before reusing it. The largest individual RData file still requires substantial RAM.

The fault detector uses 52 variables to classify the current sample. The separate seven-feature regressor estimates reactor pressure at +20 simulated minutes. The RTF regressor uses current-and-past windows to estimate time to the recorded simulated endpoint. Because the archive has no verified terminal-equipment labels, its component output deliberately abstains. A separate labelled dynamic-surrogate benchmark trains within-hour risk, equipment/mode and RUL models for five units; those labels are synthetic and are never attached to official RTF runs. Features, source fingerprints, run-group splits, metrics and limitations are in `docs/models/`. Every trainer atomically publishes a model/card pair with one shared artifact ID, and backend inference rejects crossed versions. These are research models, not validated failure probabilities or plant controls.

`prepare_tep_replay` is an optional legacy extraction. The main dashboard selects trajectories directly from the full Parquet dataset and does not depend on that fixed extraction.

