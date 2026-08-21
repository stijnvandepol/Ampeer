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
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def service(name: str) -> dict[str, Any]:
    services = compose()["services"]
    assert name in services, f"no service {name!r}: {sorted(services)}"
    return services[name]


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
