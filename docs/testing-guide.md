# End-to-End Testing Guide (Admin/Ops)

This guide walks through the full process of provisioning test team repos, writing test code, running evaluations, and verifying scores land on the leaderboard. Follow these steps to validate the entire pipeline before the hackathon.

## Prerequisites

- `gh` CLI authenticated with the `awsbaku` org (admin access)
- AWS CLI configured (e.g., `export AWS_PROFILE=tarlan`)
- Infrastructure deployed via Terraform:
  - IAM OIDC role with org-wide access (`repo:awsbaku/*:*`)
  - Leaderboard Lambda + DynamoDB table
  - S3 bucket + CloudFront (dual-origin: versioned SPA + root for leaderboard data)

## 1. Secrets and Variables Reference

### Org-level secrets

| Secret | Purpose | How to set |
|--------|---------|------------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude API auth for evaluations | `gh secret set CLAUDE_CODE_OAUTH_TOKEN --org awsbaku --visibility all` |
| `AWS_ROLE_ARN` | IAM role for OIDC (leaderboard submission) | `gh secret set AWS_ROLE_ARN --org awsbaku --visibility all --body "<arn>"` |

> **GitHub Free limitation:** Org secrets with "all" visibility may not propagate to private repos. Set them at the repo level too (see step 2).

### Repo-level variables (per team repo)

| Variable | Example | Set by |
|----------|---------|--------|
| `TEAM_NAME` | `Team Alpha` | `provision-team.sh` |
| `TEAM_SIZE` | `3` | `provision-team.sh` |
| `EVAL_ADMINS` | `["tarlan-huseynov"]` | `provision-team.sh` |
| `LEADERBOARD_FUNCTION` | `awsbaku-infrastructure-org-leaderboard` | `provision-team.sh` or manual |

### Verify what's configured

```bash
# Org secrets (names + visibility only)
gh api orgs/awsbaku/actions/secrets --jq '.secrets[] | "\(.name) → \(.visibility)"'

# Repo secrets (names only — values are hidden)
gh api repos/awsbaku/<team-slug>/actions/secrets --jq '.secrets[].name'

# Repo variables (names + values)
gh variable list --repo awsbaku/<team-slug>

# IAM OIDC trust policy
aws iam get-role --role-name awsbaku-infrastructure-org-gha-deploy \
  --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition' --output json
```

## 2. Provision a Test Team Repo

```bash
./scripts/provision-team.sh <team-slug> "<team-name>" <team-size>

# Examples:
./scripts/provision-team.sh test-team-alpha "Test Team Alpha" 3
./scripts/provision-team.sh test-team-beta "Test Team Beta" 2
./scripts/provision-team.sh test-team-gamma "Test Team Gamma" 2
```

The script:
1. Creates `awsbaku/<team-slug>` from `awsbaku/template-team-project`
2. Creates `development` branch from `main`
3. Sets `development` as default branch
4. Sets variables: `TEAM_NAME`, `TEAM_SIZE`, `EVAL_ADMINS`, `LEADERBOARD_FUNCTION`

### Post-provision: set secrets manually

On GitHub Free with private repos, org secrets don't propagate. Set them per repo:

```bash
# Claude auth (will prompt for the token value)
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo awsbaku/<team-slug>

# IAM role ARN
gh secret set AWS_ROLE_ARN --repo awsbaku/<team-slug> \
  --body "$(aws iam get-role --role-name awsbaku-infrastructure-org-gha-deploy --query 'Role.Arn' --output text)"
```

If `LEADERBOARD_FUNCTION` wasn't set automatically:
```bash
gh variable set LEADERBOARD_FUNCTION --repo awsbaku/<team-slug> \
  --body "awsbaku-infrastructure-org-leaderboard"
```

### Disable cron on test repos

The template has a 6-hour cron schedule. Disable it on test repos to avoid unnecessary runs.

**Important:** Edit on the `main` branch — `pull_request` triggers use the workflow from the base branch.

```bash
gh repo clone awsbaku/<team-slug> /tmp/<team-slug>
cd /tmp/<team-slug>

# Disable on main
git checkout main
# In .github/workflows/eval.yml, change:
#   schedule:
#     - cron: "0 */6 * * *"
# To:
#   # schedule:
#   #   - cron: "0 */6 * * *"
git add .github/workflows/eval.yml
git commit -m "Disable cron schedule for test repo"
git push origin main

# Also disable on development
git checkout development
# Same edit
git add .github/workflows/eval.yml
git commit -m "Disable cron schedule for test repo"
git push origin development
```

## 3. Write Test Code and Open PRs

Push code to `development`, then open a PR targeting `main`.

### Test quality tiers

