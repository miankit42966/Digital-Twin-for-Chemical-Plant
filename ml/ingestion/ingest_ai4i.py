"""Validate AI4I's documented schema and write a versioned Parquet dataset."""
from __future__ import annotations

import pandas as pd

from ml.ingestion.common import REPO_ROOT, atomic_output, write_manifest

VERSION = "uci-601"
RAW = REPO_ROOT / "data" / "raw" / "ai4i" / "ai4i2020.csv"
OUTPUT = REPO_ROOT / "data" / "processed" / "ai4i" / VERSION
EXPECTED = ["UDI", "Product ID", "Type", "Air temperature [K]", "Process temperature [K]", "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]", "Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"]


def main() -> None:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing {RAW}. Run: py -m ml.ingestion.fetch_ai4i")
    frame = pd.read_csv(RAW)
    if frame.columns.tolist() != EXPECTED:
        raise ValueError(f"AI4I column mismatch. Expected {EXPECTED}; got {frame.columns.tolist()}")
    if len(frame) != 10_000:
        raise ValueError(f"AI4I UCI 601 should have 10,000 records; got {len(frame)}")
    if frame.isna().any().any():
        raise ValueError("AI4I contains null values, contrary to documented source metadata; raw input was not altered.")
    if set(frame["Type"].unique()) - {"L", "M", "H"}:
        raise ValueError("Unexpected AI4I product-type code.")
    for label in ["Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"]:
        if set(frame[label].unique()) - {0, 1}:
            raise ValueError(f"{label} is not a binary indicator.")
    if frame["UDI"].tolist() != list(range(1, 10_001)):
        raise ValueError("UDI must be exactly 1 through 10000 in source order.")
    # Lossless name normalization supports stable feature references in later phases.
    processed = frame.rename(columns={column: column.lower().replace(" ", "_").replace("[", "").replace("]", "").replace("/", "_") for column in frame.columns})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with atomic_output(OUTPUT / "ai4i.parquet") as temporary:
        processed.to_parquet(temporary, index=False)
    write_manifest(OUTPUT, [RAW], len(processed), processed.columns.tolist(), "ml.ingestion.ingest_ai4i")
    print(f"Wrote {len(processed)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

