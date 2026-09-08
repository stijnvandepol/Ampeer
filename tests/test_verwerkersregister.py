"""The article 30 register must describe the service that actually runs.

Same idea as tests/test_dpia.py, applied to a second document: a table this
project processes personal data through belongs in this register by name, a
retention window quoted here is a number the code actually enforces, and a
number that drifts from the code should turn this suite red rather than sit
unnoticed in prose.
"""

from __future__ import annotations

import ast
import re
from datetime import timedelta
from pathlib import Path

import pytest
from helpers.shell import shell_int
from test_dpia import _DUTCH_NUMERALS, ACCOUNT_MODELS, MODELS, SETTINGS, _int_constant

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "docs" / "verwerkersregister.md"
DPIA = REPO_ROOT / "docs" / "dpia.md"
BACKUP = REPO_ROOT / "scripts" / "backup_db.sh"
TEXT = REGISTER.read_text(encoding="utf-8")

#: The two whole-day figures this document quotes in words rather than digits:
#: the advice retention (AMPEER_ADVICE_TTL_DAYS) and the backup window
#: (KEEP_DAYS). Same idiom as test_dpia.py's own NUMBER_WORDS, kept separate
#: from it because this document does not carry every figure that one does.
NUMBER_WORDS = {90: "negentig dagen", 7: "zeven dagen"}

#: OneTimeToken.LIFETIMES maps a token kind to a timedelta; this maps every
#: timedelta the model declares today to the Dutch words the register uses for
#: it. Built from the two lifetimes that exist rather than guessed, so a third
#: lifetime, or an existing one changing to a value with no Dutch phrase here,
#: fails loudly instead of being silently skipped.
LIFETIME_WORDS = {
    timedelta(hours=1): "een uur",
    timedelta(days=7): "zeven dagen",
}

#: AuditEvent.record's callers write thirteen kinds today, which is past the
#: range _DUTCH_NUMERALS covers (it stops at "Tien", because every other user
#: of that table counts a short list of open questions or answered questions).
#: Extended here rather than copied: importing _DUTCH_NUMERALS and adding the
#: two words it does not yet need keeps this file from retyping "Een" through
#: "Tien" while still being able to name thirteen.
_AUDIT_KIND_WORDS: dict[int, str] = {**_DUTCH_NUMERALS, 11: "Elf", 12: "Twaalf", 13: "Dertien"}


