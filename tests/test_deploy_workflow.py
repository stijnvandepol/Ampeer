"""The deploy workflow and its preflight, read as documents rather than run.

Nothing here starts a container, contacts GitHub or touches a host. Every
property below is one that would otherwise only be discovered on the LXC, and
two of them would be discovered by somebody else: the deploy job is the single
job in this repository allowed to run on the self-hosted runner, and the
preflight is the only thing standing between a missing variable and a container
in a restart loop.

The exception itself is the point. `tests/test_pipeline_contract.py` refuses any
job that selects the self-hosted runner, because `ci.yml` triggers on push to
`feat/**` where no ruleset applies. That rule now has an exception, and an
exception that is not bounded is the gate being removed slowly, so the bound is
asserted here: exactly one workflow, exactly one job, and that job has to earn
it by triggering only on a tag and waiting for a review.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from helpers.shell import shell_int

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

#: The thirteen names prod.py refuses to start without. Written out here
#: rather than imported from the preflight or from .env.example, for the
#: reason tests/test_infra.py gives about the same list: an imported list
#: follows the change it was supposed to catch, so a drifting script would
#: still be green.
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
    "AMPEER_MAIL_TRANSPORT",
    "RESEND_API_KEY",
    "AMPEER_MAIL_FROM",
    "AMPEER_SITE_ORIGIN",
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


def _triggers(document: dict[Any, Any]) -> dict[str, Any]:
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
    """Every step of a job, refusing a job that has none.

    `_job` already refuses a name that is not there. What it cannot refuse is a
    job whose shape changed: a job that calls a reusable workflow carries `uses`
    at job level and no steps, and twenty assertions here read as "no step does
    X", every one of which passes over an empty list.
    """
    steps: list[dict[str, Any]] = _job(job).get("steps", [])
    assert steps, (
        f"the {job!r} job declares no steps, so every check over them below would "
        "pass without reading anything"
    )
    return steps


def _step_text(job: str) -> str:
    return "\n".join(
        f"{step.get('uses', '')}\n{step.get('run', '')}" for step in _steps(job)
    ).lower()


def test_the_deploy_job_checks_the_tag_out_without_keeping_the_token() -> None:
    """The opposite of what this asserted until 2026-09-14, and the reversal is
    the point of the change rather than a detail of it.

    It used to demand no checkout, on the grounds that source on the host is a
    thing an attacker inherits. What that actually bought was four releases
    that stopped on a file nobody had copied, and it bought nothing against the
    only person who can start this job: whoever pushes a tag already decides
    every step it runs, because this workflow comes from that tag.

    `persist-credentials: false` is the part still worth asserting. This runner
    is not ephemeral, measured on 2026-08-21, so a token left in .git/config
    outlives the job that needed it and is readable by whatever runs next.
    """
    deploy = _job("deploy")
    checkout = [step for step in deploy["steps"] if "actions/checkout" in str(step.get("uses", ""))]
    assert len(checkout) == 1, f"the deploy job has {len(checkout)} checkout steps"
    assert checkout[0]["with"]["persist-credentials"] is False, (
        "the deploy leaves its token in .git/config on a runner that is not ephemeral"
    )


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


def test_the_deploy_job_reads_and_writes_nothing_else() -> None:
    """Two reads and no writes, asserted as the exact set.

    This demanded `packages: read` alone until 2026-09-14, when the job gained
    a checkout. A token without `contents: read` cannot see a private
    repository at all, and GitHub says `Repository not found` rather than
    forbidden so that a token cannot be used to enumerate private repositories.
    So the checkout costs exactly this one permission.

    Asserted as equality rather than as a subset, because that is what keeps it
    honest: declaring any permission sets every unnamed one to none, and a
    third entry appearing here should be a decision somebody made rather than a
    line that slipped in with something else.
    """
    assert _job("deploy")["permissions"] == {"contents": "read", "packages": "read"}


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
    restart loop has already caused.

    The match is on `docker compose` and a whole word, not on the substrings
    "compose" and "up". Those two caught a step added on 2026-09-15 that only
    copies files: it names docker-compose.yml, and "backup_db.sh" contains
    "up". A check that fires on the letters u and p inside another word is a
    check somebody eventually silences rather than reads.
    """
    runs = [str(step.get("run", "")) for step in _steps("deploy")]
    preflight = next((i for i, run in enumerate(runs) if "preflight_env.sh" in run), None)
    assert preflight is not None, f"the deploy job never runs the preflight: {runs}"
    for index, run in enumerate(runs):
        if "docker compose" in run and re.search(r"\b(up|pull)\b", run):
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
    start = _unconditional_start()
    check = _only_deploy_step(lambda run: "RepoDigests" in run, "inspects a pulled image digest")
    assert pull < check < start, f"pull at {pull}, check at {check}, up at {start}"


