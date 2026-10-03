"""Fetch the unmodified AI4I archive from UCI Dataset 601."""
from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256

URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
DESTINATION = REPO_ROOT / "data" / "raw" / "ai4i"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download AI4I 2020 directly from UCI.")
    parser.add_argument("--force", action="store_true", help="Replace existing archive and CSV.")
    args = parser.parse_args()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    archive = DESTINATION / "ai4i_uci_601.zip"
    csv = DESTINATION / "ai4i2020.csv"
    if csv.exists() and not args.force:
        print(f"Already present: {csv} (sha256={sha256(csv)})")
        return
    print(f"Downloading {URL}")
    with atomic_output(archive) as temporary:
        with urllib.request.urlopen(URL, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        with zipfile.ZipFile(temporary) as zipped:
            if zipped.testzip() is not None:
                raise ValueError("UCI archive failed its CRC check")
            if len([name for name in zipped.namelist() if name.lower().endswith('.csv')]) != 1:
                raise ValueError("UCI archive must contain exactly one CSV")
    with zipfile.ZipFile(archive) as zipped:
        members = [member for member in zipped.namelist() if member.lower().endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"Expected one CSV in UCI archive; found {members!r}")
        with atomic_output(csv) as temporary:
            with zipped.open(members[0]) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
    print(f"Saved unchanged CSV: {csv} (sha256={sha256(csv)})")


if __name__ == "__main__":
    main()

