"""The compose file is configuration, so it is read like code.

Nothing here starts a container. These are properties of the document, and they
are the properties that would otherwise be discovered on the host: an image that
moved under a tag, a port published to the world, a secret with a default.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

INFRA = Path(__file__).resolve().parent.parent / "infra"
COMPOSE = INFRA / "docker-compose.yml"
ENV_EXAMPLE = INFRA / ".env.example"

#: prod.py refuses to start without each of these. Kept here as a literal
#: rather than imported, so a test failure names the drift instead of hiding it
#: behind an import that follows the change.
REQUIRED_ENV = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "DJANGO_NUM_PROXIES",
    "AMPEER_NEDU_PROFILE_PATH",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
)

#: The two images this repository builds itself. They carry a tag that the
#: deploy rewrites per release, so a digest cannot be written down here; every
#: other image comes from a registry and must be pinned. This tuple is the
#: whole exemption, and a test below asserts it cannot widen without saying so.
BUILT_IN_THIS_REPOSITORY = ("api", "web")

#: Everything a compose service can use to make itself reachable from the host.
#: `ports:` in either syntax is the obvious one; `network_mode: host` is the
#: one that publishes nothing and listens on everything.
PORT_KEY = re.compile(r"^\s*ports\s*:", re.MULTILINE)
PUBLISHED_KEY = re.compile(r"^\s*published\s*:", re.MULTILINE)


def compose() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return loaded


def service(name: str) -> dict[str, Any]:
    services = compose()["services"]
    assert name in services, f"no service {name!r}: {sorted(services)}"
    definition: dict[str, Any] = services[name]
    return definition


def test_the_stack_has_the_four_services_it_needs() -> None:
    assert set(compose()["services"]) == {"api", "web", "db", "tunnel"}


@pytest.mark.parametrize("name", ["db", "tunnel"])
def test_every_image_pulled_from_a_registry_is_pinned_by_digest(name: str) -> None:
    """A tag is a name somebody else can repoint.

    `api` and `web` are built from Dockerfiles in this repository and carry a
    build stanza plus the release tag the deploy rewrites, so they are exempt
    here; what has to be pinned is anything pulled from a registry, including
    the base images inside those Dockerfiles, which Tasks 2 and 3 assert
    separately.
    """
    image = str(service(name).get("image", ""))
    assert "@sha256:" in image, f"{name} is not pinned by digest: {image!r}"


def test_only_the_images_this_repository_builds_are_exempt_from_the_digest_rule() -> None:
    """The exemption above is two names, and it stays two names.

    Without this, a fifth service pulled by tag is exempt from the digest rule
    by the simple fact that nobody added it to the parametrisation, which is the
    quietest way a gate stops covering the thing it was written for.
    """
    services = compose()["services"]
    built = {name for name, spec in services.items() if spec.get("build")}
    assert built == set(BUILT_IN_THIS_REPOSITORY), f"services carrying a build stanza: {built}"
    unpinned = [
        f"{name}: {spec.get('image')!r}"
        for name, spec in services.items()
        if name not in BUILT_IN_THIS_REPOSITORY and "@sha256:" not in str(spec.get("image", ""))
    ]
    assert not unpinned, f"images from a registry that are not pinned by digest: {unpinned}"


def test_nothing_publishes_a_port_to_the_world() -> None:
    """Cloudflare Tunnel makes an outbound connection, so nothing listens.

    A published port here is how a stack that was designed to be unreachable
    quietly becomes reachable, and the person who adds one is usually debugging,
    not deploying. Three forms of the same mistake are checked, because the
    parsed-document check alone would miss two of them:

    * the short syntax, `- "8000:8000"`, and the long one, a mapping with a
      `published:` key, which reads as documentation rather than as an opening
    * a mapping under any key at all, not only under a service, so a fragment
      parked in an anchor or an unused block cannot carry one in
    * `network_mode: host`, which publishes nothing and listens on everything
    """
    text = COMPOSE.read_text(encoding="utf-8")
    services = compose()["services"]

    declared = [name for name, spec in services.items() if spec.get("ports")]
    assert not declared, f"services publishing ports: {declared}"

    host_network = [
        name for name, spec in services.items() if "host" in str(spec.get("network_mode", ""))
    ]
    assert not host_network, f"services on the host network: {host_network}"

    assert not PORT_KEY.search(text), "the compose file declares a port mapping key"
    assert not PUBLISHED_KEY.search(text), "the compose file publishes a port in the long syntax"


def test_no_secret_has_a_default_in_the_compose_file() -> None:
    """`${VAR:-something}` is a default, and a default for a secret is a secret
    in the repository with extra steps."""
    text = COMPOSE.read_text(encoding="utf-8")
    for name in REQUIRED_ENV:
        assert f"${{{name}:-" not in text, f"{name} has a default in docker-compose.yml"
        assert f"${{{name}:=" not in text, f"{name} has a default in docker-compose.yml"
    # The named nine are not the only variables this file reads. The tunnel
    # token and the release tag are interpolated here too, and a default for
    # either is the same failure wearing a different name.
    defaulted = re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\s*:?[-=]", text)
    assert not defaulted, (
        f"variables with a default in docker-compose.yml: {sorted(set(defaulted))}"
    )


def test_the_example_names_every_variable_and_carries_no_value() -> None:
    """The example is the checklist somebody works from. A value in it is a
    value somebody will ship.

    So the line shape is asserted whole rather than only after the first `=`.
    `POSTGRES_PASSWORD` and `POSTGRES_PASSWORD=` and `POSTGRES_PASSWORD= ` are
    three different lines, and only the middle one is a blank to be filled in:
    the first is a name compose never reads, and the third is a password of one
    space that starts the service and fails every connection.
    """
    lines = [
        line
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for line in lines:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*=", line), f"not an empty assignment: {line!r}"
    named = {line.split("=", 1)[0] for line in lines}
    assert set(REQUIRED_ENV) <= named, f"missing: {sorted(set(REQUIRED_ENV) - named)}"

    # Every variable the compose file interpolates has to appear here, not only
    # the nine prod.py names. A variable compose reads and the checklist omits
    # is the one that is unset on the host, and `$$` escapes are excluded so
    # the healthcheck's own shell expansion does not count as a requirement.
    text = COMPOSE.read_text(encoding="utf-8")
    interpolated = set(re.findall(r"(?<!\$)\$\{([A-Z_][A-Z0-9_]*)[:}]", text))
    absent = sorted(interpolated - named)
    assert not absent, f"read by compose, absent from the example: {absent}"


def test_the_database_volume_survives_a_restart() -> None:
    """Without a named volume the first `docker compose down` takes every
    stored advice with it, and that is a data loss nobody would attribute to
    the compose file."""
    assert compose().get("volumes", {}), "no named volumes declared"
    mounts = [str(m) for m in service("db").get("volumes", [])]
    assert any("/var/lib/postgresql/data" in m for m in mounts), mounts


def test_the_profile_file_is_mounted_read_only() -> None:
    """It is somebody else's data under unconfirmed redistribution terms. A
    read-write mount is a way for this service to change it."""
    mounts = [str(m) for m in service("api").get("volumes", [])]
    profile = [m for m in mounts if "nedu" in m.lower() or "profile" in m.lower()]
    assert profile, f"the api service mounts no profile file: {mounts}"
    assert all(m.endswith(":ro") for m in profile), profile


def test_every_service_restarts_unless_stopped_on_purpose() -> None:
    for name, spec in compose()["services"].items():
        assert spec.get("restart") == "unless-stopped", f"{name}: {spec.get('restart')}"


def test_an_image_this_repository_builds_declares_its_own_health() -> None:
    """A healthcheck in compose overrides the image's, so writing it twice is
    writing one copy that goes stale.

    It did, inside a few hours. The compose block named /api/health/ where the
    route is /api/advice/health/, and sent no X-Forwarded-Proto, so
    SECURE_SSL_REDIRECT answered 301 and urlopen followed it into a TLS
    handshake against a plain socket. The api container could never have become
    healthy, and `depends_on: service_healthy` would never have released.

    The image is the only thing that knows its own route and its own redirect
    behaviour, so the rule is that services built here declare health there.
    Pulled images like postgres keep theirs in compose, because their image has
    none worth having.
    """
    built = {name for name, spec in compose()["services"].items() if spec.get("build")}
    assert built == {"api", "web"}, built
    offenders = [name for name in built if compose()["services"][name].get("healthcheck")]
    assert not offenders, (
        f"{offenders} declare a healthcheck in compose, which overrides the one in their Dockerfile"
    )


def _api_healthcheck() -> str:
    """The HEALTHCHECK instruction of api.Dockerfile, comments excluded.

    Read from the file rather than from a built image, so this runs in CI where
    there is no Docker.
    """
    dockerfile = (INFRA / "api.Dockerfile").read_text(encoding="utf-8")
    marker = "\nHEALTHCHECK "
    assert marker in dockerfile, "api.Dockerfile declares no HEALTHCHECK"
    return dockerfile[dockerfile.index(marker) :]


def test_the_readiness_check_asks_with_a_host_the_service_answers_on() -> None:
    """Django refuses a request whose Host is not in ALLOWED_HOSTS before any
    view runs, so a check that sends the wrong one can only ever be red.

    It was. The check sent a hardcoded `Host: 127.0.0.1:8000` while prod.py
    builds ALLOWED_HOSTS from DJANGO_ALLOWED_HOSTS, which infra/README.md and
    infra/.env.example both tell the operator to fill with `ampeer.nl`.
    Measured on 2026-08-21 against a running stack with that value: every probe
    returned `HTTP Error 400: Bad Request`, `docker ps` read `Up About a minute
    (unhealthy)` and never changed, and a POST to /api/advice/estimate/
    carrying `Host: ampeer.nl` answered 201 at the same moment.

    Nothing caught it, and three things depended on it: this check is the only
    thing that notices a NEDU profile mounted as a directory, `web` now waits
    on it, and the README's verify step tells the operator to expect `healthy`.
    Django's test client never validates a Host, and the local fixture happened
    to allow 127.0.0.1, so both places that could have failed agreed.

    The rule is therefore that the header is derived from the same variable
    Django reads, never written down.
    """
    healthcheck = _api_healthcheck()
    assert "'Host'" in healthcheck, "the readiness check sends no Host header at all"
    assert "DJANGO_ALLOWED_HOSTS" in healthcheck, (
        "the readiness check does not read the list Django validates Host against, "
        "so it can be red on a working service"
    )
    for literal in ("'Host': '127.0.0.1", '"Host": "127.0.0.1', "'Host': 'localhost"):
        assert literal not in healthcheck, f"the readiness check hardcodes a Host: {literal!r}"


def test_web_waits_for_the_api_to_be_healthy_rather_than_merely_started() -> None:
    """`up -d` returns when every container it started is running, and running
    says nothing about whether the thing inside works.

    Measured on 2026-08-21 with a deliberately broken api image and
    `condition: service_started`: `up -d` printed `Started` and exited 0, the
    api container was `Restarting (1)` from then on, and the first red was two
    steps later at `migrate`. With `service_healthy` the same deploy stops at
    `up`: `dependency failed to start: container ampeer-api-1 is unhealthy`,
    exit 1, which is the step somebody is watching.

    Measured cost, same day, over a probe every 0.23 seconds across a release
    that changes both image tags: the window in which nothing served went from
    0.74 seconds to 3.29 seconds, because `web` now starts after the first
    successful probe instead of immediately. That is the trade, and it is
    written down here so it is a decision rather than a surprise.
    """
    web = service("web")
    condition = web.get("depends_on", {}).get("api", {}).get("condition")
    assert condition == "service_healthy", (
        f"web depends on api with condition {condition!r}, so `up -d` is green on an api "
        "that starts and immediately dies"
    )


def test_every_manage_py_call_resolves_inside_the_image() -> None:
    """The image's working directory and the commands that use it must agree.

    They did not. api.Dockerfile ended on WORKDIR /app/backend while the
    systemd unit and the deploy workflow both wrote `backend/manage.py`, which
    resolves to /app/backend/backend/manage.py. That would have failed on the
    first deploy and on the first purge, in a container nobody was watching,
    and each lane wrote its half correctly against a different assumption.

    Read from the files rather than from a container, so this runs in CI where
    there is no Docker.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    dockerfile = (root / "infra" / "api.Dockerfile").read_text(encoding="utf-8")
    workdirs = re.findall(r"^WORKDIR\s+(\S+)", dockerfile, re.MULTILINE)
    assert workdirs, "api.Dockerfile sets no WORKDIR"
    final = workdirs[-1]

    callers = {
        "infra/systemd/ampeer-purge.service": root / "infra" / "systemd" / "ampeer-purge.service",
        ".github/workflows/deploy.yml": root / ".github" / "workflows" / "deploy.yml",
    }
    seen = 0
    for label, path in callers.items():
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            # Comments explain these paths at length; only what runs counts.
            if raw.lstrip().startswith("#"):
                continue
            for call in re.findall(r"(\S*manage\.py)", raw):
                if call.startswith("/"):
                    continue
                seen += 1
                resolved = f"{final.rstrip('/')}/{call}"
                assert resolved == "/app/backend/manage.py", (
                    f"{label} calls {call!r} and the image ends on WORKDIR "
                    f"{final}, which resolves to {resolved}"
                )
    assert seen >= 2, f"found only {seen} manage.py call sites; the check found nothing to check"


