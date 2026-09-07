from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(output_dir: Path, source_files: list[Path], row_count: int, columns: list[str], script: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "processing_timestamp_utc": datetime.now(UTC).isoformat(),
        "script": script,
        "source_files": [{"name": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in source_files],
        "row_count": row_count,
        "columns": columns,
        "transformations": "Schema validation and lossless column-name normalization only; no rows are imputed, dropped, sampled, or synthetically generated.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

