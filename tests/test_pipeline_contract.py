"""The delivery pipeline's own invariants, as tests rather than comments.

Every rule checked here was previously written down in a comment somewhere and
enforced by nothing. A comment does not fail a build. These run inside the
`test` job, so the pipeline defends its own shape on every pull request.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
RULESET_SCRIPT = REPO_ROOT / "scripts" / "setup_rulesets.sh"
PYPROJECT = REPO_ROOT / "pyproject.toml"
PRE_COMMIT = REPO_ROOT / ".pre-commit-config.yaml"
UV_LOCK = REPO_ROOT / "uv.lock"
NVMRC = REPO_ROOT / "frontend" / ".nvmrc"
FRONTEND_PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"
#: The second place an image enters this project. Workflow service containers
#: were the first, and until 2026-08-21 they were the only place anything read.
INFRA_COMPOSE = REPO_ROOT / "infra" / "docker-compose.yml"

#: The two services in infra/docker-compose.yml built from Dockerfiles in this
#: repository. They carry the release tag the deploy rewrites, so no digest can
#: be written down for them; every other image there is pulled from a registry.
#: Named rather than derived from the `build:` key, so adding a build stanza to
#: a fifth service does not quietly buy it an exemption here as well.
INFRA_IMAGES_BUILT_HERE = ("api", "web")

#: The GitHub Actions app. Binding a required check to it means a check can only
#: be satisfied by a workflow run, not by any commit status with the right name.
GITHUB_ACTIONS_APP_ID = 15368

#: The floor may be raised, never lowered. See CLAUDE.md. Tracks the measured
#: floor in pyproject.toml's fail_under; move it only when a re-measurement
#: raises fail_under, never to make room for a lower one.
MINIMUM_COVERAGE_FLOOR = 98.82


def _workflows() -> dict[str, dict[str, Any]]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOW_DIR.glob("*.yml"))
    }


def _jobs() -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for document in _workflows().values():
        jobs.update(document.get("jobs", {}))
    return jobs


def _ruleset_payloads() -> list[dict[str, Any]]:
    blocks = re.findall(
        r"<<'JSON'\n(.*?)\nJSON", RULESET_SCRIPT.read_text(encoding="utf-8"), re.DOTALL
    )
    return [json.loads(block) for block in blocks]


def _required_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        check
        for rule in payload["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    ]


def _pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_every_required_check_is_published_by_a_workflow() -> None:
    """The failure this whole gate exists for.

    A ruleset requiring a check that no workflow publishes errors nowhere. It
    produces a pull request that waits forever with no message explaining why.
    """
    published = set(_jobs())
    for payload in _ruleset_payloads():
        required = {check["context"] for check in _required_checks(payload)}
        missing = required - published
        assert not missing, f"{payload['name']} requires unpublished checks: {sorted(missing)}"


def test_every_required_check_is_bound_to_github_actions() -> None:
    """Without integration_id, any commit status with the right name satisfies it.

    A required check that a plain status API call can green out is not a gate.
    """
    for payload in _ruleset_payloads():
        for check in _required_checks(payload):
            assert check.get("integration_id") == GITHUB_ACTIONS_APP_ID, (
                f"{payload['name']} check {check['context']!r} is not bound to GitHub Actions"
            )


def test_main_has_no_bypass_actors() -> None:
    """A rule with an exception for the only person on the project is not a rule."""
    main = next(p for p in _ruleset_payloads() if p["name"] == "protect-main")
    assert main["bypass_actors"] == []


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    """A tag can be moved by whoever owns the action. A SHA cannot."""
    unpinned = [
        f"{name}: {line.strip()}"
        for name, path in ((p.name, p) for p in sorted(WORKFLOW_DIR.glob("*.yml")))
        for line in path.read_text(encoding="utf-8").splitlines()
        if "uses:" in line and not re.search(r"@[0-9a-f]{40}", line)
    ]
    assert not unpinned, f"unpinned actions: {unpinned}"


#: A `uses:` line, taken apart: the action, the SHA it is pinned to, and the
#: version the comment claims that SHA is.
#:
#: The comment is optional in this pattern on purpose. A line that has no
#: comment has to be reported by name rather than silently skipped, and a
#: pattern that required one would simply not match it.
_USES = re.compile(r"uses:\s*([^@\s]+)@([0-9a-f]{40})\s*(?:#\s*(\S+))?")


def _pinned_actions() -> list[tuple[str, str, str, str | None]]:
    """Every action the workflows use, as (where, action, sha, version)."""
    found: list[tuple[str, str, str, str | None]] = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "uses:" not in line:
                continue
            match = _USES.search(line)
            if match is None:
                continue  # the test above is what reports a line with no SHA
            action, sha, version = match.groups()
            found.append((f"{path.name}:{number}", action, sha, version))
    return found


def test_every_pinned_action_says_which_version_its_sha_is() -> None:
    """The other half of the rule, and the half that makes the first readable.

    CLAUDE.md asks for a commit SHA "met de versie als comment erachter". The
    test above enforces the SHA. Nothing enforced the comment, and without it
    the pin is forty characters that no reviewer can place: there is no way to
    tell whether 3d3c42e5 is checkout v7 or checkout v2, so a bump cannot be
    reviewed and a downgrade looks the same as an upgrade.
    """
    naked = [
        f"{where}: {action}@{sha[:8]}"
        for where, action, sha, version in _pinned_actions()
        if version is None
    ]
    assert not naked, (
        "these actions are pinned to a SHA with no version beside it:\n  "
        + "\n  ".join(naked)
        + "\nAdd the tag it points at as a trailing comment, which is what makes "
        "the next bump reviewable."
    )


def test_one_sha_never_carries_two_version_numbers() -> None:
    """A stale comment is worse than a missing one, and this is how it happens.

    Bumping an action means changing two things on one line. Change the SHA and
    leave the comment and the line now states a version it is not, confidently,
    in a file nobody rereads. The same SHA appears in several workflows here, so
    updating four of five occurrences leaves the fifth contradicting the rest,
    and that contradiction is decidable without asking GitHub anything.

    What cannot be decided here is whether the comment is right about the SHA at
    all. That needs the tag list from the API, and this project does not reach
    outward from a test.
    """
    versions: dict[str, set[str]] = {}
    where: dict[str, list[str]] = {}
    for place, action, sha, version in _pinned_actions():
        if version is None:
            continue
        versions.setdefault(sha, set()).add(version)
        where.setdefault(sha, []).append(f"{place} {action} {version}")
    disagreeing = {sha: sorted(seen) for sha, seen in versions.items() if len(seen) > 1}
    assert not disagreeing, "one commit is described as two versions:\n  " + "\n  ".join(
        f"{sha[:8]} is called {sorted(versions[sha])}: {where[sha]}" for sha in disagreeing
    )


def test_one_version_of_an_action_never_carries_two_shas() -> None:
    """The same contradiction from the other side.

    Half-finishing a bump leaves the old SHA under the new version number
    somewhere, which reads as though two commits are both v7.0.1. It is the
    likelier direction, because the comment is the part a person edits by hand.
    """
    shas: dict[tuple[str, str], set[str]] = {}
    for _, action, sha, version in _pinned_actions():
        if version is None:
            continue
        shas.setdefault((action, version), set()).add(sha)
    split = {key: sorted(seen) for key, seen in shas.items() if len(seen) > 1}
    assert not split, "one version is pinned to two different commits:\n  " + "\n  ".join(
        f"{action}@{version} is pinned to {[sha[:8] for sha in seen]}"
        for (action, version), seen in split.items()
    )


def test_the_action_scan_reads_the_workflows() -> None:
    """The floor under the three above, all of which are statements about a set.

    A pattern that stopped matching, a workflow directory that moved, or a
    `uses:` written in another shape would leave every one of them green over an
    empty list. Measured on 2026-08-22: 23 uses lines across three workflows,
    naming 7 distinct actions.
    """
    pinned = _pinned_actions()
    assert len(pinned) >= 20, f"only {len(pinned)} pinned actions found under {WORKFLOW_DIR}"
    actions = {action for _, action, _, _ in pinned}
    assert len(actions) >= 6, f"only these actions were parsed: {sorted(actions)}"
    assert "actions/checkout" in actions, (
        "no workflow checks out the repository, which would be a larger change than "
        "anything this test is written for"
    )


#: The one job allowed on the self-hosted runner, as (workflow file, job name).
#:
#: Added 2026-08-21 with the deploy. The rule below is why no unreviewed code
#: has ever run inside the owner's own network, and an exception that is not
#: bounded is that gate being removed slowly, so the bound is written into the
#: shape of this constant: a workflow and a job, not a runner label and not a
#: workflow. `tests/test_deploy_workflow.py` asserts this list is exactly one
#: entry long, and asserts of every entry in it that the workflow triggers on a
#: tag alone and the job carries `environment: production`. A second entry
#: therefore has to pass both, and still fails the count, which is a deletion a
#: reviewer sees rather than a list that grew.
#:
#: Keyed by workflow as well as job because `_jobs()` merges every workflow into
#: one mapping: a bare name would hand the same exemption to a job called
#: `deploy` added to ci.yml, which triggers on push to feat/**.
SELF_HOSTED_EXCEPTIONS = frozenset({("deploy.yml", "deploy")})


def test_no_job_runs_on_the_self_hosted_runner() -> None:
    """A self-hosted runner is registered on this repository.

    ci.yml triggers on push to feat/**, which no ruleset protects, so a job
    there that selected self-hosted would run unreviewed code inside the owner's
    own network. security.yml is narrower and its earliest trigger is a pull
    request; this refusal covers every workflow anyway, and
    test_only_ci_triggers_on_a_feature_branch_push keeps that sentence true. Nothing here may target it except the one job named in
    SELF_HOSTED_EXCEPTIONS above, which is reachable only by pushing a tag and
    only through a review.

    The runner being non-ephemeral, measured on 2026-08-21, is a separate and
    still open decision that belongs to the owner; it is why the exempt job is
    also held to checking nothing out, building nothing, and logging out of the
    registry when it finishes.
    """
    offenders = {
        f"{workflow}:{name}": job.get("runs-on")
        for workflow, document in _workflows().items()
        for name, job in document.get("jobs", {}).items()
        if "self-hosted" in str(job.get("runs-on", ""))
        and (workflow, name) not in SELF_HOSTED_EXCEPTIONS
    }
    assert not offenders, f"jobs targeting the self-hosted runner: {offenders}"


#: What the comment in scripts/setup_rulesets.sh has to keep saying, and why
#: each fragment is in the list.
#:
#: The gap it describes cannot be closed from this repository, and the test
#: directly above cannot close it either: ci.yml triggers on `push` to feat/**,
#: setup_rulesets.sh protects only main and dev, so a commit adding a workflow
#: with `runs-on: self-hosted` executes on web2 at push time and
#: test_no_job_runs_on_the_self_hosted_runner goes red minutes later, on a job
#: that has already run. No required status check can help, because the
#: workflow starts before any check does. Measured on 2026-08-21: the runner's
#: user is in the docker group, so `docker run -v /:/host` in such a job reads
#: /etc/shadow, and one push is root on the LXC.
#:
#: The two controls that would work are settings and host configuration rather
#: than files here, which is exactly why they need writing down somewhere a
#: person configuring this repository will read: a control nobody is told about
#: is a control nobody applies.
RUNNER_GAP_NOTES = (
    "feat/**",
    "self-hosted",
    "runner group",
    "docker group",
    "sudoers",
    "detect",
    "neither is in this repository",
    "test_no_job_runs_on_the_self_hosted_runner",
)


@pytest.mark.parametrize("fragment", RUNNER_GAP_NOTES)
def test_the_ruleset_script_writes_down_the_gap_no_ruleset_can_cover(fragment: str) -> None:
    """The one finding in this round that is not fixable in code.

    It is written into setup_rulesets.sh rather than into a doc, because that
    script is what somebody runs when they are configuring the protections for
    this repository, which is the moment the two missing controls are relevant
    and the only moment anyone is thinking about them.

    One case per fragment, so deleting a sentence names the sentence rather
    than failing on a paragraph that is still mostly there.
    """
    body = RULESET_SCRIPT.read_text(encoding="utf-8")
    comments = "\n".join(line for line in body.splitlines() if line.lstrip().startswith("#"))
    assert fragment in comments.lower(), (
        f"scripts/setup_rulesets.sh no longer says {fragment!r}; the self-hosted runner gap "
        "is documented nowhere else and no test can prevent it"
    )


def test_every_job_has_a_timeout() -> None:
    """Without one, a hung job holds a runner for six hours."""
    missing = [name for name, job in _jobs().items() if "timeout-minutes" not in job]
    assert not missing, f"jobs without timeout-minutes: {missing}"


def test_every_checkout_refuses_to_persist_credentials() -> None:
    """actions/checkout leaves the token in .git/config unless told not to.

    No job here pushes, so no job here needs it, and the `secrets` job in
    particular runs a third party binary across the full history.
    """
    offenders = [
        f"{workflow}:{job_name}"
        for workflow, document in _workflows().items()
        for job_name, job in document.get("jobs", {}).items()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and step.get("with", {}).get("persist-credentials") is not False
    ]
    assert not offenders, f"checkouts that keep the token: {offenders}"


def test_the_coverage_floor_is_not_lowered() -> None:
    report = _pyproject()["tool"]["coverage"]["report"]
    assert report["fail_under"] >= MINIMUM_COVERAGE_FLOOR


def test_the_coverage_comparison_is_not_rounded_away() -> None:
    """precision = 2 is load bearing.

    pytest-cov decides its exit code with round(total, precision) < fail_under.
    At the default precision of 0 a real 96.86 rounds to 97 and clears a floor
    of 97, so the check exits green while printing FAIL in its own log.
    """
    assert _pyproject()["tool"]["coverage"]["report"]["precision"] >= 2


def test_every_package_is_measured_for_coverage() -> None:
    """A new package must not be exempt from the gates while they stay green.

    Both levels are checked. The first version of this globbed only the
    repository root, which would have let every Django app under backend/ in
    without being measured.
    """
    roots = {
        path.parent.name
        for path in REPO_ROOT.glob("*/__init__.py")
        if not path.parent.name.startswith(".")
    }
    measured = set(_pyproject()["tool"]["coverage"]["run"]["source"])
    assert roots <= measured, f"packages outside coverage: {sorted(roots - measured)}"

    backend = REPO_ROOT / "backend"
    if backend.is_dir():
        assert "backend" in measured, "backend/ exists but is not measured for coverage"
        apps = {path.parent.name for path in backend.glob("*/__init__.py")}
        assert apps, "backend/ holds no python package; check this test still applies"


