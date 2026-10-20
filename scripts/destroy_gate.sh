#!/usr/bin/env bash
# Fails if the plan deletes or replaces anything, unless ALLOW_DESTROY=true.
set -euo pipefail
PLAN_JSON="${1:?usage: destroy_gate.sh tfplan.json}"
ALLOW="${ALLOW_DESTROY:-false}"

mapfile -t hits < <(jq -r '.resource_changes[]?
  | select(.change.actions | index("delete"))
  | "\(.change.actions | join("/"))\t\(.address)"' "$PLAN_JSON")

if (( ${#hits[@]} == 0 )); then
  echo "Destroy gate: no deletes or replacements."
  exit 0
fi

printf 'Destroy gate: %d resource(s) would be deleted or replaced:\n' "${#hits[@]}"
printf '  %s\n' "${hits[@]}"

if [[ "$ALLOW" == "true" ]]; then
  echo "::warning::allow-destroy label present; proceeding."
  exit 0
fi
echo "::error::Plan deletes resources. Add the 'allow-destroy' label to the PR if this is intended."
exit 1