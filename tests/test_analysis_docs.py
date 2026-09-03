"""The analysis sheets are the input to decisions that have not been taken yet.

``docs/analysis/`` holds the long form measurements behind the open questions at
the end of ``docs/decisions.md``: what the double count is worth, and what the
2029 network tariff actually says. Every other document under ``docs/`` has a
suite that reads it. ``docs/methodologie.md`` has ``tests/test_methodology.py``,
``docs/dpia.md`` has ``tests/test_dpia.py``, the decision log and the plans have
one each. This directory had nothing, and it showed: two days after they landed,
one sheet said in one paragraph that a golden household already sits below the
carve-out floor and in another that no household in its own table does.

What is checked is what stays true while the prose is rewritten.

* The directory is read by globbing it, so a third sheet cannot arrive unchecked.
* Every backticked token that is a path from the root of this repository is in
  the tree, which is the rule ``tests/test_decisions.py`` applies to the decision
  log for the same reason: a rename leaves prose pointing at nothing and prose
  cannot fail a build.
* No document carries an em-dash or an en-dash.
* Each document says when its figures were taken and against what.

What is not checked is whether a figure is still the figure the engine produces.
That is not mechanically knowable from a document, and a test that implied
otherwise would be a worse guarantee than none. The provenance header is the
compromise: it cannot verify a number, it can refuse a number that arrives with
no date and nothing to reproduce it against, which is the shape of claim this
project keeps deleting.

Deliberately not checked either: whether the sha256 prefixes the double counting
sheet pins are still the digests of the files it names. That check is tempting
and it was left out on purpose. It would go red on any edit to
``ampeer_sim/production/pvgis.py``, which is another lane's file, and a red test
nobody in this lane can fix is a test people learn to skip. The digest is there
for a reader, and the reader is who it is for.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = REPO_ROOT / "docs" / "analysis"

#: Read by globbing rather than listed, so a document added tomorrow is checked
#: without an edit here. Listing them is how the third one arrives unread.
ANALYSIS = sorted(ANALYSIS_DIR.glob("*.md"))

#: The provenance every sheet carries. Two fields, for the two halves of a
#: measurement: when it was taken, and what it was taken against. A figure
#: without the second cannot be reproduced and a figure without the first cannot
#: be judged stale, and both are the failure this repository keeps removing.
REQUIRED_FIELDS = ("**Measured on:**", "**Measured against:**")

#: What CLAUDE.md forbids in text a reader sees. These sheets are English and
#: internal, so this is stricter than the rule as written, on purpose: they
#: quote Dutch from PDFs and their conclusions are destined for
#: ``docs/methodologie.md`` and the advice copy, and a pasted dash travels. It
#: is not a claim about the rest of ``docs/``: the plans carry three em-dashes
#: today. The user-facing check lives in ``tests/test_advice_nl.py``.
#: Written by codepoint rather than as the characters themselves, so that the
#: one file whose job is to refuse these does not contain either of them, and so
#: that a reader can see which two codepoints are meant without measuring the
#: width of a glyph.
FORBIDDEN_DASHES = {chr(0x2014): "em-dash", chr(0x2013): "en-dash"}

#: The first segment of a path written from the root of this repository, read
#: from the tree rather than listed, the way ``tests/test_plans.py`` reads it.
#: This is what separates `docs/decisions.md`, which is a path, from
#: `households.json` and `acm-kamerbrief-nettarieven.pdf`, which are a sibling
#: reference and an external source document. A suffix alone cannot tell those
#: apart, and reporting a regulator's PDF as a missing file would make this scan
#: noise, which is a scan people stop reading.
TOP_LEVEL = frozenset(path.name for path in REPO_ROOT.iterdir() if not path.name.startswith("__"))

#: Directories git is told to ignore, read from the file that tells it. A sheet
#: may legitimately name `data/nedu-profiles-2025.csv`, whose redistribution
#: terms are unconfirmed so it is not committed, and asserting that a git-ignored
#: file exists would make this suite pass on the machine that ingested the
#: profiles and fail in CI. This comment said "whose licence forbids committing
#: it" until 2026-09-02. There is no such licence: the profiles carry no licence
#: and no reuse condition at all, which is why the files are kept out rather than
#: in. See docs/decisions.md, "Whether the allowlist in CLAUDE.md should name a
#: fourth source".
IGNORED_ROOTS = frozenset(
    line.strip().rstrip("/")
    for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#") and line.strip().endswith("/")
)

_QUOTED = re.compile(r"`([^`]+)`")
_DATED_FILENAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-.+\.md$")
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _is_ignored(token: str) -> bool:
    return any(token == root or token.startswith(f"{root}/") for root in IGNORED_ROOTS)


def _repository_paths(text: str) -> list[str]:
    """Every backticked token that reads as a path from the root of this repo.

    ``::`` is stripped first, because a sheet cites a test by name as
    ``tests/test_methodology.py::_reference_shock`` and the file is the part that
    can be renamed out from under it.
    """
    found: list[str] = []
    for raw in _QUOTED.findall(text):
        token = raw.split("::")[0].strip()
        if not token or token.split("/")[0] not in TOP_LEVEL or _is_ignored(token):
            continue
        found.append(token)
    return found


def _field(text: str, label: str) -> str:
    """One provenance field, read to the end of its paragraph.

    Both fields wrap over several lines, so reading the label's own line would
    take the first clause and call it the whole answer.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(label):
            collected: list[str] = []
            for following in lines[index:]:
                if not following.strip():
                    break
                collected.append(following)
            return " ".join(collected)
    return ""