#: Every gate that reads source, and the job that publishes it. The entry that
#: would go missing quietly is `backend`: drop it from the bandit line and the
#: `sast` check stays green over the part of the tree that was already safe,
#: while the three anonymous public endpoints stop being scanned and nothing
#: anywhere reports it. Coverage is asserted separately above, because it is
#: configured in pyproject.toml rather than on a command line.
SOURCE_GATES = (
    ("ci.yml", "quality", "ruff check"),
    ("ci.yml", "quality", "ruff format --check"),
    ("ci.yml", "quality", "mypy"),
    ("security.yml", "sast", "bandit"),
)

#: Every directory those gates have to name. Read from the tree rather than
#: written down, so a package added later is covered by the same assertion.
GATED_ROOTS = ("ampeer_sim", "ampeer_advice", "backend", "tools")


def _run_steps(workflow: str, job: str) -> list[str]:
    """The shell commands a job runs, refusing a job with no steps at all.

    The emptiness that matters is the job's, not this filter's: a job made
    entirely of actions has no `run` step and that is fine. A job with no steps
    is a job whose shape changed, and the gate comparisons below would then
    report agreement about nothing.
    """
    steps = _workflows()[workflow]["jobs"][job].get("steps", [])
    assert steps, f"{workflow}:{job} declares no steps"
    return [str(step["run"]) for step in steps if "run" in step]


