# Plan: Live Hackathon Leaderboard

## Context

The evaluation pipeline is complete and tested. Teams get scored on PRs via Claude Code Actions, with results posted as PR comments and saved as artifacts. The missing piece is a **live leaderboard** that aggregates scores across all teams and displays rankings.

## Architecture (Revised)

```
GitHub Actions (eval workflow)
    | POST eval_result.json (SigV4-signed via OIDC role)
    v
Lambda Function URL (IAM auth)
    |-- Validate JSON
    |-- Write raw eval --> DynamoDB (history/audit)
    |-- Query all teams' latest scores
    |-- Compute aggregated leaderboard.json
    +-- Write leaderboard.json --> existing S3 bucket (public-frontend)
                                       |
                              CloudFront (existing distribution)
                                       |
                              React app at /hackathon-leaderboard route
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth | Lambda Function URL with IAM auth | Reuses existing OIDC role, no API keys |
| Storage | DynamoDB for history, S3 for rendered JSON | Full audit trail + zero-cost static serving |
| Frontend | React route in existing `public-frontend` | No new CloudFront distribution needed |
| S3 target | Same bucket as `public-frontend` | Lambda writes to `hackathon-leaderboard/` prefix |
| CloudFront | No changes to `cloudfront-app` module | SPA error responses already serve index.html for all paths |

### Why No CloudFront Changes Needed

The existing `cloudfront-app` module has `spa_error_responses = true` which returns `index.html` for 403/404. When a browser hits `/hackathon-leaderboard`, CloudFront returns the React SPA, which handles routing client-side. The React app then fetches `leaderboard.json` from the same bucket via a known path.

### Cost Estimate

Under **$0.10/month** for 20 teams x 4 evals/day x 30 days:
- Lambda: ~2,400 invocations/month (free tier covers 1M)
- DynamoDB: ~2,400 writes + reads (free tier covers 25 WCU/RCU)
- S3: negligible (single JSON file overwritten in existing bucket)
- CloudFront: already provisioned

## DynamoDB Table Design

**Table: `<name_prefix>-hackathon-scores`**

| Key | Type | Purpose |
|-----|------|---------|
| PK: `TEAM#<slug>` | String | Partition key |
| SK: `PR#<number>#<timestamp>` | String | Sort key -- allows multiple evals per PR |
| `overall_score` | Number | For GSI queries |
| `dimensions` | Map | Full dimension scores |
| `eval_json` | String | Raw eval result |
| `team_name` | String | Display name |
| `pr_number` | Number | PR number |
| `timestamp` | String | ISO 8601 eval timestamp |

**GSI: `leaderboard-index`**
- PK: `HACKATHON` (constant string), SK: `overall_score` (descending)
- Enables single-query leaderboard fetch

## Lambda Function

**Runtime:** Python 3.13
**Trigger:** Function URL (authorization_type = AWS_IAM)
**IAM:** DynamoDB read/write + S3 PutObject on existing bucket

### Logic

1. Receive POST with `eval_result.json` payload (SigV4-signed)
2. Validate JSON structure
3. Write raw eval to DynamoDB (`hackathon-scores` table)
4. Query all teams' latest scores from DynamoDB
5. Apply aggregation rules (diminishing returns for PR count, time decay)
6. Generate `leaderboard.json` with rankings
7. Upload to S3 bucket at `hackathon-leaderboard/leaderboard.json`

### Aggregation Rules

- PRs 1-5: full credit (1.0x)
- PRs 6-10: 80% credit (0.8x)
- PRs 11+: 50% credit (0.5x)

Time decay:
- First 50% of hackathon: 1.0x
- 50-75%: 0.95x
- 75-90%: 0.90x
- Final 10%: 0.75x

### leaderboard.json Format

```json
{
  "updated_at": "2026-03-05T12:00:00Z",
  "hackathon": {
    "start": "2026-03-10T09:00:00Z",
    "end": "2026-03-10T21:00:00Z"
  },
  "rankings": [
    {
      "rank": 1,
      "team": "Team Alpha",
      "repo": "awsbaku/test-team-alpha",
      "cumulative_score": 7.2,
      "pr_count": 3,
      "latest_eval": {
        "overall_score": 7.8,
        "dimensions": {
          "functional_value": 8,
          "aws_integration": 7,
          "innovation": 8,
          "code_quality": 7,
          "documentation": 9
        }
      },
      "trend": "up"
    }
  ]
}
```

