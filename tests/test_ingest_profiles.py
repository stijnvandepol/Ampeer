from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import requests

from tools import ingest_profiles
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


def test_download_returns_the_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        content = b"zipbytes"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("tools.ingest_profiles.requests.get", lambda url, timeout: _Response())
    assert ingest_profiles._download("https://example.invalid/profiles.zip") == b"zipbytes"


def test_download_propagates_an_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        content = b""

        def raise_for_status(self) -> None:
            raise requests.HTTPError("404 Not Found")

    monkeypatch.setattr("tools.ingest_profiles.requests.get", lambda url, timeout: _Response())
    with pytest.raises(requests.HTTPError):
        ingest_profiles._download("https://example.invalid/profiles.zip")


def test_main_writes_the_profile_and_reports_where(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _archive_bytes(["Standaardprofielen elektriciteit 2025 versie 1.00.csv"])
    monkeypatch.setattr(ingest_profiles, "_download", lambda url: payload)

    exit_code = ingest_profiles.main(["2025", "--target", str(tmp_path)])

    assert exit_code == 0
    written = tmp_path / "nedu-profiles-2025.csv"
    assert written.exists()
    assert str(written) in capsys.readouterr().out


def test_main_defaults_to_the_data_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        ingest_profiles,
        "ingest",
        lambda year, target: (
            captured.update(year=year, target=target) or Path("data/nedu-profiles-2025.csv")
        ),
    )
    assert ingest_profiles.main(["2025"]) == 0
    assert captured == {"year": 2025, "target": Path("data")}
