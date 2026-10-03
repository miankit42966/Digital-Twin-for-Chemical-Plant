"""Extract one bounded, reproducible TEP testing run for interactive replay."""
from __future__ import annotations

import argparse
import json

import pyarrow.parquet as pq

from ml.ingestion.common import REPO_ROOT, atomic_output

SOURCE = REPO_ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet"
OUTPUT = REPO_ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/replay.json"
MEASUREMENTS = tuple(f"xmeas_{i}" for i in range(1, 42)) + tuple(f"xmv_{i}" for i in range(1, 12))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault", type=int, default=6, choices=range(1, 21))
    parser.add_argument("--run", type=int, default=401, choices=range(1, 501))
    args = parser.parse_args()
    if not SOURCE.exists():
        raise FileNotFoundError(f"Run TEP ingestion first: {SOURCE}")
    columns = ("faultnumber", "simulationrun", "sample", "dataset_partition", "published_condition", *MEASUREMENTS)
    records: list[dict[str, int | float]] = []
    for batch in pq.ParquetFile(SOURCE).iter_batches(batch_size=50_000, columns=columns):
        frame = batch.to_pandas()
        chosen = frame.loc[
            (frame["faultnumber"] == args.fault)
            & (frame["simulationrun"] == args.run)
            & (frame["dataset_partition"] == "testing")
            & (frame["published_condition"] == "faulty"),
            ["sample", *MEASUREMENTS],
        ]
        if not chosen.empty:
            records.extend(chosen.to_dict(orient="records"))
    records.sort(key=lambda row: int(row["sample"]))
    if len(records) != 960 or [int(row["sample"]) for row in records] != list(range(1, 961)):
        raise ValueError(f"Expected one complete 960-sample testing run; got {len(records)} rows")
    payload = {
        "source": "Harvard Dataverse doi:10.7910/DVN/6C3JR1, version 1.0",
        "partition": "testing", "fault_number": args.fault, "simulation_run": args.run,
        "sample_period_minutes": 3,
        "sample_period_source": "Tennessee Eastman simulator documentation; dataset rows have no wall-clock timestamp",
        "rows": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output(OUTPUT) as temporary:
        temporary.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"Prepared {len(records)} TEP replay samples: {OUTPUT}")


if __name__ == "__main__":
    main()