@pytest.mark.parametrize(("workflow", "job", "tool"), SOURCE_GATES)
def test_every_source_gate_reads_every_package(workflow: str, job: str, tool: str) -> None:
    commands = [run for run in _run_steps(workflow, job) if tool in run]
    assert commands, f"{workflow}:{job} runs no {tool} step at all"
    for command in commands:
        arguments = command.split(tool, 1)[1]
        missing = [root for root in GATED_ROOTS if not re.search(rf"\b{root}\b", arguments)]
        assert not missing, f"{tool} in {workflow}:{job} does not read {missing}"


def test_the_deployment_checklist_runs_against_production_settings() -> None:
    """wsgi.py is not imported by any test and is on the coverage omit list, so
    a mistake in prod.py has no other way of being found before a deploy. The
    fail level matters as much as the command: at the default, a warning about
    a missing security header prints and exits zero."""
    steps = _workflows()["ci.yml"]["jobs"]["quality"].get("steps", [])
    checks = [step for step in steps if "check --deploy" in str(step.get("run", ""))]
    assert len(checks) == 1, "the quality job does not run Django's deployment checklist"
    step = checks[0]
    assert "--fail-level WARNING" in step["run"], "a warning that exits zero is not a gate"
    assert step["env"]["DJANGO_SETTINGS_MODULE"] == "ampeer.settings.prod"


def test_the_coverage_omit_list_stays_short_and_justified() -> None:
    """An omit entry is the quietest way to make a coverage floor stop meaning
    anything: the percentage stays high because the untested code is no longer
    counted. Only the two generated entry points may be listed."""
    allowed = {"backend/manage.py", "backend/ampeer/wsgi.py"}
    omitted = set(_pyproject()["tool"]["coverage"]["run"].get("omit", []))
    assert omitted <= allowed, f"unjustified coverage omissions: {sorted(omitted - allowed)}"


def test_every_service_container_is_pinned_by_digest() -> None:
    """A tag is mutable. `postgres:16-alpine` on Tuesday and on Thursday are two
    different images, and the pipeline already refuses an action pinned by tag
    for exactly that reason."""
    offenders = [
        f"{name}.{service}: {config['image']}"
        for name, job in _jobs().items()
        for service, config in (job.get("services") or {}).items()
        if "@sha256:" not in str(config.get("image", ""))
    ]
    assert not offenders, f"service containers not pinned by digest: {offenders}"


def test_every_image_in_the_deploy_stack_is_pinned_by_digest() -> None:
    """The same rule, read in the second place an image enters this project.

    Workflow service containers were the only place anything looked, and
    `infra/docker-compose.yml` is the file that decides what actually runs on
    the host. A digest dropped there would have reached production with every
    check in this repository still green, so it fails here, in the job that
    already runs on every pull request, rather than on the host.
    """
    services = yaml.safe_load(INFRA_COMPOSE.read_text(encoding="utf-8"))["services"]
    offenders = [
        f"{name}: {spec.get('image')!r}"
        for name, spec in services.items()
        if name not in INFRA_IMAGES_BUILT_HERE and "@sha256:" not in str(spec.get("image", ""))
    ]
    assert not offenders, f"deploy stack images not pinned by digest: {offenders}"


def test_the_build_backend_is_pinned_exactly() -> None:
    """uv does not lock build backend requirements.

    With a range here, `uv sync --locked` resolves setuptools live from PyPI and
    runs its build backend, under the very flag whose job is to forbid unlocked
    resolution.
    """
    for requirement in _pyproject()["build-system"]["requires"]:
        assert "==" in requirement, f"build requirement is not pinned: {requirement}"


