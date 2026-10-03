"""Read the published AI4I 2020 maintenance benchmark without invented telemetry."""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
from app.services.cache import singleflight_cache

SOURCE = Path(__file__).resolve().parents[3] / "data/processed/ai4i/uci-601/ai4i.parquet"
NOTICE = (
    "Published AI4I 2020 synthetic-but-realistic machining benchmark. "
    "It is not chemical-plant telemetry or a live machine connection."
)


def available() -> bool:
    return SOURCE.is_file()


def _rows() -> tuple[dict, ...]:
    if not available():
        raise FileNotFoundError(f"AI4I Parquet dataset missing: {SOURCE}")
    stat = SOURCE.stat()
    return _read_rows((stat.st_mtime_ns, stat.st_size))


@singleflight_cache(maxsize=1)
def _read_rows(signature: tuple[int, int]) -> tuple[dict, ...]:
    rows = tuple(pq.read_table(SOURCE).sort_by([("udi", "ascending")]).to_pylist())
    if len(rows) != 10_000 or [int(row["udi"]) for row in rows] != list(range(1, 10_001)):
        raise ValueError("AI4I dataset is incomplete or UDI sequence is invalid")
    return rows


def summary() -> dict:
    return _summary(_rows())


def _summary(rows: tuple[dict, ...]) -> dict:
    return {
        "source_kind": "AI4I_DATASET", "notice": NOTICE, "total_records": len(rows),
        "failure_records": sum(int(row["machine_failure"]) for row in rows),
        "product_types": {kind: sum(row["type"] == kind for row in rows) for kind in ("L", "M", "H")},
        "failure_modes": {name.upper(): sum(int(row[name]) for row in rows) for name in ("twf", "hdf", "pwf", "osf", "rnf")},
    }


def record(udi: int) -> dict:
    if not 1 <= udi <= 10_000:
        raise ValueError("udi must be from 1 to 10000")
    return {"source_kind": "AI4I_DATASET", "notice": NOTICE, **_rows()[udi - 1]}


def records(start: int = 1, limit: int = 50) -> dict:
    if not 1 <= start <= 10_000:
        raise ValueError("start must be from 1 to 10000")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be from 1 to 200")
    return {"source_kind": "AI4I_DATASET", "notice": NOTICE, "start": start,
            "records": _rows()[start - 1:start - 1 + limit]}


def frame(udi: int = 1) -> dict:
    if not 1 <= udi <= 10_000:
        raise ValueError("udi must be from 1 to 10000")
    rows = _rows()
    start = max(1, udi - 4)
    return {"source_kind": "AI4I_DATASET", "summary": _summary(rows),
            "record": {"source_kind": "AI4I_DATASET", "notice": NOTICE, **rows[udi - 1]},
            "neighbors": {"source_kind": "AI4I_DATASET", "notice": NOTICE,
                          "start": start, "records": rows[start - 1:start + 8]}}
