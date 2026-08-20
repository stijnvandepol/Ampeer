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
    {"type": "required_linear_history"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true,
      "allowed_merge_methods": ["squash", "merge"]
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false,
      "required_status_checks": [
        {"context": "quality"},
        {"context": "test"},
        {"context": "dependencies"},
        {"context": "sast"},
        {"context": "secrets"}
      ]
    }}
  ]
}
JSON
)"

# dev: you work here, so direct commits are allowed. What is forbidden is losing
# history, because that is the one mistake nothing else can undo.
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

echo
echo "rulesets now on ${REPO}:"
gh api "repos/${REPO}/rulesets" --jq '.[] | "  \(.name): \(.enforcement)"'