| Tier | Expected score | Characteristics |
|------|---------------|-----------------|
| High (alpha) | 7-8/10 | Working Bedrock app, error handling, good README, descriptive commits |
| Medium (gamma) | 5-6/10 | Functional but minimal, basic README, simple code |
| Low (beta) | 3-4/10 | Stub code, no error handling, unfilled README template, vague commits |

### Push code and open PR

```bash
cd /tmp/<team-slug>
git checkout development

# ... write your test code ...

git add -A
git commit -m "Add Bedrock document Q&A agent with streaming"
git push origin development

gh pr create --repo awsbaku/<team-slug> \
  --base main --head development \
  --title "Feature: Bedrock document Q&A agent" \
  --body "## Summary
- What the code does
- AWS services used
## Testing
- How to run it"
```

## 4. Trigger Evaluations

### Via PR event (automatic)
Opening a PR to `main` auto-triggers the eval. Uses `eval.yml` from the `main` branch.

### Via workflow_dispatch (manual)
```bash
# Single repo
gh workflow run eval.yml --repo awsbaku/<team-slug>

# All test repos at once
gh workflow run eval.yml --repo awsbaku/test-team-alpha && \
gh workflow run eval.yml --repo awsbaku/test-team-beta && \
gh workflow run eval.yml --repo awsbaku/test-team-gamma
```

Only users in `EVAL_ADMINS` can trigger manual runs.

## 5. Monitor Runs

```bash
# List recent runs
gh run list --repo awsbaku/<team-slug> --limit 3

# Detailed view of a run
gh run view <run-id> --repo awsbaku/<team-slug>

# Failed step logs
gh run view <run-id> --repo awsbaku/<team-slug> --log-failed

# Monitor all 3 test repos at once
for repo in test-team-alpha test-team-beta test-team-gamma; do
  echo "--- $repo ---"
  gh run list --repo awsbaku/$repo --limit 1
done
```

### Pipeline steps and what can go wrong

| Step | Duration | Common failures |
|------|----------|----------------|
| Discover Open PRs | ~5s | No open PRs → eval skipped |
| Checkout repos | ~5s | Repo access issues |
| Collect PR metadata | ~5s | Empty diff, PR not found |
| **Run Claude evaluation** | **2-3 min** | Missing `CLAUDE_CODE_OAUTH_TOKEN` |
| Verify eval result | ~1s | Claude didn't write `eval_result.json` |
| Post score to PR | ~2s | — |
| Configure AWS credentials | ~3s | Missing `AWS_ROLE_ARN`, OIDC trust policy doesn't include repo |
| **Submit to leaderboard** | ~3s | Missing `LEADERBOARD_FUNCTION`, IAM missing `lambda:InvokeFunction` |
| Save artifact | ~3s | — |

## 6. Verify Results

### PR comment
```bash
# Latest comment on a PR (the score)
gh pr view <pr-number> --repo awsbaku/<team-slug> --json comments --jq '.comments[-1].body'
```

Expected output: formatted score table with overall score, per-dimension breakdown, penalties, reasoning, and summary.

### Eval artifact
```bash
gh run download <run-id> --repo awsbaku/<team-slug>
cat eval-pr-<number>/eval_result.json | python3 -m json.tool
cat eval-pr-<number>/pr_context.json | python3 -m json.tool
```

### Leaderboard JSON in S3
```bash
aws s3 cp s3://awsbaku-infrastructure-org-public-frontend/hackathon-leaderboard/leaderboard.json - \
  | python3 -m json.tool
```

Verify:
- All teams are present with correct names
- `cumulative_score` reflects the eval results
- `latest_eval.dimensions` has all 5 dimension scores
- `trend` is `stable` (first eval), `up`, or `down`
- `rank` is ordered by `cumulative_score` descending

### DynamoDB records
```bash
aws dynamodb scan --table-name awsbaku-infrastructure-org-hackathon-scores \
  --projection-expression "PK, SK, team_name, overall_score, pr_number" \
  --output table
```

### Live leaderboard UI
Visit https://www.awsbaku.tech/hackathon-leaderboard

- Data auto-refreshes every 30 seconds
- Click a team row to expand dimension breakdown
- Verify scores, ranks, and trend arrows match the data

## 7. Troubleshooting

### "Workflow file issue" on PR trigger
The reusable workflow has a YAML syntax error. Validate:
```bash
actionlint .github/workflows/evaluate-prs.yml
```
Common cause: duplicate YAML keys (e.g., two `env:` blocks on the same step).

### "ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN is required"
Secret isn't reaching the repo. Set it at the repo level:
```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo awsbaku/<team-slug>
```

### "Not authorized to perform sts:AssumeRoleWithWebIdentity"
OIDC trust policy doesn't include the repo. The policy should have:
```json
"token.actions.githubusercontent.com:sub": "repo:awsbaku/*:*"
```
Fix in Terraform: ensure `org_wide_access = true` in the `gha-oidc` module, then `terraform apply`.

