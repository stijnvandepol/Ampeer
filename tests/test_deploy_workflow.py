"""The deploy workflow and its preflight, read as documents rather than run.

Nothing here starts a container, contacts GitHub or touches a host. Every
property below is one that would otherwise only be discovered on the LXC, and
two of them would be discovered by somebody else: the deploy job is the single
job in this repository allowed to run on the self-hosted runner, and the
preflight is the only thing standing between a missing variable and a container
in a restart loop.

The exception itself is the point. `tests/test_pipeline_contract.py` refuses any
job that selects the self-hosted runner, because the workflows trigger on push
to `feat/**` where no ruleset applies. That rule now has an exception, and an
exception that is not bounded is the gate being removed slowly, so the bound is
asserted here: exactly one workflow, exactly one job, and that job has to earn
it by triggering only on a tag and waiting for a review.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

# Reused rather than re-derived. `_workflows` is the same parse the pipeline
# contract reads, and SELF_HOSTED_EXCEPTIONS is the exception itself: importing
# it means the two files cannot drift into disagreeing about which job is
# exempt, which is the failure this whole file exists to prevent.
from test_pipeline_contract import SELF_HOSTED_EXCEPTIONS, _workflows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_WORKFLOW = "deploy.yml"
PREFLIGHT = REPO_ROOT / "scripts" / "preflight_env.sh"
ENV_EXAMPLE = REPO_ROOT / "infra" / ".env.example"
COMPOSE = REPO_ROOT / "infra" / "docker-compose.yml"

#: The two images this repository builds, as (output name, published name).
#: Read as a pair because the digest that leaves the build job and the tag the
#: host pulls have to name the same image; a check that compares one image
#: against the other's digest passes on every deploy and stops nothing.
BUILT_IMAGES = (
    ("api", "ghcr.io/stijnvandepol/ampeer-api"),
    ("web", "ghcr.io/stijnvandepol/ampeer-web"),
)

#: The nine names prod.py refuses to start without. Written out here rather
#: than imported from the preflight or from .env.example, for the reason
#: tests/test_infra.py gives about the same list: an imported list follows the
#: change it was supposed to catch, so a drifting script would still be green.
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


def _deploy() -> dict[str, Any]:
    workflows = _workflows()
    assert DEPLOY_WORKFLOW in workflows, f"no {DEPLOY_WORKFLOW}: {sorted(workflows)}"
    return workflows[DEPLOY_WORKFLOW]


def _job(name: str) -> dict[str, Any]:
    jobs = _deploy()["jobs"]
    assert name in jobs, f"no job {name!r} in {DEPLOY_WORKFLOW}: {sorted(jobs)}"
    job: dict[str, Any] = jobs[name]
    return job


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    """The `on:` block, fetched past a YAML trap that would make this vacuous.

    PyYAML resolves an unquoted `on` key to the boolean True, so
    `document["on"]` raises and `document.get("on", {})` returns an empty
    mapping. Every assertion below of the form "this workflow has no branch
    trigger" would then pass on a workflow that triggers on every branch there
    is. Both spellings are read, and the result is asserted non-empty.
    """
    block = document.get("on", document.get(True))
    assert block, f"the workflow declares no triggers at all: {sorted(document)}"
    assert isinstance(block, dict), f"triggers are not a mapping: {block!r}"
    return block


# --------------------------------------------------------------------------
# The trigger. A deploy that can be started from a branch is a deploy that runs
# unreviewed code, which is the thing the self-hosted rule exists to prevent.
# --------------------------------------------------------------------------


def test_the_deploy_triggers_on_a_tag_and_on_nothing_else() -> None:
    triggers = _triggers(_deploy())
    assert set(triggers) == {"push"}, f"extra triggers: {sorted(set(triggers) - {'push'})}"
    push = triggers["push"]
    assert set(push) == {"tags"}, f"the push trigger names more than tags: {sorted(push)}"
    assert push["tags"] == ["v*"], push["tags"]


def test_no_branch_can_start_a_deploy() -> None:
    """Stated separately from the shape above, because this is the property.

    `branches:` under push, a `pull_request:` block or a `workflow_dispatch:`
    each make the deploy reachable from a ref that no ruleset protects, and the
    job it starts runs inside the owner's network.
    """
    triggers = _triggers(_deploy())
    assert "branches" not in triggers.get("push", {})
    for reachable_from_a_branch in ("pull_request", "pull_request_target", "workflow_dispatch"):
        assert reachable_from_a_branch not in triggers, reachable_from_a_branch


# --------------------------------------------------------------------------
# The exception, and its bound.
# --------------------------------------------------------------------------


def test_the_self_hosted_exception_names_exactly_one_job() -> None:
    """The bound. Adding a second self-hosted job anywhere fails here.

    Not "at most one job in deploy.yml": exactly one entry in the whole
    exception list, so the next person who needs a self-hosted job has to
    delete this assertion in the same diff, which is a thing a reviewer sees.
    """
    assert len(SELF_HOSTED_EXCEPTIONS) == 1, sorted(SELF_HOSTED_EXCEPTIONS)
    assert SELF_HOSTED_EXCEPTIONS == frozenset({(DEPLOY_WORKFLOW, "deploy")}), sorted(
        SELF_HOSTED_EXCEPTIONS
    )


def test_every_exempt_job_earns_its_exemption() -> None:
    """Read from the exception list, so a second entry has to pass this too.

    A job is only allowed inside the network if nothing that runs there can be
    chosen by whoever pushed: the workflow triggers on a tag alone, and the job
    waits for the review that `environment: production` requires.
    """
    for workflow, job_name in SELF_HOSTED_EXCEPTIONS:
        document = _workflows()[workflow]
        triggers = _triggers(document)
        assert set(triggers) == {"push"} and set(triggers["push"]) == {"tags"}, (
            f"{workflow} is reachable from something other than a tag: {sorted(triggers)}"
        )
        job = document["jobs"][job_name]
        assert job.get("environment") == "production", (
            f"{workflow}:{job_name} runs on the self-hosted runner without a review gate"
        )


def test_the_build_job_runs_on_a_github_hosted_runner() -> None:
    assert _job("build")["runs-on"] == "ubuntu-latest"


def test_the_deploy_job_is_the_only_one_that_says_self_hosted() -> None:
    selectors = {
        name: job.get("runs-on")
        for name, job in _deploy()["jobs"].items()
        if "self-hosted" in str(job.get("runs-on", ""))
    }
    assert set(selectors) == {"deploy"}, selectors


def test_the_deploy_job_waits_for_a_review() -> None:
    """`environment: production` is what turns a tag push into a request.

    The deployment branch policy and the reviewer list are configured on the
    environment itself and are not in this repository, so this asserts the hook
    exists rather than what is attached to it.
    """
    assert _job("deploy")["environment"] == "production"


def test_the_deploy_job_needs_the_build_job() -> None:
    """Without it the deploy pulls whatever the tag pointed at last time,
    which on a failed build is the previous release under a new name."""
    assert _job("deploy")["needs"] == "build" or "build" in _job("deploy")["needs"]


# --------------------------------------------------------------------------
# What the runner may do. The less it may do, the less it matters that it
# exists.
# --------------------------------------------------------------------------


def _steps(job: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = _job(job).get("steps", [])
    return steps


def _step_text(job: str) -> str:
    return "\n".join(
        f"{step.get('uses', '')}\n{step.get('run', '')}" for step in _steps(job)
    ).lower()


def test_the_deploy_job_checks_nothing_out() -> None:
    """No source on the host, so no build chain and no token that can read the
    repository. The compose file and this preflight are placed on the host by
    hand, which is written down in both of them."""
    assert "checkout" not in _step_text("deploy")


def test_the_deploy_job_builds_no_image() -> None:
    """The LXC pulls what CI built. A `docker build` here would mean the thing
    that runs was assembled on the host from inputs nothing verified."""
    text = _step_text("deploy")
    assert "docker build" not in text
    assert "docker compose build" not in text
    assert "build-push-action" not in text


def test_the_build_job_asks_for_exactly_two_permissions() -> None:
    """It reads the repository and writes a package. Anything else it is
    granted is something a compromised build step inherits."""
    assert _job("build")["permissions"] == {"contents": "read", "packages": "write"}


def test_the_deploy_job_cannot_read_the_repository() -> None:
    """It pulls two private images, so it needs `packages: read` and nothing
    else. Declaring any permission at all sets every unnamed one to none."""
    assert _job("deploy")["permissions"] == {"packages": "read"}


def test_the_deploy_job_does_not_leave_a_registry_credential_behind() -> None:
    """web2 is not ephemeral, measured on 2026-08-21, so its home directory
    survives the job. `docker login` writes the token to ~/.docker/config.json
    and leaves it there for whatever runs next."""
    text = _step_text("deploy")
    assert "docker logout" in text, "the deploy logs in and never logs out"
    logouts = [step for step in _steps("deploy") if "docker logout" in str(step.get("run", ""))]
    assert any(step.get("if") == "always()" for step in logouts), (
        "the logout is skipped on the failing deploys, which are the ones that leave a mess"
    )


def test_the_preflight_runs_before_anything_restarts() -> None:
    """Order, not presence. A preflight after `up -d` reports a problem the
    restart loop has already caused."""
    runs = [str(step.get("run", "")) for step in _steps("deploy")]
    preflight = next((i for i, run in enumerate(runs) if "preflight_env.sh" in run), None)
    assert preflight is not None, f"the deploy job never runs the preflight: {runs}"
    for index, run in enumerate(runs):
        if "compose" in run and ("up" in run or "pull" in run):
            assert index > preflight, f"step {index} touches the stack before the preflight: {run}"


def test_two_deploys_cannot_run_at_once() -> None:
    """Both would run `migrate` against one database. Concurrency here is not
    a speed setting."""
    concurrency = _deploy().get("concurrency")
    assert concurrency, "the deploy workflow declares no concurrency group"
    assert concurrency.get("cancel-in-progress") is False, (
        "cancelling a running deploy can leave it half migrated"
    )


def test_the_workflow_pins_a_tag_to_the_images_it_publishes() -> None:
    """The compose file pulls `ampeer-api:${AMPEER_VERSION}` and
    `ampeer-web:${AMPEER_VERSION}`. If the build publishes under another name,
    the deploy succeeds and pulls the previous release."""
    text = (REPO_ROOT / ".github" / "workflows" / DEPLOY_WORKFLOW).read_text(encoding="utf-8")
    for image in ("ghcr.io/stijnvandepol/ampeer-api", "ghcr.io/stijnvandepol/ampeer-web"):
        assert image in text, f"the build job never publishes {image}"
    assert "AMPEER_VERSION" in text, "nothing tells compose which release to pull"


# --------------------------------------------------------------------------
# The approval window.
#
# `environment: production` puts a review between the build and the pull, and
# that review can take hours. The compose file pulls a tag, and a tag is a name
# whoever holds `packages: write` on this repository can repoint while the
# review is open: the reviewer approves the run they read, and the host pulls
# whatever the tag says at pull time, which is a different thing.
#
# The tag stays. It is what lets the host bring itself back up after a reboot
# with no CI involved, and what makes a rollback one string in a file a person
# can read. What closes the window is checking afterwards: the build job says
# which digest it pushed, and the deploy asserts that is what arrived.
# --------------------------------------------------------------------------


def _deploy_run_lines() -> list[str]:
    return [str(step.get("run", "")) for step in _steps("deploy")]


def _only_deploy_step(predicate: Any, what: str) -> int:
    matches = [index for index, run in enumerate(_deploy_run_lines()) if predicate(run)]
    assert len(matches) == 1, f"expected exactly one deploy step that {what}, found {matches}"
    return matches[0]


@pytest.mark.parametrize(("name", "published"), BUILT_IMAGES)
def test_the_build_job_publishes_the_digest_it_pushed(name: str, published: str) -> None:
    """The digest is only knowable in the job that pushed it.

    docker/build-push-action reports it as a step output, and a step output
    dies with its job unless the job declares it as one of its own. Without
    that there is nothing for the deploy to compare against, and the tag stays
    the only name anywhere in the pipeline.
    """
    outputs = _job("build").get("outputs") or {}
    key = f"{name}-digest"
    assert key in outputs, f"the build job publishes no {key}: {sorted(outputs)}"
    reference = str(outputs[key])
    match = re.search(r"steps\.([A-Za-z0-9_-]+)\.outputs\.digest", reference)
    assert match, f"{key} is not a step digest output: {reference!r}"
    step = next((s for s in _steps("build") if s.get("id") == match.group(1)), None)
    assert step is not None, f"{key} names step {match.group(1)!r}, which does not exist"
    assert "build-push-action" in str(step.get("uses", "")), step
    assert published in str(step.get("with", {}).get("tags", "")), (
        f"{key} carries the digest of a step that does not push {published}"
    )


def test_the_deploy_checks_what_it_pulled_against_what_the_build_pushed() -> None:
    """Both images, because verifying one of the two leaves the other
    repointable, and `web` is the one that serves the pages."""
    index = _only_deploy_step(lambda run: "RepoDigests" in run, "inspects a pulled image digest")
    step = _steps("deploy")[index]
    environment = " ".join(str(value) for value in (step.get("env") or {}).values())
    for name, _published in BUILT_IMAGES:
        assert f"needs.build.outputs.{name}-digest" in environment, (
            f"the digest check never reads the build job's {name}-digest output: {environment!r}"
        )


def test_the_digest_check_sits_between_the_pull_and_the_start() -> None:
    """Order is the property. Before the pull there is nothing to inspect, and
    after `up` the container the check would have rejected is already serving."""
    pull = _only_deploy_step(lambda run: "compose" in run and " pull" in run, "pulls")
    start = _only_deploy_step(lambda run: "compose" in run and "up -d" in run, "starts the stack")
    check = _only_deploy_step(lambda run: "RepoDigests" in run, "inspects a pulled image digest")
    assert pull < check < start, f"pull at {pull}, check at {check}, up at {start}"


def test_the_workflow_says_what_provenance_true_does_and_does_not_buy() -> None:
    """`provenance: true` was on both build steps from the first version and
    nothing anywhere reads the attestation it produces. An unverified
    attestation is a claim; a claim that reads as a control is worse than no
    control at all, so the file has to say which of the two this one is."""
    text = (REPO_ROOT / ".github" / "workflows" / DEPLOY_WORKFLOW).read_text(encoding="utf-8")
    assert "provenance: true" in text
    comments = "\n".join(line for line in text.splitlines() if line.lstrip().startswith("#"))
    assert "provenance" in comments, (
        "provenance: true is set and no comment says whether anything verifies it"
    )


# --------------------------------------------------------------------------
# The compose file on the host, which nothing has ever read.
# --------------------------------------------------------------------------


def test_the_deploy_pins_the_checksum_of_the_compose_file_it_runs() -> None:
    """The same hole the preflight had, in the file that decides what runs.

    /srv/ampeer/docker-compose.yml is placed by hand and the deploy job has no
    checkout, so every test in this repository reads a copy that is not the one
    the host uses. Measured on 2026-08-21: adding
    `- /var/run/docker.sock:/var/run/docker.sock` to the api service on the
    host leaves the whole suite green, and it is permanent.

    This recomputes the digest from the repository, so the literal in the
    workflow cannot drift from infra/docker-compose.yml. It can only disagree
    with the host, which is the disagreement worth stopping a deploy for.
    """
    digest = hashlib.sha256(COMPOSE.read_bytes()).hexdigest()
    text = (REPO_ROOT / ".github" / "workflows" / DEPLOY_WORKFLOW).read_text(encoding="utf-8")
    assert digest in text, (
        f"infra/docker-compose.yml hashes to {digest}, which .github/workflows/deploy.yml "
        "does not name. Update COMPOSE_SHA256 in the workflow and re-copy the file to "
        "/srv/ampeer/ on the host."
    )


def test_the_compose_file_is_checked_before_anything_uses_it() -> None:
    """A checksum verified after `up` describes a file that has already started
    containers."""
    check = _only_deploy_step(
        lambda run: "sha256sum" in run and "docker-compose.yml" in run,
        "hashes the compose file",
    )
    for index, run in enumerate(_deploy_run_lines()):
        if "compose" in run and ("up -d" in run or " pull" in run or "run --rm" in run):
            assert index > check, f"step {index} uses the compose file before it is checked: {run}"


# --------------------------------------------------------------------------
# The one edge in the concurrency group, which cannot be closed here.
# --------------------------------------------------------------------------


def _comment_block_above(marker: str) -> str:
    text = (REPO_ROOT / ".github" / "workflows" / DEPLOY_WORKFLOW).read_text(encoding="utf-8")
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    block: list[str] = []
    while index > 0 and lines[index - 1].lstrip().startswith("#"):
        index -= 1
        block.append(lines[index])
    return "\n".join(reversed(block)).lower()


def test_the_concurrency_group_writes_down_the_run_it_silently_cancels() -> None:
    """GitHub keeps at most one pending run per concurrency group.

    Pushing v3 while v2 waits on the environment review cancels v2, with no
    deploy and no failure anywhere: the tag exists, the images are in GHCR, and
    nothing put them on the host. No workflow file can prevent it, because the
    run that would report it is the run being cancelled, so the control here is
    a sentence rather than a step and this keeps the sentence in place.
    """
    block = _comment_block_above("concurrency:")
    assert "pending" in block, "the concurrency comment does not mention the pending run"
    assert "cancel" in block, "the concurrency comment does not say what gets cancelled"


# --------------------------------------------------------------------------
# The preflight itself, driven as a program.
#
# Every case below is an outage that would otherwise present as a code fault: a
# container restarting every five seconds with a Django traceback about a
# setting, on a host nobody is logged in to.
# --------------------------------------------------------------------------


def _write_env(path: Path, values: dict[str, str], *, newline: str = "\n") -> Path:
    """newline is explicit because the default on this platform is not LF.

    The file on the host is an LF file, and a CRLF one is its own failure with
    its own test below, so writing it either way has to be deliberate: an
    accidental CRLF fixture would make every case here exercise the wrong path.
    """
    env_file = path / "ampeer.env"
    body = (
        "# a comment, and a blank line, both of which are legal\n\n"
        + "\n".join(f"{name}={value}" for name, value in values.items())
        + "\n"
    )
    env_file.write_text(body.replace("\n", newline), encoding="utf-8", newline="")
    return env_file


def _complete(profile: Path) -> dict[str, str]:
    """A file the preflight has no complaint about, as the baseline every case
    below breaks in exactly one way.

    Two names cannot take the filler. AMPEER_NEDU_PROFILE_PATH has to be a
    readable path, and DJANGO_NUM_PROXIES has to be a whole number, because
    prod.py parses that one rather than reading it. Giving them real values
    here is what keeps each case testing the thing it names instead of failing
    on the fixture.
    """
    values = dict.fromkeys(REQUIRED_ENV, "set")
    values["AMPEER_NEDU_PROFILE_PATH"] = profile.as_posix()
    values["DJANGO_NUM_PROXIES"] = "2"
    return values


def _profile(path: Path) -> Path:
    profile = path / "nedu-profiles-2025.csv"
    profile.write_text("stub\n", encoding="utf-8")
    return profile


def _preflight(env_file: Path) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash, "these tests drive a shell script and need bash on PATH"
    return subprocess.run(
        [bash, PREFLIGHT.as_posix(), env_file.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )


class TestThePreflight:
    def test_it_is_quiet_and_exits_zero_when_all_nine_are_set(self, tmp_path: Path) -> None:
        result = _preflight(_write_env(tmp_path, _complete(_profile(tmp_path))))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_names_every_missing_variable_and_not_only_the_first(self, tmp_path: Path) -> None:
        """The reason this is a script and not a `set -u`.

        Fixing one name, redeploying, and being told about the next one is four
        deploys and four restart loops for one mistake.
        """
        values = _complete(_profile(tmp_path))
        del values["DJANGO_SECRET_KEY"]
        del values["POSTGRES_USER"]
        del values["DJANGO_NUM_PROXIES"]
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0
        output = result.stdout + result.stderr
        for name in ("DJANGO_SECRET_KEY", "POSTGRES_USER", "DJANGO_NUM_PROXIES"):
            assert name in output, output

    @pytest.mark.parametrize("name", REQUIRED_ENV)
    def test_it_catches_each_of_the_nine_on_its_own(self, tmp_path: Path, name: str) -> None:
        """One case per variable, so a name dropped from the script's list
        names itself instead of hiding in a list that is still nine long."""
        values = _complete(_profile(tmp_path))
        del values[name]
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"{name} may be missing without the deploy stopping"
        assert name in result.stdout + result.stderr

    def test_an_empty_value_counts_as_missing(self, tmp_path: Path) -> None:
        """`POSTGRES_PASSWORD=` is what a half-filled copy of .env.example
        looks like, and it is the shape the checklist ships in."""
        values = _complete(_profile(tmp_path))
        values["POSTGRES_PASSWORD"] = ""
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0
        assert "POSTGRES_PASSWORD" in result.stdout + result.stderr

    @pytest.mark.parametrize("name", REQUIRED_ENV)
    def test_a_whitespace_only_value_counts_as_missing(self, tmp_path: Path, name: str) -> None:
        """Measured on 2026-08-21: `DJANGO_SECRET_KEY="   "` printed
        "9 variables set" and exited zero.

        Nothing downstream saves it. prod.py tests `if not value`, and three
        spaces are truthy, so the process starts: the signing key is three
        spaces, `DJANGO_ALLOWED_HOSTS` becomes `["   "]` and every request is
        answered with 400 DisallowedHost. That is not a restart loop, it is
        worse, because the container reports itself as up. It is what a half
        filled .env looks like when somebody lines the values up in a column.
        """
        values = _complete(_profile(tmp_path))
        values[name] = "   "
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"{name} may be whitespace without the deploy stopping"
        assert name in result.stdout + result.stderr

    @pytest.mark.parametrize("value", ["two", "2.5", "-1", " 2", "2 ", "1,2", "one"])
    def test_it_refuses_a_proxy_count_that_is_not_a_whole_number(
        self, tmp_path: Path, value: str
    ) -> None:
        """The one variable prod.py parses rather than reads.

        `_required_count` refuses anything `str.isdigit()` refuses, and that is
        a RuntimeError at import time, which is a container that exits and is
        restarted and exits again. Measured on 2026-08-21:
        `DJANGO_NUM_PROXIES=two` passed this preflight and produced exactly
        that loop, which is the outage the preflight exists to stop.
        """
        values = _complete(_profile(tmp_path))
        values["DJANGO_NUM_PROXIES"] = value
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"DJANGO_NUM_PROXIES={value!r} passed the preflight"
        assert "DJANGO_NUM_PROXIES" in result.stdout + result.stderr

    @pytest.mark.parametrize("value", ["0", "1", "2", "10"])
    def test_it_accepts_a_whole_number_of_proxies_including_zero(
        self, tmp_path: Path, value: str
    ) -> None:
        """Zero is a legal count and prod.py accepts it. A check that treated
        the count as a flag would refuse the only value that means "no proxy in
        front of this", which is how the stack is run locally."""
        values = _complete(_profile(tmp_path))
        values["DJANGO_NUM_PROXIES"] = value
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_never_prints_a_rejected_value_either(self, tmp_path: Path) -> None:
        """The proxy count is not a secret, but the message that reports it is
        written next to eight values that are, and a preflight that echoes what
        it read once will echo it again. Same rule, stated where the new check
        could have broken it."""
        values = _complete(_profile(tmp_path))
        values["DJANGO_NUM_PROXIES"] = "hunter2-would-be-in-the-log"
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0
        assert "hunter2" not in result.stdout + result.stderr

    def test_it_stops_on_an_env_file_with_windows_line_endings(self, tmp_path: Path) -> None:
        """Found by this suite on 2026-08-21, on the first run.

        The carriage return is the last character of every value and nothing
        strips it. POSTGRES_PASSWORD then does not match the one the database
        was created with and DJANGO_ALLOWED_HOSTS does not match the host
        header, while every emptiness check passes, because a lone carriage
        return is not empty. The file is written on a Windows machine and the
        stack runs on Linux, so this is the ordinary case rather than an exotic
        one, and it presents as an authentication failure nobody can explain.
        """
        result = _preflight(_write_env(tmp_path, _complete(_profile(tmp_path)), newline="\r\n"))
        assert result.returncode != 0, result.stdout + result.stderr
        assert "line endings" in result.stdout + result.stderr

    def test_it_stops_when_the_env_file_is_not_there(self, tmp_path: Path) -> None:
        result = _preflight(tmp_path / "nothing-here.env")
        assert result.returncode != 0
        assert "nothing-here.env" in result.stdout + result.stderr

    def test_it_reads_the_host_side_of_the_profile_mount(self, tmp_path: Path) -> None:
        """AMPEER_NEDU_PROFILE_PATH carries two meanings on purpose: the host
        path is the bind mount source, and the value the API reads is fixed to
        /srv/profiles/nedu.csv by the compose file. The host side is the one
        that can be wrong, and a wrong one mounts an empty directory over the
        file, so the API starts, reports its path set, and answers nothing.
        """
        values = _complete(_profile(tmp_path))
        values["AMPEER_NEDU_PROFILE_PATH"] = (tmp_path / "typo.csv").as_posix()
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0
        assert "typo.csv" in result.stdout + result.stderr

    def test_it_refuses_a_bare_name_compose_would_turn_into_a_volume(self, tmp_path: Path) -> None:
        """A source with no slash in it is not a path to compose, it is the
        name of a volume it will create empty and mount over the file."""
        values = _complete(_profile(tmp_path))
        values["AMPEER_NEDU_PROFILE_PATH"] = "nedu.csv"
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0
        assert "nedu.csv" in result.stdout + result.stderr

    def test_it_never_prints_a_value(self, tmp_path: Path) -> None:
        """Its output goes to a workflow log that GitHub keeps for ninety days
        and that anyone with read access to the repository can open. Only the
        secrets GitHub knows about are masked there, and none of these are."""
        values = _complete(_profile(tmp_path))
        values["DJANGO_SECRET_KEY"] = "hunter2-would-be-in-the-log"
        del values["POSTGRES_HOST"]
        result = _preflight(_write_env(tmp_path, values))
        assert "hunter2" not in result.stdout + result.stderr

    def test_it_does_not_execute_the_file_it_reads(self, tmp_path: Path) -> None:
        """`source` on an env file runs it. The file holds a secret key and a
        tunnel token, so whoever can write it can already do damage, but a
        parser that executes turns a stray backtick in a password into a
        command and turns a typo into an incident."""
        marker = tmp_path / "executed"
        values = _complete(_profile(tmp_path))
        values["DJANGO_ALLOWED_HOSTS"] = f'$(touch "{marker.as_posix()}")'
        _preflight(_write_env(tmp_path, values))
        assert not marker.exists(), "the preflight sourced the env file"


def test_the_preflight_and_the_checklist_name_the_same_variables() -> None:
    """The interface between this lane and the compose file.

    infra/.env.example is what a person fills in. A name the preflight requires
    and the example never mentions is a deploy that fails on a variable nobody
    was told about.
    """
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    script = PREFLIGHT.read_text(encoding="utf-8")
    for name in REQUIRED_ENV:
        assert re.search(rf"^{name}=", example, re.MULTILINE), f"{name} is not in .env.example"
        assert name in script, f"{name} is not checked by the preflight"


def test_the_preflight_says_it_is_installed_by_hand() -> None:
    """Nothing in this repository puts it on the host, and the deploy job runs
    the copy that is already there. A file that looks automatic and is not is
    worse than one that says so."""
    header = PREFLIGHT.read_text(encoding="utf-8")[:2000]
    assert "/srv/ampeer" in header
    assert "by hand" in header