def _unconditional_start() -> int:
    """The index of the one step that switches traffic.

    Two steps in the deploy job run `up -d`: the one that starts the release
    and the one that puts the previous release back when it refuses to come
    up. Telling them apart by their `if:` rather than by their text is what
    keeps a second unconditional start from hiding behind a matching string,
    and asserting there is exactly one is the property worth holding: a job
    that starts the stack twice is not a deploy, it is a race.
    """
    steps = _steps("deploy")
    unconditional = [
        index
        for index, step in enumerate(steps)
        if "up -d" in str(step.get("run", "")) and not step.get("if")
    ]
    assert len(unconditional) == 1, (
        f"expected exactly one unconditional `up -d`, found "
        f"{[steps[i].get('name') for i in unconditional]}"
    )
    return unconditional[0]


def _named_deploy_step(name_fragment: str) -> int:
    steps = _steps("deploy")
    matches = [
        index for index, step in enumerate(steps) if name_fragment in str(step.get("name", ""))
    ]
    assert len(matches) == 1, (
        f"expected exactly one deploy step named like {name_fragment!r}, found "
        f"{[steps[i].get('name') for i in matches]}"
    )
    return matches[0]


def test_the_migration_runs_before_the_traffic_switches() -> None:
    """Order, and the reason is which window a failure leaves open.

    Migrating after `up -d` puts every deploy through a moment where the new
    release is already serving against the previous schema, and a migration
    that fails there leaves it serving errors with no step left to abort. This
    way round a failed migration stops the deploy while the previous release
    is still whole. The price is that the old code briefly meets the new
    schema, which the workflow's own comment states as a rule about what a
    migration may contain.
    """
    migrate = _only_deploy_step(lambda run: "manage.py migrate" in run, "runs migrations")
    assert migrate < _unconditional_start(), (
        "the migration runs after the traffic has already switched"
    )


def test_the_migration_runs_after_the_images_are_verified() -> None:
    """The other side of the same ordering.

    Migrating before the digest check would let a repointed tag write to the
    database, which is the one thing in this stack that no later step can put
    back.
    """
    check = _only_deploy_step(lambda run: "RepoDigests" in run, "inspects a pulled image digest")
    migrate = _only_deploy_step(lambda run: "manage.py migrate" in run, "runs migrations")
    assert check < migrate, f"digest check at {check}, migrate at {migrate}"


def test_the_deploy_records_the_running_release_before_it_replaces_it() -> None:
    """After `up -d` the container carrying the answer is gone.

    The recorded tag is the whole of the fallback: there is no second instance
    and no state on the host that says which release was serving, only the
    image reference on the container that was serving it.
    """
    record = _named_deploy_step("Record the release")
    assert record < _unconditional_start(), "the running release is read after it is replaced"
    step = _steps("deploy")[record]
    assert step.get("id") == "current", f"the recording step has no id to be read by: {step}"
    assert "GITHUB_OUTPUT" in str(step.get("run", "")), (
        "the recording step publishes nothing, so no later step can read it"
    )


def test_a_failed_start_puts_the_previous_release_back() -> None:
    """Without this the end of an outage is a person noticing it."""
    fallback = _named_deploy_step("Fall back")
    step = _steps("deploy")[fallback]
    condition = str(step.get("if", ""))
    assert "steps.start.outcome" in condition, (
        f"the fallback does not name the step it answers for: {condition!r}"
    )
    assert "up -d" in str(step.get("run", "")), "the fallback starts nothing"
    environment = " ".join(str(value) for value in (step.get("env") or {}).values())
    assert "steps.current.outputs.version" in environment, (
        f"the fallback never reads the recorded release: {environment!r}"
    )
    assert fallback > _unconditional_start(), "the fallback runs before the start it answers for"


def test_no_step_in_the_deploy_can_turn_a_failure_green() -> None:
    """A fallback that reported success would be the worst outcome here.

    The job has to stay red when a release did not come up, even when putting
    the previous one back worked, because the alternative is a pipeline that
    calls an outage a successful deploy and a next release cut on top of a
    version nobody knows is not running. `continue-on-error` on any step in
    this job is how that would happen.
    """
    for step in _steps("deploy"):
        assert "continue-on-error" not in step, (
            f"{step.get('name')!r} can fail without failing the deploy: {step}"
        )


#: The operator's copy of what a deploy does. It is the file somebody reads at
#: two in the morning, so a description here that no longer matches the job is
#: worse than no description at all.
DEPLOY_README = REPO_ROOT / "infra" / "README.md"

#: Each step of the deploy job and the words the README summary uses for it, in
#: the order the workflow runs them.
#:
#: This pairing exists because the README went stale the same day the job was
#: reordered. Moving `migrate` in front of `up -d` and adding a fallback left
#: three passages here describing the previous deploy, including a paragraph
#: stating that nothing in this repository rolls back automatically, which by
#: then it did. Every gate was green: the workflow tests read the workflow and
#: nothing read the prose.
README_STEP_WORDS = (
    ("Check out the tag", "checks the tag out"),
    ("Put the release's own files", "places the host's copies"),
    ("Check the thirteen variables", "runs the preflight"),
    ("Log in to the registry", "logs in to GHCR"),
    ("Pull what CI built", "`pull`"),
    ("Confirm the images", "confirms the pulled digests"),
    ("Record the release", "records the running release"),
    ("Confirm something is backing", "confirms a recent backup"),
    ("Migrate", "`migrate`"),
    ("Start it", "`up -d`"),
    ("Fall back", "falls back"),
    ("Confirm expired advice", "`purge_expired_advice --check`"),
    ("Confirm the outbox", "`send_outbound_mail --check`"),
    ("Drop the registry credential", "`docker logout`"),
)


