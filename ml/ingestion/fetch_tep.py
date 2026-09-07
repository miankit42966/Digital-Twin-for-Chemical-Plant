"""Fetch the four unmodified TEP v1.0 RData files from Harvard Dataverse."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from pathlib import Path

from ml.ingestion.common import REPO_ROOT, sha256

DESTINATION = REPO_ROOT / "data" / "raw" / "tep"
FILES = {
    "TEP_FaultFree_Testing.RData": (3031240, "38ad9810fc871026157086ae2c2f0ee9"),
    "TEP_FaultFree_Training.RData": (3031241, "ec126484534331f85001d8c4ebce6d17"),
    "TEP_Faulty_Testing.RData": (3031243, "556bdb64c83021bc0c5f92e427753565"),
    "TEP_Faulty_Training.RData": (3031242, "c5f594d54c47e620ff877feb58407fda"),
}


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Harvard Dataverse TEP files (about 1.4 GB).")
    parser.add_argument("--force", action="store_true", help="Re-download files even if already present.")
    parser.add_argument("--only", choices=tuple(FILES), help="Fetch exactly one file for an interrupted-download recovery.")
    args = parser.parse_args()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    selected = {args.only: FILES[args.only]} if args.only else FILES
    for name, (file_id, expected_md5) in selected.items():
        target = DESTINATION / name
        if target.exists() and not args.force and md5sum(target) == expected_md5:
            print(f"Already present and verified: {name} (sha256={sha256(target)})")
            continue
        if target.exists() and not args.force:
            print(f"Existing {name} failed the published MD5 check; downloading it again.")
        url = f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
        print(f"Downloading {name} from Dataverse file ID {file_id}")
        request = urllib.request.Request(url, headers={"User-Agent": "SentinelTwin-Academic-Data-Ingestion/0.1 (contact: local-project)"})
        with urllib.request.urlopen(request) as response, target.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        # Dataverse exposes MD5 in v1.0 metadata; verify it before accepting raw data.
        md5 = md5sum(target)
        if md5 != expected_md5:
            raise RuntimeError(f"Checksum mismatch for {name}: expected {expected_md5}, got {md5}")
        print(f"Saved unchanged: {name} (sha256={sha256(target)})")


if __name__ == "__main__":
    main()