def _locked_version(package: str) -> str:
    match = re.search(
        rf'^name = "{re.escape(package)}"\nversion = "([^"]+)"',
        UV_LOCK.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match, f"{package} not found in uv.lock"
    return match.group(1)


def test_pre_commit_and_the_lockfile_agree_on_ruff() -> None:
    """Two formatters on different versions take turns rewriting the same files.

    The loop only shows up as a pull request that is never quite formatted.
    """
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hook_rev = next(repo["rev"] for repo in config["repos"] if "ruff-pre-commit" in repo["repo"])
    assert hook_rev.lstrip("v") == _locked_version("ruff"), (
        f"pre-commit pins ruff {hook_rev} but uv.lock has {_locked_version('ruff')}"
    )


def test_the_node_types_describe_the_node_that_actually_runs() -> None:
    """`@types/node` major tracks the Node major it describes, so it is a claim
    about the platform and not a dependency like any other.

    Every Node-touching job in ci.yml takes its version from
    `frontend/.nvmrc`. If the types say a later Node than the one the jobs
    install, `tsc` type checks the code against a standard library that is not
    there, and the failure is the quiet kind: green here, `undefined is not a
    function` in production. Dependabot proposed exactly that on 2026-08-24,
    six majors at once, and nothing in the pipeline objected because nothing
    was reading these two files together.
    """
    node_major = NVMRC.read_text(encoding="utf-8").strip().split(".")[0]
    package = json.loads(FRONTEND_PACKAGE_JSON.read_text(encoding="utf-8"))
    declared = package["devDependencies"]["@types/node"]
    types_major = re.match(r"[\^~]?(\d+)", declared)
    assert types_major, f"cannot read a major version out of @types/node {declared!r}"
    assert types_major.group(1) == node_major, (
        f"frontend/.nvmrc installs Node {node_major} and package.json asks for "
        f"@types/node {declared}; tsc would be checking against the wrong platform"
    )


@pytest.mark.parametrize("workflow", sorted(path.name for path in WORKFLOW_DIR.glob("*.yml")))
def test_every_workflow_declares_least_privilege_permissions(workflow: str) -> None:
    """Read from the directory rather than from a list of two names.

    The list was ci.yml and security.yml until 2026-08-21, when deploy.yml
    arrived; a third workflow added later would have been outside this
    assertion, which is the shape of every finding in that round. A job that
    needs more says so on the job, where it is scoped to the job: `build` in
    deploy.yml adds `packages: write` that way.
    """
    document = _workflows()[workflow]
    assert document.get("permissions") == {"contents": "read"}


# --------------------------------------------------------------------------
# The frontend half of the same gates.
#
# SOURCE_GATES above reads Python paths off Python command lines, so it cannot
# express a gate whose whole argument list is "the frontend directory" and
# whose tool is a pnpm script. Every entry below was, on 2026-08-21, a step
# that could be deleted from a workflow with every test in this file still
# green: the semgrep line in `sast`, the four pnpm steps in `dependencies`,
# and the lint and typecheck in `frontend-quality`. That is the third instance
# of the same shape in one day, and the comment above SOURCE_GATES names it:
# the entry that goes missing quietly is the newest one.
# --------------------------------------------------------------------------

#: (workflow, job, fragments that must all appear in one `run` line). One tuple
#: per gate, not per job, so deleting any single line turns exactly one of these
#: red with the deleted command in the message.
FRONTEND_GATES = (
    ("ci.yml", "frontend-quality", ("pnpm install", "--frozen-lockfile")),
    ("ci.yml", "frontend-quality", ("pnpm lint",)),
    ("ci.yml", "frontend-quality", ("pnpm typecheck",)),
    # Added 2026-08-21. The Python half has checked formatting since the
    # first commit and this half had no formatter at all, so the two jobs
    # were not the same gate under two names.
    ("ci.yml", "frontend-quality", ("pnpm format:check",)),
    ("ci.yml", "frontend-test", ("pnpm install", "--frozen-lockfile")),
    ("ci.yml", "frontend-test", ("pnpm test",)),
    ("ci.yml", "frontend-test", ("pnpm build",)),
    ("ci.yml", "frontend-test", ("pnpm e2e",)),
    ("security.yml", "dependencies", ("pnpm install", "--frozen-lockfile")),
    ("security.yml", "dependencies", ("pnpm audit", "--audit-level low")),
    (
        "security.yml",
        "sast",
        ("semgrep", "--config .semgrep/frontend.yml", "--error", "frontend/src"),
    ),
)


def _steps(workflow: str, job: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = _workflows()[workflow]["jobs"][job].get("steps", [])
    assert steps, f"{workflow}:{job} declares no steps"
    return steps


@pytest.mark.parametrize(("workflow", "job", "fragments"), FRONTEND_GATES)
def test_every_frontend_gate_is_still_in_its_job(
    workflow: str, job: str, fragments: tuple[str, ...]
) -> None:
    commands = [
        run for run in _run_steps(workflow, job) if all(fragment in run for fragment in fragments)
    ]
    assert commands, f"{workflow}:{job} runs no step containing {list(fragments)}"


@pytest.mark.parametrize(("workflow", "job"), [("security.yml", "dependencies")])
def test_every_pnpm_step_outside_a_frontend_job_says_where_it_runs(workflow: str, job: str) -> None:
    """`dependencies` has no `defaults.run.working-directory`, so a pnpm step
    there runs at the repository root, where there is no package.json.

    It would fail rather than pass quietly, but it would fail for a reason that
    reads as a broken runner rather than as a missing `working-directory`, and
    the fix somebody reaches for under that misreading is to delete the step.
    """
    default = _workflows()[workflow]["jobs"][job].get("defaults", {}).get("run", {})
    if default.get("working-directory") == "frontend":
        return
    offenders = [
        step.get("name", step["run"])
        for step in _steps(workflow, job)
        if "pnpm" in str(step.get("run", "")) and step.get("working-directory") != "frontend"
    ]
    assert not offenders, f"{workflow}:{job} pnpm steps with no working-directory: {offenders}"


def test_every_job_that_holds_a_gate_is_a_required_check() -> None:
    """A gate in a job no ruleset requires is a gate a merge does not wait for.

    Both halves are read from the tables above rather than written down again,
    so a gate added to a new job is covered by this the moment it is listed.
    """
    gated_jobs = {job for _, job, _ in SOURCE_GATES} | {job for _, job, _ in FRONTEND_GATES}
    gated_jobs.add("test")  # the coverage floor lives there
    main = next(p for p in _ruleset_payloads() if p["name"] == "protect-main")
    required = {check["context"] for check in _required_checks(main)}
    assert gated_jobs <= required, (
        f"gates in jobs nothing requires: {sorted(gated_jobs - required)}"
    )


# --------------------------------------------------------------------------
# The frontend's own configuration, read from Python because this is where the
# repository keeps the tests that can fail a build over a configuration file.
# --------------------------------------------------------------------------

FRONTEND = REPO_ROOT / "frontend"
VITEST_CONFIG = FRONTEND / "vitest.config.ts"
PACKAGE_JSON = FRONTEND / "package.json"
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"

#: The four vitest thresholds, as measured on 2026-08-21 and written down in
#: vitest.config.ts. Each may be raised and none may be lowered, which is the
#: rule that file states about itself and that nothing enforced: the Python
#: floor is defended by `test_the_coverage_floor_is_not_lowered` above, and
#: `branches: 91` could be edited to 70 with every test in this repository
#: still green.
MINIMUM_FRONTEND_COVERAGE = {
    "statements": 95,
    "branches": 91,
    "functions": 94,
    "lines": 96,
}


def _vitest_thresholds() -> dict[str, float]:
    source = VITEST_CONFIG.read_text(encoding="utf-8")
    block = re.search(r"thresholds:\s*\{(.*?)\}", source, re.DOTALL)
    assert block, "vitest.config.ts declares no coverage thresholds block"
    return {
        name: float(value) for name, value in re.findall(r"(\w+)\s*:\s*([\d.]+)", block.group(1))
    }


@pytest.mark.parametrize(("metric", "floor"), sorted(MINIMUM_FRONTEND_COVERAGE.items()))
def test_the_frontend_coverage_floor_is_not_lowered(metric: str, floor: int) -> None:
    """Same rule as the Python floor, now with the same enforcement.

    Four metrics rather than one because they fail on different things, and one
    parametrised case each so a single lowered number names itself.
    """
    thresholds = _vitest_thresholds()
    assert metric in thresholds, f"vitest.config.ts sets no {metric} threshold"
    assert thresholds[metric] >= floor, (
        f"{metric} is {thresholds[metric]}, below the floor of {floor}; "
        "the floor may rise and may never fall, so the fix is a test"
    )


def test_the_frontend_coverage_gate_still_measures_and_still_fails() -> None:
    """A threshold nothing reads is a comment.

    `pnpm test` has to run vitest with coverage on, and the coverage has to be
    measured over src/. Dropping --coverage from the script leaves four
    thresholds in a file that is still parsed and never applied.
    """
    scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]
    assert "--coverage" in scripts["test"], (
        f"pnpm test does not measure coverage: {scripts['test']}"
    )
    source = VITEST_CONFIG.read_text(encoding="utf-8")
    assert 'include: ["src/**"]' in source, "coverage no longer includes src/**"


def test_the_frontend_lint_gate_can_fail_on_a_warning() -> None:
    """eslint exits 0 while it has only warnings to report.

    So `pnpm lint` without `--max-warnings 0` is a step that runs the linter,
    prints its findings into the job log, and passes. That is what it did until
    2026-09-01, and three unused-variable warnings had been riding along in
    green runs on that branch because of it. Adding the flag is only half the
    fix; without this test the next person to find it noisy can take it back
    out and the gate goes quiet again in a way no run would report.
    """
    scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]
    assert "--max-warnings 0" in scripts["lint"], (
        f"pnpm lint cannot fail on a warning: {scripts['lint']}"
    )


