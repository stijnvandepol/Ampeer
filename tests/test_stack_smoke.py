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
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "infra"
COMPOSE = INFRA / "docker-compose.yml"
OVERRIDE = INFRA / "compose.test.yml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
PREFLIGHT = REPO_ROOT / "scripts" / "preflight_env.sh"

#: Where the generated fixtures land. Git-ignored: one of them is a megabyte of
#: synthetic numbers and the other is shaped exactly like the env file that
#: holds a signing key on the host, and neither belongs in a repository.
FIXTURES = INFRA / "fixtures"
PROFILE_FIXTURE = FIXTURES / "nedu-flat-2025.csv"
ENV_FIXTURE = FIXTURES / "env.smoke"

#: The year the profile fixture carries, which is settings.AMPEER_PROFILE_YEAR.
#: 2025 is not a leap year, so a full series is 365 * 96 quarters.
FIXTURE_YEAR = 2025
FIXTURE_QUARTERS = 365 * 96

#: The series name the fixture publishes. advice.assembly never sets a profile
#: category, so every household reaching the engine is the E1A default, and
#: ampeer_sim.profiles.nedu asks for `<name>E1A_AZI_A` in the year row.
FIXTURE_SERIES = "SMOKE_E1A_AZI_A"


def _compose_document(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document


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


def test_the_override_does_not_start_the_tunnel() -> None:
    """A connector started from a developer machine registers a route to a
    tunnel that serves a real domain, which is a change to a host.

    Checked as "has a profile nobody enables" rather than as "is absent",
    because a compose override cannot remove a service: the only two honest
    outcomes are this one and a container that is up and doing nothing.
    """
    tunnel = _compose_document(OVERRIDE)["services"]["tunnel"]
    assert tunnel.get("profiles"), "the tunnel would start with the rest of the stack"


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


def test_the_production_file_still_publishes_nothing() -> None:
    """The reason the override exists is that the production file may not do
    this. Asserted here as well as in tests/test_infra.py, because the failure
    that matters is somebody moving a line from this file into that one.
    """
    text = COMPOSE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*ports\s*:", text, re.MULTILINE)
    assert "127.0.0.1" not in text


def test_the_override_says_it_must_never_reach_a_host() -> None:
    """The file is one page of YAML that would work perfectly on the LXC and
    would undo the network design if it ran there. Saying so is the only thing
    standing between it and a copy."""
    head = OVERRIDE.read_text(encoding="utf-8")[:400]
    assert "NEVER BE USED ON A HOST" in head


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


def test_the_deploy_pins_the_checksum_of_the_preflight_it_runs() -> None:
    """scripts/preflight_env.sh is copied to /srv/ampeer/ by hand and the
    deploy job has no checkout, so the copy it runs is whatever was left there.

    A change to this script therefore did nothing until somebody remembered to
    copy it again, and nothing anywhere reported the gap: the old copy still
    exits zero, so the deploy is green and the check it was meant to add is not
    running. That is the same shape as the purge nobody scheduled.

    The mechanism is a sha256 written into the workflow, compared on the host
    before the script is used. It can fail, which is the point: a stale copy
    stops the deploy with a message naming the file to re-copy. And it cannot
    rot, because this test recomputes the digest from the script and fails if
    the literal in the workflow no longer matches.

    This assertion belongs with the deploy tests and lives here instead because
    the workflow, the script and the tests that read them are three different
    lanes' files and this is the barrier's own change. It is duplication of
    location, not of rule.
    """
    digest = hashlib.sha256(PREFLIGHT.read_bytes()).hexdigest()
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert digest in workflow, (
        f"scripts/preflight_env.sh hashes to {digest}, which .github/workflows/deploy.yml "
        "does not name. Update the PREFLIGHT_SHA256 in the workflow and re-copy the script "
        "to /srv/ampeer/ on the host."
    )


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
        # Through nginx, Django sees the Host header nginx sets from $host,
        # which is the name without the port: 127.0.0.1.
        "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost",
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
        # Not a release. The local run builds both images from this tree and
        # tags them with this string, so nothing here can be confused with
        # something CI published.
        "AMPEER_VERSION=smoke",
        # Empty and present. compose interpolates it into the tunnel's command
        # whether or not the tunnel starts, and an absent name is a warning on
        # every command; an empty one is the truth, since there is no tunnel.
        "CLOUDFLARE_TUNNEL_TOKEN=",
    ]


def test_the_environment_fixture_names_every_variable_the_stack_reads() -> None:
    """The same coupling tests/test_infra.py asserts for .env.example, for the
    file the local checks actually run with.

    A missing name here does not fail loudly: compose substitutes an empty
    string, prints a warning among a hundred other lines, and the api container
    exits with a RuntimeError that reads like a code fault. That is the failure
    scripts/preflight_env.sh exists to prevent, and it would be embarrassing to
    meet it in the rehearsal for it.
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


def test_the_environment_fixture_holds_no_value_that_could_be_mistaken_for_real() -> None:
    """It is generated into a git-ignored directory, but it is one `cp` away
    from /srv/ampeer/.env, and a placeholder that looks like a key is a key
    somebody ships."""
    for line in env_fixture_lines("/tmp/profile.csv"):
        if line.startswith(("DJANGO_SECRET_KEY=", "POSTGRES_PASSWORD=")):
            assert "placeholder-not-a-secret" in line, line


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
    print(f"wrote {ENV_FIXTURE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
