from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from tools.ingest_profiles import ProfileArchiveError, ingest

CSV_BODY = "header;row\n2025-01-01 00:15;0.1\n"


def _archive_bytes(names: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, CSV_BODY)
    return buffer.getvalue()


def test_ingest_extracts_the_main_profile_csv(tmp_path: Path) -> None:
    payload = _archive_bytes(
        [
            "Standaardprofielen elektriciteit 2025 versie 1.00.csv",
            "Standaardprofielen elektriciteit 2025 versie E4A_21 1.00.csv",
            "readme.pdf",
        ]
    )
    written = ingest(2025, tmp_path, opener=lambda url: payload)
    assert written == tmp_path / "nedu-profiles-2025.csv"
    assert written.read_text(encoding="utf-8") == CSV_BODY


def test_ingest_rejects_an_archive_without_a_profile_csv(tmp_path: Path) -> None:
    payload = _archive_bytes(["readme.pdf"])
    with pytest.raises(ProfileArchiveError, match="no profile CSV"):
        ingest(2025, tmp_path, opener=lambda url: payload)


def test_ingest_rejects_an_ambiguous_archive(tmp_path: Path) -> None:
    payload = _archive_bytes(
        [
            "Standaardprofielen elektriciteit 2025 versie 1.00.csv",
            "Standaardprofielen elektriciteit 2025 versie 1.01.csv",
        ]
    )
    with pytest.raises(ProfileArchiveError, match="ambiguous"):
        ingest(2025, tmp_path, opener=lambda url: payload)


def test_ingest_creates_the_target_directory(tmp_path: Path) -> None:
    payload = _archive_bytes(["Standaardprofielen elektriciteit 2025 versie 1.00.csv"])
    target = tmp_path / "nested" / "data"
    written = ingest(2025, target, opener=lambda url: payload)
    assert written.exists()