def test_the_package_manager_is_pinned_by_hash() -> None:
    """corepack downloads and executes whatever the registry serves under this
    version unless the field carries an integrity hash.

    Three required jobs run `corepack enable` before anything else, so without
    the suffix the first executable in each of them is unverified. security.yml
    pins gitleaks by SHA256 and calls it "the only unhashed executable in the
    pipeline"; on 2026-08-21 that sentence had stopped being true.
    """
    declared = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["packageManager"]
    assert re.fullmatch(r"pnpm@\d+\.\d+\.\d+\+sha512\.[0-9a-f]{128}", declared), (
        f"packageManager is not pinned by a sha512 digest: {declared!r}"
    )


def test_every_lockfile_has_something_that_updates_it() -> None:
    """Pinning without dependabot trades one risk for another, as the header of
    dependabot.yml says about itself.

    The lockfiles are read from the tree rather than listed here, so a second
    ecosystem arriving later is covered by the same assertion. `pnpm audit
    --audit-level low` in the `dependencies` job goes red on the first advisory
    at any severity; with no entry for that lockfile, nothing anywhere produces
    the pull request that fixes it.
    """
    ecosystem_for = {
        "uv.lock": ("uv", "/"),
        "pnpm-lock.yaml": ("npm", "/frontend"),
    }
    configured = {
        (update["package-ecosystem"], update["directory"])
        for update in yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))["updates"]
    }
    missing = [
        f"{path.relative_to(REPO_ROOT).as_posix()} needs {ecosystem_for[path.name]}"
        for path in sorted(REPO_ROOT.glob("*/pnpm-lock.yaml")) + [UV_LOCK]
        if path.name in ecosystem_for and ecosystem_for[path.name] not in configured
    ]
    assert not missing, f"lockfiles nothing updates: {missing}"
    assert ("github-actions", "/") in configured, "nothing updates the pinned action SHAs"


