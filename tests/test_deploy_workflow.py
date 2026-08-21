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
    values = dict.fromkeys(REQUIRED_ENV, "set")
    values["AMPEER_NEDU_PROFILE_PATH"] = profile.as_posix()
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
