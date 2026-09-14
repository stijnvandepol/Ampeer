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
from helpers.shell import shell_int

REPO_ROOT = Path(__file__).resolve().parent.parent
DPIA = REPO_ROOT / "docs" / "dpia.md"
TEXT = DPIA.read_text(encoding="utf-8")

#: One path, unchanged. Two tests read MODELS.read_text directly for a property
#: of backend/advice/models.py specifically (the token length, and AuditEvent's
#: own kinds), and widening this to a list would break both with an
#: AttributeError that this task does not own the file to fix.
MODELS = REPO_ROOT / "backend" / "advice" / "models.py"

#: The second address to check, kept separate rather than folded into MODELS for
#: the reason above. _model_field_names is the only reader of both; every other
#: use of MODELS stays about backend/advice/models.py alone.
ACCOUNT_MODELS = REPO_ROOT / "backend" / "accounts" / "models.py"

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
    days = shell_int(BACKUP, "KEEP_DAYS")
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
    """Every model in backend/advice/models.py and backend/accounts/models.py,
    and the fields each declares.

    Read with ast rather than through Django, so this runs without a database
    and without a settings module, which is the same reason
    tests/test_infra.py reads the Dockerfile instead of a container. Both
    files are read and merged here, and this is the only function that reads
    ACCOUNT_MODELS: the app that actually holds the account's personal
    details would otherwise escape the address check entirely.
    """
    models: dict[str, list[str]] = {}
    for source in (MODELS, ACCOUNT_MODELS):
        tree = ast.parse(source.read_text(encoding="utf-8"))
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
    """Fifteen event types today, and the document explains every one of them.

    A ninth kind arriving means a handling arrived with it, which is precisely
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
    assert kinds == [
        "ADVICE_GENERATED",
        "ACCOUNT_CREATED",
        "LOGIN_SUCCEEDED",
        "LOGIN_FAILED",
        "LOGOUT",
        "CONSENT_GRANTED",
        "CONSENT_WITHDRAWN",
        "DATA_EXPORTED",
        "ACCOUNT_DELETED",
        "PASSWORD_RESET_REQUESTED",
        "PASSWORD_RESET_COMPLETED",
        "EMAIL_VERIFIED",
        "MAIL_SENT",
        "METER_LINKED",
        "METER_UNLINKED",
    ], (
        f"the audit log now records {kinds}; docs/dpia.md chapter 2 lists what it records "
        "and why the two that are still absent are absent. Both have to change together."
    )


SERVICE = REPO_ROOT / "backend" / "advice" / "service.py"

#: Every field the audit line carries, and the words the document uses for it.
#:
#: Prose and not key names, because a privacy document is read by people who do
#: not have the source open, and "engine_version" tells them nothing. The
#: pairing is asserted in both directions below, so a sixth field cannot be
#: added to the log without a sentence about it, and a sentence cannot survive
#: the field it describes being removed.
AUDIT_CONTEXT_PHRASES = {
    "token_sha256": "sha256 van het token",
    "postcode4": "viercijferige postcodegebied",
    "confidence": "betrouwbaarheidsniveau",
    "engine_version": "versienummers van de motor",
    "advice_version": "de regeltabel",
    "user_id": "`user_id`",
    "kind": "`kind`",
    "reused": "`reused`",
    "provider_id": "`provider_id`",
}

#: Every accounts/ source file, walked rather than named one by one: eleven
#: AuditEvent.record() call sites exist today across views.py and service.py,
#: and a twelfth arriving with a new keyword should fail this test rather than
#: silently ship a document that no longer says what the log carries.
ACCOUNTS = REPO_ROOT / "backend" / "accounts"


def _audit_context_keys() -> list[str]:
    """What the one AuditEvent.record call actually writes into the row.

    Read from service.py rather than by making a request, so this says what the
    code does rather than what one code path happened to produce.
    """
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "record"
    ]
    assert len(calls) == 1, (
        f"{len(calls)} calls to record() in service.py; this test assumes the audit "
        "line is written in exactly one place and has to be rewritten if it is not"
    )
    return [keyword.arg for keyword in calls[0].keywords if keyword.arg]


def _accounts_audit_context_keys() -> set[str]:
    """Every keyword an `AuditEvent.record(` call writes, anywhere under
    backend/accounts/.

    Matched on the callee's own name (`AuditEvent`) and not merely the method
    name `record`, so `Consent.record(user, kind, action)`, which shares the
    method name but takes no keywords, cannot be mistaken for the audit call
    it sits beside on the same lines.
    """
    keys: set[str] = set()
    for path in sorted(ACCOUNTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "record"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "AuditEvent"
            ):
                keys.update(keyword.arg for keyword in node.keywords if keyword.arg)
    return keys


def test_the_document_names_everything_the_audit_line_carries() -> None:
    """Chapter 2 listed two of the five fields, and got one of those wrong.

    It said the log records "het token en de viercijferige postcode". The code
    has written a sha256 since the log was built, and there is a test in
    tests/test_advice_api.py asserting the plaintext token appears nowhere in
    the row. So the document described a permanent, never expiring table full
    of working links to advice that the ninety day purge was supposed to remove.

    Wrong in the direction that matters. A privacy document that overstates
    what is kept is not a cautious error: it is the document a reader would
    hold the service to, and it was describing a worse service than the one
    that runs. The other three fields it did not mention at all.

    Both directions are asserted, over every AuditEvent.record() call this
    repository writes: the one in backend/advice/service.py and every one
    under backend/accounts/. A sixth field cannot join the audit line without
    a sentence about it, and a sentence cannot outlive the field.
    """
    keys = set(_audit_context_keys()) | _accounts_audit_context_keys()
    assert keys == set(AUDIT_CONTEXT_PHRASES), (
        f"the audit line carries {sorted(keys)} and this table describes "
        f"{sorted(AUDIT_CONTEXT_PHRASES)}. Chapter 2 has to say what is written down."
    )
    flattened = re.sub(r"\s+", " ", TEXT)
    unmentioned = {
        key: phrase for key, phrase in AUDIT_CONTEXT_PHRASES.items() if phrase not in flattened
    }
    assert not unmentioned, (
        "the audit line carries these and the document does not say so:\n  "
        + "\n  ".join(f"{key}: expected {phrase!r}" for key, phrase in unmentioned.items())
    )


def test_the_document_is_right_that_the_token_itself_is_not_written_down() -> None:
    """The claim and the code, held against each other.

    The document now says in bold that the token itself is not in the log. That
    is the sentence a reader would rely on, and it is worth exactly what
    enforces it. Here it is enforced from the source: the row carries a digest
    field and no plaintext one.

    What this does not check is that the digest is a digest. That is
    tests/test_advice_api.py, which hashes the token it was given and compares.
    """
    keys = _audit_context_keys()
    assert "token" not in keys, (
        "the audit line now carries the token itself, and chapter 2 of docs/dpia.md "
        "says in bold that it does not. One of the two is wrong and it is not the "
        "document that decides."
    )
    assert "token_sha256" in keys, (
        "the audit line no longer carries a token digest at all, so a reader who holds "
        "a link can no longer find their own line, which is what the document says the "
        "digest is for"
    )
    assert "**Niet het token zelf.**" in TEXT, (
        "chapter 2 no longer says the token itself is absent, which is the claim the "
        "check above exists to keep true"
    )


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


#: A list rather than one path, because the app that actually holds the personal
#: details would otherwise escape the verb check entirely. A guard that reads one
#: file while its commit claims a property of the package is the failure
#: advice/nl.py already carries a note about.
VIEWS = [
    REPO_ROOT / "backend" / "advice" / "views.py",
    REPO_ROOT / "backend" / "accounts" / "views.py",
]

#: The HTTP verbs a DRF APIView turns into a handler by defining a method with
#: that name. OPTIONS is answered by the framework and is not a handling of
#: anybody's data, so it is not in this set.
HTTP_HANDLERS = frozenset({"get", "post", "put", "patch", "delete", "head"})


def _handlers_per_view() -> dict[str, set[str]]:
    """Every view across the VIEWS list and the verbs it answers.

    Read with ast rather than through Django's URL resolver, so this runs
    without a settings module and without a database, for the reason the model
    walk above gives.
    """
    views: dict[str, set[str]] = {}
    for source in VIEWS:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            verbs = {
                statement.name
                for statement in node.body
                if isinstance(statement, ast.FunctionDef) and statement.name in HTTP_HANDLERS
            }
            if verbs:
                views[node.name] = verbs
    assert views, "no view handlers found; this test no longer reads what it thinks it does"
    return views


def test_the_api_answers_only_the_verbs_the_document_describes() -> None:
    """Chapter 7 says what a visitor can and cannot do, verb by verb.

    Two of those sentences are about something that does not exist: there is no
    way to delete an advice and no way to correct one in place. A handler
    arriving would make the chapter wrong in the direction that matters most,
    because it is the chapter somebody would read to find out whether a right
    can be exercised.

    Asserting the whole set rather than only the absence of delete, so a PUT or
    a PATCH cannot arrive unremarked either. Both would be a rectification, and
    the chapter says rectification adds a row instead of changing one.
    """
    verbs = {verb for handlers in _handlers_per_view().values() for verb in handlers}
    assert verbs == {"get", "post"}, (
        f"the API now answers {sorted(verbs)}. docs/dpia.md chapter 7 describes an API "
        "that reads and computes and does nothing else; it has to be reread before this "
        "test is updated, and chapter 10 lists the deletion question as unanswered."
    )


def test_the_document_says_which_data_an_access_request_does_not_reach() -> None:
    """The nuance that makes the access claim honest rather than flattering.

    The stored row holds the answers as well as the advice, and the read route
    returns `stored.advice` alone. Saying inzage works without saying that would
    overstate what a visitor sees about themselves.

    Read explicitly from backend/advice/views.py and not from VIEWS: this
    assertion is about the token route specifically, not about the account
    routes VIEWS now also carries, and account/views.py's export route
    deliberately does return the inputs, which is not the fact this test
    checks.
    """
    source = (REPO_ROOT / "backend" / "advice" / "views.py").read_text(encoding="utf-8")
    assert "stored.advice" in source, (
        "the read route no longer returns the advice alone; chapter 7 says it does"
    )
    assert "stored.inputs" not in source, (
        "the read route now returns the stored answers too, so chapter 7 understates "
        "what an access request reaches"
    )
    assert "ziet dus de uitkomst en niet de invoer" in TEXT


def test_the_document_carries_no_em_dashes() -> None:
    """The same rule the methodology is held to, for the same reason."""
    assert "—" not in TEXT


def test_every_section_is_numbered_consecutively() -> None:
    """A renumbering that skips or repeats is a merge accident, not a choice."""
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(len(numbers))), numbers


#: Dutch for the counts a list in this document can plausibly reach.
#:
#: The chapter writes its total in words rather than digits, which is right for
#: prose and is also why the drift below was invisible: a digit that disagreed
#: with a list would catch a reader's eye, and "Vier" above five numbered items
#: does not.
_DUTCH_NUMERALS = {
    1: "Een",
    2: "Twee",
    3: "Drie",
    4: "Vier",
    5: "Vijf",
    6: "Zes",
    7: "Zeven",
    8: "Acht",
    9: "Negen",
    10: "Tien",
}


def test_the_chapter_of_open_decisions_states_how_many_there_are() -> None:
    """Chapter 10 is the list of what the controller still has to decide.

    It opened by saying four things and then listed five. The fifth, access to
    the host and whether web2 becomes ephemeral, was added on 2026-08-21 and the
    count above it was not. Nothing noticed, because a document cannot fail a
    build and because the total is written in words.

    That matters more here than in most places. This chapter is the one a
    reader consults to find out what is still undecided, and a total that says
    four is an invitation to stop reading at the fourth. Deciding four of five
    open questions and believing the list is finished is the failure this
    guards, not the arithmetic.

    The count is derived from the list rather than repeated here, so the sixth
    item is covered by the same assertion without anybody remembering.
    """
    chapter = TEXT.split("## 10. Wat bij Stijn ligt", 1)[1]
    items = re.findall(r"^\d+\. \*\*", chapter, re.MULTILINE)
    assert items, (
        "chapter 10 has no numbered items, so this test is reading something other "
        "than the list of open decisions"
    )
    assert len(items) in _DUTCH_NUMERALS, (
        f"chapter 10 lists {len(items)} decisions and this test only knows the Dutch "
        "word for one through ten; extend the table above rather than dropping the check"
    )
    stated = _DUTCH_NUMERALS[len(items)]
    assert f"{stated} dingen kan dit document niet" in chapter, (
        f"chapter 10 lists {len(items)} decisions, so it has to open with "
        f"{stated!r}. A total that undercounts is how one of them gets left behind."
    )


def _serializer_fields(class_name: str) -> list[str]:
    """The fields a serializer declares itself, without its inherited ones.

    RefineInputSerializer extends the estimate, so its own body is exactly what
    round two adds, which is the number chapter 2 is making a claim about.
    """
    tree = ast.parse(SERIALIZERS.read_text(encoding="utf-8"))
    declared = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return [
        target.id
        for statement in declared.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
        and isinstance(statement.value, ast.Call)
        and "serializers." in ast.unparse(statement.value.func)
    ]


def _question_count(class_name: str) -> int:
    """The QUESTION_COUNT a serializer declares, read without importing Django."""
    tree = ast.parse(SERIALIZERS.read_text(encoding="utf-8"))
    declared = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    for statement in declared.body:
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "QUESTION_COUNT"
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, int)
        ):
            return statement.value.value
    raise AssertionError(f"{class_name} declares no QUESTION_COUNT")


def test_the_document_counts_the_answers_it_says_are_stored() -> None:
    """Chapter 2 said round two adds seven answers, then listed eight.

    The list was right and the total was not. It is the second miscount found
    in this document, after chapter 10 opening with "Vier dingen" above five,
    and both went unnoticed for the same reason: a total written in words does
    not catch the eye the way a digit disagreeing with a list would.

    Here it matters more than in chapter 10. This is the chapter that answers
    what the service stores about a person, so a count that is one short is a
    privacy document under-reporting its own processing. Nobody was misled,
    since the fields are listed beside it, but the number is the part a reader
    quotes.

    Derived from the serializers rather than repeated: RefineInputSerializer
    extends the estimate, so its own body is exactly what round two adds. Both
    the questions asked and the answers kept are paired, because they differ
    and the document now says why: roof direction and tilt are one question and
    two stored values.
    """
    # Lowercased on both sides: a total that opens a sentence is capitalised in
    # the document and that is not a difference worth failing on.
    flattened = re.sub(r"\s+", " ", TEXT).lower()
    for class_name, kind, count in (
        (
            "EstimateInputSerializer",
            "antwoorden",
            len(_serializer_fields("EstimateInputSerializer")),
        ),
        ("RefineInputSerializer", "antwoorden", len(_serializer_fields("RefineInputSerializer"))),
        ("EstimateInputSerializer", "vragen", _question_count("EstimateInputSerializer")),
        ("RefineInputSerializer", "vragen", _question_count("RefineInputSerializer")),
    ):
        assert count in _DUTCH_NUMERALS, f"{class_name} has {count} {kind}, past this table"
        phrase = f"{_DUTCH_NUMERALS[count].lower()} {kind}"
        assert phrase in flattened, (
            f"{class_name} has {count} {kind} and chapter 2 does not say {phrase!r}. "
            "A privacy document that undercounts what it keeps is describing a "
            "different service than the one that runs."
        )


def test_the_two_rounds_are_read_apart_rather_than_together() -> None:
    """The floor under the pairing above, and it guards a specific mistake.

    RefineInputSerializer inherits from EstimateInputSerializer, so a reading
    that walked the inherited fields as well would report thirteen for round
    two and pass against a document that said thirteen. The counts have to stay
    the ones the classes declare themselves.
    """
    first = _serializer_fields("EstimateInputSerializer")
    second = _serializer_fields("RefineInputSerializer")
    assert first and second, f"the scan found {first} and {second}"
    assert not set(first) & set(second), (
        f"round two is being read as including round one: {sorted(set(first) & set(second))}"
    )
    assert "postcode4" in first, "round one no longer asks for a postcode"
    assert _question_count("RefineInputSerializer") > _question_count("EstimateInputSerializer"), (
        "the second round does not ask more than the first, so one of the two counts is "
        "not being read from the class it belongs to"
    )


METHODOLOGY = REPO_ROOT / "docs" / "methodologie.md"


def test_the_document_states_the_backup_window_the_prune_actually_leaves() -> None:
    """KEEP_DAYS is not the number of days a dump survives, and it was quoted
    as though it were.

    The test above pairs KEEP_DAYS with the sentence that describes the rule,
    and that sentence is right: dumps older than seven days are removed at
    every run. Two summaries of it were not. The risk table said at most seven
    files, and chapter 4 said at most a week, and both are one short.

    Measured on 2026-08-22 by making files aged nought to nine days and running
    the prune over them: eight survive. `find -mtime +7` deletes only from
    eight whole days, so today's dump stands beside the ones from days one to
    seven. The script prunes after writing, deliberately, so the new dump is
    always among them.

    This is a sharper failure than a miscount. The guard was there, it was
    green, and it was comparing the number an operator types against a sentence
    about it, while the number the system produces is one higher. The docstring
    above it warns in so many words about a privacy assessment understating how
    long deleted data survives, which is exactly what happened, and not because
    anybody changed KEEP_DAYS.
    """
    days = shell_int(BACKUP, "KEEP_DAYS")
    script = BACKUP.read_text(encoding="utf-8")
    assert '-mtime "+${KEEP_DAYS}"' in script, (
        "the prune no longer uses find's +N form, and the arithmetic below is only "
        "true of that form: +N matches from N+1 whole days. Re-derive it before "
        "trusting the numbers in chapter 4."
    )
    standing = days + 1
    assert standing in _DUTCH_NUMERALS, f"{standing} dumps stand and this table has no word"
    flattened = re.sub(r"\s+", " ", TEXT).lower()
    for phrase in (
        f"{_DUTCH_NUMERALS[standing].lower()} bestanden",
        f"{_DUTCH_NUMERALS[standing].lower()} dagen",
    ):
        assert phrase in flattened, (
            f"the prune leaves {standing} dumps standing and the document does not say "
            f"{phrase!r}. Quoting KEEP_DAYS instead understates how long a purged "
            "advice survives in a copy."
        )


def test_every_chapter_this_document_points_at_exists() -> None:
    """A renumbering leaves a cross reference pointing at the wrong chapter.

    docs/methodologie.md has a test that its sections are numbered
    consecutively, which means inserting one renumbers those after it, which
    means every reference to a later chapter moves. Nothing checked that the
    references moved with them.

    What this does not catch is the error that prompted it. Chapter 0 said the
    controller's decisions are in chapter 9, and they are in chapter 10.
    Chapter 9 exists, so a resolvable-reference check passes. That one is
    caught by the pairing below, which asks what the chapter is about rather
    than whether it is there.
    """
    for name, document in (
        ("docs/dpia.md", TEXT),
        ("docs/methodologie.md", METHODOLOGY.read_text(encoding="utf-8")),
    ):
        chapters = {
            int(match.group(1)) for match in re.finditer(r"^## (\d+)\.", document, re.MULTILINE)
        }
        assert chapters, f"{name} has no numbered chapters, so this test read nothing"
        flattened = re.sub(r"\s+", " ", document)
        dangling = sorted(
            {
                int(match.group(1))
                for match in re.finditer(
                    r"hoofdstuk (\d+)(?! van de methodologie)", flattened, re.IGNORECASE
                )
            }
            - chapters
        )
        assert not dangling, (
            f"{name} points at chapters {dangling}, which it does not have. A reference "
            "to another document has to say so, the way 'hoofdstuk 17 van de "
            "methodologie' does."
        )


def test_the_opening_points_at_the_chapter_that_holds_the_open_decisions() -> None:
    """The forward reference in chapter 0, against the chapter it names.

    It said chapter 9 and meant chapter 10, and said four where there are five.
    Both were fixed in chapter 10 two commits earlier without the sentence that
    points at it being touched, which is the ordinary way a correction leaves a
    second copy behind.

    Asked of the heading rather than the number, so a chapter inserted above it
    moves the reference instead of breaking it.
    """
    heading = re.search(r"^## (\d+)\. Wat bij Stijn ligt", TEXT, re.MULTILINE)
    assert heading, "the chapter of open decisions is no longer called 'Wat bij Stijn ligt'"
    number = heading.group(1)
    chapter = TEXT.split(f"## {number}. Wat bij Stijn ligt", 1)[1]
    count = len(re.findall(r"^\d+\. \*\*", chapter, re.MULTILINE))
    assert count in _DUTCH_NUMERALS, f"chapter {number} lists {count} decisions"
    expected = f"{_DUTCH_NUMERALS[count]} dingen zijn"
    assert expected in TEXT, (
        f"chapter 0 does not open the count as {expected!r}, and chapter {number} lists "
        f"{count} decisions"
    )
    assert f"staan in hoofdstuk {number}" in re.sub(r"\s+", " ", TEXT), (
        f"chapter 0 does not point at hoofdstuk {number}, which is where the decisions are"
    )


#: nginx's own default, which `infra/nginx/` sets no `gzip_comp_level` to
#: override. The document quotes what a visitor's connection carries, so it has
#: to be measured at the level that connection actually uses. Level 9 is 1454
#: bytes smaller and would be a figure for a server this project does not run.
NGINX_GZIP_LEVEL = 1


#: How far the document's two byte counts may sit from a fresh measurement.
#:
#: Not a comfort tolerance, and the two halves have different reasons. The
#: uncompressed figure is almost entirely structural: 35040 bytes per series
#: become 46720 base64 characters whatever the household did, and only the
#: three ceilings vary, so it moves by a few bytes at most. The compressed one
#: is a property of the data, so every correction to the production model moves
#: it: measured twice on 2026-08-27, half an hour apart and across one such
#: correction, it read 45.242 and 45.333 bytes, which is 0,2 percent. Two
#: percent is ten times that and still an order of magnitude below the
#: difference the mistake this pins was made of, which was 12 percent.
MAX_QUOTED_SIZE_DRIFT = 0.02


def _quoted_bytes(pattern: str) -> int:
    """A byte count the document writes with a Dutch thousands separator."""
    match = re.search(pattern, TEXT)
    assert match, f"the document no longer quotes a byte count matching {pattern!r}"
    return int(match.group(1).replace(".", ""))


def test_the_document_quotes_what_a_year_costs_to_send() -> None:
    """The two byte counts in chapter 6, measured rather than remembered.

    They matter because they are the only figures in this document about what
    a visitor's connection carries, and because the pair that stood here before
    was mismatched: the uncompressed figure described the JSON and the
    compressed one described the packed bytes before base64 was applied, so the
    ratio between them was a saving nobody ever gets. Measured on 2026-08-27
    those are 93.608 and 40.693 bytes, so the document was quoting a 57 percent
    saving where the real one is 52, off a base that was not the artefact
    either. A document that quotes a measurement of a different thing is worse
    than one that quotes none.

    Measured on the household `docs/dpia.md` names, through the two functions
    that build the field on the way out, and gzipped at the level nginx uses.
    Read out of the document by pattern rather than searched for as a literal,
    so the failure can say what the figure has become instead of only that it
    is absent.
    """
    import gzip
    import json

    from test_advice_series import reference_household_flows

    from advice.assembly import build_year
    from advice.serializers import year_field

    body = json.dumps(year_field(build_year(reference_household_flows()))).encode("utf-8")
    packed = gzip.compress(body, NGINX_GZIP_LEVEL, mtime=0)

    for label, measured, pattern in (
        ("as JSON", len(body), r"het veld is ([\d.]+)\s*\n?bytes aan JSON"),
        ("gzipped", len(packed), r"en ([\d.]+) bytes zodra nginx"),
    ):
        quoted = _quoted_bytes(pattern)
        drift = abs(quoted - measured) / measured
        assert drift <= MAX_QUOTED_SIZE_DRIFT, (
            f"the document says the year is {quoted} bytes {label} and it measures "
            f"{measured}, which is {drift:.1%} away. Re-measure and rewrite the sentence"
        )


def test_the_document_is_right_that_the_answer_now_carries_the_year() -> None:
    """Chapter 6 stopped describing a field nobody sends, so this holds it to that.

    The chapter used to say the answer *can* carry a year, which was true in
    the way a shape in a serializer is true: nothing handed it one. It now says
    the answer carries one, and the sentence is only worth writing if something
    fails when it stops being true. `advice.service` is the single composition
    root, so a `render` call there without a year is a response without one.
    """
    calls = [
        node
        for node in ast.walk(ast.parse(SERVICE.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render"
    ]
    assert len(calls) == 1, f"advice/service.py calls render {len(calls)} times"
    assert any(keyword.arg == "year" for keyword in calls[0].keywords), (
        "advice/service.py renders without a year, so no answer carries one and "
        "chapter 6 describes a field that is not sent"
    )


NGINX = REPO_ROOT / "infra" / "nginx" / "nginx.conf"

#: The sentence in `infra/nginx/nginx.conf` that turns the tunnel from a wire
#: into a processor. It is a comment rather than a directive, so the directive
#: it explains is asserted beside it: a comment can be deleted without changing
#: what the server does, and the constant it justifies cannot.
TLS_TERMINATION = "Cloudflare terminates TLS at the edge"


def _nginx() -> tuple[str, str]:
    """infra/nginx/nginx.conf as flattened prose, and as directives alone.

    Split apart for the reason tests/test_nginx_config.py gives at length: the
    comments in that file quote the directives they explain, so a grep over the
    whole text matches the sentence about a directive as readily as the
    directive. Here both halves are wanted, and each has to be asked the right
    question.
    """
    conf = NGINX.read_text(encoding="utf-8")
    prose = re.sub(r"\s+", " ", re.sub(r"^\s*#\s?", "", conf, flags=re.MULTILINE))
    directives = "\n".join(line for line in conf.splitlines() if not line.lstrip().startswith("#"))
    return prose, directives


def test_the_document_names_the_party_that_reads_the_token_in_the_clear() -> None:
    """Chapter 5 named the tunnel and then denied what naming it implies.

    It said "Er is geen verwerker" and, in the same sentence, that a third
    party service passes the traffic through. Passing through is not what
    happens. Cloudflare terminates TLS at the edge, which `infra/nginx/nginx.conf`
    states as the reason `X-Forwarded-Proto` may be a constant there, so
    Cloudflare reads in cleartext the path of every request. That path is
    `/advies/<token>/`, and the token in it is the only credential that opens a
    household's advice: the same string four separate mechanisms in this
    repository exist to keep out of logs. The visitor's address is in the clear
    beside it, the address chapter 2 says is hashed before it is counted.

    That makes Cloudflare a processor under article 4(8) and article 28 asks for
    a written agreement. A privacy assessment that says there is no processor is
    not merely incomplete; it is the one sentence a reader would rely on to
    conclude no such agreement is owed.

    The premise is asserted rather than assumed. A test that only looked for the
    word "Cloudflare" in the document would pass against a sentence claiming the
    opposite, and would keep passing after the day TLS reaches this container
    and the chapter becomes an overstatement instead of a correction.
    """
    prose, directives = _nginx()
    assert TLS_TERMINATION in prose, (
        f"infra/nginx/nginx.conf no longer says {TLS_TERMINATION!r}, and that sentence "
        "is the entire premise of chapter 5 of docs/dpia.md. Re-read nginx.conf before "
        "touching this test. If the phrase only moved or was reworded, move this "
        "constant with it; if TLS now reaches this container, then Cloudflare no longer "
        "reads the token and chapter 5 overstates the exposure and has to be rewritten."
    )
    assert "proxy_set_header X-Forwarded-Proto https;" in directives, (
        "nginx no longer sets X-Forwarded-Proto to a constant. That constant is only "
        "correct because TLS is terminated upstream, so its absence means the comment "
        "above is describing a deployment that no longer exists. Chapter 5 rests on it."
    )

    assert "Er is geen verwerker" not in TEXT, (
        "chapter 5 says there is no processor while the tunnel that carries every "
        "request reads the token and the address in the clear"
    )
    assert "**Cloudflare Inc. is een verwerker.**" in TEXT, (
        "chapter 5 no longer names Cloudflare as a processor, which is what the "
        "premise above makes it"
    )
    flattened = re.sub(r"\s+", " ", TEXT)
    for phrase in (
        "`GET /advies/<token>/`",
        "artikel 4 lid 8",
        "artikel 28",
        "verwerkersovereenkomst",
    ):
        assert phrase in flattened, (
            f"chapter 5 does not say {phrase!r}. Naming the processor without saying "
            "what it sees, or without the agreement article 28 asks for, leaves the "
            "reader with the half of the correction that costs nothing."
        )


def test_the_document_points_at_the_register_and_the_statement() -> None:
    """Chapter 10's closing paragraph and chapter 5's Resend paragraph both
    point at the register this cycle added; red-proof: remove either sentence
    by hand and rerun."""
    assert "verwerkersregister.md" in TEXT
    chapter_10 = TEXT.split("## 10. Wat bij Stijn ligt", 1)[1]
    assert "verwerkersregister.md" in chapter_10
    chapter_5 = TEXT.split("## 5. Wie erbij kan", 1)[1].split("## 6.", 1)[0]
    assert "verwerkersregister.md" in chapter_5


def test_the_risk_table_carries_the_token_in_the_url_and_the_fix_not_taken() -> None:
    """The row, and the paragraph that keeps "nothing yet" from reading as "nothing to do".

    Every other row in chapter 8 names something that stands against the risk.
    This one cannot, and writing it down anyway is the point: the token is in
    the path by design, so what mitigates it today is a ninety day expiry and
    nothing structural.

    The structural fix exists and is not built. A URL fragment is never sent to
    any server, so `/advies/#<token>` with an `Authorization` header would put
    the token out of Cloudflare's reach, and it is what OWASP ASVS v5.0.0
    requires in 14.2.1 at L1, which the current design fails. Recording it
    beside the row is what tells the next reader it was costed rather than
    missed, and asserting it here is what keeps the row from being quietly
    softened into a mitigation that does not exist.
    """
    chapter = TEXT.split("## 8. Risico's, en wat ertegen staat", 1)[1].split("\n## 9.", 1)[0]
    rows = [line for line in chapter.splitlines() if line.startswith("|") and "Cloudflare" in line]
    assert len(rows) == 1, (
        f"chapter 8 has {len(rows)} rows naming Cloudflare and there should be exactly "
        "one: the token is readable to it in the URL of every request"
    )
    assert "Niets structureels" in rows[0], (
        f"the row now claims something stands against the risk: {rows[0]!r}. The token "
        "is in the path by design, so the honest second column says so. Anything else "
        "has to be a change to the code, not to this table."
    )
    for phrase in ("14.2.1", "/advies/#<token>", "Authorization", "frontend/src/lib/api.ts"):
        assert phrase in chapter, (
            f"chapter 8 does not say {phrase!r}, so the fix that was considered and not "
            "taken is not written down, and the row above reads as an oversight"
        )


def _flat(chapter: str) -> str:
    """One chapter as a single line.

    docs/dpia.md is hard wrapped, so a sentence a reader reads as one sentence
    is several lines in the file and a substring search for it finds nothing.
    Not hypothetical: the first run of the two tests below failed on "niet
    langer waarschijnlijk verplicht maar verplicht" purely because the wrap
    fell between the third and fourth word.
    """
    return " ".join(chapter.split())


def test_the_assessment_does_not_still_say_the_risky_data_is_absent() -> None:
    """Chapter 1 rests the whole article 35 weighing on one sentence.

    "Die data is er niet", about quarter-hour readings from the meter. It was
    true of phase 0.5 and it is the reason the chapter reaches "waarschijnlijk
    niet verplicht". `QuarterReading` has existed in backend/accounts/models.py
    since the meter link, so the sentence stopped being true and the conclusion
    above it kept standing on it. Found on 2026-09-13, three phases later.

    Paired against the model rather than asserted as a phrase, because the
    thing that makes the sentence false is the table existing. A future phase
    that removed the table would make the original weighing correct again, and
    this test would then stop demanding the correction rather than demanding it
    forever on the strength of one day's reading.
    """
    if "class QuarterReading" not in ACCOUNT_MODELS.read_text(encoding="utf-8"):
        pytest.skip("no quarter-hour table; chapter 1's original weighing stands")
    chapter = _flat(TEXT.split("## 1. Is een DPIA hier verplicht", 1)[1].split("\n## 2.", 1)[0])
    assert "Die data is er niet" in chapter, (
        "chapter 1 no longer carries the sentence this test is about; if it was "
        "rewritten rather than corrected, delete this test in the same commit"
    )
    assert 'de zin "die data is er niet" onwaar' in chapter, (
        "QuarterReading exists and chapter 1 still says the quarter-hour data "
        "does not, which is the sentence its article 35 weighing rests on"
    )


def test_the_assessment_does_not_put_its_own_obligation_in_the_future() -> None:
    """Chapter 9 set a condition and the condition is met.

    It said a review becomes certainly required "zodra die laatste verwerking
    bestaat". That processing exists. A document that states its own obligation
    as a future event reads as a plan when it is a debt, and the difference
    matters to the only person who can discharge it.
    """
    chapter = _flat(TEXT.split("\n## 9.", 1)[1].split("\n## 10.", 1)[0])
    assert "Zodra die laatste verwerking bestaat" not in chapter, (
        "chapter 9 still states the obligation as a condition on a future phase"
    )
    assert "niet langer waarschijnlijk verplicht maar verplicht" in chapter, (
        "chapter 9 no longer says plainly that the review is required now"
    )
