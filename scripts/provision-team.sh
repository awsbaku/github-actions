#!/usr/bin/env bash
set -euo pipefail

# Provision a team repo from the template
# Usage: ./scripts/provision-team.sh <team-slug> <team-name> <team-size>
# Example: ./scripts/provision-team.sh test-team-alpha "Test Team Alpha" 3

ORG="awsbaku"
TEMPLATE="awsbaku/template-team-project"

SLUG="${1:?Usage: $0 <team-slug> <team-name> <team-size>}"
TEAM_NAME="${2:?Usage: $0 <team-slug> <team-name> <team-size>}"
TEAM_SIZE="${3:?Usage: $0 <team-slug> <team-name> <team-size>}"

REPO="$ORG/$SLUG"

echo "=== Provisioning $REPO ==="

# 1. Create repo from template
echo "[1/5] Creating repo from template..."
gh repo create "$REPO" --template "$TEMPLATE" --private

# 2. Wait for GitHub to finish generating from template
echo "[2/5] Waiting for repo to be ready..."
MAIN_SHA=""
for i in $(seq 1 30); do
  # Check if template generation is complete
  IS_GENERATING=$(gh api "repos/$REPO" --jq '.template_repository // empty' 2>/dev/null || echo "waiting")
  SHA_CANDIDATE=$(gh api "repos/$REPO/git/ref/heads/main" --jq '.object.sha' 2>/dev/null || echo "")

  # SHA must be exactly 40 hex chars
  if echo "$SHA_CANDIDATE" | grep -qE '^[0-9a-f]{40}$'; then
    MAIN_SHA="$SHA_CANDIDATE"
    echo "  Repo ready (main SHA: ${MAIN_SHA:0:7})"
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 3
done

if [ -z "$MAIN_SHA" ]; then
  echo "ERROR: Timed out waiting for repo to be ready"
  exit 1
fi

# 3. Create development branch from main (shared history for PRs)
echo "[3/5] Creating development branch from main..."
gh api "repos/$REPO/git/refs" \
  -f ref="refs/heads/development" \
  -f sha="$MAIN_SHA" \
  --silent

# 4. Set development as default branch
echo "[4/5] Setting development as default branch..."
gh api "repos/$REPO" -X PATCH \
  -f default_branch=development \
  --silent

# 5. Set repo variables
echo "[5/6] Setting repo variables..."
gh variable set TEAM_NAME --repo "$REPO" --body "$TEAM_NAME"
gh variable set TEAM_SIZE --repo "$REPO" --body "$TEAM_SIZE"

# 6. Set EVAL_ADMINS (org vars don't reach private repos on Free plan)
echo "[6/6] Setting EVAL_ADMINS..."
ADMINS=$(gh variable get EVAL_ADMINS --org "$ORG" 2>/dev/null || echo '["tarlan-huseynov"]')
gh variable set EVAL_ADMINS --repo "$REPO" --body "$ADMINS"

echo ""
echo "=== Done ==="
echo "Repo:        https://github.com/$REPO"
echo "Team:        $TEAM_NAME ($TEAM_SIZE members)"
echo "Branches:    main (eval target), development (default)"
echo "Variables:   TEAM_NAME=$TEAM_NAME, TEAM_SIZE=$TEAM_SIZE, EVAL_ADMINS=$ADMINS"