## Terraform Module: `modules/hackathon-leaderboard`

Located in `awsbaku/terraform-infrastructure` repo, following existing patterns.

### Resources

| Resource | Purpose |
|----------|---------|
| `aws_dynamodb_table.scores` | Store eval history |
| `aws_lambda_function.receiver` | Process incoming evals |
| `aws_lambda_function_url.receiver` | IAM-authed HTTP endpoint |
| `aws_iam_role.lambda` | Lambda execution role (DynamoDB + S3) |
| `aws_cloudwatch_log_group.lambda` | Lambda logs with retention |

### Module Interface

```hcl
# Inputs
variable "name_prefix"      # e.g. "awsbaku-infrastructure-org"
variable "s3_bucket_name"    # existing public-frontend bucket
variable "s3_bucket_arn"     # for IAM policy
variable "s3_leaderboard_prefix" # default: "hackathon-leaderboard"
variable "hackathon_start"   # ISO 8601
variable "hackathon_end"     # ISO 8601

# Outputs
output "function_url"        # Lambda Function URL (for GHA workflow)
output "dynamodb_table_name" # For debugging/queries
output "lambda_role_arn"     # For OIDC policy if needed
```

### Environment Wiring (main.tf)

```hcl
module "hackathon_leaderboard" {
  source = "../../modules/hackathon-leaderboard"

  name_prefix    = local.name_prefix
  s3_bucket_name = module.cloudfront_app_public_frontend.s3_bucket_name
  s3_bucket_arn  = module.cloudfront_app_public_frontend.s3_bucket_arn
}
```

### GHA OIDC Role Update

The existing `gha_oidc` role needs `lambda:InvokeFunctionUrl` permission so GitHub Actions can POST to the Lambda. Add the leaderboard Lambda ARN to the OIDC module.

## Workflow Integration

Add a step to `evaluate-prs.yml` after score posting:

```yaml
- name: Submit score to leaderboard
  if: steps.verify.outputs.valid == 'true'
  env:
    LEADERBOARD_URL: ${{ vars.LEADERBOARD_URL }}
  run: |
    if [ -n "$LEADERBOARD_URL" ]; then
      aws lambda invoke-function-url \
        --url "$LEADERBOARD_URL" \
        --http-method POST \
        --body fileb://eval_result.json
    fi
```

Uses `aws lambda invoke-function-url` which automatically signs with the assumed OIDC role credentials.

## Implementation Steps

1. **Terraform module** (`modules/hackathon-leaderboard`) -- Lambda + DynamoDB + Function URL + IAM
2. **Lambda function** (Python, bundled in module) -- receives POST, validates, writes DynamoDB, generates leaderboard.json, uploads to S3
3. **Wire in environment** (`environments/infrastructure-org/main.tf`) -- instantiate module with existing bucket outputs
4. **Update OIDC role** -- add `lambda:InvokeFunctionUrl` for the new Lambda
5. **terraform plan** -- review and apply
6. **Update evaluate-prs.yml** -- add leaderboard submission step
7. **Set org variable** -- `LEADERBOARD_URL` pointing to Lambda Function URL
8. **Frontend** -- add `/hackathon-leaderboard` route in React app
9. **Test** -- trigger eval on test repos, verify leaderboard updates

## Status

- [x] Evaluation pipeline working end-to-end
- [x] Anti-gaming protections tested (prompt injection, multi-PR, protected files)
- [x] Schema aligned with Claude output
- [x] All changes synced to template and test repos
- [ ] Terraform module for leaderboard infra
- [ ] Lambda function implementation
- [ ] Wire module in environment + terraform apply
- [ ] Update OIDC role for Lambda invoke
- [ ] Workflow integration (aws lambda invoke-function-url step)
- [ ] Frontend leaderboard route in React app
- [ ] End-to-end leaderboard test
