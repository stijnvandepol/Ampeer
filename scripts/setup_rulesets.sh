#!/usr/bin/env bash
# Create or update the branch rulesets for Ampeer. Idempotent: safe to re-run.
#
# The required checks below must match the job names in .github/workflows/ci.yml
# and .github/workflows/security.yml exactly. A renamed job produces a check that
# never arrives and a pull request that waits forever.

# ---------------------------------------------------------------------------
# What this script cannot protect, and what would.
#
# Read this before deciding the repository is configured. Written here rather
# than in a doc because this file is what somebody runs when they set the
# protections up, which is the only moment the two settings below are on
# anybody's mind.
#
# The rulesets created here cover refs/heads/main and refs/heads/dev. Nothing
# covers feat/**, and .github/workflows/ci.yml triggers on `push` to feat/**.
# So a commit on any feature branch that adds a workflow job with
# `runs-on: self-hosted` runs that job on web2, inside the owner's own network,
# at push time. No review, no pull request, no ruleset.
#
# tests/test_pipeline_contract.py has test_no_job_runs_on_the_self_hosted_runner
# and it does not prevent this. It detects it: the test runs in the `test` job
# of the same push, so it goes red minutes after the job it objects to has
# already finished. No required status check can help either, because a
# required check gates a merge and the workflow starts before any check does.
#
# What that job can do was measured on 2026-08-21. The runner's user is in the
# docker group, `docker run -v /:/host` then reads /etc/shadow, and membership
# of that group is root on the host by design. One push is root on the LXC.
#
# The two controls that would actually work:
#
#   1. Restrict which workflows may use the runner. GitHub can scope a
#      self-hosted runner group to selected repositories and selected
#      workflows; pointing the runner group at .github/workflows/deploy.yml
#      alone means a workflow added on a feature branch has nothing to run on.
#      This is the one that closes it, because it removes the runner from the
#      reach of a push rather than reporting afterwards that a push reached it.
#   2. Take the runner's user out of the docker group and give it a sudoers
#      rule for the fixed compose command line the deploy needs instead. Docker
#      group membership is unrestricted root; a sudoers entry naming the exact
#      command with no wildcard is not. This one does not stop a job running,
#      it bounds what the job can do when one does.
#
# Both are Stijn's to apply and neither is in this repository: the first is a
# setting in GitHub's runner group configuration, the second is a file on the
# LXC. Nothing here can create either one, and no test can assert that they are
# in place, so this comment is the whole of the control until they are.
# ---------------------------------------------------------------------------

set -euo pipefail

REPO="${1:-stijnvandepol/Ampeer}"

apply_ruleset() {
  local name="$1" payload="$2"
  local existing
  existing=$(gh api "repos/${REPO}/rulesets" --jq \
    ".[] | select(.name == \"${name}\") | .id" || true)
  if [ -n "${existing}" ]; then
    echo "updating ruleset ${name} (id ${existing})"
    gh api "repos/${REPO}/rulesets/${existing}" -X PUT --input - <<<"${payload}" >/dev/null
  else
    echo "creating ruleset ${name}"
    gh api "repos/${REPO}/rulesets" -X POST --input - <<<"${payload}" >/dev/null
  fi
}

# No required_linear_history, and merge commits are allowed. This reverses two
# earlier decisions, and the reason is worth writing down because the earlier
# ones looked right.
#
# Linear history was set first, which forced squash merges, which collapse every
# commit message into one. In this project the reasoning behind a correction
# lives in those messages, so rebase was allowed instead: same linear history,
# messages intact.
#
# That worked exactly once. dev is long lived and cannot be force pushed, quite
# rightly, so after a rebase merge it has to take main back to stay in step, and
# that back merge puts a merge commit in dev. GitHub then refuses to rebase dev
# onto main at all, and the only method left is the one that destroys the
# messages.
#
# Linear history on main and a protected long lived integration branch are not
# compatible without force pushes. Given the choice, the commit messages are
# worth more than the straight line: a merge commit per promotion keeps every
# message and marks where each promotion happened, which is more informative for
# a reader than either alternative.
# main: nothing lands here except through a green pull request. bypass_actors is
# empty on purpose, including for the repository owner. A rule with an exception
# for the only person who works on the project is not a rule.
#
# Deliberately NOT required here: `build` and `deploy` from
# .github/workflows/deploy.yml. Added 2026-08-21 with those two jobs, so that
# their absence reads as a decision rather than as an oversight.
#
# They cannot be required, in the strict sense. deploy.yml triggers on a tag and
# on nothing else, so neither job ever reports on a pull request, and a required
# check that never arrives is a pull request that waits forever. That is the
# same failure the first test in tests/test_pipeline_contract.py exists to
# catch, and it would be self-inflicted here.
#
# They should not be required even if they could. The tag is cut from a `main`
# that has already passed the seven checks below; the deploy runs afterwards and
# against a host. Requiring it would mean a failed deploy, for a reason as
# unrelated as the LXC being down or a variable missing from the env file on it,
# blocks every future merge to main until somebody re-runs it. That inverts the
# direction the gate is supposed to work in: these checks exist to keep bad code
# out of main, not to let a sick host stop good code from getting in.
#
# What does gate the deploy is elsewhere and is stronger: the `production`
# environment, whose review has to be given before the `deploy` job starts, and
# whose deployment branch policy is what decides which tags may reach it. Both
# are configured on the environment in repository settings, not in this script,
# because this script does not create environments and pretending otherwise
# would produce a file that looks like it configured something it did not.
apply_ruleset "protect-main" "$(cat <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true,
      "allowed_merge_methods": ["merge", "squash", "rebase"]
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false,
      "required_status_checks": [
        {"context": "quality", "integration_id": 15368},
        {"context": "test", "integration_id": 15368},
        {"context": "frontend-quality", "integration_id": 15368},
        {"context": "frontend-test", "integration_id": 15368},
        {"context": "dependencies", "integration_id": 15368},
        {"context": "sast", "integration_id": 15368},
        {"context": "secrets", "integration_id": 15368}
      ]
    }}
  ]
}
JSON
)"

