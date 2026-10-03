# Tennessee Eastman Process (TEP) simulation data

## Source and version

* Official source: [Rieth et al., Harvard Dataverse](https://doi.org/10.7910/DVN/6C3JR1)
* Persistent identifier: `doi:10.7910/DVN/6C3JR1`; released dataset version **1.0** on 2017-07-06.
* Published files: `TEP_FaultFree_Training.RData`, `TEP_Faulty_Training.RData`, `TEP_FaultFree_Testing.RData`, and `TEP_Faulty_Testing.RData` (about 1.4 GB total as published).
* Terms: the Dataverse v1.0 terms dedicate the data to the public domain while disclaiming warranties and endorsement. Read the source terms before reuse.

## Contents and labels

This is a **simulation dataset**, not measurements from an operating chemical plant. The published RData tables expose 41 measured process variables (`xmeas_1`–`xmeas_41`) and 11 manipulated variables (`xmv_1`–`xmv_11`), plus fault/run/sample identifiers. `faultNumber=0` denotes the fault-free condition; faults 1–20 identify injected scenarios. There are 500 runs per fault/partition, 500 samples per training run and 960 per testing run: 15,330,000 rows and 21,000 complete trajectories.

The processor preserves the source sample index. The dashboard uses the documented **three simulated minutes** between process measurements, not physical plant timestamps: [simulator measurement documentation](https://github.com/jkitchin/tennessee-eastman-profbraatz/blob/master/docs/api.md). UI playback speed does not change that cadence. Reactor pressure is XMEAS(7) in kPa gauge, converted by division by 100 to bar(g); reactor temperature and level are XMEAS(9) and XMEAS(8). Separator and stripper mappings are explicit in `backend/app/services/tep_dataset.py`.

## Local acquisition and limitations

Run `py -m ml.ingestion.fetch_tep` to download the exact four Dataverse v1.0 files into `data/raw/tep/`, unchanged. The script checks the published MD5 checksums and later records SHA-256 values in the processed manifest. If Dataverse blocks automated access, manually download those exact four named files from the DOI landing page into that directory, then run `py -m ml.ingestion.ingest_tep` followed by `py -m ml.eda.tep_eda`. Raw RData and processed Parquet are ignored by Git because they are large. No TEP-derived dashboard value, model output, or EDA conclusion is published until this acquisition and the corresponding scripts run successfully.