# ---------------------------------------------------------------------------
# The log ceiling, which the file argues for at length and nothing read
# ---------------------------------------------------------------------------


def _log_options(spec: dict[str, Any]) -> dict[str, str]:
    logging = spec.get("logging")
    assert isinstance(logging, dict), f"no logging block: {logging!r}"
    assert logging.get("driver") == "json-file", f"driver is {logging.get('driver')!r}"
    options = logging.get("options")
    assert isinstance(options, dict), f"no logging options: {options!r}"
    return {str(key): str(value) for key, value in options.items()}


def test_every_service_caps_how_much_log_it_can_keep() -> None:
    """The property the compose file says was missing, and then never checked.

    Its own comment: everything in this stack writes to stdout, Docker's
    json-file driver keeps every byte until the container is removed, and
    `restart: unless-stopped` means these containers are not removed, so
    "until it is removed" is "for as long as the machine lives". The two
    options were added so that no log on this host can grow without bound.

    A fifth service added without `logging: *logging` would be exactly the case
    that argument is about, and nothing said so. The anchor makes it one edit to
    get right and one omission to get wrong, which is why this asks every
    service rather than the anchor.
    """
    for name, spec in compose()["services"].items():
        options = _log_options(spec)
        assert "max-size" in options and "max-file" in options, f"{name}: {options}"