### Lambda returns `{"error": "Invalid JSON"}`
The Lambda couldn't parse the payload. When using `aws lambda invoke`, the payload goes directly as the event (not wrapped in `event['body']`). The Lambda handler supports both formats — if this error appears, check that `eval_result.json` is valid:
```bash
gh run download <run-id> --repo awsbaku/<team-slug>
python3 -m json.tool eval-pr-*/eval_result.json
```

### Lambda returns `{"error": "Missing fields: [...]"}`
The eval result JSON doesn't have the expected fields. Required: `team`, `repo`, `pr_number`, `overall_score`, `dimensions`. Check the Claude output in the artifact.

### Leaderboard shows stale data
- CloudFront caches leaderboard.json for 30 seconds. Wait or invalidate:
  ```bash
  aws cloudfront create-invalidation \
    --distribution-id E2ZVXO3H5DKFUO \
    --paths "/hackathon-leaderboard/*"
  ```
- Verify Lambda wrote to S3: check the `aws s3 cp` command above.

### Pipeline succeeds but leaderboard not updated
Check that all 3 pieces are in place:
```bash
# 1. Secret exists?
gh api repos/awsbaku/<team-slug>/actions/secrets --jq '.secrets[].name' | grep AWS_ROLE_ARN

# 2. Variable exists?
gh variable get LEADERBOARD_FUNCTION --repo awsbaku/<team-slug>

# 3. IAM policy allows lambda:InvokeFunction?
aws iam get-role-policy \
  --role-name awsbaku-infrastructure-org-gha-deploy \
  --policy-name awsbaku-infrastructure-org-gha-deploy-deploy-policy \
  --query 'PolicyDocument.Statement[?Sid==`LambdaInvoke`]'
```

## 8. Cleanup

### Delete test repos
```bash
gh repo delete awsbaku/test-team-alpha --yes
gh repo delete awsbaku/test-team-beta --yes
gh repo delete awsbaku/test-team-gamma --yes
```

### Clear DynamoDB test data
```bash
# Scan for all test items
aws dynamodb scan \
  --table-name awsbaku-infrastructure-org-hackathon-scores \
  --filter-expression "begins_with(PK, :prefix)" \
  --expression-attribute-values '{":prefix": {"S": "TEAM#test-"}}' \
  --projection-expression "PK, SK" \
  --output json | jq '.Items[]'

# Delete each item (replace PK and SK values)
aws dynamodb delete-item \
  --table-name awsbaku-infrastructure-org-hackathon-scores \
  --key '{"PK": {"S": "TEAM#test-team-alpha"}, "SK": {"S": "<sk-value>"}}'
```

### Reset leaderboard.json to empty
```bash
echo '{"updated_at":"","hackathon":{"start":"","end":""},"rankings":[]}' | \
  aws s3 cp - s3://awsbaku-infrastructure-org-public-frontend/hackathon-leaderboard/leaderboard.json \
  --content-type application/json --cache-control "max-age=30"
```

## 9. Quick Reference: Full Test Run

```bash
# 1. Provision
./scripts/provision-team.sh test-team-foo "Test Team Foo" 3

# 2. Secrets (GitHub Free + private repo)
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo awsbaku/test-team-foo
gh secret set AWS_ROLE_ARN --repo awsbaku/test-team-foo \
  --body "$(aws iam get-role --role-name awsbaku-infrastructure-org-gha-deploy \
    --query 'Role.Arn' --output text)"

# 3. Leaderboard function (if not set by provision script)
gh variable set LEADERBOARD_FUNCTION --repo awsbaku/test-team-foo \
  --body "awsbaku-infrastructure-org-leaderboard"

# 4. Clone, disable cron, write code, push, open PR
gh repo clone awsbaku/test-team-foo /tmp/test-team-foo
cd /tmp/test-team-foo
git checkout main
# ... disable cron in .github/workflows/eval.yml ...
git add . && git commit -m "Disable cron" && git push origin main
git checkout development
# ... write test code ...
git add -A && git commit -m "Add Bedrock feature" && git push origin development
gh pr create --base main --head development \
  --title "Feature: Bedrock app" --body "Description of the feature"

# 5. Trigger evaluation
gh workflow run eval.yml --repo awsbaku/test-team-foo

# 6. Monitor
gh run list --repo awsbaku/test-team-foo --limit 1
gh run view <run-id> --repo awsbaku/test-team-foo

# 7. Verify
gh pr view <pr-number> --repo awsbaku/test-team-foo \
  --json comments --jq '.comments[-1].body'
aws s3 cp s3://awsbaku-infrastructure-org-public-frontend/hackathon-leaderboard/leaderboard.json - \
  | python3 -m json.tool

# 8. Cleanup
gh repo delete awsbaku/test-team-foo --yes
```