# dev: you work here, so direct commits are allowed. What is forbidden is losing
# history, because that is the one mistake nothing else can undo.
#
# Deliberately no required_status_checks here. Tried on 2026-08-20 and reverted:
# a status check rule on a branch ruleset applies to direct pushes as well as to
# pull requests, so `git push origin dev` was rejected with "2 of 2 required
# status checks are expected". There is no setting that scopes it to pull
# requests only. Requiring checks on dev therefore means requiring a pull request
# for every commit, which is the workflow this branch exists to avoid. The gate
# that matters is on main.
apply_ruleset "protect-dev" "$(cat <<'JSON'
{
  "name": "protect-dev",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"}
  ]
}
JSON
)"

# Dependabot alerts and automated security fixes are off by default on a
# private repository, so .github/dependabot.yml alone does nothing. These are
# idempotent PUTs, the same contract as the rulesets above.
echo "enabling vulnerability alerts and automated security fixes"
gh api "repos/${REPO}/vulnerability-alerts" -X PUT
gh api "repos/${REPO}/automated-security-fixes" -X PUT

# Caps what GITHUB_TOKEN can do by default, so a compromised step starts from
# read rather than write. This does NOT enforce SHA pinning; see the next call.
echo "restricting default workflow token permissions to read"
gh api "repos/${REPO}/actions/permissions/workflow" -X PUT   -f default_workflow_permissions=read   -F can_approve_pull_request_reviews=false

# GitHub itself then refuses to run any action referenced by tag or branch, so
# the project's SHA-pinning rule stops depending on a test that happens to check
# it. tests/test_pipeline_contract.py stays as the local, faster copy.
echo "requiring SHA-pinned actions server side"
gh api "repos/${REPO}/actions/permissions" -X PUT   -F enabled=true -f allowed_actions=all -F sha_pinning_required=true

# The one gate this repository claims and cannot create.
#
# .github/workflows/deploy.yml says, in its own header, that `environment:
# production` makes "a tag push a request that waits for a review rather than a
# deploy". That is only true if the environment carries required reviewers, and
# that is a setting on the environment rather than anything in a file here.
# tests/test_deploy_workflow.py can assert the workflow names the environment
# and stops there, as its own docstring says.
#
# On 2026-09-13 the environment carried a branch policy and no reviewers, so
# `git push origin v0.3.0` went straight at the host with nobody asked. It
# stopped on the first digest check and touched nothing, which is a different
# control doing its job and not this one. The claim had been in the file since
# 2026-08-21 and nothing had ever looked.
#
# So this reports rather than sets. Creating the reviewer list would mean this
# script deciding who may approve a deploy, and that is the repository owner's
# choice about people; what it can do is refuse to let the question go
# unanswered by whoever runs it. Settings, Environments, production, Required
# reviewers is where it is set.
echo
echo "the production environment:"
if reviewers="$(gh api "repos/${REPO}/environments/production"   --jq '[.protection_rules[] | select(.type == "required_reviewers")
         | .reviewers[].reviewer.login // .reviewers[].reviewer.name] | join(", ")' 2>/dev/null)"; then
  if [ -n "${reviewers}" ]; then
    echo "  required reviewers: ${reviewers}"
  else
    echo "  NO REQUIRED REVIEWERS. A tag push deploys to the host with nobody asked." >&2
    echo "  deploy.yml's header says it waits for a review. Today it does not." >&2
    echo "  Set them at Settings > Environments > production > Required reviewers." >&2
  fi
else
  echo "  could not be read; check it by hand before trusting a tag push" >&2
fi

echo
echo "rulesets now on ${REPO}:"
gh api "repos/${REPO}/rulesets" --jq '.[] | "  \(.name): \(.enforcement)"'