def _filename_date(document: Path) -> date:
    """The date in the filename, which is the day the lane was opened."""
    match = _DATED_FILENAME.match(document.name)
    assert match, (
        f"{document.name} is not named <YYYY-MM-DD>-<subject>.md, so the directory "
        "no longer says when each sheet was started"
    )
    return date.fromisoformat(match.group(1))


@pytest.mark.parametrize("document", ANALYSIS, ids=lambda document: document.name)
def test_every_repository_path_an_analysis_document_names_exists(document: Path) -> None:
    """A sheet that points at a file which moved is a sheet nobody can follow.

    These two are read by somebody deciding what to build next, and every path
    in them is an instruction to go and look. The same rule the decision log
    gets, for the same reason.
    """
    named = _repository_paths(document.read_text(encoding="utf-8"))
    missing = sorted({path for path in named if not (REPO_ROOT / path).exists()})
    assert not missing, (
        f"{document.name} names paths that are not in the tree:\n"
        + "\n".join(f"  {path}" for path in missing)
        + "\nEither something was renamed and the sheet still points at where it "
        "used to be, or the sheet describes work that was never done."
    )


@pytest.mark.parametrize("document", ANALYSIS, ids=lambda document: document.name)
def test_no_analysis_document_uses_a_dash_claude_md_forbids(document: Path) -> None:
    """The dash arrives by paste, from a PDF or from a draft written elsewhere.

    It is worth catching here rather than downstream, because these conclusions
    are copied into the methodology and into advice text, where the rule is not
    a convention but a check.
    """
    text = document.read_text(encoding="utf-8")
    present = {name: text.count(dash) for dash, name in FORBIDDEN_DASHES.items() if dash in text}
    assert not present, f"{document.name} carries {present}, which CLAUDE.md forbids"


@pytest.mark.parametrize("document", ANALYSIS, ids=lambda document: document.name)
def test_every_analysis_document_says_when_and_against_what_it_was_measured(
    document: Path,
) -> None:
    """A number with no date and no state behind it cannot be judged or redone.

    The date has to be a real date and it may not predate the filename, which is
    the day the lane opened: a sheet measured before its own question was asked
    is a header that was copied rather than written.

    "Measured against" has to name something in backticks. That is a low bar and
    it is the highest one available here, because what a sheet is measured
    against may be a file in this tree, a sha256 of one, or a PDF on a
    regulator's website. What the check refuses is the header that says nothing.
    """
    text = document.read_text(encoding="utf-8")
    missing = [field for field in REQUIRED_FIELDS if field not in text]
    assert not missing, f"{document.name} has no {', '.join(missing)}"

    measured_on = _field(text, "**Measured on:**")
    stamp = _ISO_DATE.search(measured_on)
    assert stamp, f"{document.name} says {measured_on!r}, which carries no YYYY-MM-DD date"
    taken = date.fromisoformat(stamp.group(1))
    opened = _filename_date(document)
    assert taken >= opened, (
        f"{document.name} says its figures were measured on {taken}, before the "
        f"{opened} its own filename carries"
    )

    against = _field(text, "**Measured against:**")
    assert _QUOTED.findall(against), (
        f"{document.name} names nothing its figures were measured against: {against!r}. "
        "A file, a digest or a document reference, in backticks, so a reader can go there."
    )


