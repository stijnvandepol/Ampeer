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


def test_no_job_runs_on_the_self_hosted_runner() -> None:
    """A self-hosted runner is registered on this repository.

    These workflows trigger on push to feat/**, which no ruleset protects. A job
    that selected self-hosted would run unreviewed code inside the owner's own
    network. Until a sub-project designs that runner properly, with ephemeral
    instances and an isolated container, nothing here may target it.
    """
    offenders = {
        name: job.get("runs-on")
        for name, job in _jobs().items()
        if "self-hosted" in str(job.get("runs-on", ""))
    }
    assert not offenders, f"jobs targeting the self-hosted runner: {offenders}"


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


@pytest.mark.parametrize("workflow", ["ci.yml", "security.yml"])
def test_every_workflow_declares_least_privilege_permissions(workflow: str) -> None:
    document = _workflows()[workflow]
    assert document.get("permissions") == {"contents": "read"}