def _readme_deploy_summary() -> str:
    """The one paragraph in the README that lists what the deploy job runs.

    Scoped to that paragraph rather than the whole file on purpose: `up -d` and
    `migrate` appear in the sections below it as well, so a search over the
    whole document would find them there and pass while the summary itself said
    something else.
    """
    text = DEPLOY_README.read_text(encoding="utf-8")
    assert "- `deploy` on the self-hosted runner" in text, (
        "the README no longer summarises the deploy job"
    )
    paragraph = text.split("- `deploy` on the self-hosted runner", 1)[1].split("\n\n", 1)[0]
    # Collapsed to one line, because the file is hard wrapped and a phrase
    # that happens to straddle a line break is still the phrase a reader
    # reads.
    return " ".join(paragraph.split())


def test_the_pairing_covers_every_step_the_deploy_has() -> None:
    """The hole this pairing had for exactly one round.

    README_STEP_WORDS is written by hand, so on its own it guards the steps
    somebody already thought about and says nothing about a new one. Two steps
    were added to the deploy job on 2026-08-21, neither was in this list,
    neither was in the README, and all seventy four tests passed. That is the
    same defect as the one this file's own commit message described in the
    methodology test a round earlier, built into the fix for it.

    Requiring the pairing to be total is what closes it: a step with no entry
    fails here, and an entry with no step fails as well, so neither list can
    grow past the other.
    """
    names = [str(step.get("name", "")) for step in _steps("deploy")]
    unpaired = [
        name for name in names if not any(fragment in name for fragment, _ in README_STEP_WORDS)
    ]
    assert not unpaired, (
        "the deploy job has steps this pairing knows nothing about, so the README "
        f"is not required to mention them: {unpaired}"
    )
    assert len(README_STEP_WORDS) == len(names), (
        f"{len(README_STEP_WORDS)} pairings against {len(names)} steps; one entry "
        "matches more than one step or the job gained one nothing describes"
    )


def test_the_readme_summary_names_every_step_the_deploy_runs() -> None:
    """A step nobody wrote down is a step nobody expects to see fail."""
    summary = _readme_deploy_summary()
    names = [str(step.get("name", "")) for step in _steps("deploy")]
    for step_fragment, words in README_STEP_WORDS:
        assert any(step_fragment in name for name in names), (
            f"no deploy step is named like {step_fragment!r} any more; this pairing is stale"
        )
        assert words in summary, f"the README summary does not mention {step_fragment!r}"


def test_the_readme_lists_the_steps_in_the_order_they_run() -> None:
    """Order, because the order is the part that changed and went unread.

    A summary that names every step but puts `migrate` after `up -d` describes
    a deploy with a window this one no longer has, and it is the sentence an
    operator would act on.
    """
    summary = _readme_deploy_summary()
    names = [str(step.get("name", "")) for step in _steps("deploy")]
    in_workflow = [
        next(i for i, name in enumerate(names) if fragment in name)
        for fragment, _ in README_STEP_WORDS
    ]
    in_readme = [summary.index(words) for _, words in README_STEP_WORDS]
    assert in_workflow == sorted(in_workflow), f"this pairing is out of order: {in_workflow}"
    assert in_readme == sorted(in_readme), (
        "the README lists the deploy's steps in an order the job does not run them in:\n"
        + "\n".join(
            f"  {words}" for _, words in sorted(zip(in_readme, README_STEP_WORDS, strict=True))
        )
    )


def test_the_readme_does_not_deny_a_fallback_the_job_performs() -> None:
    """The sentence that was true until the fallback landed, and then was not.

    Kept as its own test rather than folded into the order check, because the
    damage is different in kind: an operator reading it would start doing by
    hand what the job had already done, on a stack whose state they had just
    been told wrongly.
    """
    text = DEPLOY_README.read_text(encoding="utf-8")
    has_fallback = any("Fall back" in str(step.get("name", "")) for step in _steps("deploy"))
    if not has_fallback:
        pytest.skip("the deploy job no longer falls back, so the README should say so")
    assert "Nothing in this repository does that automatically" not in text, (
        "the README still says nothing rolls back automatically, and the deploy job does"
    )


