"""The integration gate's own file: the local override, and the fixtures it needs.

Nothing here starts a container. The seven checks in section 12 of the design
are run by hand against a running stack and their output is recorded in the
commit that brings this file in; what is left over afterwards is the part that
can go stale silently, and that part is asserted here so it fails in CI, where
there is no Docker at all.

Three of the four things checked below came out of the barrier's own reading
rather than out of a lane, because each one sits between two lanes and neither
could have owned it:

* the log driver's retention, which is nginx's promise and compose's setting
* .dockerignore, which is what every Dockerfile in the tree depends on and no
  Dockerfile can state
* the checksum that ties the deploy job to the copy of preflight_env.sh that
  lives on the host, which is the workflow's line and the script's content

Running this file rather than importing it writes the two git-ignored fixtures
the override needs:

    uv run python tests/test_stack_smoke.py

THE LIVE CHECKS RUN OUT OF REGISTRATIONS, and the first time that happens it
looks like a broken stack. `auth-register` is five an hour per address and the
checks below use several between them, so a second full run inside the hour
answers 429 on registration and fails four of them at once. That is the rate
limit working, and reading the body says so in Dutch. To start again rather
than wait:

    docker compose -f infra/docker-compose.yml -f infra/compose.test.yml       --env-file infra/fixtures/env.smoke exec -T api       python backend/manage.py shell -c "from django.core.cache import cache; cache.clear()"

The counters live in the database cache table, so that clears them and nothing
else a local stack cares about. Never on a host: the same table holds every
throttle bucket the site is using at that moment.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from helpers.accounts import OTHER_PASSWORD, TEST_PASSWORD

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "infra"
COMPOSE = INFRA / "docker-compose.yml"
OVERRIDE = INFRA / "compose.test.yml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
README = REPO_ROOT / "infra" / "README.md"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
PREFLIGHT = REPO_ROOT / "scripts" / "preflight_env.sh"

#: Where the generated fixtures land. Git-ignored: one of them is a megabyte of
#: synthetic numbers and the other is shaped exactly like the env file that
#: holds a signing key on the host, and neither belongs in a repository.
FIXTURES = INFRA / "fixtures"
PROFILE_FIXTURE = FIXTURES / "nedu-flat-2025.csv"
ENV_FIXTURE = FIXTURES / "env.smoke"
MAIL_FIXTURE_DIR = FIXTURES / "mail"

#: The year the profile fixture carries, which is settings.AMPEER_PROFILE_YEAR.
#: 2025 is not a leap year, so a full series is 365 * 96 quarters.
FIXTURE_YEAR = 2025
FIXTURE_QUARTERS = 365 * 96

#: The series name the fixture publishes. advice.assembly never sets a profile
#: category, so every household reaching the engine is the E1A default, and
#: ampeer_sim.profiles.nedu asks for `<name>E1A_AZI_A` in the year row.
FIXTURE_SERIES = "SMOKE_E1A_AZI_A"

#: The address of a running stack, or nothing. Opt in, because there is no
#: Docker in CI and a check that cannot run must not read as one that passed.
SMOKE_BASE_URL_ENV = "AMPEER_SMOKE_BASE_URL"

STACK = os.environ.get(SMOKE_BASE_URL_ENV)

#: Every live check carries this, and the test below is what keeps that true.
needs_stack = pytest.mark.skipif(
    STACK is None,
    reason=(
        f"{SMOKE_BASE_URL_ENV} is not set. Start the stack per infra/README.md "
        "section 7 and set it to, for example, http://127.0.0.1:8080"
    ),
)


def test_every_live_check_is_gated_on_the_same_variable() -> None:
    """A skipped check is not proof, and an ungated one is worse.

    Every function whose name begins with `test_live_` talks to a machine that
    is not there in CI. One that lost its marker would not skip, it would fail
    on a refused connection, and the honest reading of that failure is
    "somebody forgot a decorator" rather than "the stack is broken". Read off
    this module rather than listed, so a live check added later is covered
    without anybody remembering this test exists.
    """
    live = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_live_") and callable(value)
    ]
    assert live, "no live checks found at all; this test is reading nothing"
    for name, function in live:
        marks = getattr(function, "pytestmark", [])
        reasons = [
            str(mark.kwargs.get("reason", ""))
            for mark in marks
            if getattr(mark, "name", "") == "skipif"
        ]
        assert any(SMOKE_BASE_URL_ENV in reason for reason in reasons), (
            f"{name} is not gated on {SMOKE_BASE_URL_ENV}, so it fails on a refused "
            "connection in CI instead of saying it did not run"
        )


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands compose's own merge tags.

    `!override` and `!reset` tell compose to replace a value from an earlier
    file rather than merge into it. They are compose's, not YAML's, so
    `safe_load` refuses the document outright. Reading them as their plain
    value is right for every test here: what a test asks is what the value is,
    and `test_the_override_replaces_the_published_port_rather_than_adding_to_it`
    asserts the tag's presence separately, on the raw text, because that is the
    part a parsed document cannot show.
    """


