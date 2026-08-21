#!/usr/bin/env bash
# Create or update the branch rulesets for Ampeer. Idempotent: safe to re-run.
#
# The required checks below must match the job names in .github/workflows/ci.yml
# and .github/workflows/security.yml exactly. A renamed job produces a check that
# never arrives and a pull request that waits forever.
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

echo
echo "rulesets now on ${REPO}:"
gh api "repos/${REPO}/rulesets" --jq '.[] | "  \(.name): \(.enforcement)"'