def test_the_language_boundary_check_is_still_in_the_tree() -> None:
    """The check the spec asks for, and the file it compares against.

    Spec chapter 10 point 3 asks for a test that no Dutch advice text lives in
    frontend source. It is an end to end test, so it is a file in a directory
    playwright globs: deleting it removes the gate and turns nothing red, which
    is the exact shape every finding in this round has. The allowlist beside it
    is the other half; an emptied one would make the check vacuous, so the
    minimum here is a floor on the file and the check has its own floor on what
    it extracted.
    """
    spec = FRONTEND / "e2e" / "language.spec.ts"
    allowlist = FRONTEND / "tests" / "ui-strings.txt"
    assert spec.is_file(), "the language boundary check is gone"
    assert allowlist.is_file(), "the allowlist the language boundary check reads is gone"
    entries = [
        line
        for line in allowlist.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert len(entries) > 60, f"the allowlist holds {len(entries)} entries"
    body = spec.read_text(encoding="utf-8")
    for required in ("typescript", "ui-strings.txt", "aria-label"):
        assert required in body, f"the language check no longer mentions {required}"


def test_the_interpreter_running_this_matches_the_pinned_version() -> None:
    """`.python-version` has to be a fact, not a wish.

    The workflows used to pass `python-version-file` to setup-uv. That input
    does not exist in v10, so the action ignored it and said so as a workflow
    annotation, which does not fail a build: five jobs claimed to pin an
    interpreter and none of them did. It happened to be right anyway, because uv
    reads the file itself, but nothing had checked.

    This runs inside the interpreter under test, which is what makes it an
    observation rather than another claim.
    """
    import sys

    pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    running = ".".join(str(part) for part in sys.version_info[:2])
    assert running == pinned, f"running Python {running}, .python-version says {pinned}"


def test_no_workflow_passes_setup_uv_an_input_it_does_not_have() -> None:
    """The specific mistake, so re-adding it fails here rather than in an
    annotation nobody reads. setup-uv v10 accepts `version`, `version-file` and
    `python-version`; `python-version-file` is not one of them."""
    for name, document in _workflows().items():
        for job, spec in document["jobs"].items():
            for step in spec.get("steps", []):
                if "astral-sh/setup-uv" not in str(step.get("uses", "")):
                    continue
                unknown = set(step.get("with", {})) & {"python-version-file"}
                assert not unknown, f"{name}:{job} passes setup-uv {sorted(unknown)}"


#: The local runner. It is a convenience and not an authority: the required
#: checks are the workflows, and this file exists so the convenience cannot
#: quietly come to cover less than the workflows do. Until 2026-08-21 there was
#: no runner at all, every pre-push check was improvised at the prompt, and a
#: grep for "High" over bandit's output reported a Medium finding as clean.
LOCAL_GATES = REPO_ROOT / "scripts" / "gates.sh"

#: Commands in the workflows that set something up rather than judge it, with
#: the reason each one is not a gate. An entry here is an exemption, so the
#: list is short on purpose and every line has to earn itself; the test below
#: fails on an entry that no longer matches any workflow, so it cannot become
#: a drawer for gates that were dropped.
SETUP_NOT_A_GATE = (
    # Writes the file the two audit steps read. Its own failure is not a
    # finding, and gates.sh runs it as part of those gates rather than beside
    # them, so the export failing cannot read as an audit that passed.
    (
        "uv export --format requirements-txt --no-emit-project --all-groups"
        " --output-file requirements-audit.txt"
    ),
    (
        "uv export --format requirements-txt --no-emit-project --all-groups"
        " --output-file requirements-sbom.txt"
    ),
    # Downloads a browser. Left to CI deliberately; gates.sh names it in the
    # line that reports e2e as not run here.
    "pnpm exec playwright install --with-deps chromium",
    # The `sast` and `dependencies` jobs build a smaller environment than
    # `test` does. gates.sh syncs the superset once, so the narrower spelling
    # would only assert that the same thing happened twice.
    "uv sync --locked --group dev",
)

#: What each workflow command has to look like inside scripts/gates.sh. A
#: fragment rather than the whole command, because a few of them legitimately
#: differ: gitleaks is invoked from PATH instead of a downloaded binary, and
#: the pull request scan names a base branch that a working copy does not know.
#: What may never differ is the part that decides how strict the check is.
GATE_FRAGMENTS = {
    "uv sync --locked --group dev --group backend": "uv sync --locked --group dev --group backend",
    "uv run ruff check ampeer_sim ampeer_advice backend tests tools": (
        "uv run ruff check ampeer_sim ampeer_advice backend tests tools"
    ),
    "uv run ruff format --check ampeer_sim ampeer_advice backend tests tools": (
        "uv run ruff format --check ampeer_sim ampeer_advice backend tests tools"
    ),
    "uv run mypy ampeer_sim ampeer_advice backend tests tools": (
        "uv run mypy ampeer_sim ampeer_advice backend tests tools"
    ),
    "uv run shellcheck --severity=style --format=gcc $(git ls-files '*.sh')": (
        "uv run shellcheck --severity=style --format=gcc"
    ),
    "uv run python backend/manage.py check --deploy --fail-level WARNING": (
        "uv run python backend/manage.py check --deploy --fail-level WARNING"
    ),
    "uv run pre-commit run --all-files --show-diff-on-failure": (
        "uv run pre-commit run --all-files --show-diff-on-failure"
    ),
    'uv run pytest -m "not perf" --cov --cov-report=term-missing': (
        'uv run pytest -m "not perf" --cov --cov-report=term-missing'
    ),
    "uv run pytest -m perf": "uv run pytest -m perf",
    "uv run bandit -c pyproject.toml -r ampeer_sim ampeer_advice backend tools": (
        "uv run bandit -c pyproject.toml -r ampeer_sim ampeer_advice backend tools"
    ),
    "uv run semgrep --config .semgrep/frontend.yml --error --quiet frontend/src": (
        "uv run semgrep --config .semgrep/frontend.yml --error --quiet frontend/src"
    ),
    "uv run pip-audit --requirement requirements-audit.txt --strict": (
        "uv run pip-audit --requirement requirements-audit.txt --strict"
    ),
    (
        "uv run cyclonedx-py requirements requirements-sbom.txt --output-format JSON"
        " --output-file sbom.json"
    ): ("uv run cyclonedx-py requirements requirements-sbom.txt --output-format JSON"),
    "pnpm install --frozen-lockfile": "pnpm install --frozen-lockfile",
    "pnpm lint": "pnpm lint",
    "pnpm typecheck": "pnpm typecheck",
    "pnpm format:check": "pnpm format:check",
    "pnpm test": "pnpm test",
    "pnpm build": "pnpm build",
    "pnpm e2e": "pnpm e2e",
    "pnpm audit --audit-level low": "pnpm audit --audit-level low",
    './gitleaks detect --source . --redact --no-banner --log-opts "origin/${BASE_REF}..HEAD"': (
        "gitleaks detect --source . --redact --no-banner"
    ),
    "./gitleaks detect --source . --redact --no-banner || true": (
        "gitleaks detect --source . --redact --no-banner"
    ),
}

#: The prefixes that make a line in a `run:` block a tool invocation rather
#: than shell plumbing. Anything matching one of these is held to the contract
#: below; `set -euo pipefail`, an assignment and a `curl` are not.
_GATE_PREFIXES = ("uv run ", "uv sync ", "uv export ", "pnpm ", "./gitleaks ")


def _workflow_commands() -> set[str]:
    """Every tool invocation the pipeline runs, from every job in every workflow.

    Line continuations are joined first, so a command split across three lines
    for readability is compared as the one command it is.
    """
    found: set[str] = set()
    for workflow in _workflows().values():
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                if "run" not in step:
                    continue
                joined = str(step["run"]).replace(chr(92) + chr(10), " ")
                for line in joined.splitlines():
                    command = " ".join(line.split())
                    if command.startswith(_GATE_PREFIXES):
                        found.add(command)
    return found


def test_the_local_runner_accounts_for_every_command_the_pipeline_runs() -> None:
    """No gate may exist in CI and be unknown to scripts/gates.sh.

    Accounting for a gate means running it or naming it in the line that
    reports it as not runnable here. Both are honest; silence is not, and
    silence is the failure this whole file was written against.
    """
    known = set(GATE_FRAGMENTS) | set(SETUP_NOT_A_GATE)
    unaccounted = sorted(_workflow_commands() - known)
    assert not unaccounted, (
        "the pipeline runs commands scripts/gates.sh knows nothing about, so a "
        "local run would report green over them:\n  " + "\n  ".join(unaccounted)
    )


@pytest.mark.parametrize(("command", "fragment"), sorted(GATE_FRAGMENTS.items()))
def test_every_pipeline_gate_appears_in_the_local_runner(command: str, fragment: str) -> None:
    text = LOCAL_GATES.read_text(encoding="utf-8")
    assert fragment in text, f"scripts/gates.sh does not run or name `{command}`"


@pytest.mark.parametrize("command", sorted(set(GATE_FRAGMENTS) | set(SETUP_NOT_A_GATE)))
def test_the_local_runner_lists_no_command_the_pipeline_stopped_running(command: str) -> None:
    """A stale entry is how this contract would rot into always passing.

    Without this, a gate removed from CI keeps its line here, and the day it
    comes back under a different spelling the new spelling is unaccounted for
    while the list still looks complete.
    """
    assert command in _workflow_commands(), (
        f"`{command}` is listed here but no workflow runs it any more; remove the "
        "entry rather than leaving it to vouch for a gate that is gone"
    )


#: Every file that explains the self-hosted refusal by naming what a push to an
#: unprotected branch can start. Each one has to name the workflows that
#: actually do it and no others.
#:
#: All five said "ci.yml and security.yml", or "the workflows", until
#: 2026-08-21. security.yml has never triggered on a feature push: its push
#: trigger names dev alone and its earliest reach is a pull request. The rule
#: those sentences justify is right and stays; the reason given for it
#: overstated the exposure of one of the two workflows, in five places at once,
#: because each was copied from the last.
CLAIMS_ABOUT_FEATURE_PUSHES = (
    ".github/workflows/deploy.yml",
    "infra/README.md",
    "tests/test_pipeline_contract.py",
    "tests/test_deploy_workflow.py",
    "docs/superpowers/specs/2026-08-21-deploy-design.md",
)


def _push_branches(workflow: dict[Any, Any]) -> list[str]:
    """The branches a workflow triggers on for a push, past the YAML trap.

    PyYAML resolves an unquoted `on` key to the boolean True, so reading
    `document["on"]` finds nothing and every assertion of the form "this does
    not trigger on X" passes on a workflow that triggers on everything.
    """
    block = workflow.get("on", workflow.get(True))
    assert block, "the workflow declares no triggers at all"
    push = block.get("push") or {}
    branches = push.get("branches") or []
    return [str(branch) for branch in branches]


def _workflows_started_by_a_feature_push() -> set[str]:
    return {
        name
        for name, workflow in _workflows().items()
        if any(branch.startswith("feat/") for branch in _push_branches(workflow))
    }


def test_only_ci_triggers_on_a_feature_branch_push() -> None:
    """The fact five comments rest on, measured instead of repeated.

    It is the reason `test_no_job_runs_on_the_self_hosted_runner` exists, and it
    is the kind of sentence that gets copied from file to file and then quietly
    stops being true when a trigger moves. Asserting the set rather than the
    presence of ci.yml, so a second workflow gaining that trigger fails here and
    has to be written into the five files below rather than widening what they
    already claim.
    """
    assert _workflows_started_by_a_feature_push() == {"ci.yml"}, (
        f"a feature push now starts {sorted(_workflows_started_by_a_feature_push())}; "
        "the comments listed in CLAIMS_ABOUT_FEATURE_PUSHES describe the old set"
    )


#: The wordings that were wrong, each split in two so this file does not
#: contain the phrases it refuses. The first attempt spelled them out and failed
#: on itself, which is the same shape as a `# nosec` comment that explains what
#: follows a `# nosec` comment: a check that reads text cannot quote the text it
#: rejects. Neither half is a forbidden phrase on its own.
WRONG_WORDINGS = (
    ("ci.yml and secu", "rity.yml trigger on push"),
    ("`ci.yml` and `secu", "rity.yml` trigger on push"),
    ("These workflows trig", "ger on push to feat"),
    ("the workflows trig", "ger on push"),
    ("de workflows draai", "en op `push` naar `feat/**`"),
)


@pytest.mark.parametrize("path", CLAIMS_ABOUT_FEATURE_PUSHES)
def test_no_file_still_says_the_security_workflow_runs_on_a_feature_push(path: str) -> None:
    """The exact wordings that were wrong, refused by name.

    A looser check would be a check on prose, which this repository has learned
    not to trust: an earlier version of the methodology test searched a whole
    document for a figure and passed on the paragraph that explained it rather
    than the table that carried it.
    """
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    for head, tail in WRONG_WORDINGS:
        assert head + tail not in text, f"{path} still says {head + tail!r}"


#: Directories whose contents are not this repository's own source: installed
#: packages, build output, and the profile data that is not committed.
_NOT_OURS = (
    "/.venv/",
    "/node_modules/",
    "/.git/",
    "/out/",
    "/data/",
    "/.next/",
    "/htmlcov/",
    "/.superpowers/",
)

_TEST_REFERENCE = re.compile(r"tests/test_[a-z0-9_]+\.py")


def _files_that_can_carry_a_reference(root: Path = REPO_ROOT) -> list[Path]:
    """Every file of ours that could name a test, pruned during the walk.

    Pruned rather than filtered afterwards: rglob descends into .venv and
    node_modules first and discards them second, which cost fourteen seconds
    against a suite that runs in forty. A test slow enough to be noticed is a
    test somebody eventually runs with -k.

    `root` defaults to this repository and exists so a test can point this at
    a throwaway tree instead, the same reason tests/test_plans.py takes
    `tmp_path` rather than writing into `PLANS_DIR`.
    """
    suffixes = {".py", ".sh", ".yml", ".yaml", ".ts", ".tsx", ".md", ".toml", ".conf"}
    skip = {name.strip("/") for name in _NOT_OURS}
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in skip]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix in suffixes:
                found.append(path)
    return found