def test_the_readme_heading_matches_where_migrate_runs() -> None:
    """The heading is what a reader skims, so it carries the claim on its own."""
    text = DEPLOY_README.read_text(encoding="utf-8")
    migrate = _only_deploy_step(lambda run: "manage.py migrate" in run, "runs migrations")
    if migrate < _unconditional_start():
        assert "`migrate` runs before it" in text, (
            "the deploy migrates before it switches and no heading in the README says so"
        )
        assert "`migrate` runs after traffic" not in text
    else:
        assert "`migrate` runs after traffic" in text


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
    on the fixture. AMPEER_MAIL_TRANSPORT has to be `resend`, because the
    preflight refuses every other value on a host.
    """
    values = dict.fromkeys(REQUIRED_ENV, "set")
    values["AMPEER_NEDU_PROFILE_PATH"] = profile.as_posix()
    values["DJANGO_NUM_PROXIES"] = "2"
    values["AMPEER_MAIL_TRANSPORT"] = "resend"
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
    def test_it_is_quiet_and_exits_zero_when_all_thirteen_are_set(self, tmp_path: Path) -> None:
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
    def test_it_catches_each_of_the_thirteen_on_its_own(self, tmp_path: Path, name: str) -> None:
        """One case per variable, so a name dropped from the script's list
        names itself instead of hiding in a list that is still thirteen long."""
        values = _complete(_profile(tmp_path))
        del values[name]
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"{name} may be missing without the deploy stopping"
        assert name in result.stdout + result.stderr

    @pytest.mark.parametrize("value", ["file", "memory", "smtp"])
    def test_the_host_preflight_refuses_any_transport_but_resend(
        self, tmp_path: Path, value: str
    ) -> None:
        """prod.py accepts `file` for the local stack's sake; a host must not
        be able to say it. Red-proof: drop the case block from the script."""
        values = _complete(_profile(tmp_path))
        values["AMPEER_MAIL_TRANSPORT"] = value
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"{value!r} passed the preflight"
        assert "AMPEER_MAIL_TRANSPORT" in result.stdout + result.stderr

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


# ---------------------------------------------------------------------------
# The backup
# ---------------------------------------------------------------------------

BACKUP = REPO_ROOT / "scripts" / "backup_db.sh"

#: The tail of a dump pg_dump finished writing. Copied from a real one taken on
#: 2026-08-21 against PostgreSQL 16.15 in this stack, including the unrestrict
#: line 16.15 writes after the marker, because that line is why the script
#: searches the tail rather than comparing the last line.
FINISHED_DUMP_TAIL = chr(10).join(
    (
        "SET row_security = off;",
        "",
        "--",
        "-- PostgreSQL database dump complete",
        "--",
        "",
        chr(92) + "unrestrict HACdGL7B29Eo9IeL5tPGCr4cm3AcvLK9laqrRj8r34kl",
        "",
    )
)


def _posix_modes_work(path: Path) -> bool:
    """Whether this filesystem carries the permission bits the check reads.

    On Windows it does not: `chmod 700` leaves a directory at 755, so the last
    two checks in the script can never pass there. Skipping on that is honest;
    asserting it anyway would teach a developer that a red suite is normal, and
    the host and CI are both Linux where it is the property that matters.
    """
    probe = path / "probe"
    probe.mkdir()
    probe.chmod(0o700)
    return stat.S_IMODE(probe.stat().st_mode) == 0o700


def _backup_check(directory: Path) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash, "these tests drive a shell script and need bash on PATH"
    return subprocess.run(
        [bash, BACKUP.as_posix(), "--check", directory.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )


def _dump(directory: Path, name: str = "ampeer-20260821T043000Z.sql") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = directory / name
    path.write_text("-- PostgreSQL database dump\n" + FINISHED_DUMP_TAIL, encoding="utf-8")
    path.chmod(0o600)
    return path


def test_the_backup_check_runs_before_the_migration() -> None:
    """The placement is the point.

    This deploy applies migrations and nothing rolls a schema back, so the
    moment a recent dump matters is the moment before the first statement runs.
    A check at the end of the job reports there is no backup immediately after
    the release that needed one.
    """
    check = _only_deploy_step(
        lambda run: "backup_db.sh" in run and "--check" in run, "runs the backup check"
    )
    migrate = _only_deploy_step(lambda run: "manage.py migrate" in run, "runs migrations")
    assert check < migrate, f"backup check at {check}, migrate at {migrate}"


class TestTheBackupCheck:
    def test_it_reports_a_directory_that_was_never_created(self, tmp_path: Path) -> None:
        result = _backup_check(tmp_path / "absent")
        assert result.returncode == 1, result.stdout
        assert "no backup directory" in result.stderr

    def test_it_reports_a_directory_with_nothing_in_it(self, tmp_path: Path) -> None:
        """Different from the one above, and the difference is what to do next.

        An absent directory means nobody installed this. An empty one means the
        unit ran and produced nothing, or somebody deleted the dumps.
        """
        empty = tmp_path / "backups"
        empty.mkdir()
        empty.chmod(0o700)
        result = _backup_check(empty)
        assert result.returncode == 1, result.stdout
        assert "no dump in" in result.stderr

    def test_it_refuses_a_dump_that_stops_halfway(self, tmp_path: Path) -> None:
        """The check a size threshold cannot make.

        pg_dump exiting zero says nothing about a redirect that ran out of
        disk. A truncated file is worse than no file, because it is the one
        somebody would restore from.
        """
        directory = tmp_path / "backups"
        path = _dump(directory)
        path.write_text("-- PostgreSQL database dump" + chr(10) + "CREATE TABLE half_")
        result = _backup_check(directory)
        assert result.returncode == 1, result.stdout
        assert "does not end the way a finished dump ends" in result.stderr

    def test_it_refuses_an_empty_file(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        _dump(directory).write_text("", encoding="utf-8")
        result = _backup_check(directory)
        assert result.returncode == 1, result.stdout

    def test_it_reports_a_dump_older_than_the_timer_period(self, tmp_path: Path) -> None:
        """Two days, which is one entirely missed run rather than a late one."""
        directory = tmp_path / "backups"
        path = _dump(directory)
        two_days = time.time() - 48 * 3600
        os.utime(path, (two_days, two_days))
        result = _backup_check(directory)
        assert result.returncode == 1, result.stdout
        assert "hours old" in result.stderr

    def test_it_accepts_a_dump_from_this_morning(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        if not _posix_modes_work(tmp_path):
            pytest.skip("this filesystem does not carry POSIX modes; the host and CI do")
        _dump(directory)
        result = _backup_check(directory)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_it_refuses_a_directory_other_people_can_read(self, tmp_path: Path) -> None:
        """These files hold advice the service has already stopped serving."""
        directory = tmp_path / "backups"
        if not _posix_modes_work(tmp_path):
            pytest.skip("this filesystem does not carry POSIX modes; the host and CI do")
        _dump(directory)
        directory.chmod(0o755)
        result = _backup_check(directory)
        assert result.returncode == 1, result.stdout
        assert "somebody other than its owner" in result.stderr

    def test_it_refuses_a_readable_dump_inside_a_closed_directory(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        if not _posix_modes_work(tmp_path):
            pytest.skip("this filesystem does not carry POSIX modes; the host and CI do")
        _dump(directory).chmod(0o644)
        result = _backup_check(directory)
        assert result.returncode == 1, result.stdout
        assert "expected 600" in result.stderr

    def test_the_permission_checks_come_after_the_ones_about_existence(
        self, tmp_path: Path
    ) -> None:
        """Ordering inside the script, asserted from the outside.

        A directory somebody left at 755 must not be the answer that comes back
        when there is no dump in it at all. Both are wrong; only one of them
        means there is no backup.
        """
        directory = tmp_path / "backups"
        directory.mkdir()
        directory.chmod(0o755)
        result = _backup_check(directory)
        assert result.returncode == 1
        assert "no dump in" in result.stderr, result.stderr
        assert "somebody other than its owner" not in result.stderr


def test_the_backup_unit_fails_when_the_dump_it_just_took_is_not_usable() -> None:
    """The same shape as ampeer-purge.service, and for the same reason.

    ExecStartPost runs only if ExecStart succeeded, so it asks the question the
    exit status did not: the dump reported a byte count, and is the directory
    now something a restore could use?
    """
    unit = (REPO_ROOT / "infra" / "systemd" / "ampeer-backup.service").read_text(encoding="utf-8")
    post = [line for line in unit.splitlines() if line.startswith("ExecStartPost=")]
    assert post, "the backup unit cannot fail on a dump that is not usable"
    assert "backup_db.sh --check" in post[0], post


def test_the_backup_timer_runs_after_the_purge() -> None:
    """A dump taken before the purge is a snapshot of rows about to be deleted.

    Taken after, it only ever holds what the service could still serve when it
    was written. That does not make the copy disappear, and infra/README.md
    section 8 says what it does and does not buy, but the ordering is the
    difference between a backup that happens to hold expired advice and one
    that is scheduled to.
    """
    units = REPO_ROOT / "infra" / "systemd"
    digit = chr(92) + "d"
    pattern = "^OnCalendar=.*?(" + digit + digit + "):(" + digit + digit + "):"
    minutes = {}
    for name in ("ampeer-purge.timer", "ampeer-backup.timer"):
        text = (units / name).read_text(encoding="utf-8")
        found = re.findall(pattern, text, re.MULTILINE)
        assert found, f"{name} has no OnCalendar with a time of day"
        hour, minute = found[0]
        minutes[name] = int(hour) * 60 + int(minute)
    assert minutes["ampeer-backup.timer"] > minutes["ampeer-purge.timer"], (
        "the backup runs before the purge, so every dump is a snapshot of rows "
        f"the purge is about to delete: {minutes}"
    )


#: A schedule this test is willing to reduce to a period: every day, once, at a
#: fixed time. Anything else is refused rather than guessed at, because the
#: number it feeds is a threshold and a wrong period silently makes a health
#: check either useless or permanently red.
_DAILY_SCHEDULE = re.compile(r"^OnCalendar=\*-\*-\* \d{2}:\d{2}:\d{2}$")


def _timer_period_hours(name: str) -> int:
    """How often a timer fires, for the one shape that can be read off."""
    text = (REPO_ROOT / "infra" / "systemd" / name).read_text(encoding="utf-8")
    schedules = [line.strip() for line in text.splitlines() if line.startswith("OnCalendar=")]
    assert len(schedules) == 1, (
        f"{name} declares {len(schedules)} OnCalendar lines; systemd takes the union of "
        "them and this test cannot reduce that to a period"
    )
    assert _DAILY_SCHEDULE.match(schedules[0]), (
        f"{name} is scheduled as {schedules[0]!r}, which is no longer the daily shape "
        "this test can decide. MAX_AGE_HOURS in scripts/backup_db.sh has to be "
        "re-derived by hand and this test taught to read the new shape."
    )
    return 24


def test_the_staleness_threshold_clears_the_timer_it_is_measured_against() -> None:
    """MAX_AGE_HOURS and the timer decide each other, in two files.

    The constant says so itself: it has to be more than the timer's period or
    --check goes red every day in the minutes before the run, and the timer
    unit says the same thing from the other side. Two comments agreeing is not
    a check, and the failure they describe is the loud kind: a health check
    that is red every morning is one somebody turns off.

    Both bounds matter and they come from the same sentence in the script.
    Above the period, or the check is red before every run. Below twice the
    period, or a single missed run no longer fails it, which is the thing the
    check exists for. Twenty six against a daily timer sits in the middle with
    room for AccuracySec and a slow dump.
    """
    hours = shell_int(BACKUP, "MAX_AGE_HOURS")
    period = _timer_period_hours("ampeer-backup.timer")

    assert hours > period, (
        f"--check calls a dump stale after {hours} hours and the timer only runs every "
        f"{period}, so the deploy would refuse a backup that is working"
    )
    assert hours < 2 * period, (
        f"--check tolerates {hours} hours against a timer that runs every {period}, so a "
        "whole missed run passes as healthy, and a check that survives the failure it "
        "is for is not a check"
    )


def test_the_purge_timer_is_the_shape_the_retention_promise_assumes() -> None:
    """The other daily timer, held to the same reading.

    docs/dpia.md promises the service stops answering after ninety days, and
    that promise rests on the read path filtering on expires_at rather than on
    this timer, which is why it is exact. What the timer decides is how long a
    dead row stays on disk after that, and chapter 4 describes it as daily.
    A weekly timer would leave a purged advice in the table for six more days
    while the document went on calling the task daily.
    """
    assert _timer_period_hours("ampeer-purge.timer") == 24, (
        "the purge no longer runs daily, and docs/dpia.md chapter 4 calls it 'een dagelijkse taak'"
    )


METER_PURGE_COMMAND = (
    REPO_ROOT / "backend" / "accounts" / "management" / "commands" / "purge_meter_readings.py"
)


def test_the_meter_purge_timer_is_the_shape_the_retention_promise_assumes() -> None:
    """The third daily timer, held to the same reading as the advice purge.

    docs/dpia.md's retention table promises a quarter reading is folded into
    an hour after ninety days, and chapter 5 of the meter link design calls
    the fold a daily task. A weekly timer would leave raw quarters on disk for
    up to six extra days while the document went on calling it daily.
    """
    assert _timer_period_hours("ampeer-meter-purge.timer") == 24, (
        "the meter purge no longer runs daily, and the retention table calls it a daily fold"
    )


def test_the_meter_purge_grace_clears_the_timer_it_is_measured_against() -> None:
    """GRACE_DAYS and the timer period decide each other, the same pairing
    `test_the_purge_grace_clears_the_timer_it_is_measured_against` makes for
    the advice purge, read here against the meter purge's own command and timer.
    """
    grace_hours = _python_int(METER_PURGE_COMMAND, "GRACE_DAYS") * 24
    period = _timer_period_hours("ampeer-meter-purge.timer")

    assert grace_hours >= period, (
        f"--check calls the meter purge timer dead after {grace_hours} hours and the timer "
        f"only runs every {period}, so a working host is reported broken before every run"
    )
    assert grace_hours < 2 * period, (
        f"--check tolerates {grace_hours} hours against a timer that runs every {period}, so "
        "a whole missed run passes as healthy, and a check that survives the failure it is "
        "for is not a check"
    )


def test_the_meter_purge_timer_needs_no_catch_up() -> None:
    """No `Persistent=` directive, the same shape
    `test_the_mail_unit_runs_the_command_every_minute` checks for the mail
    timer, and for a related but distinct reason: a missed run loses nothing
    because the next run folds every quarter now past the retention window
    regardless of how long it waited, and the day of slack `--check` allows on
    top of ninety is far wider than any realistic downtime.

    Line-anchored rather than a substring check, so the unit may still explain
    the absence in a comment: only an actual `[Timer]` directive line is
    forbidden.
    """
    text = (REPO_ROOT / "infra" / "systemd" / "ampeer-meter-purge.timer").read_text(
        encoding="utf-8"
    )
    assert not any(line.startswith("Persistent=") for line in text.splitlines()), (
        "ampeer-meter-purge.timer now catches up after downtime, which the unit's own "
        "comment says it deliberately does not"
    )


# --------------------------------------------------------------------------
# The purge timer and the check that watches for its silence.
#
# Three properties, each argued at length in the unit file and none of them
# asserted anywhere until 2026-08-23. Every one was measured to leave the whole
# suite green when reversed.
# --------------------------------------------------------------------------

PURGE_COMMAND = (
    REPO_ROOT / "backend" / "advice" / "management" / "commands" / "purge_expired_advice.py"
)


def _python_int(path: Path, name: str) -> int:
    """A module level integer constant, read without importing the module.

    Importing it would need Django configured, and the question here is what the
    source says, which is also what a reviewer reads.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == name
    ]
    assert len(found) == 1, f"{path.name} defines {name} {len(found)} times"
    return int(found[0])


