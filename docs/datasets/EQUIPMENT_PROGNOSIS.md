# Equipment Prognosis Lab dataset

This dataset is generated locally by `ml.simulation.generate_equipment_prognosis`; it is not part of the official TEP or TEP run-to-failure publications.

- 1,200 complete run families at a three-simulated-minute cadence.
- 1,000 terminal runs: 100 for each of ten injected degradation modes across five equipment units.
- 200 healthy/censored 24-hour runs.
- Coupled reactor, condenser, separator, stripper and compressor measurements with bounded stochastic variation.
- Explicit run-level equipment, mode, onset, terminal, RUL, shutdown-reason and censoring labels.

The generator seed, configuration identity, columns, run metadata, row count and Parquet SHA-256 are stored in `data/processed/equipment_prognosis/manifest.json`. Training uses only current and previous measurements. Labels, run identity, future samples, terminal time and true RUL are excluded from model inputs. Complete runs are assigned to one deterministic train, validation or test partition.

The benchmark is designed to test software/data contracts and demonstrate prognosis with known simulation truth. High held-out scores measure recovery of its injected patterns; they do not establish performance on a real chemical plant.
