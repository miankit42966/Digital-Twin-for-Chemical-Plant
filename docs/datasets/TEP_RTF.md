# TEP run-to-failure dataset

This project uses the official archive published at DOI [`10.57745/1KATN7`](https://doi.org/10.57745/1KATN7), data-file ID `762134`, as a dataset separate from the Rieth/Harvard TEP fault benchmark.

## Integrity and ingestion

- Expected archive size: `2,673,538,262` bytes.
- Published MD5: `f892a79202a80d95e4c3d146b8c32412`.
- `ml.ingestion.fetch_tep_rtf` resumes into `TEP.zip.part`, verifies size and MD5, and only then atomically publishes `TEP.zip`.
- `ml.ingestion.ingest_tep_rtf` streams the CSV members into compressed Parquet, checks the 58-column schema, finite values, integer run IDs and strictly increasing within-run time, and writes an immutable provenance manifest.
- The archive has eight CSVs (`case1` through `case7`, including `case5_1`) while the source metadata, scenario illustration and consolidated HDF5 contain six cases. Only `case1` through `case6` are eligible for modeling; `case5_1` and `case7` are quarantined pending source documentation.
- During ingestion, every value, column and row in the six documented CSVs is compared with `teps.h5`. The manifest also records each run's observed minimum/maximum timestamp step instead of assuming cadence from UI playback speed.
- Every generated case Parquet has a SHA-256 fingerprint in the manifest. A repeat ingestion validates schema, row count and this fingerprint; legacy manifests are upgraded only after a full finite-value scan.

## Target and leakage controls

Remaining time is derived from each run's recorded final timestamp. Features use a 21-sample current-and-past window only. Case, run ID, future measurements and the true terminal timestamp are not model inputs. Complete runs are assigned deterministically to train, validation or test, so samples from one run cannot cross splits.

This target means **time to the simulated run endpoint**. It does not prove equipment damage, establish that flow caused a failure, or predict a real-plant safety event.

## Equipment-label gate

The CSV schema has no independently verified per-run field naming the equipment that reaches its shutdown limit. Scenario names or process trends are not treated as ground truth. Consequently the current model card records 100% unit-classifier abstention, the API returns `next_unit_id: null`, and neither the 3D nor 2D view highlights equipment.

The highlighting path is implemented but fail-closed: it requires a ready remaining-time forecast at or below 60 simulated minutes **and** a verified, validated next-unit classifier. Adding terminal-unit labels requires publisher documentation or another independently auditable run-level outcome source, followed by grouped retraining and per-equipment precision/recall evaluation.
