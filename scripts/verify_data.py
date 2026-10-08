r"""Read-only, full-dataset integrity/provenance audit (not a sampled check).

Run from the repository root: .venv\Scripts\python.exe -m scripts.verify_data
"""
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import joblib

from ml.ingestion.common import REPO_ROOT, sha256
from ml.ingestion.fetch_tep_rtf import EXPECTED_BYTES as RTF_BYTES, EXPECTED_MD5 as RTF_MD5, md5sum
from ml.ingestion.ingest_tep_rtf import CSV_NAMES as RTF_CASES, DOCUMENTED_CASES as RTF_DOCUMENTED, OUTPUT as RTF_OUTPUT
from ml.simulation.generate_equipment_prognosis import DATA as LAB_DATA, MANIFEST as LAB_MANIFEST, SENSORS as LAB_SENSORS

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
    for name, model_name in (('TEP_fault_detector.json', 'tep_fault_detector.joblib'),
                             ('TEP_pressure_20m.json', 'tep_pressure_20m.joblib')):
        card = json.loads((REPO_ROOT / 'docs/models' / name).read_text(encoding='utf-8'))
        check(card['dataset_sha256'] == digest, f'Model card is stale: {name}')
        bundle = joblib.load(REPO_ROOT / 'models' / model_name)
        check(bundle.get('artifact_id') == card.get('artifact_id'), f'Model/card artifact mismatch: {name}')
    ai4i, ai_digest = provenance(REPO_ROOT / 'data/processed/ai4i/uci-601', REPO_ROOT / 'data/raw/ai4i', 'ai4i.parquet')
    table = ai4i.read().sort_by([('udi', 'ascending')])
    check(table.num_rows == 10_000 and table.column('udi').to_pylist() == list(range(1, 10_001)), 'Incomplete AI4I sequence')
    check(all(table.column(name).null_count == 0 for name in table.column_names), 'AI4I null values')
    check(sum(table.column('machine_failure').to_pylist()) == 339, 'AI4I label count mismatch')
    rtf_manifest = json.loads((RTF_OUTPUT / 'manifest.json').read_text(encoding='utf-8'))
    rtf_archive = REPO_ROOT / 'data/raw/tep_rtf/TEP.zip'
    check(rtf_archive.stat().st_size == RTF_BYTES and md5sum(rtf_archive) == RTF_MD5, 'TEP RTF archive integrity mismatch')
    check(sha256(rtf_archive) == rtf_manifest['source_sha256'], 'TEP RTF source fingerprint mismatch')
    check(set(rtf_manifest['cases']) == set(RTF_CASES), 'TEP RTF case manifest mismatch')
    rtf_rows = 0
    rtf_runs = 0
    for case in RTF_CASES:
        parquet = pq.ParquetFile(RTF_OUTPUT / f'{case}.parquet')
        detail = rtf_manifest['cases'][case]
        check(parquet.metadata.num_rows == detail['rows'], f'{case}: RTF row count mismatch')
        check(parquet.schema_arrow.names == rtf_manifest['columns'], f'{case}: RTF schema mismatch')
        expected_hdf = 'all_values_match' if case in RTF_DOCUMENTED else 'not_present_in_hdf5'
        check(detail['hdf5_consistency'] == expected_hdf, f'{case}: RTF HDF5 audit status mismatch')
        check(sha256(RTF_OUTPUT / f'{case}.parquet') == detail.get('processed_sha256'), f'{case}: RTF Parquet checksum mismatch')
        for batch in parquet.iter_batches(batch_size=100_000):
            for column in batch.columns:
                check(column.null_count == 0 and np.isfinite(column.to_numpy()).all(), f'{case}: non-finite RTF value')
        rtf_rows += parquet.metadata.num_rows
        rtf_runs += detail['run_count']
    rtf_card = json.loads((REPO_ROOT / 'docs/models/TEP_RTF_prognosis.json').read_text(encoding='utf-8'))
    rtf_bundle = joblib.load(REPO_ROOT / 'models/tep_rtf_prognosis.joblib')
    check(rtf_card['source_sha256'] == rtf_manifest['source_sha256'], 'TEP RTF model card is stale')
    check(rtf_bundle.get('artifact_id') == rtf_card.get('artifact_id'), 'TEP RTF model/card artifact mismatch')
    check(rtf_card['next_unit_status'] == 'unavailable_no_verified_terminal_unit_labels'
          and rtf_card['abstention_rate'] == 1.0, 'TEP RTF equipment-label gate is not fail-closed')
    lab_manifest = json.loads(LAB_MANIFEST.read_text(encoding='utf-8'))
    lab_parquet = pq.ParquetFile(LAB_DATA)
    check(lab_manifest['run_count'] == 1200 and lab_manifest['failure_run_count'] == 1000
          and lab_manifest['censored_run_count'] == 200, 'Synthetic prognosis run contract mismatch')
    check(lab_parquet.metadata.num_rows == lab_manifest['rows'], 'Synthetic prognosis row count mismatch')
    check(lab_parquet.schema_arrow.names == lab_manifest['columns'], 'Synthetic prognosis schema mismatch')
    check(sha256(LAB_DATA) == lab_manifest['data_sha256'], 'Synthetic prognosis data fingerprint mismatch')
    for batch in lab_parquet.iter_batches(columns=list(LAB_SENSORS), batch_size=100_000):
        for column in batch.columns:
            check(column.null_count == 0 and np.isfinite(column.to_numpy()).all(), 'Non-finite synthetic prognosis value')
    lab_card = json.loads((REPO_ROOT / 'docs/models/EQUIPMENT_PROGNOSIS.json').read_text(encoding='utf-8'))
    lab_bundle = joblib.load(REPO_ROOT / 'models/equipment_prognosis.joblib')
    check(lab_bundle.get('artifact_id') == lab_card.get('artifact_id'), 'Synthetic prognosis model/card artifact mismatch')
    check(lab_card['data_sha256'] == lab_manifest['data_sha256'], 'Synthetic prognosis model/data mismatch')
    check(lab_card['release_ready'] and all(lab_card['release_gates'].values()), 'Synthetic prognosis release gates failed')
    print(json.dumps({'status': 'pass', 'tep_rows': tep.metadata.num_rows, 'complete_tep_trajectories': 21_000,
                      'tep_features': len(FEATURES), 'tep_sha256': digest,
                      'ai4i_rows': table.num_rows, 'ai4i_failure_labels': 339, 'ai4i_sha256': ai_digest,
                      'tep_rtf_rows': rtf_rows, 'tep_rtf_runs': rtf_runs,
                      'tep_rtf_documented_csv_hdf5': 'all values match',
                      'tep_rtf_next_unit': 'unavailable; 100% abstention',
                      'synthetic_prognosis_rows': lab_parquet.metadata.num_rows,
                      'synthetic_prognosis_runs': lab_manifest['run_count'],
                      'synthetic_prognosis_release_gates': 'all pass',
                      'raw_source_hashes': 'all match ingestion manifests'}, indent=2))


if __name__ == '__main__':
    main()