def test_the_log_ceiling_is_the_one_the_file_works_out() -> None:
    """The arithmetic in the comment, held against the values under it.

    The comment derives two figures from max-size and max-file: fifty megabytes
    per service and two hundred for the whole stack. Both depend on the number
    of services as well as on the options, so a fifth service would make the
    second sentence wrong while every option stayed correct.

    max-file above one is the other half and it is argued for in the same
    paragraph: rotation has to discard a fifth at a time instead of everything,
    which is what keeps the oldest file readable while the newest is written. A
    single file turns every rotation into a full loss.
    """
    services = compose()["services"]
    options = {name: _log_options(spec) for name, spec in services.items()}
    sizes = {options[name]["max-size"] for name in options}
    counts = {int(options[name]["max-file"]) for name in options}
    assert len(sizes) == 1 and len(counts) == 1, (
        f"the services no longer share one ceiling: {options}"
    )

    size_mb = int(sizes.pop().removesuffix("m"))
    count = counts.pop()
    assert count > 1, (
        f"max-file is {count}, so a rotation discards everything rather than a fraction"
    )

    # The comment is hard wrapped and prefixed, so "200 MB" can sit at the end
    # of one line with "for the whole stack" starting the next. Matched against
    # the prose with its hashes and line breaks taken out, because an assertion
    # that fails on a rewrap is one somebody loosens rather than fixes. The
    # first version of this test failed on exactly that.
    prose = " ".join(
        line.lstrip().lstrip("#").strip()
        for line in COMPOSE.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("#")
    )
    per_service = size_mb * count
    whole_stack = per_service * len(services)
    assert f"{per_service} MB per service" in prose, (
        f"the options come to {per_service} MB per service and the comment says otherwise"
    )
    assert f"{whole_stack} MB for the whole stack" in prose, (
        f"{len(services)} services at {per_service} MB is {whole_stack} MB and the comment "
        "says otherwise"
    )