def test_a_directory_named_dot_superpowers_is_never_walked(tmp_path: Path) -> None:
    """The SDD scratch workspace, which git never sees and os.walk always does.

    `_NOT_OURS`'s own docstring calls itself "directories whose contents are
    not this repository's own source", and a git-ignored agent workspace is
    exactly that. Built on a throwaway tree rather than the real repository,
    so this does not depend on a run happening to be mid-flight when it runs.
    """
    # Built from two halves at runtime rather than written out whole: a whole
    # "tests/test_..._anywhere.py" literal in this plan's own source would be
    # a reference this very check would flag once the plan is no longer
    # exempt, which is the trap ruling 6 already names for the status marker.
    nonexistent = "tests/test_does_not" + "_exist_anywhere.py"
    (tmp_path / ".superpowers" / "sdd").mkdir(parents=True)
    carrier = tmp_path / ".superpowers" / "sdd" / "progress.md"
    carrier.write_text(f"{nonexistent}\n", encoding="utf-8")
    (tmp_path / "real.md").write_text("tests/test_pipeline_contract.py\n", encoding="utf-8")

    found = {path.name for path in _files_that_can_carry_a_reference(tmp_path)}
    assert "progress.md" not in found, ".superpowers is walked and should be pruned"
    assert "real.md" in found, "the walk was pruned so hard it lost a file that is ours"


