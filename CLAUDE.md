# CLAUDE.md — hackathon-judge

Automated AI-powered code evaluation system for AWS hackathons using Claude Code Actions in GitHub Actions.

## Project Purpose

Score hackathon team PRs on a 0-10 scale multiple times per day using Claude as an AI judge. Results feed into a leaderboard. Designed for an AWS Bedrock-focused hackathon with ~20 teams, each in their own repo.

## Architecture

```
                    ┌──────────────────────────────────┐
                    │   Central Repo (this repo)       │
                    │   awsbaku/github-actions          │
                    │                                   │
                    │  .github/workflows/               │
                    │    evaluate-prs.yml  (reusable)   │
                    │  prompts/                         │
                    │    aws-bedrock.md (+ more themes) │
                    │  schemas/                         │
                    │    eval-output.schema.json        │
                    │  scripts/                         │
                    │    post_score.py                  │
                    └──────────┬────────────────────────┘
                               │ workflow_call
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼───────┐  ┌────────▼──────┐  ┌──────────▼────┐
  │ team-alpha/   │  │ team-beta/    │  │ team-gamma/   │
  │ .github/      │  │ .github/      │  │ .github/      │
  │  workflows/   │  │  workflows/   │  │  workflows/   │
  │   eval.yml    │  │   eval.yml    │  │   eval.yml    │
  │  (caller)     │  │  (caller)     │  │  (caller)     │
  └───────────────┘  └───────────────┘  └───────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │ POST JSON
                    ┌──────────▼───────────────────────┐
                    │   Leaderboard API / S3 bucket     │
                    │   scores/{team}/pr-{n}.json       │
                    │   leaderboard.json (aggregated)   │
                    └──────────────────────────────────┘
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Distribution model | Reusable workflow (`workflow_call`) | `secrets: inherit` passes org secrets to all team repos without per-repo config |
| Claude integration | `anthropics/claude-code-action@v1` in agent mode | Scheduled runs have no PR event context; agent mode with `prompt:` lets us inject diff + metadata |
| Structured output | `--output-format json` in `claude_args` | Captures JSON scoring result from `structured_output` action output |
| PR discovery | `gh pr list` matrix job | Fan out evaluation per-PR with `max-parallel: 3` to respect rate limits |
| Scoring rubric | 5 dimensions, weighted, 0-10 each | See `prompts/aws-bedrock.md` for full rubric |
| Prompt templates | Theme-selectable via `hackathon_theme` input | Each hackathon gets its own rubric file in `prompts/` |
| Anti-gaming | Separate detection pass with penalty flags | Catches trivial commits, boilerplate dumps, credential leaks |
| Score delivery | PR comment + POST to leaderboard endpoint | Teams see scores inline; leaderboard aggregates centrally |
| Model | `claude-sonnet-4-6` for eval passes, `claude-opus-4-6` for final judging | Cost/quality tradeoff; Sonnet is sufficient for structured rubric scoring |
| Auth | Anthropic API key (not OAuth) | Simpler for org-wide deployment; OAuth requires per-user setup |

## Scoring Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Functional Value | 30% | Does the code solve a real problem? Working features vs stubs |
| AWS/Bedrock Integration | 25% | Quality and depth of AWS service usage |
| Innovation & Creativity | 20% | Novel approaches vs tutorial copies |
| Code Quality | 15% | Readability, structure, error handling, security |
| Documentation | 10% | README, comments, PR descriptions |

Overall = weighted average - anti-gaming penalties, clamped to [0, 10].

## Anti-Gaming Flags

| Flag | Trigger | Penalty |
|------|---------|---------|
| `whitespace_padding` | >80% of changes are whitespace/blank lines | -0.5 |
| `trivial_commit` | Back-and-forth renames, no-op changes | -0.3 each |
| `boilerplate_dump` | >200 lines of unmodified framework scaffold | -1.0 to Innovation |
| `code_dump` | Single commit >1000 lines + bad commit message | -0.5 to Functional |
| `hardcoded_credentials` | AWS keys, secrets in code | -2.0 overall |
| `low_commit_quality` | All commit messages non-descriptive | Informational |
| `suspected_generated_dump` | Large code, empty PR description | Informational |

## File Structure

```
github-actions/
├── CLAUDE.md                              # This file
├── .github/
│   └── workflows/
│       └── evaluate-prs.yml               # Reusable workflow (workflow_call)
├── prompts/
│   ├── README.md                          # How to create new themes
│   └── aws-bedrock.md                     # AWS Bedrock hackathon rubric (default)
├── schemas/
│   └── eval-output.schema.json            # JSON schema for structured output
├── scripts/
│   └── post_score.py                      # Format + post score as PR comment
└── templates/
    └── team-caller-workflow.yml            # Template for each team repo's workflow