def test_the_purge_grace_clears_the_timer_it_is_measured_against() -> None:
    """GRACE_DAYS and the timer period decide each other, in two files.

    The unit file says it in as many words: the check mode allows exactly
    GRACE_DAYS of slack, so the period there and this constant are one number
    seen from two sides, and changing one means moving the other. Two comments
    agreeing is not a check. The same pairing already exists for the backup
    timer and MAX_AGE_HOURS, one file over, and this one was missing.

    Both bounds, and they are the same two the backup pairing uses. At least the
    period, or a healthy stack is red in the minutes before every run, and a
    check that is red every morning is one somebody turns off. Under twice the
    period, or a whole missed run passes as healthy, which is the failure the
    check exists for.

    The lower bound is met exactly, by design rather than by luck. A row expires
    at most one run before it is deleted, so the worst case sits just under the
    period, and AccuracySec is the entire margin. That is why the two tests
    below are not decoration.
    """
    grace_hours = _python_int(PURGE_COMMAND, "GRACE_DAYS") * 24
    period = _timer_period_hours("ampeer-purge.timer")

    assert grace_hours >= period, (
        f"--check calls the timer dead after {grace_hours} hours and the timer only runs "
        f"every {period}, so a working host is reported broken before every run"
    )
    assert grace_hours < 2 * period, (
        f"--check tolerates {grace_hours} hours against a timer that runs every {period}, so "
        "a whole missed run passes as healthy, and a check that survives the failure it is "
        "for is not a check"
    )


