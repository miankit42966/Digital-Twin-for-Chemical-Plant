"""Validate and combine published TEP RData tables without fabricating labels."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pyreadr

from ml.ingestion.common import REPO_ROOT, write_manifest

VERSION = "harvard-dvn-6c3jr1-v1.0"
RAW_DIR = REPO_ROOT / "data" / "raw" / "tep"
OUTPUT = REPO_ROOT / "data" / "processed" / "tep" / VERSION
FILES = ("TEP_FaultFree_Training.RData", "TEP_Faulty_Training.RData", "TEP_FaultFree_Testing.RData", "TEP_Faulty_Testing.RData")


def normalized(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_one(path: Path) -> pd.DataFrame:
    objects = pyreadr.read_r(path)
    frames = [value for value in objects.values() if isinstance(value, pd.DataFrame)]
    if len(frames) != 1:
        raise ValueError(f"{path.name}: expected one tabular R object; found {len(frames)}")
    frame = frames[0].copy()
    frame.columns = [normalized(str(column)) for column in frame.columns]
    sensor_columns = [column for column in frame.columns if column.startswith("xmeas_") or column.startswith("xmv_")]
    if len(sensor_columns) != 52:
        raise ValueError(f"{path.name}: expected 41 xmeas + 11 xmv columns (52); found {len(sensor_columns)}")
    for required in ("faultnumber", "simulationrun", "sample"):
        if required not in frame.columns:
            raise ValueError(f"{path.name}: missing required TEP field {required!r}; got {frame.columns.tolist()}")
    if frame[sensor_columns].isna().any().any():
        raise ValueError(f"{path.name}: sensor nulls found; raw data was not altered.")
    return frame


def main() -> None:
    paths = [RAW_DIR / name for name in FILES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing TEP source file(s): " + ", ".join(missing) + ". Run: py -m ml.ingestion.fetch_tep")
    tables: list[pd.DataFrame] = []
    for path in paths:
        frame = load_one(path)
        frame["dataset_partition"] = "training" if "Training" in path.name else "testing"
        frame["published_condition"] = "fault_free" if "FaultFree" in path.name else "faulty"
        tables.append(frame)
    merged = pd.concat(tables, ignore_index=True)
    if (merged["faultnumber"] < 0).any() or (merged["simulationrun"] < 1).any() or (merged["sample"] < 1).any():
        raise ValueError("TEP identifiers include out-of-range values.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUTPUT / "tep.parquet", index=False)
    write_manifest(OUTPUT, paths, len(merged), merged.columns.tolist(), "ml.ingestion.ingest_tep")
    print(f"Wrote {len(merged)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