```

## Rate Limits & Parallelism

- Tier 1 Anthropic API: 50 RPM, 30k input tokens/min
- Each eval is multi-turn (~5 API calls internally)
- Strategy: `max-parallel: 3` per repo + stagger cron schedules across repos
- 20 repos staggered in 4 groups (5 repos per hour offset)
- **Recommendation**: upgrade to Tier 2 ($40+ cumulative) for 1000 RPM before hackathon

## Hackathon Setup Checklist

1. Create this repo as `awsbaku/github-actions` on GitHub
2. Set org-level secrets: `ANTHROPIC_API_KEY`
3. Set org-level variables: `HACKATHON_START_TIME`, `HACKATHON_END_TIME`, `LEADERBOARD_URL`
4. Per team repo: add `TEAM_NAME` and `TEAM_SIZE` as repo variables
5. Per team repo: copy `templates/team-caller-workflow.yml` to `.github/workflows/eval.yml`
6. Set up leaderboard endpoint (S3 bucket or API) to receive POST requests
7. Calibrate: run against 3-4 sample PRs and verify scores match expectations
8. Set `hackathon_theme` in team caller workflows (default: `aws-bedrock`)
9. Adjust rubric weights in the prompt template if needed (see `prompts/README.md`)

## Development Commands

```bash
# Validate workflow syntax
actionlint .github/workflows/evaluate-prs.yml

# Validate JSON schema
python3 -m json.tool schemas/eval-output.schema.json

# Test score posting script locally
python3 scripts/post_score.py --dry-run --input sample-eval.json

# Test the full flow via workflow_dispatch
gh workflow run evaluate-prs.yml --repo awsbaku/github-actions -f pr_number=1 -f team_repo=awsbaku/team-alpha
```

## Key Technical Notes from Prior Work

These insights come from building the Claude Code review workflow for `awsbaku/public-frontend`:

- **Agent mode vs Tag mode**: Setting `prompt:` input activates agent mode (no auto-injected PR context). For scheduled evals, this is required — we must gather and inject PR context ourselves.
- **`--append-system-prompt`** adds to Claude's system prompt without replacing defaults. Use this for the rubric.
- **`--allowedTools`** is required in CI (no interactive approval). Syntax: `"Bash(gh:*)" "Read" "Glob" "Grep"`.
- **`--output-format json`** in `claude_args` enables `structured_output` in action outputs.
- **`show_full_output: true`** is useful during development but should be disabled in production.
- **`secrets: inherit`** in reusable workflows passes all org secrets — scope carefully.
- **YAML `on:` must be quoted as `"on":`** to avoid boolean parsing issues.
- **`model:` is NOT a valid action input** — set model via `--model` in `claude_args`.

## Leaderboard Score Aggregation

Team cumulative score uses diminishing returns to prevent PR spam:
- PRs 1-5: full credit
- PRs 6-10: 80% credit
- PRs 11+: 50% credit

Each PR score is multiplied by a time decay factor:
- First 50% of hackathon: 1.0x
- 50-75%: 0.95x
- 75-90%: 0.90x
- Final 10%: 0.75x

## Future Considerations

- [ ] Leaderboard UI (static site reading from S3/API)
- [ ] Slack notifications when scores are posted
- [ ] Final judging round with `claude-opus-4-6` and human review
- [ ] Cross-team comparison prompt (at end of hackathon)
- [ ] Score history visualization per team