#: Both units, because both carry the same two sentences and the backup one
#: says so explicitly: it has no RandomizedDelaySec "for the same reason
#: ampeer-purge.timer" has none.
TIMERS = ("ampeer-purge.timer", "ampeer-backup.timer")


def _timer_directives(name: str) -> list[str]:
    text = (REPO_ROOT / "infra" / "systemd" / name).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if not line.lstrip().startswith("#")]


@pytest.mark.parametrize("timer", TIMERS)
def test_the_timer_adds_no_jitter_to_a_window_that_has_none_to_give(timer: str) -> None:
    """RandomizedDelaySec is absent on purpose and nothing said so.

    The unit explains it: the grace above is met exactly, so any delay added
    here pushes the worst case past the window and turns a healthy stack red for
    the length of the jitter. Adding an hour of it was measured to leave the
    whole suite green.
    """
    jitter = [line for line in _timer_directives(timer) if line.startswith("RandomizedDelaySec=")]
    assert not jitter, (
        f"{timer} declares {jitter}, which widens the worst case past the window its own "
        "--check allows, so a working host would be reported as broken"
    )


@pytest.mark.parametrize("timer", TIMERS)
def test_the_timer_catches_up_on_a_day_the_host_was_off(timer: str) -> None:
    """Persistent=true, and the unit says what its absence costs.

    Without it systemd skips a missed run rather than running it after the next
    boot, so a weekend of downtime extends the retention window by two days and,
    in the unit's own words, nothing anywhere says so. That was true of this
    sentence too: setting it to false left the whole suite green.

    docs/dpia.md promises deletion on a schedule. A promise that quietly waits
    for the host to be awake is a different promise.
    """
    assert "Persistent=true" in _timer_directives(timer), (
        f"{timer} no longer catches up after downtime, so a day the host was off silently "
        "extends the window its own check measures"
    )


