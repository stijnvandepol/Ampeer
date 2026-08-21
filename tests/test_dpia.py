"""The data protection assessment must describe the service that actually runs.

`docs/dpia.md` states what the service holds, for how long, where the copies
are and what leaves the machine. Every one of those is a number or a shape
somewhere in the code, and a document that carries them in prose goes stale the
same way `docs/methodologie.md` did within a day of being written: silently,
because a document cannot fail a build.

The pairing here is deliberately about the figures a reader would check. A
retention window quoted in a privacy document is not decoration; it is the
sentence somebody would hold the service to.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DPIA = REPO_ROOT / "docs" / "dpia.md"
TEXT = DPIA.read_text(encoding="utf-8")

MODELS = REPO_ROOT / "backend" / "advice" / "models.py"
SETTINGS = REPO_ROOT / "backend" / "ampeer" / "settings" / "base.py"
SERIALIZERS = REPO_ROOT / "backend" / "advice" / "serializers.py"
BACKUP = REPO_ROOT / "scripts" / "backup_db.sh"
PRIVACY_SPEC = REPO_ROOT / "frontend" / "e2e" / "privacy.spec.ts"

#: The figures the document spells out in Dutch words rather than digits, and
#: the module constant each one is. Written as words on purpose: this is a
#: document a household reads, and "negentig dagen" belongs in it rather than
#: "90". The consequence is that a search for the digits finds nothing, which
#: is exactly how the ageing correction in docs/methodologie.md stayed wrong
#: for as long as it did.
NUMBER_WORDS = {
    90: "negentig dagen",
    7: "zeven dagen",
    22: "22 tekens",
    4: "vier cijfers",
    120: "120 leesverzoeken per uur",
}


def _assign(source: Path, name: str) -> ast.expr:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
    raise AssertionError(f"{source.name} no longer assigns {name}")


def _int_constant(source: Path, name: str) -> int:
    value = _assign(source, name)
    assert isinstance(value, ast.Constant) and isinstance(value.value, int), (
        f"{name} in {source.name} is no longer a plain integer"
    )
    return value.value


def _shell_int(source: Path, name: str) -> int:
    """A bare `NAME=value` assignment in a shell script.

    Read rather than sourced, for the reason scripts/preflight_env.sh gives
    about the env file it parses: running a file to find out what is in it is a
    different act from reading it.
    """
    pattern = re.compile("^" + name + "=([0-9]+)$", re.MULTILINE)
    match = pattern.search(source.read_text(encoding="utf-8"))
    assert match, f"{source.name} no longer assigns {name}"
    return int(match.group(1))


def test_the_document_quotes_the_retention_the_service_applies() -> None:
    """Ninety days is the promise the whole document rests on."""
    days = _int_constant(SETTINGS, "AMPEER_ADVICE_TTL_DAYS")
    assert days in NUMBER_WORDS, (
        f"the retention is now {days} days and this test has no words for it"
    )
    assert NUMBER_WORDS[days] in TEXT, f"the document does not say {NUMBER_WORDS[days]}"


def test_the_document_quotes_how_long_a_backup_outlives_a_deletion() -> None:
    """The one figure in this document that describes a trade rather than a rule.

    A dump keeps a purged advice readable for as long as the dump is kept, so
    this number and the sentence about it are the same statement. Changing
    KEEP_DAYS without changing the document would leave a privacy assessment
    understating how long deleted data survives.
    """
    days = _shell_int(BACKUP, "KEEP_DAYS")
    assert days in NUMBER_WORDS, f"backups are kept {days} days and this test has no words for it"
    assert NUMBER_WORDS[days] in TEXT, f"the document does not say {NUMBER_WORDS[days]}"


def test_the_document_quotes_the_length_of_a_token() -> None:
    """The document calls a token unguessable and then says how long it is.

    token_urlsafe takes a byte count and returns base64url without padding, so
    the character count is not the number in the source. It is computed here
    rather than written down twice.
    """
    import secrets

    characters = len(secrets.token_urlsafe(_int_constant(MODELS, "TOKEN_BYTES")))
    assert characters in NUMBER_WORDS, f"a token is now {characters} characters"
    assert NUMBER_WORDS[characters] in TEXT, f"the document does not say {characters} tekens"


def test_the_document_quotes_the_read_limit_the_api_enforces() -> None:
    """It appears in the risk table as what makes walking tokens impractical."""
    text = SETTINGS.read_text(encoding="utf-8")
    match = re.search(r'"advice-read":\s*"(\d+)/hour"', text)
    assert match, "settings no longer set a read throttle"
    per_hour = int(match.group(1))
    assert per_hour in NUMBER_WORDS, f"the read limit is now {per_hour}/hour"
    assert NUMBER_WORDS[per_hour] in TEXT, f"the document does not quote {per_hour} an hour"


def test_the_postcode_is_refused_rather_than_shortened() -> None:
    """The difference the document rests a claim on.

    A serializer that truncated six characters to four would mean the full
    postcode reached the application before anything shortened it. The claim in
    the document is that it never arrives, and that is only true while the
    pattern anchors both ends.
    """
    pattern = _assign(SERIALIZERS, "POSTCODE4_PATTERN")
    assert isinstance(pattern, ast.Constant) and isinstance(pattern.value, str)
    compiled = re.compile(pattern.value)
    assert compiled.match("1234"), pattern.value
    assert not compiled.match("123456"), (
        f"{pattern.value} accepts a six digit postcode, so the document is wrong "
        "to say four digits is all that can arrive"
    )
    assert NUMBER_WORDS[4] in TEXT


def _model_field_names() -> dict[str, list[str]]:
    """Every model in backend/advice/models.py and the fields it declares.

    Read with ast rather than through Django, so this runs without a database
    and without a settings module, which is the same reason
    tests/test_infra.py reads the Dockerfile instead of a container.
    """
    tree = ast.parse(MODELS.read_text(encoding="utf-8"))
    models: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields = [
            target.id
            for statement in node.body
            if isinstance(statement, ast.Assign)
            for target in statement.targets
            if isinstance(target, ast.Name)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and isinstance(statement.value.func.value, ast.Name)
            and statement.value.func.value.id == "models"
        ]
        if fields:
            models[node.name] = fields
    assert models, "no models found; this test no longer reads what it thinks it does"
    return models


def test_no_table_has_a_column_for_an_address() -> None:
    """The claim that the IP address is used and not kept.

    It is hashed before it becomes a throttle counter, and the document says so.
    A field added later would make that sentence false while every other test
    stayed green, because nothing else in this repository asks what the columns
    are for.
    """
    suspicious = re.compile(r"(^|_)(ip|address|remote_addr|client)($|_)")
    found = {
        f"{model}.{field}"
        for model, fields in _model_field_names().items()
        for field in fields
        if suspicious.search(field)
    }
    assert not found, f"a model now stores something that looks like an address: {sorted(found)}"


def test_the_audit_log_records_exactly_what_the_document_says_it_does() -> None:
    """One event type today, and the document explains why the others are absent.

    A second one arriving means a handling arrived with it, which is precisely
    when a privacy document has to be reread rather than assumed.
    """
    tree = ast.parse(MODELS.read_text(encoding="utf-8"))
    audit = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AuditEvent"
    )
    kinds = [
        target.id
        for statement in audit.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value == target.id
    ]
    assert kinds == ["ADVICE_GENERATED"], (
        f"the audit log now records {kinds}; docs/dpia.md chapter 2 says it records one "
        "kind of event and explains why the others are absent. Both have to change together."
    )
    assert "precies een soort gebeurtenis" in TEXT


def test_the_document_names_the_test_that_keeps_the_browser_honest() -> None:
    """A claim about outbound requests is worth what enforces it.

    The document says loading a page reaches nothing outside this machine. That
    was measured once and is now a test; naming it is what lets a reader check
    the claim instead of trusting it.
    """
    assert PRIVACY_SPEC.exists(), "the test the document points at does not exist"
    assert "privacy.spec.ts" in TEXT, "the document no longer names what enforces its claim"


@pytest.mark.parametrize("mode", ["0600", "0700"])
def test_the_document_quotes_the_permissions_the_backup_check_enforces(mode: str) -> None:
    """Who can read a backup is the question chapter 4 says the backup raises."""
    assert mode.lstrip("0") in BACKUP.read_text(encoding="utf-8"), (
        f"scripts/backup_db.sh no longer mentions {mode}"
    )
    assert f"`{mode}`" in TEXT, f"the document does not quote {mode}"


def test_the_document_carries_no_em_dashes() -> None:
    """The same rule the methodology is held to, for the same reason."""
    assert "—" not in TEXT


def test_every_section_is_numbered_consecutively() -> None:
    """A renumbering that skips or repeats is a merge accident, not a choice."""
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(len(numbers))), numbers
