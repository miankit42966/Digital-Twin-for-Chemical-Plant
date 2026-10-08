"""Resume and verify the published TEP run-to-failure archive."""
from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from ml.ingestion.common import REPO_ROOT

URL = "https://entrepot.recherche.data.gouv.fr/api/access/datafile/762134"
DESTINATION = REPO_ROOT / "data/raw/tep_rtf/TEP.zip"
EXPECTED_BYTES = 2_673_538_262
EXPECTED_MD5 = "f892a79202a80d95e4c3d146b8c32412"
CHUNK = 4 * 1024 * 1024


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verified(path: Path) -> bool:
    return path.is_file() and path.stat().st_size == EXPECTED_BYTES and md5sum(path) == EXPECTED_MD5


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if verified(DESTINATION):
        print(f"Verified existing archive: {DESTINATION}", flush=True)
        return
    if DESTINATION.exists():
        raise RuntimeError(f"Existing archive failed verification; preserve and inspect it: {DESTINATION}")
    partial = DESTINATION.with_suffix(".zip.part")
    consecutive_failures = 0
    while True:
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > EXPECTED_BYTES:
            raise RuntimeError(f"Partial file exceeds published size: {partial}")
        if offset == EXPECTED_BYTES:
            break
        headers = {"User-Agent": "SentinelTwin-Academic-Data-Ingestion/0.1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(URL, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = response.status
                if offset and status == 206:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise RuntimeError(f"Unexpected Content-Range: {content_range}")
                    mode = "ab"
                elif status == 200:
                    mode = "wb"
                else:
                    raise RuntimeError(f"Unexpected HTTP status {status} for offset {offset}")
                with partial.open(mode) as output:
                    while block := response.read(CHUNK):
                        output.write(block)
            print(f"Downloaded {partial.stat().st_size:,} / {EXPECTED_BYTES:,} bytes", flush=True)
            consecutive_failures = 0
        except (OSError, urllib.error.URLError) as exc:
            consecutive_failures += 1
            print(f"Download interrupted ({consecutive_failures}/20) at {partial.stat().st_size if partial.exists() else 0:,} bytes: {exc}", flush=True)
            if consecutive_failures >= 20:
                raise
            time.sleep(min(30, consecutive_failures * 3))
    if partial.stat().st_size != EXPECTED_BYTES:
        raise RuntimeError(f"Archive size mismatch: {partial.stat().st_size} != {EXPECTED_BYTES}")
    actual = md5sum(partial)
    if actual != EXPECTED_MD5:
        raise RuntimeError(f"Archive checksum mismatch: {actual} != {EXPECTED_MD5}; partial preserved")
    os.replace(partial, DESTINATION)
    print(f"Verified and saved: {DESTINATION}", flush=True)


if __name__ == "__main__":
    main()