# --------------------------------------------------------------------------
# What the two units say about their own command lines.
#
# Both were measured on 2026-08-24 and both left the suite green when reversed.
# --------------------------------------------------------------------------

UNITS = REPO_ROOT / "infra" / "systemd"


def _unit_directives(name: str) -> list[str]:
    text = (UNITS / name).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if not line.lstrip().startswith("#")]


def test_the_purge_overrides_the_entrypoint_it_would_otherwise_inherit() -> None:
    """Without this the unit starts a web server and deletes nothing.

    The api image's entrypoint execs gunicorn and ignores its arguments, so
    `compose run --rm api backend/manage.py purge_expired_advice` runs a server
    rather than a management command. Overriding the entrypoint is what makes
    this a purge at all, and the unit says so.

    Three invocations now, not two. The first `ExecStart` deletes expired
    advice, the second `ExecStart` deletes expired refresh sessions (accounts
    task 6), and systemd runs both in the order they are declared because the
    unit is `Type=oneshot`. `ExecStartPost` runs only if both `ExecStart` lines
    succeeded, and asks whether anything is still past its date. A check that
    inherited the entrypoint would answer a question nobody asked.

    --env-file with all three, from the same paragraph: docker-compose.yml
    interpolates thirteen variables and gives none of them a default, so
    without the file the unit fails while resolving it instead of connecting
    somewhere unintended, which is the right way round.

    The count below is exact on purpose, the same house style as
    `test_dpia.py::test_the_audit_log_records_exactly_what_the_document_says_it_does`:
    a fourth command has to make this assertion fail and a person come here to
    raise it, rather than land unexamined under a `>=`. Whoever adds one reads
    this docstring first and confirms the new line carries both flags below.
    """
    calls = [
        line
        for line in _unit_directives("ampeer-purge.service")
        if line.startswith(("ExecStart=", "ExecStartPost="))
    ]
    assert len(calls) == 3, f"the unit declares {len(calls)} commands, not the three this reads"
    for call in calls:
        assert "--entrypoint python" in call, (
            f"{call.split('=', 1)[0]} inherits the image's entrypoint, which execs gunicorn "
            "and ignores its arguments"
        )
        assert "--env-file /srv/ampeer/.env" in call, (
            f"{call.split('=', 1)[0]} resolves compose without the env file, and nothing in "
            "that file has a default"
        )