def test_the_scan_actually_reads_the_analysis_directory() -> None:
    """The half that keeps the three above from passing over an empty reading.

    All three are statements about every member of a set this file globs, and
    pytest reports zero parametrised cases as a pass. A moved directory, a
    renamed suffix or a sheet written as something other than markdown would
    leave the suite green over nothing at all.

    The block at the end is the instrument being shown to work rather than
    assumed to. A path under a real top level directory that is not in the tree
    has to come back from the scan as a path, so the existence check has
    something to fail on; a bare filename and a regulator's PDF have to come back
    as neither, so the scan is not passing by reporting everything; and the two
    codepoints refused have to be the two that were meant. A check that cannot be
    made to fail is not evidence.

    The three checks above were also shown to fail, on 2026-08-27, by breaking a
    real sheet: a line naming `docs/no-such-file.md` with an em-dash in it, and
    the "Measured on" label misspelled. Three of them went red and the document
    was put back.
    """
    assert len(ANALYSIS) >= 2, f"only found {[doc.name for doc in ANALYSIS]} under {ANALYSIS_DIR}"

    named = [
        path
        for document in ANALYSIS
        for path in _repository_paths(document.read_text(encoding="utf-8"))
    ]
    assert len(named) >= 10, f"the scan reads only {sorted(set(named))} across the sheets"
    assert "docs/decisions.md" in named, (
        "neither sheet points back at the decision log, which is the document that "
        "sends a reader here and the reason these sheets exist"
    )
    assert TOP_LEVEL >= {"docs", "tests", "ampeer_sim"}, (
        f"the top level of this repository reads as {sorted(TOP_LEVEL)}, so the rule "
        "that separates a repository path from a bare filename is not deciding anything"
    )
    assert "data" in IGNORED_ROOTS, (
        "data/ is no longer git-ignored, so the exemption above is either wrong or stale"
    )

    invented = "docs/no-such-analysis-sheet.md"
    assert _repository_paths(f"see `{invented}`") == [invented], (
        "a path under a real top level directory no longer reads as a path, so the "
        "existence check above is looking at nothing"
    )
    assert not (REPO_ROOT / invented).exists(), "the path chosen to prove the scan works exists"
    assert _repository_paths("`households.json` and `BR-2026-2242.pdf`") == [], (
        "a bare filename and an external source document now read as repository "
        "paths, which is the noise that makes a scan unreadable"
    )
    assert set(FORBIDDEN_DASHES) == {chr(0x2014), chr(0x2013)}, (
        "the two characters this suite refuses are no longer the em-dash and the en-dash"
    )


# --------------------------------------------------------------------------
# The one table in this directory that was copied out of a regulator's PDF
# --------------------------------------------------------------------------

TOU_SHEET = ANALYSIS_DIR / "2026-08-24-tou-tariff-2029.md"

#: Rows of the annex 5, seventh member table as the TOU sheet transcribes them:
#: a profile category, an offtake type, then five percentages. Anchored on the
#: leading pipe so the block tables in section 2, which have a different shape,
#: cannot match.
_SHARE_ROW = re.compile(
    r"^\|\s*(E\d[A-Z])\s*\|\s*([A-Z()a-z]+)\s*\|"
    r"\s*(\d+)%\s*\|\s*(\d+)%\s*\|\s*(\d+)%\s*\|\s*(\d+)%\s*\|\s*(\d+)%\s*\|\s*$",
    re.MULTILINE,
)

#: Rows the corrected annex 5, seventh member carries. Eleven, because five
#: profile categories are split by afnametype and E4A is not.
EXPECTED_SHARE_ROWS = 11


def test_the_offtake_share_table_still_sums_the_way_the_sheet_says_it_does() -> None:
    """Section 4 claims every row sums to exactly 100 percent. Check it.

    The sheet says so in words, and a claim in words about a table three lines
    above it is a claim nothing enforces. This table was retyped out of a PDF
    that the sheet itself warns misparses, and its own gap list carried a wrong
    statement about these same rows until 2026-09-02. A transposed digit here
    would be invisible: five plausible percentages that no longer describe the
    published distribution, in the one table this project would validate its
    synthetic profile against.

    This checks arithmetic and internal consistency, not the source. Whether the
    figures are the regulator's is what the reference numbers and the URLs in the
    header are for, and no test can do that.
    """
    text = TOU_SHEET.read_text(encoding="utf-8")
    rows = _SHARE_ROW.findall(text)
    assert len(rows) == EXPECTED_SHARE_ROWS, (
        f"{TOU_SHEET.name} has {len(rows)} offtake share rows and the corrected annex 5, "
        f"seventh member has {EXPECTED_SHARE_ROWS}; a row was lost, added or reshaped"
    )
    for category, kind, *shares in rows:
        total = sum(int(share) for share in shares)
        assert total == 100, (
            f"{category} {kind} sums to {total} percent in {TOU_SHEET.name}, and the "
            "sheet says every row sums to exactly 100"
        )
