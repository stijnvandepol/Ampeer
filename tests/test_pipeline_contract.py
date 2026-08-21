"""The delivery pipeline's own invariants, as tests rather than comments.

Every rule checked here was previously written down in a comment somewhere and
enforced by nothing. A comment does not fail a build. These run inside the
`test` job, so the pipeline defends its own shape on every pull request.
"""

from __future__ import annotations

import json
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

#: The floor may be raised, never lowered. See CLAUDE.md.
MINIMUM_COVERAGE_FLOOR = 98


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

    These workflows trigger on push to feat/**, which no ruleset protects. A job
    that selected self-hosted would run unreviewed code inside the owner's own
    network. Nothing here may target it except the one job named in
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
    steps = _workflows()[workflow]["jobs"][job].get("steps", [])
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
