r"""Read-only, full-dataset integrity/provenance audit (not a sampled check).

Run from the repository root: .venv\Scripts\python.exe -m scripts.verify_data
"""
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from ml.ingestion.common import REPO_ROOT, sha256

FEATURES = [f'xmeas_{i}' for i in range(1, 42)] + [f'xmv_{i}' for i in range(1, 12)]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def provenance(directory: Path, raw_directory: Path, data_file: str):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    parquet = pq.ParquetFile(directory / data_file)
    check(parquet.metadata.num_rows == manifest['row_count'], 'Manifest row count mismatch')
    check(parquet.schema_arrow.names == manifest['columns'], 'Manifest schema mismatch')
    for source in manifest['source_files']:
        path = raw_directory / source['name']
        check(path.stat().st_size == source['bytes'], f'Source size mismatch: {path.name}')
        check(sha256(path) == source['sha256'], f'Source checksum mismatch: {path.name}')
    return parquet, sha256(directory / data_file)


def main():
    tep, digest = provenance(REPO_ROOT / 'data/processed/tep/harvard-dvn-6c3jr1-v1.0', REPO_ROOT / 'data/raw/tep', 'tep.parquet')
    check(tep.metadata.num_rows == 15_330_000, 'Incomplete TEP dataset')
    observed = {'training': np.zeros(21 * 500 * 500, dtype=bool), 'testing': np.zeros(21 * 500 * 960, dtype=bool)}
    check(set(FEATURES).issubset(tep.schema_arrow.names), 'TEP feature schema mismatch')
    for batch in tep.iter_batches(batch_size=50_000):
        for name in FEATURES:
            values = batch.column(name)
            check(values.null_count == 0 and np.isfinite(values.to_numpy()).all(), f'Non-finite TEP values: {name}')
        faults, runs, samples = [batch.column(name).to_numpy() for name in ('faultnumber', 'simulationrun', 'sample')]
        for values in (faults, runs, samples):
            check(np.isfinite(values).all() and np.equal(values, values.astype(np.int32)).all(), 'TEP identifier invalid')
        check(((faults >= 0) & (faults <= 20) & (runs >= 1) & (runs <= 500)).all(), 'TEP run/fault out of bounds')
        partitions = np.asarray(batch.column('dataset_partition').to_pylist())
        conditions = np.asarray(batch.column('published_condition').to_pylist())
        check(np.isin(partitions, ['training', 'testing']).all(), 'Unknown partition')
        check((conditions == np.where(faults == 0, 'fault_free', 'faulty')).all(), 'Fault condition mismatch')
        for partition, length in (('training', 500), ('testing', 960)):
            mask = partitions == partition
            selected = samples[mask]
            check(((selected >= 1) & (selected <= length)).all(), 'Sample out of bounds')
            keys = ((faults[mask].astype(np.int32) * 500 + runs[mask].astype(np.int32) - 1) * length + selected.astype(np.int32) - 1)
            check(len(np.unique(keys)) == len(keys) and not observed[partition][keys].any(), 'Duplicate TEP sample')
            observed[partition][keys] = True
    check(all(values.all() for values in observed.values()), 'Missing TEP trajectory samples')
    for name in ('TEP_fault_detector.json', 'TEP_pressure_20m.json'):
        card = json.loads((REPO_ROOT / 'docs/models' / name).read_text(encoding='utf-8'))
        check(card['dataset_sha256'] == digest, f'Model card is stale: {name}')
    ai4i, ai_digest = provenance(REPO_ROOT / 'data/processed/ai4i/uci-601', REPO_ROOT / 'data/raw/ai4i', 'ai4i.parquet')
    table = ai4i.read().sort_by([('udi', 'ascending')])
    check(table.num_rows == 10_000 and table.column('udi').to_pylist() == list(range(1, 10_001)), 'Incomplete AI4I sequence')
    check(all(table.column(name).null_count == 0 for name in table.column_names), 'AI4I null values')
    check(sum(table.column('machine_failure').to_pylist()) == 339, 'AI4I label count mismatch')
    print(json.dumps({'status': 'pass', 'tep_rows': tep.metadata.num_rows, 'complete_tep_trajectories': 21_000,
                      'tep_features': len(FEATURES), 'tep_sha256': digest,
                      'ai4i_rows': table.num_rows, 'ai4i_failure_labels': 339, 'ai4i_sha256': ai_digest,
                      'raw_source_hashes': 'all match ingestion manifests'}, indent=2))


if __name__ == '__main__':
    main()
