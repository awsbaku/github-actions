# Plan: Live Hackathon Leaderboard

## Context

The evaluation pipeline is complete and tested. Teams get scored on PRs via Claude Code Actions, with results posted as PR comments and saved as artifacts. The missing piece is a **live leaderboard** that aggregates scores across all teams and displays rankings in real-time.

## Architecture: S3 + Lambda + DynamoDB Hybrid

```
GitHub Actions (eval workflow)
    | POST eval_result.json
    v
Lambda Function URL (receiver)
    |-- Validate JSON against schema
    |-- Write raw eval --> DynamoDB (history table)
    |-- Compute aggregated leaderboard.json
    +-- Write leaderboard.json --> S3
            |
    CloudFront (30s TTL)
            |
    Frontend (polls every 30s)
```

### Why This Approach

| Option | Verdict |
|--------|---------|
| Pure S3 (JSON files) | Works but no query capability, race conditions on concurrent writes |
| DynamoDB only | Overkill -- need API Gateway for reads, adds cost |
| ElastiCache/Redis | Too expensive for this scale (~$15/month minimum) |
| AppSync + DynamoDB | Real-time subscriptions unnecessary -- evals happen every 6h |
| **S3 + Lambda + DynamoDB** | **Best fit -- simple, cheap, reuses existing infra** |

### Cost Estimate

Under **$0.10/month** for 20 teams x 4 evals/day x 30 days:
- Lambda: ~2,400 invocations/month (free tier covers 1M)
- DynamoDB: ~2,400 writes + reads (free tier covers 25 WCU/RCU)
- S3: negligible (single JSON file overwritten)
- CloudFront: already provisioned

## DynamoDB Table Design

**Table: `hackathon-scores`**

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

**Runtime:** Python 3.12
**Trigger:** Function URL (no API Gateway needed)
**IAM:** DynamoDB read/write + S3 PutObject

### Logic

1. Receive POST with `eval_result.json` payload
2. Validate against `schemas/eval-output.schema.json`
3. Write raw eval to DynamoDB (`hackathon-scores` table)
4. Query all teams' latest scores from DynamoDB
5. Apply aggregation rules (diminishing returns for PR count, time decay)
6. Generate `leaderboard.json` with rankings
7. Upload to S3 bucket (served via CloudFront)

### Aggregation Rules

From CLAUDE.md:
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

## Workflow Integration

Add a step to `evaluate-prs.yml` after score posting:

```yaml
- name: Submit score to leaderboard
  if: steps.verify.outputs.valid == 'true'
  env:
    LEADERBOARD_URL: ${{ vars.LEADERBOARD_URL }}
  run: |
    if [ -n "$LEADERBOARD_URL" ]; then
      curl -s -X POST "$LEADERBOARD_URL" \
        -H "Content-Type: application/json" \
        -d @eval_result.json
    fi
```

## Terraform Resources

All infrastructure in `terraform/modules/leaderboard/`:

| Resource | Purpose |
|----------|---------|
| `aws_dynamodb_table.scores` | Store eval history |
| `aws_lambda_function.receiver` | Process incoming evals |
| `aws_lambda_function_url.receiver` | Public HTTP endpoint |
| `aws_iam_role.lambda` | Lambda execution role |
| `aws_s3_object.leaderboard` | Initial empty leaderboard.json |
| `aws_cloudfront_*` | Reuse existing distribution (add origin) |

## Implementation Steps

1. **Terraform module** -- Lambda + DynamoDB table + S3 bucket policy + Function URL
2. **Lambda function** (Python) -- receives POST, validates, writes DynamoDB, generates `leaderboard.json`, uploads to S3
3. **Update evaluate-prs.yml** -- add `curl` step after score posting to POST eval JSON to Lambda URL
4. **Set org variable** -- `LEADERBOARD_URL` pointing to Lambda Function URL
5. **Frontend** -- simple static page reading `leaderboard.json` from CloudFront
6. **Test** -- trigger eval on test repos, verify leaderboard updates

## Frontend (Minimal)

Static HTML + vanilla JS (or add to existing `public-frontend`):
- Fetch `leaderboard.json` from CloudFront every 30 seconds
- Render sortable table with team rankings
- Show dimension breakdown on row expand
- Highlight score changes with animations
- Mobile-responsive

## Status

- [x] Evaluation pipeline working end-to-end
- [x] Anti-gaming protections tested (prompt injection, multi-PR, protected files)
- [x] Schema aligned with Claude output
- [x] All changes synced to template and test repos
- [ ] Terraform module for leaderboard infra
- [ ] Lambda function implementation
- [ ] Workflow integration (curl step)
- [ ] Frontend leaderboard page
- [ ] End-to-end leaderboard test