def _construct_tagged(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    """The tagged value, with the tag dropped."""
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    raise TypeError(f"compose tag on an unexpected node: {node!r}")


for _tag in ("!override", "!reset"):
    _ComposeLoader.add_constructor(_tag, _construct_tagged)


def _compose_document(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader)
    return document


class _Session:
    """One caller against the running stack, with the raw Set-Cookie kept.

    urllib rather than a new dependency, and deliberately not a client that
    manages cookies for you: the attributes on those headers are half of what
    this file is here to read, and a jar that parsed them away would leave the
    test asserting that a 200 came back.
    """

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.cookies: dict[str, str] = {}
        self.set_cookie: list[str] = []
        # infra/nginx/nginx.conf:302 sets `proxy_set_header Host $host;`, and
        # $host is the Host header with any port stripped (unlike $http_host,
        # which would keep it). So Django never sees the :8080 this session
        # connects to, and the Origin a real browser would send here carries
        # the same bare host.
        from urllib.parse import urlsplit

        self._origin_host = urlsplit(self.base).hostname

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        import json as jsonlib
        import urllib.error
        import urllib.request

        data = None if body is None else jsonlib.dumps(body).encode("utf-8")
        sending = dict(headers or {})
        if data is not None:
            sending["Content-Type"] = "application/json"
        if self.cookies:
            sending["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if method != "GET":
            # infra/nginx/nginx.conf:316 SETS X-Forwarded-Proto to "https" on
            # every proxied request (not $scheme, which is http on this plain
            # socket), and backend/ampeer/settings/prod.py:132 trusts that
            # header via SECURE_PROXY_SSL_HEADER. So Django treats this
            # http:// connection as secure, and its CSRF middleware then
            # demands an Origin (or Referer) header on every unsafe request
            # before it looks at the token at all. A browser on
            # https://ampeer.nl/account/ would send exactly this Origin:
            # https, because that is genuinely the scheme it used.
            sending["Origin"] = f"https://{self._origin_host}"
        request = urllib.request.Request(
            f"{self.base}{path}", data=data, headers=sending, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, payload, raw = response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            status, payload, raw = error.code, error.read(), error.headers
        self.set_cookie = list(raw.get_all("Set-Cookie") or [])
        for header in self.set_cookie:
            name, _, rest = header.partition("=")
            self.cookies[name.strip()] = rest.split(";", 1)[0]
        return status, payload

    def json(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        import json as jsonlib

        headers = {}
        token = self.cookies.get("csrftoken")
        if method != "GET" and token is not None:
            headers["X-CSRFToken"] = token
        status, payload = self.request(method, path, body, headers)
        assert 200 <= status < 300, f"{method} {path} answered {status}: {payload!r}"
        return jsonlib.loads(payload) if payload else None

    def attributes(self, cookie: str) -> dict[str, str]:
        """The attributes on one Set-Cookie header, lowercased by name."""
        for header in self.set_cookie:
            if not header.startswith(f"{cookie}="):
                continue
            found: dict[str, str] = {}
            for part in header.split(";")[1:]:
                key, _, value = part.strip().partition("=")
                found[key.lower()] = value
            return found
        raise AssertionError(f"{cookie} was not set at all; headers were {self.set_cookie}")


def _fresh_email() -> str:
    """A new address per run, so a stack that is reused does not collide."""
    import secrets

    return f"smoke-{secrets.token_hex(6)}@voorbeeld.invalid"


def _assert_session_cookie_attributes(session: _Session, issued_by: str) -> None:
    """The four attributes a browser enforces, off one pair of Set-Cookie lines."""
    access = session.attributes("ampeer_access")
    refresh = session.attributes("ampeer_refresh")
    assert "httponly" in access, (
        f"the access cookie {issued_by} set is readable from JavaScript: {access}"
    )
    assert "httponly" in refresh, (
        f"the refresh cookie {issued_by} set is readable from JavaScript: {refresh}"
    )
    assert access.get("samesite") == "Strict", (issued_by, access)
    assert refresh.get("samesite") == "Strict", (issued_by, refresh)
    # Two different paths on purpose: the access token reaches every API route
    # and the refresh token only the two that need it, so it does not travel
    # on every request the access token makes.
    assert access.get("path") == "/api/", (issued_by, access)
    assert refresh.get("path") == "/api/auth/", (issued_by, refresh)


@needs_stack
def test_live_the_session_cookies_carry_the_attributes_a_browser_enforces() -> None:
    """The header on the wire, and not the morsel Django built.

    tests/test_accounts_api.py already reads httponly, SameSite and the two
    paths off `response.cookies`, which is Django's own object in Django's own
    process. This reads the text that travelled through nginx under
    ampeer.settings.prod, which is what a browser actually interprets, and it
    is the only place the deployed settings are the ones being described.

    Both routes that hand out a session are read, and that is the second thing
    this proves. Every other live check here signs in by registering, so until
    now nothing in this file had ever completed a `login/` at all: the one
    route a returning visitor uses was covered only by the Django test client,
    which never sees these headers. And the cookies are set from two call
    sites, so "register/ gets them right" is not a statement about login/.

    Registering once and reusing that account is deliberate: `auth-register`
    is five an hour and this file is meant to be runnable more than once in a
    sitting.
    """
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    status, _ = session.request("GET", "/api/auth/me/")
    assert status == 401, "a stranger is signed in, which is a different problem"
    assert "csrftoken" in session.cookies, (
        "the 401 did not hand out a CSRF token, so nobody can ever sign in"
    )

    email = _fresh_email()
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    _assert_session_cookie_attributes(session, "register/")

    # Out and back in on the same account. `logout/` revokes the refresh token
    # and clears both cookies, so what login/ answers with is a new pair and
    # not the old one echoed back.
    session.json("POST", "/api/auth/logout/")
    session.json("POST", "/api/auth/login/", {"email": email, "password": TEST_PASSWORD})
    _assert_session_cookie_attributes(session, "login/")

    session.json("POST", "/api/auth/delete/", {"password": TEST_PASSWORD})


@needs_stack
def test_live_a_post_without_the_csrf_header_is_refused() -> None:
    """The half no mock can reach.

    Django's test client sets `_dont_enforce_csrf_checks`, so the check does
    not run there at all unless a test asks for a strict client; page.route in
    Playwright answers whatever it is asked and never checks a header. Over the
    real stack there is nothing to switch on, and this is the request an
    attacker's page would make.

    The request below carries the same production-shaped Origin header every
    other write in this file sends (see _Session.request), so the 403 it
    provokes is about the missing X-CSRFToken and not about Origin or Referer
    checking failing first. The second request is the positive control that
    proves that: same session, same body, only the header restored, and
    Django moves past the CSRF check to answer something that is not 403 (a
    plain 400 for the bogus credentials below is expected, not a login).
    """
    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    assert "csrftoken" in session.cookies, "no token to leave out"
    body = {"email": "iemand@voorbeeld.invalid", "password": "maakt-niet-uit"}
    status, payload = session.request("POST", "/api/auth/login/", body)
    assert status == 403, (
        f"a state changing request went through without X-CSRFToken and answered {status}: "
        f"{payload!r}. SameSite would then be the only thing standing between this API "
        "and a cross site POST."
    )

    status, payload = session.request(
        "POST", "/api/auth/login/", body, {"X-CSRFToken": session.cookies["csrftoken"]}
    )
    assert status != 403, (
        f"even with X-CSRFToken present the request still answered 403: {payload!r}, which "
        "means the first 403 above was never about the missing token"
    )


@needs_stack
def test_live_the_consent_text_shown_is_the_text_recorded() -> None:
    """The loop chapter 5 exists to close, over one real HTTP route.

    Shown, sent and recorded are three places. Layer 2 proves that shown equals
    delivered and layer 4 that delivered equals nl.py; only this puts the whole
    loop end to end, and only this does it through the database the service
    actually writes to.
    """
    from accounts.nl import NL

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    texts = session.json("GET", "/api/auth/consent-texts/")
    version = texts["text_version"]
    assert texts["texts"]["METER_LINK"] == NL["CONSENT_METER_LINK"]

    password = TEST_PASSWORD
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": _fresh_email(),
            "password": password,
            "consent_meter_link": True,
            "consent_lead_generation": False,
            "text_version": version,
        },
    )
    exported = session.json("POST", "/api/auth/export/")
    rows = [row for row in exported["consents"] if row["kind"] == "METER_LINK"]
    assert rows, f"the export carries no METER_LINK row: {exported['consents']}"
    assert rows[0]["text_version"] == version, (
        f"the row records {rows[0]['text_version']} and the screen showed {version}, "
        "which is the exact drift the text_version field exists to prevent"
    )
    session.json("POST", "/api/auth/delete/", {"password": password})


@needs_stack
def test_live_a_stale_version_is_refused_over_the_real_route() -> None:
    """The lock, through nginx and the deployed serializer rather than through
    a serializer imported in the same process as the test."""
    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    status, payload = session.request(
        "POST",
        "/api/auth/register/",
        {
            "email": _fresh_email(),
            "password": TEST_PASSWORD,
            "consent_meter_link": True,
            "consent_lead_generation": False,
            "text_version": "1999-01-01",
        },
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 400, f"a stale version was accepted, answering {status}: {payload!r}"
    assert b"text_version" in payload


def _run_outbox() -> None:
    """Run send_outbound_mail once, inside the api container of the local stack.

    The timer that does this on a host does not exist on a developer machine,
    so the check does what the timer would: one run, foreground, exit code
    read. `--entrypoint python` for the reason the systemd unit gives.
    """
    import subprocess

    docker = shutil.which("docker")
    assert docker, "the live checks need docker on PATH to run the outbox command"
    subprocess.run(
        [
            docker,
            "compose",
            "-f",
            COMPOSE.as_posix(),
            "-f",
            OVERRIDE.as_posix(),
            "--env-file",
            ENV_FIXTURE.as_posix(),
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "api",
            "backend/manage.py",
            "send_outbound_mail",
        ],
        check=True,
        timeout=120,
    )


def _link_token_from_newest_mail(fragment: str) -> str:
    """The token off the newest file the file transport wrote, and the file removed.

    Removed, so a second run of this file reads its own mail and not the
    previous run's, and so no working link stays on disk after the check.
    """
    files = sorted(MAIL_FIXTURE_DIR.glob("outbox-*.txt"), key=lambda path: path.stat().st_mtime)
    assert files, f"no mail was written to {MAIL_FIXTURE_DIR}; did the transport run at all?"
    newest = files[-1]
    text = newest.read_text(encoding="utf-8")
    newest.unlink()
    match = re.search(rf"http://127\.0\.0\.1:8080/account/#{fragment}=([A-Za-z0-9_-]{{43}})", text)
    assert match, f"the mail carries no {fragment} link:\n{text}"
    return match.group(1)


#: The one account the two recovery checks share, set by the verification
#: check and read by the reset check. One registration instead of two, on
#: purpose: auth-register allows five an hour per caller and the four
#: existing live checks already spend three, so a second registration here
#: would put every rerun inside the hour on a 429. pytest runs the functions
#: of a module in definition order, which is why the verification check is
#: written first.
_RECOVERY_ACCOUNT: dict[str, str] = {}


@needs_stack
def test_live_a_verification_link_sets_the_timestamp() -> None:
    """The mail registration itself queued, followed on a session that is not
    signed in, and `me/` afterwards saying when. Leaves the account in place
    for the reset check below."""
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    email = _fresh_email()
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    assert session.json("GET", "/api/auth/me/")["email_verified_at"] is None
    _run_outbox()
    token = _link_token_from_newest_mail("verificatie")

    stranger = _Session(STACK)
    stranger.request("GET", "/api/auth/me/")
    status, payload = stranger.request(
        "POST",
        "/api/auth/verify/confirm/",
        {"token": token},
        {"X-CSRFToken": stranger.cookies["csrftoken"]},
    )
    assert status == 204, payload

    assert session.json("GET", "/api/auth/me/")["email_verified_at"] is not None
    session.json("POST", "/api/auth/logout/")
    _RECOVERY_ACCOUNT["email"] = email


@needs_stack
def test_live_a_reset_link_closes_the_loop() -> None:
    """The whole recovery flow over one real connection, with the mail read
    back out of a file: request, send, follow, set, sign in. No layer above
    this can prove that the link in the mail is the link the API accepts.

    Runs on the account the verification check registered, so the address is
    already confirmed here; that a completed reset confirms an address on its
    own is proved in tests/test_accounts_recovery.py and not repeated over
    the wire.
    """
    assert STACK is not None
    email = _RECOVERY_ACCOUNT.get("email")
    assert email, (
        "no account to reset: the verification check runs first and registers it, "
        "and the two share one registration on purpose"
    )
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")

    answer = session.json("POST", "/api/auth/reset/request/", {"email": email})
    assert answer == {}
    _run_outbox()
    token = _link_token_from_newest_mail("herstel")

    status, payload = session.request(
        "POST",
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 204, payload
    assert not any(header.startswith("ampeer_") for header in session.set_cookie), (
        f"a reset signed somebody in: {session.set_cookie}"
    )

    status, _ = session.request(
        "POST",
        "/api/auth/login/",
        {"email": email, "password": TEST_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 401, "the old password still works after a reset"
    session.json("POST", "/api/auth/login/", {"email": email, "password": OTHER_PASSWORD})
    _assert_session_cookie_attributes(session, "login/ after a reset")
    assert session.json("GET", "/api/auth/me/")["email_verified_at"] is not None

    status, payload = session.request(
        "POST",
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 400 and b"token" in payload, (status, payload)
    session.json("POST", "/api/auth/delete/", {"password": OTHER_PASSWORD})
    _RECOVERY_ACCOUNT.clear()


# ---------------------------------------------------------------------------
# The override
# ---------------------------------------------------------------------------


def test_the_override_publishes_only_on_the_loopback_interface() -> None:
    """A published port is the one thing this override adds that production
    forbids, so the interface it binds is the whole of its safety.

    "8080:80" and "0.0.0.0:8080:80" are the same string to Docker and both are
    reachable from whatever network the machine is on, because a published port
    is a forwarding rule evaluated before the host firewall sees the packet. A
    developer laptop is usually on somebody else's wifi.
    """
    services = _compose_document(OVERRIDE)["services"]
    published = {
        name: spec["ports"] for name, spec in services.items() if spec.get("ports") is not None
    }
    assert published, "the override publishes nothing, so the stack cannot be driven"
    for name, ports in published.items():
        for entry in ports:
            assert str(entry).startswith("127.0.0.1:"), (
                f"{name} publishes {entry!r} beyond loopback"
            )


def test_the_override_introduces_no_image_of_its_own() -> None:
    """It holds a door open in the production stack; it is not a second stack.

    An `image:` here would mean the thing being driven locally is not the thing
    that runs on the host, and every one of the seven checks would then be a
    check of something else.
    """
    offenders = [
        name for name, spec in _compose_document(OVERRIDE)["services"].items() if spec.get("image")
    ]
    assert not offenders, f"the override names its own images for: {offenders}"


def test_the_override_replaces_the_published_port_rather_than_adding_to_it() -> None:
    """The tag is the whole fix, and it is invisible in a parsed document.

    Compose MERGES two `ports:` lists rather than replacing one with the
    other. Without `!override` a local run published 0.0.0.0:80 from
    docker-compose.yml as well as the loopback binding from this file, so the
    override that exists to make the opening smaller made it larger, on a
    machine that is on somebody's wifi. Seen on 2026-09-13 in
    `docker compose ps`, which listed both mappings on one container, and not
    seen by the first version of this test, which compared the two files and
    never asked what compose does with them.

    Since 2026-09-14 the production file publishes 8080 as well, so the merged
    pair would be 0.0.0.0:8080 and 127.0.0.1:8080 and the container would
    refuse to start on an address already in use. That is a louder failure than
    the quiet one this test was written for, and it is not a reason to keep the
    tag any less deliberately: a loud failure on a developer machine is still
    the override doing the opposite of what it exists for.

    Asserted on the raw text, because a parsed document cannot show a tag.

    Red proof: drop the tag and `docker compose ... ps` shows two mappings
    again; this assertion is what makes that visible without Docker.
    """
    raw = OVERRIDE.read_text(encoding="utf-8")
    assert "ports: !override" in raw, (
        "the override adds a port mapping instead of replacing the production "
        "one, so a local run publishes on every interface as well"
    )

    production = _compose_document(COMPOSE)["services"]["web"]["ports"]
    override = _compose_document(OVERRIDE)["services"]["web"]["ports"]
    assert production == ["8080:80"], production
    assert "127.0.0.1" not in COMPOSE.read_text(encoding="utf-8"), (
        "the production file binds to the loopback, which no other machine can reach"
    )
    assert all(str(entry).startswith("127.0.0.1:") for entry in override), override


def test_the_override_says_it_must_never_reach_a_host() -> None:
    """The file is one page of YAML that would work perfectly on the LXC and
    would undo the network design if it ran there. Saying so is the only thing
    standing between it and a copy."""
    head = OVERRIDE.read_text(encoding="utf-8")[:400]
    assert "NEVER BE USED ON A HOST" in head


def test_the_override_runs_under_a_project_name_of_its_own() -> None:
    """A local teardown must not be able to name the production project.

    docker-compose.yml sets `name: ampeer` and compose takes the project name
    from the last file that names one, so until 2026-08-21 every command in
    section 7 of infra/README.md ran under the production project name, and the
    last of those commands is `down -v`. In a checkout on a machine whose
    docker context points at the LXC that removes the volume holding every
    stored advice, and nothing in this repository backs it up or mentions a
    backup.

    Verified on 2026-08-21 against compose v2.39.4: with this line,
    `docker compose -f docker-compose.yml -f compose.test.yml config` prints
    `name: ampeer-local`, and the production file on its own still prints
    `name: ampeer`.

    The `-p` the audits used is not a fix, because it is a property of whoever
    typed the command. This is a property of the file.
    """
    local = _compose_document(OVERRIDE).get("name")
    production = _compose_document(COMPOSE).get("name")
    assert production, "docker-compose.yml no longer names a project"
    assert local, "the override sets no project name, so a local `down -v` names the production one"
    assert local != production, f"the override runs under the production project name: {local!r}"


def test_the_readme_never_prints_a_volume_wiping_teardown_outside_the_override() -> None:
    """`down -v` on the production project deletes the database.

    The README is where somebody copies a command from, so the rule is about
    the text and not only about the file: any block in it that prints `down -v`
    has to be a block that also names compose.test.yml, which carries a project
    name of its own. A block that prints the two words next to `-f
    docker-compose.yml` alone is a line somebody pastes into the wrong shell.
    """
    readme = (INFRA / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```[a-z]*\n(.*?)```", readme, re.DOTALL)
    offenders = [
        block for block in blocks if "down -v" in block and "compose.test.yml" not in block
    ]
    assert not offenders, f"README blocks that wipe volumes without the local override: {offenders}"


# ---------------------------------------------------------------------------
# The log driver: an unrotated log is a retention nobody chose
# ---------------------------------------------------------------------------


def test_every_service_bounds_how_long_its_log_lives() -> None:
    """Docker's json-file driver keeps every line until the container is
    removed, and `restart: unless-stopped` means these containers are not
    removed.

    Everything in this stack logs to stdout and stderr on purpose, so the log
    driver is the only place the retention can be set at all. Section 9 of the
    design asks for it to be chosen; without these options it is the default,
    and a default is not a choice. Both keys are required: max-size alone
    rotates and keeps every rotated file forever.
    """
    for name, spec in _compose_document(COMPOSE)["services"].items():
        logging = spec.get("logging")
        assert logging, f"{name} has no logging configuration, so its log grows without bound"
        options = logging.get("options", {})
        assert options.get("max-size"), f"{name} sets no max-size"
        assert options.get("max-file"), f"{name} sets no max-file"


# ---------------------------------------------------------------------------
# .dockerignore
# ---------------------------------------------------------------------------


def _copy_sources(dockerfile: Path) -> list[str]:
    """Every path a Dockerfile copies out of the build context.

    `COPY --from=...` is excluded: those read an earlier stage or another image
    and never touch the context, so requiring them here would demand that
    /app/.venv be un-ignored, which is nonsense.
    """
    sources: list[str] = []
    for raw in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.upper().startswith("COPY "):
            continue
        parts = line.split()[1:]
        if any(part.startswith("--from=") for part in parts):
            continue
        sources.extend(part for part in parts[:-1] if not part.startswith("--"))
    return sources


def test_the_build_context_is_an_allow_list_and_it_covers_every_copy() -> None:
    """Until 2026-08-21 there was no .dockerignore, so the context for both
    images was the whole tree: .git, .venv at 558 MB, frontend/node_modules,
    and data/ with the NEDU profile in it.

    The file is written as `*` plus exceptions, so the failure mode when a
    Dockerfile starts copying something new is a build that stops on a missing
    file. This test turns that into a red test first, and it is the reason the
    allow-list is safe to keep: an allow-list nobody maintains is a build
    everybody works around.
    """
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines[0] == "*", f"the first pattern is not a deny-everything: {lines[0]!r}"
    allowed = {line[1:].rstrip("/") for line in lines if line.startswith("!")}

    for dockerfile in (INFRA / "api.Dockerfile", INFRA / "web.Dockerfile"):
        for source in _copy_sources(dockerfile):
            covered = any(source == entry or source.startswith(f"{entry}/") for entry in allowed)
            assert covered, f"{dockerfile.name} copies {source!r}, which .dockerignore excludes"


def test_the_profile_directory_never_enters_a_build_context() -> None:
    """data/ holds a developer's copy of the NEDU standard profile, which is
    somebody else's data under redistribution terms that are not confirmed, and
    both images are published to a public registry.

    `*` already excludes it. This asserts that no exception takes it back,
    which is the change a person makes while trying to get a test to pass.
    """
    lines = [line.strip() for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()]
    for line in lines:
        assert not line.startswith("!data"), f".dockerignore re-includes the profile data: {line}"


# ---------------------------------------------------------------------------
# The preflight script lives on the host, and nothing noticed when it drifted
# ---------------------------------------------------------------------------


def test_the_deploy_checks_that_retention_is_still_running() -> None:
    """`purge_expired_advice --check` was implemented, tested, and called by
    nothing.

    The design said it would be the container's healthcheck. It cannot be: the
    readiness check that the api image does declare issues no database query on
    purpose, and a check running every thirty seconds that counts rows is the
    load generator that decision exists to avoid. So it runs in two places that
    are not a healthcheck, and this asserts the second of them.

    Neither place notices a timer that was never enabled. See infra/README.md.
    """
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "purge_expired_advice --check" in workflow, (
        "the deploy job does not run the retention check, so a deploy stays green "
        "while nothing is being deleted"
    )


def test_the_deploy_checks_that_the_outbox_is_being_emptied() -> None:
    """The same shape as the retention check, for the mails a household is
    waiting on. Neither notices a timer that was never enabled."""
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "send_outbound_mail --check" in workflow


def test_the_mail_unit_runs_the_command_every_minute() -> None:
    service = (INFRA / "systemd" / "ampeer-mail.service").read_text(encoding="utf-8")
    timer = (INFRA / "systemd" / "ampeer-mail.timer").read_text(encoding="utf-8")
    assert "backend/manage.py send_outbound_mail" in service
    assert "--entrypoint python" in service
    assert "OnCalendar=*-*-* *:*:00" in timer
    # Line-anchored rather than a substring check: the file may still mention
    # the flag in a comment explaining why it is absent, as ampeer-mail.timer
    # does; only an actual `[Timer]` directive line has to be missing.
    assert not any(line.startswith("Persistent=") for line in timer.splitlines())
    assert "INSTALLED BY HAND" in service[:400]


def test_the_purge_unit_fails_when_the_purge_achieved_nothing() -> None:
    """The other of the two places, on the host.

    ExecStartPost runs only if ExecStart succeeded, so this asks the question
    that is left after a purge has just run: is anything still overdue? If it
    is, the delete did not do what its own output claimed, and the unit goes to
    `failed` instead of reporting a count nobody reads.
    """
    unit = (INFRA / "systemd" / "ampeer-purge.service").read_text(encoding="utf-8")
    post = [line for line in unit.splitlines() if line.startswith("ExecStartPost=")]
    assert post, "the purge unit cannot fail on a purge that deleted nothing"
    assert "purge_expired_advice --check" in post[0], post


# ---------------------------------------------------------------------------
# The profile fixture
# ---------------------------------------------------------------------------


def write_profile_fixture(path: Path) -> None:
    """Write a synthetic NEDU-shaped file with one flat E1A series.

    Flat on purpose, and not a plausible curve. A synthetic profile that looked
    like a household would produce an advice that looks like an advice, and the
    numbers in it would be arithmetic on a shape nobody measured. The whole
    reason advice/profiles.py refuses to start without the real file is that
    such a number is indistinguishable from a real one from the outside. A
    perfectly flat day makes the output obviously not about anybody, which is
    what a fixture for the request path should be.

    The layout is the one ampeer_sim.profiles.nedu reads: semicolon separated,
    seven header rows, data from column three. Columns zero to two of the
    header rows are never parsed, so the warning goes there and travels with
    the file.
    """
    value = repr(1.0 / FIXTURE_QUARTERS)
    header = [
        f"NOT A NEDU PROFILE. Generated, synthetic, and not to be shipped.;;;{FIXTURE_SERIES}",
        f"Every quarter of the year carries the same fraction of the annual total.;;;{FIXTURE_YEAR}",
        "It exists so infra/compose.test.yml can prove that the bind mount, the;;;",
        "readiness check and the request path work. The advice computed from it;;;",
        "is arithmetic on a curve nobody measured and is not an advice: nobody;;;",
        "reads it, and no deployment may mount this file. The real file and its;;;",
        "redistribution terms are the open question in section 10 of the design.;;;",
    ]
    body = "\n".join(f";;;{value}" for _ in range(FIXTURE_QUARTERS))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")


def test_the_generated_profile_is_one_the_engine_accepts(tmp_path: Path) -> None:
    """The generator and the reader have to agree, and they are in different
    packages.

    Without this the first symptom of a drifting fixture is a container that
    reports unhealthy for a reason that looks like a broken mount, at the point
    where somebody is trying to find out whether the mount works.
    """
    from ampeer_sim.profiles.nedu import NeduFileProvider, validate_fractions
    from ampeer_sim.timebase import YearGrid
    from ampeer_sim.types import ProfileCategory

    fixture = tmp_path / "nedu-flat.csv"
    write_profile_fixture(fixture)

    fractions = NeduFileProvider(fixture).fractions(FIXTURE_YEAR, ProfileCategory.E1A)
    assert fractions.shape == (FIXTURE_QUARTERS,)
    validate_fractions(fractions, ProfileCategory.E1A, YearGrid.for_year(FIXTURE_YEAR))


def test_the_generated_profile_says_what_it_is_in_its_own_first_line(tmp_path: Path) -> None:
    """It is a megabyte of numbers in the exact format of a file that may not
    be redistributed. Somebody will find a copy of it one day with no idea
    where it came from."""
    fixture = tmp_path / "nedu-flat.csv"
    write_profile_fixture(fixture)
    assert fixture.read_text(encoding="utf-8").startswith("NOT A NEDU PROFILE.")


# ---------------------------------------------------------------------------
# The environment fixture
# ---------------------------------------------------------------------------


def env_fixture_lines(profile_path: str) -> list[str]:
    """The env file the local checks run with, as lines.

    Generated rather than committed. It is shaped exactly like the file that
    holds the signing key and the database password on the host, and a copy of
    that shape sitting in the repository is the thing somebody edits into a
    real one. Every value below is a placeholder that says so in the value
    itself, which is also what keeps a secret scanner honest about it.
    """
    return [
        "# Generated by tests/test_stack_smoke.py for infra/compose.test.yml.",
        "# Git-ignored, local only, and every value is a placeholder.",
        "DJANGO_SECRET_KEY=smoke-check-placeholder-not-a-secret",
        # Three names, and the order is the whole point of the first one.
        #
        # Through nginx, Django sees the Host header nginx sets from $host,
        # which is the name without the port: 127.0.0.1. So the loopback names
        # have to be here or the site does not work locally.
        #
        # `ampeer.smoke.invalid` is first because the api image's readiness
        # check sends the first name in this list as its Host header, and a
        # list that begins with 127.0.0.1 would satisfy that check by accident.
        # It did: until 2026-08-21 the check sent a hardcoded
        # `Host: 127.0.0.1:8000`, this fixture happened to allow it, and the
        # same container measured with the production value
        # `DJANGO_ALLOWED_HOSTS=ampeer.nl` answered `HTTP Error 400: Bad
        # Request` on every probe and read `unhealthy` forever. The local run
        # is the only place that check is ever exercised before a host sees it,
        # so it must not be the place where it cannot fail.
        #
        # `.invalid` is the reserved suffix from RFC 2606: it can never resolve
        # anywhere, so this name cannot become a request to something real.
        "DJANGO_ALLOWED_HOSTS=ampeer.smoke.invalid,127.0.0.1,localhost",
        # Same origin as the published port, which is the point of check 3:
        # the browser never needs a CORS header because this is where the site
        # is served from as well.
        "DJANGO_CORS_ALLOWED_ORIGINS=http://127.0.0.1:8080",
        # ONE, where the host uses two. This number is the count of proxies in
        # this deployment's own chain that append to X-Forwarded-For, and the
        # local stack has one hop fewer than the host: there is no tunnel
        # connector in front of nginx here. Copying the production 2 into this
        # file would make DRF read the second entry from the right, which in a
        # one-proxy chain is whatever the caller sent, and check 7 would then
        # demonstrate the rate-limit bypass instead of the fix.
        "DJANGO_NUM_PROXIES=1",
        f"AMPEER_NEDU_PROFILE_PATH={profile_path}",
        "POSTGRES_DB=ampeer",
        "POSTGRES_USER=ampeer",
        "POSTGRES_PASSWORD=smoke-check-placeholder-not-a-secret",
        "POSTGRES_HOST=db",
        # The file transport: the two recovery checks of task 12 read the
        # mail back out of infra/fixtures/mail/, which the override mounts on
        # /srv/mail. The only file in the repository that ever says `file`;
        # the preflight refuses it on a host.
        "AMPEER_MAIL_TRANSPORT=file",
        # Unused under the file transport and interpolated by compose all the
        # same. Not beginning with `re_`, the prefix of a real Resend key, so
        # this line can never be mistaken for one.
        "RESEND_API_KEY=smoke-check-placeholder-not-a-secret",
        # The reserved suffix again: nothing can ever be delivered to it.
        "AMPEER_MAIL_FROM=noreply@ampeer.smoke.invalid",
        # Where the links in a mail point, which for this stack is the
        # published port. The check reads the token off that link's fragment.
        "AMPEER_SITE_ORIGIN=http://127.0.0.1:8080",
        # Not a release. The local run builds both images from this tree and
        # tags them with this string, so nothing here can be confused with
        # something CI published.
        "AMPEER_VERSION=smoke",
    ]


def test_the_environment_fixture_names_every_variable_the_stack_reads() -> None:
    """The same coupling tests/test_infra.py asserts for .env.example, for the
    file the local checks actually run with.

    A missing name here does not fail loudly: compose substitutes an empty
    string, prints a warning among a hundred other lines, and the api container
    exits with a RuntimeError that reads like a code fault. That is the failure
    scripts/preflight_env.sh exists to prevent, and it would be embarrassing to
    meet it in the rehearsal for it.

    Both directions, since 2026-09-13. A name the fixture sets that compose
    never reads is dead, and dead is not harmless here: this file is one `cp`
    away from /srv/ampeer/.env, so every line in it reads as something the
    stack needs. CLOUDFLARE_TUNNEL_TOKEN sat here for a day after the connector
    was removed, described by a comment about a tunnel that no longer existed,
    and the one-directional assertion above had nothing to say about it.
    """
    text = COMPOSE.read_text(encoding="utf-8")
    interpolated = set(re.findall(r"(?<!\$)\$\{([A-Z_][A-Z0-9_]*)[:}]", text))
    named = {
        line.split("=", 1)[0]
        for line in env_fixture_lines("/tmp/profile.csv")
        if not line.startswith("#")
    }
    assert not interpolated - named, (
        f"read by compose, absent from the fixture: {interpolated - named}"
    )
    assert not named - interpolated, (
        f"set by the fixture, read by nothing in the compose file: {named - interpolated}"
    )


def test_the_environment_fixture_holds_no_value_that_could_be_mistaken_for_real() -> None:
    """It is generated into a git-ignored directory, but it is one `cp` away
    from /srv/ampeer/.env, and a placeholder that looks like a key is a key
    somebody ships."""
    for line in env_fixture_lines("/tmp/profile.csv"):
        if line.startswith(("DJANGO_SECRET_KEY=", "POSTGRES_PASSWORD=", "RESEND_API_KEY=")):
            assert "placeholder-not-a-secret" in line, line
        if line.startswith("RESEND_API_KEY="):
            assert not line.split("=", 1)[1].startswith("re_"), line


def test_the_environment_fixture_cannot_satisfy_the_readiness_check_by_accident() -> None:
    """The first name in DJANGO_ALLOWED_HOSTS is the Host the api image's
    HEALTHCHECK sends, so it decides whether that check is exercised or merely
    tautological here.

    On a host the first name is `ampeer.nl`, which is a name Django has to be
    told about. If it is a loopback name here, the local run proves nothing
    about the one property that broke: a check whose Host header is not in
    ALLOWED_HOSTS is refused by Django before any view runs, and the container
    is unhealthy for as long as it lives.
    """
    values = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_fixture_lines("/tmp/profile.csv")
        if not line.startswith("#")
    }
    hosts = [host.strip() for host in values["DJANGO_ALLOWED_HOSTS"].split(",") if host.strip()]
    assert hosts, "the fixture allows no hosts at all, so prod.py refuses to start"
    assert hosts[0] not in {"127.0.0.1", "localhost", "0.0.0.0", "::1", "[::1]", "*"}, (
        f"the readiness check's Host header is a loopback name here: {hosts[0]!r}"
    )
    assert "127.0.0.1" in hosts, (
        "nginx sets Host from $host, which is 127.0.0.1 locally, so the site would 400"
    )


@pytest.mark.parametrize("name", ["DJANGO_NUM_PROXIES"])
def test_the_environment_fixture_carries_the_local_hop_count(name: str) -> None:
    """Called out on its own because it is the one value that is deliberately
    different from production, and a later reader copying this file to a host
    would be copying a rate limit that counts the wrong thing."""
    values = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_fixture_lines("/tmp/profile.csv")
        if not line.startswith("#")
    }
    assert values[name] == "1"


def main() -> int:
    """Write both fixtures where infra/compose.test.yml expects them."""
    write_profile_fixture(PROFILE_FIXTURE)
    MAIL_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    # The api container runs as uid 10001 and writes here through the bind
    # mount. On Docker Desktop any uid may; on a Linux host the directory
    # would belong to the developer, so it is opened up. Best effort: chmod is
    # a no-op on Windows and this directory holds nothing but test mail.
    MAIL_FIXTURE_DIR.chmod(0o777)
    # as_posix(), which is a no-op on the host and the whole difference on a
    # Windows developer machine. scripts/preflight_env.sh reads this value with
    # `[ -f ... ]` and refuses a path with no forward slash in it, on the
    # grounds that compose reads such a string as a volume name rather than as
    # a bind mount source. A backslashed path fails both, which would make
    # check 4 fail for a reason that has nothing to do with what it checks.
    ENV_FIXTURE.write_text(
        "\n".join(env_fixture_lines(PROFILE_FIXTURE.resolve().as_posix())) + "\n",
        encoding="utf-8",
    )
    size_mb = PROFILE_FIXTURE.stat().st_size / 1_048_576
    print(f"wrote {PROFILE_FIXTURE} ({size_mb:.2f} MB, {FIXTURE_QUARTERS} quarters)")
    print(f"prepared {MAIL_FIXTURE_DIR}")
    print(f"wrote {ENV_FIXTURE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def test_the_host_list_names_the_two_things_the_host_still_holds() -> None:
    """The README's own first list, held against what is actually left.

    It named five things until 2026-09-14. Three of them were files copied from
    this repository and verified here by digest, and four releases in a row
    died on the first of them. The deploy checks the tag out now, so those
    three arrive with the job and there is nothing to copy.

    Two remain, and neither can come from a git tag, which is exactly why they
    are the two that are left. The environment file is a secret. The
    consumption profile is gitignored because it is not ours to redistribute.
    Both are asserted by name, because a list that quietly loses an entry is
    how the old one cost four releases.
    """
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"^\s+[A-Z]+_SHA256:", workflow, re.MULTILINE), (
        "deploy.yml pins a digest again; if a file is copied by hand once more, "
        "section 0 of infra/README.md has to name it"
    )
    assert "actions/checkout" in workflow, (
        "the deploy no longer checks the tag out, so the three files it used to "
        "verify are back on the host and back in that list"
    )

    body = README.read_text(encoding="utf-8").split("## 0. ", 1)[1]
    section = re.split(r"^## ", body, maxsplit=1, flags=re.MULTILINE)[0]
    for name in (".env", "AMPEER_NEDU_PROFILE_PATH"):
        assert name in section, f"section 0 no longer names {name}"


@needs_stack
def test_live_a_linked_meter_produces_a_proposal_over_the_real_route() -> None:
    """Phase 3, end to end, over HTTP, through nginx.

    THE CHECK THAT WOULD HAVE CAUGHT IT. Until 2026-09-13 this route answered
    `"check": null` for every household that ever linked a meter, because the
    measurement was placed by counting quarters from the profile year's epoch
    and no reading in the table can be from that year. Every unit test agreed
    with it: each one used a hardcoded 2025 date. Nothing that ran against a
    stack ever pushed a reading through the ingest and asked the route what it
    made of it, so a feature that did nothing at all looked finished.

    This asserts the shape and not the figure. The container mounts a flat
    synthetic profile, so the annual consumption this fit lands on is
    arithmetic on a curve nobody measured and means nothing. What it does mean
    is that readings pushed with today's timestamps reach the window, the fit
    runs, and a band comes back: null before the meter, a band after it.
    """
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    email = _fresh_email()
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": True,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    _run_outbox()
    session.request(
        "POST",
        "/api/auth/verify/confirm/",
        {"token": _link_token_from_newest_mail("verificatie")},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )

    typed = 3500.0
    session.json(
        "POST",
        "/api/auth/advice/",
        {
            "peak_power_wp": 3500,
            "azimuth_deg": 0,
            "tilt_deg": 35,
            "annual_consumption_kwh": typed,
            "postcode4": "5401",
            # The nine question form, which is what this route takes: the
            # calibrated advice is an upgrade on a full answer and not on the
            # four question one. All five flags false, so the household is the
            # simplest one that exists and the fit has nothing extra to carry.
            "daytime_occupancy": False,
            "has_ev": False,
            "has_heat_pump": False,
            "dynamic_contract": False,
            "has_battery": False,
        },
    )
    assert session.json("POST", "/api/auth/advice/check/")["check"] is None, (
        "a household with no meter has nothing to be told"
    )

    raw = session.json("POST", "/api/auth/meter/link/")["token"]

    # Four whole weeks ending at the last complete quarter, because the fit
    # refuses a window under three and the leave-one-week-out band needs whole
    # ones. A flat offtake, which is not a household and is not meant to be:
    # what is being proved is that a reading stamped this week arrives at a
    # position on a grid that runs in 2025.
    last = datetime.now(UTC).replace(second=0, microsecond=0)
    last = last.replace(minute=last.minute - last.minute % 15) - timedelta(minutes=15)
    quarters = 4 * 7 * 96
    moments = [last - timedelta(minutes=15 * step) for step in range(quarters)]
    for start in range(0, quarters, 100):
        batch = moments[start : start + 100]
        status, payload = _push_readings(raw, batch)
        assert status == 202, payload

    check = session.json("POST", "/api/auth/advice/check/")["check"]
    assert check is not None, (
        "readings pushed with this week's timestamps reached the route and it "
        "still has nothing to say; the window is empty again"
    )
    assert check["p10_kwh"] <= check["p50_kwh"] <= check["p90_kwh"]
    assert check["typed_kwh"] == pytest.approx(typed)
    session.json("POST", "/api/auth/logout/")


def _push_readings(raw: str, moments: list[datetime]) -> tuple[int, bytes]:
    """One ingest push, as the device makes it: a bearer token and no session.

    Separate from `_Session` on purpose. The ingest carries no cookie, no CSRF
    header and no Origin, because a P1 device is not a browser, and running it
    through the session helper would prove the wrong thing about it.
    """
    import json as jsonlib
    import urllib.error
    import urllib.request

    assert STACK is not None
    body = {
        "readings": [
            {
                "measured_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                # A quarter of a kilowatt hour off the grid, and nothing back.
                "consumption_kwh": 0.25,
                "feed_in_kwh": 0.0,
            }
            for moment in moments
        ]
    }
    request = urllib.request.Request(
        f"{STACK.rstrip('/')}/api/meter/readings/",
        data=jsonlib.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Meter {raw}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