def test_the_build_uses_the_interpreter_the_image_already_carries() -> None:
    """Two settings api.Dockerfile calls load bearing, and nothing read them.

    Left to itself uv downloads a managed CPython into the build stage's home
    directory and writes that path into .venv/pyvenv.cfg. The second stage does
    not have that directory, so every process in the final image would fail to
    start on a path that exists only in a layer that was thrown away.

    That is a build that succeeds and an image that cannot run, which is the
    worst place for it: the failure arrives on the host. Measured on
    2026-08-24, setting UV_PYTHON_DOWNLOADS to automatic left the whole suite
    green.

    UV_PYTHON is asserted with it because the pair is what makes the promise.
    Forbidding the download while naming no interpreter leaves uv with nothing
    to use.
    """
    dockerfile = (INFRA / "api.Dockerfile").read_text(encoding="utf-8")
    directives = [
        line.strip() for line in dockerfile.splitlines() if not line.lstrip().startswith("#")
    ]
    joined = " ".join(directives)
    assert "UV_PYTHON_DOWNLOADS=never" in joined, (
        "uv may fetch its own interpreter again, and the path it writes into the venv "
        "does not survive into the final stage"
    )
    interpreter = re.findall(r"UV_PYTHON=(\S+)", joined)
    assert interpreter == ["/usr/local/bin/python3.12"], (
        f"UV_PYTHON names {interpreter}, and with downloads off uv needs an interpreter "
        "this image actually carries"
    )
    # The version in that path has to be the one the base images carry. With
    # downloads off, naming an interpreter this image does not have is a build
    # that fails, and naming the wrong version is a venv built against one
    # interpreter and run on another.
    version = interpreter[0].rsplit("python", 1)[1]
    bases = [line for line in directives if line.startswith("FROM python:")]
    assert bases, "no FROM names a python base image; this test read nothing"
    assert all(base.startswith(f"FROM python:{version}-") for base in bases), (
        f"UV_PYTHON names python{version} and the stages build on {bases}"
    )