def test_a_spec_is_exempt_only_when_its_own_plan_is_in_progress(tmp_path: Path) -> None:
    """The pairing, run rather than reasoned about.

    A spec never says "in progress" in its own status line: every spec in
    docs/superpowers/specs/ opens with "Status: vastgesteld, klaar voor
    implementatieplan", delivered or not, so a spec's exemption cannot come
    from its own text. It has to come from the plan it was written for, and
    this proves it both ways: exempt while that plan is in progress, not
    exempt the moment the plan says anything else, and not exempt at all when
    there is no such plan on disk.
    """
    plans = tmp_path / "docs" / "superpowers" / "plans"
    specs = tmp_path / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    plan = plans / "2026-09-04-accounts-auth.md"
    spec = specs / "2026-09-04-accounts-auth-design.md"
    spec.write_text("Status: vastgesteld, klaar voor implementatieplan\n", encoding="utf-8")

    plan.write_text("**Status:** in progress\n", encoding="utf-8")
    assert _is_in_progress(spec) is True

    plan.write_text("**Status:** delivered\n", encoding="utf-8")
    assert _is_in_progress(spec) is False

    orphan = specs / "2026-09-04-nothing-design.md"
    orphan.write_text("Status: vastgesteld, klaar voor implementatieplan\n", encoding="utf-8")
    assert _is_in_progress(orphan) is False


#: The same fail-closed marker tests/test_plans.py uses, read independently
#: here so this file's own defence does not depend on that module's
#: internals. A plan without the exact marker (a typo, another word, no
#: status line at all) falls back to the strict reading, same as there.
_PLAN_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)

#: docs/superpowers/specs/{name}-design.md pairs with docs/superpowers/plans/{name}.md:
#: the same date-prefixed name, differing only by this suffix.
_SPEC_SUFFIX = "-design.md"


def _plan_that_speaks_for(path: Path) -> Path:
    """Which file's status marker this path's references are exempt under.

    A plan under docs/superpowers/plans/ speaks for itself. A spec under
    docs/superpowers/specs/ speaks for the plan it was written for: specs
    carry no completion status of their own, so a spec's exemption has to
    come from the plan. Anything else speaks for itself too, which
    `_is_in_progress` then reads as "not a plan, no marker, not exempt".
    """
    posix = path.as_posix()
    if "docs/superpowers/specs/" in posix and path.name.endswith(_SPEC_SUFFIX):
        plan_name = path.name[: -len(_SPEC_SUFFIX)] + ".md"
        return path.parents[1] / "plans" / plan_name
    return path


def _is_in_progress(path: Path) -> bool:
    plan = _plan_that_speaks_for(path)
    if not plan.is_file():
        return False
    match = _PLAN_STATUS.search(plan.read_text(encoding="utf-8"))
    return match is not None and match.group(1).strip() == "in progress"


def test_every_test_file_named_in_a_comment_exists() -> None:
    """This repository explains itself by naming the test that holds each rule.

    Thirty-seven places do it on 2026-08-22: a constant says which pairing
    guards it, a workflow says which test recomputes its digest, a shell script
    says what would catch its drift. That is the habit this codebase is built
    on, and it is only worth anything while the file named is the file that
    exists.

    A rename is what breaks it, and it breaks silently: the comment still reads
    like a guarantee, the reader goes looking, finds nothing, and has no way to
    tell whether the guard moved or was deleted. Nothing else in the suite
    would notice, because a comment cannot fail a build.

    Only the path is checked. Whether the named test still asserts what the
    comment says it asserts is not mechanically knowable, and pretending
    otherwise would be its own false guarantee.

    A plan still being built, and the spec it was written from, may name a test
    that does not exist yet. tests/test_plans.py already holds the plan itself
    to the opposite promise elsewhere, that something it names is still
    missing, so a second red here would say nothing a reader could not already
    tell from that test. The exemption is read fresh from the plan's own
    status line on every run, not assumed, so a finished plan (and its spec)
    falls straight back under the strict reading below.
    """
    missing: dict[str, set[str]] = {}
    for path in _files_that_can_carry_a_reference():
        if _is_in_progress(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - binary with a text suffix
            continue
        for reference in set(_TEST_REFERENCE.findall(text)):
            if not (REPO_ROOT / reference).is_file():
                missing.setdefault(reference, set()).add(path.relative_to(REPO_ROOT).as_posix())
    assert not missing, "comments name test files that do not exist:\n" + "\n".join(
        f"  {reference} named in {sorted(where)}" for reference, where in sorted(missing.items())
    )


def test_the_reference_scan_actually_reads_this_repository() -> None:
    """The half that keeps the test above from passing on nothing.

    A pattern that matched nothing, a suffix list that excluded the workflows,
    or an exclusion that swallowed the tree would all leave the assertion above
    trivially true. It has to find the references that are known to be there.
    """
    found = {
        reference
        for path in _files_that_can_carry_a_reference()
        for reference in _TEST_REFERENCE.findall(path.read_text(encoding="utf-8", errors="ignore"))
    }
    assert len(found) >= 5, f"only found {sorted(found)}; the scan is not reading the repository"
    assert "tests/test_pipeline_contract.py" in found, (
        "the workflows no longer name this file, which would be a bigger change than a rename"
    )