@pytest.mark.parametrize(
    "unit", ["ampeer-purge.service", "ampeer-backup.service", "ampeer-meter-purge.service"]
)
def test_no_unit_puts_a_credential_where_the_host_can_read_it(unit: str) -> None:
    """The backup unit says it sets no environment on purpose, and neither does.

    Its own note: pg_dump runs inside the db container through `sh -c`, so
    POSTGRES_USER and POSTGRES_DB expand there and never appear on a command
    line on this host. systemd hands a unit a clean environment, which is what
    makes that true, and an Environment= line here would undo it: systemd unit
    files are world readable and `systemctl show` prints their values.

    Adding Environment=POSTGRES_PASSWORD to the backup unit was measured to
    leave the whole suite green.
    """
    directives = _unit_directives(unit)
    carried = [line for line in directives if line.startswith(("Environment=", "EnvironmentFile="))]
    assert not carried, (
        f"{unit} carries {carried}; the credentials this stack uses expand inside the db "
        "container and are not meant to reach the host's process table or systemctl show"
    )
    passwords = [line for line in directives if "PASSWORD" in line or "SECRET" in line]
    assert not passwords, f"{unit} names a secret on a directive line: {passwords}"


def test_the_documented_ingest_command_is_one_the_script_accepts() -> None:
    """A command in a document is a promise that it runs.

    infra/README.md told an operator to run `ingest_profiles.py --year 2025
    --out /srv/profiles/` on 2026-09-14. Neither flag exists: the script takes
    the year as a positional argument and the directory as `--target`. It was
    written into the release, read on the host, and answered with an argparse
    error, at the point where the only thing left between that host and a
    running site was one file.

    Nothing could have caught it. The script is not imported by the document
    and the document is not run by anything, so the two agreed with nobody.
    This holds them together by parsing the flags out of the README's own
    command and asking argparse whether it would take them.
    """
    import argparse
    import shlex

    readme = (REPO_ROOT / "infra" / "README.md").read_text(encoding="utf-8")
    documented = [
        line for line in readme.splitlines() if "ingest_profiles.py" in line and "--" in line
    ]
    assert documented, "infra/README.md no longer says how to produce the profile"

    source = (REPO_ROOT / "tools" / "ingest_profiles.py").read_text(encoding="utf-8")
    parser = argparse.ArgumentParser()
    for name, kind in re.findall(r'add_argument\(\s*"([^"]+)"(?:,\s*type=(\w+))?', source):
        parser.add_argument(name, type=Path if kind == "Path" else str)

    for line in documented:
        # Everything after the script name up to the closing quote. shlex on
        # the whole line trips over the `sh -c "..."` the docker invocation
        # wraps it in, which is a property of how it is documented rather than
        # of what is documented.
        pattern = 'ingest_profiles\\.py([^"\\n]*)'
        arguments = re.search(pattern, line)
        assert arguments, line
        tail = shlex.split(arguments.group(1))
        try:
            parser.parse_args(tail)
        except SystemExit:  # pragma: no cover - the failure is the message below
            pytest.fail(
                f"infra/README.md documents `ingest_profiles.py {' '.join(tail)}`, "
                "which the script would refuse. Its arguments are "
                f"{[action.option_strings or action.dest for action in parser._actions[1:]]}"
            )


def test_the_export_reads_the_measurement_id_from_a_variable_and_ci_uses_a_dummy() -> None:
    """The Google Analytics measurement ID is baked into every page at build
    time, so the step that exports the site is the one place it can enter.
    It comes from a repository variable and not a secret, because it is in
    the HTML anyway; unset, the site ships without measurement and without
    the consent banner, and that is a valid build.

    The CI build uses G-TESTTESTTE instead, so the banner renders and
    frontend/e2e/privacy.spec.ts can prove that nothing loads before a yes.
    A CI build that read the real variable would measure its own test runs."""
    export = next(
        step for step in _steps("build") if "Export the static site" in str(step.get("name"))
    )
    assert export["env"]["NEXT_PUBLIC_GA_MEASUREMENT_ID"] == "${{ vars.GA_MEASUREMENT_ID }}"

    ci = _workflows()["ci.yml"]
    builds = [
        step
        for job in ci["jobs"].values()
        for step in job.get("steps", [])
        if step.get("run") == "pnpm build"
    ]
    assert builds, "ci.yml no longer builds the frontend with a plain `pnpm build`"
    for step in builds:
        assert step.get("env", {}).get("NEXT_PUBLIC_GA_MEASUREMENT_ID") == "G-TESTTESTTE"
        assert "vars." not in str(step.get("env", {}))