# ---------------------------------------------------------------------------
# The gunicorn command line, which the entry point argues for and nothing read
# ---------------------------------------------------------------------------

ENTRYPOINT = INFRA / "entrypoint-api.sh"


def _gunicorn_command() -> str:
    """The exec line that serves, with its continuations joined and comments out."""
    lines = [
        line.strip()
        for line in ENTRYPOINT.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    joined = " ".join(lines).replace(r"\ ", " ")
    marker = "exec gunicorn"
    assert marker in joined, f"{ENTRYPOINT.name} no longer execs gunicorn"
    return joined[joined.index(marker) :]


def test_the_server_writes_no_access_log() -> None:
    """The other half of a promise the nginx config is held to in detail.

    gunicorn's access log writes the request line, and the request line for a
    shared advice is /api/advice/<token>/. tests/test_nginx_config.py spends
    four tests keeping exactly that pairing out of the access log, and the same
    path through gunicorn was a comment.

    Where it would land makes it worse rather than better. The container log
    goes to Docker's json-file driver, so the token would sit beside a client
    address in a file that survives every deploy, and the default gunicorn
    format carries both. Errors still reach stderr, where they belong and where
    they carry no token.

    Measured on 2026-08-24: adding --access-logfile left the whole suite green.
    """
    command = _gunicorn_command()
    for flag in ("--access-logfile", "--access-logformat"):
        assert flag not in command, (
            f"{flag} puts /api/advice/<token>/ into the container log, which is what "
            "infra/nginx/nginx.conf goes out of its way not to write"
        )


def test_the_request_timeout_outlasts_the_one_call_a_request_can_make() -> None:
    """Two timeouts in two packages, and the outer one has to be the larger.

    A request that misses the production cache fetches from PVGIS inside the
    worker. ResilientProductionProvider exists to fall back to the offline table
    when that call times out, and it can only do that if the process is still
    alive to catch requests.Timeout. A gunicorn timeout under the PVGIS one
    kills the worker mid-fetch, so the fallback never runs and the visitor gets
    nothing rather than a coarser answer.

    The inner number is read from the provider rather than repeated, so raising
    it without raising this one is what fails.
    """
    import inspect

    from ampeer_sim.production.pvgis import PvgisProvider

    inner = inspect.signature(PvgisProvider).parameters["timeout_s"].default
    declared = re.findall(r"--timeout (\d+)", _gunicorn_command())
    assert len(declared) == 1, f"the server declares {declared} timeouts"
    outer = int(declared[0])

    assert outer > inner, (
        f"gunicorn kills a worker after {outer}s and one PVGIS call may take {inner}s, so "
        "the fallback that exists for exactly that case never gets to run"
    )
    # The upper side is a judgement rather than a measurement: the frontend has
    # no client-side abort, so this number is the only thing that ends a hung
    # request, and "well below a visitor's patience" is not a figure anything
    # here measured. Pinned so raising it is a commit that says why.
    assert outer == 30, (
        f"the request timeout is now {outer}s. Nothing measured that number; it is the "
        "only thing that ends a hung request while the frontend has no abort, so a change "
        "belongs in a commit that argues for it"
    )


def test_the_server_runs_more_than_one_worker() -> None:
    """A computation is CPU bound for about half a second, says the file.

    One worker serialises every request behind that, so two visitors arriving
    together make the second wait for the first. The upper bound is the box's
    cores and is not something this file can check.
    """
    workers = re.findall(r"--workers (\d+)", _gunicorn_command())
    assert len(workers) == 1, f"the server declares {workers} worker counts"
    assert int(workers[0]) > 1, "one worker serialises every advice behind the one before it"


def _services() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services: dict[str, Any] = loaded["services"]
    return services


def test_the_tunnel_can_reach_the_web_container_and_nothing_else() -> None:
    """The one container facing the internet is not on the network the others share.

    Cloudflare Tunnel makes every request to the origin internally between
    `cloudflared` and the origin, so ``REMOTE_ADDR`` is always a bridge address
    and there is no peer signal separating "arrived through nginx" from
    "arrived from anything else on the bridge". While all four services sat on
    one implicit default network, anything holding a position there could reach
    ``api:8000`` around nginx and forge ``X-Forwarded-Proto``, which is
    Django's only TLS signal, and ``X-Forwarded-For``, which is what the
    throttle counts. Django's own ``SECURE_PROXY_SSL_HEADER`` documentation
    makes "your proxy strips the header from all incoming requests" a
    precondition for setting it, and a direct connection to the api does not
    satisfy it.

    ``tunnel`` is the likeliest holder of that position: the only image here not
    built from this repository, and the only one that talks to the internet.
    """
    services = _services()
    tunnel = set(services["tunnel"]["networks"])
    api = set(services["api"]["networks"])
    db = set(services["db"]["networks"])
    web = set(services["web"]["networks"])

    assert tunnel == {"edge"}, f"the tunnel is on {sorted(tunnel)} and should be on edge alone"
    assert not tunnel & api, "the tunnel shares a network with the api and can reach it directly"
    assert not tunnel & db, "the tunnel shares a network with the database"
    # nginx is the bridge, and the only one.
    assert tunnel & web, "the tunnel cannot reach nginx, so nothing can be served"
    assert api & web, "nginx cannot reach the api, so nothing can be served"


def test_every_service_says_which_network_it_is_on() -> None:
    """A service with no `networks` key joins the default one silently.

    That is how all four ended up sharing a network in the first place: nobody
    wrote it down, so nobody read it. An addition made without this key would
    quietly undo the split above and no assertion in this file would notice,
    because the two tests there only look at the four services that exist
    today.
    """
    missing = [name for name, body in _services().items() if "networks" not in body]
    assert not missing, f"these services join the default network by omission: {missing}"


def test_the_backend_network_can_still_reach_the_outside() -> None:
    """`internal: true` on the back network would be a plausible tightening and
    would break the product.

    The api calls PVGIS, which is one of the three sources CLAUDE.md's allowlist
    permits, and an internal network has no route out. The finding the split
    above fixes is about INGRESS, which containers are reachable from the one
    facing the internet, and marking the network internal answers a different
    question by breaking the answer to this one.
    """
    loaded: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    back = loaded["networks"]["back"] or {}
    assert not back.get("internal"), (
        "back is marked internal, so the api can no longer reach PVGIS; see the "
        "comment on the networks block"
    )