def _model_class_names(source: Path) -> list[str]:
    """Every models.Model subclass declared in one file, by name.

    The same reading test_dpia.py's test_no_table_has_a_column_for_an_address
    already does over these two files, pulled out here so both suites read the
    same tree the same way rather than keeping two slightly different parsers.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {
            base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
            for base in node.bases
        }
        if "Model" in bases:
            names.append(node.name)
    return names


def test_the_register_names_every_table_the_service_has() -> None:
    """Red-proof: remove OutboundMail from the document by hand and rerun."""
    tables = _model_class_names(MODELS) + _model_class_names(ACCOUNT_MODELS)
    assert tables, "the AST reader found no models at all, so it read the wrong file"
    missing = [name for name in tables if name not in TEXT]
    assert not missing, f"the register never names {missing}"


def test_the_register_names_both_processors_and_no_third() -> None:
    """The allowlist test_boundaries.py enforces is the outer bound on what a
    document about processors may claim exists."""
    from test_boundaries import OUTBOUND_MODULES

    # The legal name and not only the trade name: a plain "Resend" in TEXT
    # would still be true of "Resend BV", which is not the entity the DPIA
    # names, so this pins the string precisely enough that a change to it is
    # what turns this test red.
    assert "Cloudflare Inc." in TEXT
    assert "Resend, Inc." in TEXT
    hosts = {host for allowed in OUTBOUND_MODULES.values() for host in allowed}
    # energiedatawijzer.nl is a deliberate exception: a by-hand ingest run,
    # never a processing of personal data, so it does not belong in a
    # register of processing activities and this test says so by name rather
    # than asserting every host in OUTBOUND_MODULES appears here.
    assert "energiedatawijzer.nl" not in TEXT
    assert hosts == {"re.jrc.ec.europa.eu", "energiedatawijzer.nl", "api.resend.com"}


def test_the_register_quotes_the_retention_the_service_applies() -> None:
    """AMPEER_ADVICE_TTL_DAYS, KEEP_DAYS, and every OneTimeToken lifetime.

    The first two are read the way tests/test_dpia.py reads them. The third is
    derived from OneTimeToken.LIFETIMES rather than written as a literal here,
    so a lifetime that changes, or a kind that gets one this test has no Dutch
    words for, turns this test red instead of leaving the register quoting a
    number the code no longer enforces.
    """
    from accounts.models import OneTimeToken

    days = _int_constant(SETTINGS, "AMPEER_ADVICE_TTL_DAYS")
    assert days in NUMBER_WORDS, (
        f"the retention is now {days} days and this test has no words for it"
    )
    assert NUMBER_WORDS[days] in TEXT, f"the register does not say {NUMBER_WORDS[days]}"

    kept = shell_int(BACKUP, "KEEP_DAYS")
    assert kept in NUMBER_WORDS, f"backups are kept {kept} days and this test has no words for it"
    assert NUMBER_WORDS[kept] in TEXT, f"the register does not say {NUMBER_WORDS[kept]}"

    for kind, lifetime in OneTimeToken.LIFETIMES.items():
        assert lifetime in LIFETIME_WORDS, (
            f"OneTimeToken.LIFETIMES[{kind!r}] is now {lifetime}, and this test has no "
            "Dutch words for it; extend the table above rather than dropping the check"
        )
        assert LIFETIME_WORDS[lifetime] in TEXT, (
            f"the register does not say {LIFETIME_WORDS[lifetime]!r} for the {kind} lifetime"
        )


def test_the_register_counts_the_audit_kinds() -> None:
    """The Dutch numeral before "soorten" is the count of AuditEvent's own kinds.

    Read the way tests/test_dpia.py reads AuditEvent's kinds elsewhere: every
    class-body assignment whose right hand side is an upper-case string
    constant is one kind. A kind added or removed changes the count and this
    test then asks the register for a word it may not yet have, rather than
    letting a stale numeral stand next to a log that grew or shrank.
    """
    tree = ast.parse(MODELS.read_text(encoding="utf-8"))
    audit = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "AuditEvent"
    )
    count = sum(
        1
        for statement in audit.body
        if isinstance(statement, ast.Assign)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
        and statement.value.value.isupper()
    )
    assert count in _AUDIT_KIND_WORDS, (
        f"AuditEvent now declares {count} kinds and this test only knows Dutch words "
        "up to thirteen; extend the table above rather than dropping the check"
    )
    # Whitespace-flattened, the way test_dpia.py reads its own counted phrases:
    # the register wraps "Dertien\nsoorten" across a Markdown line, and a plain
    # substring check would miss it despite the sentence being right.
    flattened = re.sub(r"\s+", " ", TEXT)
    assert f"{_AUDIT_KIND_WORDS[count]} soorten" in flattened, (
        f"AuditEvent declares {count} kinds and the register does not say "
        f"{_AUDIT_KIND_WORDS[count]!r} soorten"
    )


def test_the_register_carries_no_em_dashes() -> None:
    assert "—" not in TEXT


def test_every_section_is_numbered_consecutively() -> None:
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(len(numbers))), numbers


def test_the_register_names_the_controller_the_site_names() -> None:
    identity = (REPO_ROOT / "frontend" / "src" / "app" / "privacy" / "identity.ts").read_text(
        encoding="utf-8"
    )
    kvk = re.search(r'kvkNumber:\s*"(\d+)"', identity)
    assert kvk, "identity.ts no longer assigns kvkNumber as a plain string"
    assert kvk.group(1) in TEXT
    for field in ("contactEmail", "privacyEmail"):
        # identity.ts also declares IDENTITY_FIELD_HELP, an English help string
        # under the same two keys, earlier in the file; requiring an "@" in the
        # captured value is what keeps re.search's leftmost match from picking
        # up that prose instead of the real address in IDENTITY.
        match = re.search(rf'{field}:\s*"([^"]*@[^"]*)"', identity)
        assert match, f"identity.ts no longer assigns {field} as a plain email address"
        assert match.group(1) in TEXT


@pytest.mark.xfail(
    reason="docs/dpia.md still says the sentence this cycle removes in taak 9",
    strict=True,
)
def test_the_dpia_no_longer_says_there_is_no_register() -> None:
    dpia = DPIA.read_text(encoding="utf-8")
    assert "geen verwerkersregister" not in dpia
    assert "verwerkersregister.md" in dpia
