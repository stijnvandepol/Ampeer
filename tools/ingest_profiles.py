"""Fetch NEDU standard consumption profiles into the local data directory.

The redistribution licence of these files is not confirmed, so they are never
committed. Run this at build or deploy time.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests

ARCHIVE_URL = (
    "https://energiedatawijzer.nl/app/uploads/Documenten/Profielen/Profielen/"
    "Profielen-elektriciteit-{year}-v1.00-incl.-verslag.zip"
)

UrlOpener = Callable[[str], bytes]


class ProfileArchiveError(RuntimeError):
    """The downloaded archive did not look the way we expect."""


def _download(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _select_profile_member(names: list[str]) -> str:
    candidates = [
        name
        for name in names
        if name.lower().endswith(".csv")
        and "standaardprofielen elektriciteit" in name.lower()
        and "e4a" not in name.lower()
    ]
    if not candidates:
        raise ProfileArchiveError("archive contains no profile CSV")
    if len(candidates) > 1:
        raise ProfileArchiveError(f"ambiguous archive, found {len(candidates)} profile CSVs")
    return candidates[0]


def ingest(year: int, target_dir: Path, opener: UrlOpener | None = None) -> Path:
    """Download the archive for ``year`` and write the main CSV into ``target_dir``."""
    fetch = opener or _download
    payload = fetch(ARCHIVE_URL.format(year=year))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        member = _select_profile_member(archive.namelist())
        body = archive.read(member)
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / f"nedu-profiles-{year}.csv"
    destination.write_bytes(body)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int)
    parser.add_argument("--target", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    written = ingest(args.year, args.target)
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
