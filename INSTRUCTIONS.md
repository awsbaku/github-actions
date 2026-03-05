# Hackathon Instructions

Welcome to the AWS Bedrock Hackathon! This document explains how your repository works, how your code is scored, and the rules you need to follow.

---

## How It Works

Your repository comes with an automated AI evaluation system. Every **6 hours**, an AI judge (powered by Claude) reviews your open Pull Request and posts a score as a comment on the PR.

```
You write code → Open a PR → AI evaluates your PR → Score posted as PR comment
                                                   → Score sent to leaderboard
```

You will see your score and detailed feedback directly on your Pull Request.

---

## Getting Started

### 1. Your Repository Variables

Your repo has been pre-configured with these variables by the organizers:

| Variable | What it is | Example |
|----------|-----------|---------|
| `TEAM_NAME` | Your team's display name | `Team Alpha` |
| `TEAM_SIZE` | Number of members on your team | `3` |

If these are missing or wrong, contact the organizers.

### 2. Branching & Workflow

Your repo comes with two branches:

- **`main`** — Protected. Only updated via Pull Requests. This is what the AI judge evaluates.
- **`development`** — Your working branch. Push here freely, collaborate, experiment.

You can create as many feature branches as you want off `development`. Work however you like day-to-day. The AI judge **only looks at PRs targeting `main`**.

**How to work:**

```bash
# Day-to-day: work on feature branches off development
git checkout development
git checkout -b feature/my-awesome-feature

# Commit freely to your feature branch
git add .
git commit -m "Add Bedrock agent for document Q&A with streaming responses"
git push origin feature/my-awesome-feature

# Merge feature branches into development (via PR or direct push — your choice)
git checkout development
git merge feature/my-awesome-feature
git push origin development
```

**When ready for evaluation:** open a single PR from `development` → `main`.

```bash
# On GitHub: create a Pull Request
#   base: main  ←  compare: development
```

**Important rules for PRs targeting `main`:**
- Only **one open PR** targeting `main` is allowed at a time. A second PR will be auto-closed.
- Open your PR to `main` strategically — the AI evaluates it every 6 hours.
- Keep pushing improvements to `development` and they flow into the same PR.
- After evaluation and merge, open a new PR for the next batch of work.

### 3. Fill In Your README and CLAUDE.md

Your repo includes template files — **fill them in**:

- **README.md** — Describe your project, team, tech stack, setup instructions, and AWS services used
- **CLAUDE.md** — Brief project description, how to run it, and your tech stack

The AI judge reads both of these files. Better documentation = higher documentation score.

---

## Scoring System

Your PR is scored on a **0 to 10** scale across 5 dimensions:

| Dimension | Weight | What the judge looks for |
|-----------|--------|--------------------------|
| **Functional Value** | 30% | Does your code actually work? Real features vs empty stubs. |
| **AWS/Bedrock Integration** | 25% | How well you use AWS services. Correct SDK usage, error handling, IAM best practices. |
| **Innovation & Creativity** | 20% | Original approaches vs copying tutorials. Creative use of services. |
| **Code Quality** | 15% | Readable code, good structure, error handling, no security issues. |
| **Documentation** | 10% | README, code comments, PR descriptions. Can someone understand your project? |

### Score Calculation

```
Overall Score = (Functional × 0.30) + (AWS × 0.25) + (Innovation × 0.20)
              + (Quality × 0.15) + (Documentation × 0.10)
              - Penalties

Clamped to 0.0 – 10.0
```

### What the Scores Mean

| Score | Level |
|-------|-------|
| 0–2 | Nothing functional. Empty stubs, no real code. |
| 3–4 | Partial work. Some code exists but doesn't really work. |
| 5–6 | Decent. Features work on the happy path. Standard approach. |
| 7–8 | Strong. End-to-end working features, good AWS integration, clean code. |
| 9–10 | Exceptional. Reserved for outstanding, production-quality work. |

### Momentum Bonus

If your PR builds on previous work and shows meaningful improvement, you get a **+0.5 bonus**. Iterating and improving is rewarded.

---

## Penalties

The AI judge automatically detects attempts to game the system. Penalties are subtracted from your overall score.

| What | Penalty | How to avoid it |
|------|---------|-----------------|
| **Whitespace padding** — >80% of changes are blank lines or whitespace | -0.5 | Make real code changes, not formatting-only PRs |
| **Trivial commits** — renaming files back and forth, no-op changes | -0.3 each | Every commit should add real value |
| **Boilerplate dump** — >200 lines of unmodified framework scaffolding | -1.0 | Customize your scaffolding. Don't submit raw `create-react-app` output. |
| **Code dump** — 1000+ lines in one commit with a vague message like "stuff" | -0.5 | Use descriptive commit messages. Break work into smaller commits. |
| **Hardcoded credentials** — AWS keys, passwords, or secrets in your code | -2.0 | Use environment variables. Never commit secrets. |
| **Prompt injection** — trying to trick the AI judge into giving a higher score | -3.0 | Don't do it. We will see it. |
| **PR recycling** — closing a PR and reopening nearly identical code as a new PR | -1.0 | Keep iterating on the same PR instead. |

---

## Rules

### One Active PR at a Time

Only **one open PR** is evaluated per scoring cycle. If you have multiple PRs open, only the most recent one gets scored — the others are skipped with a warning.

**Best practice:** Work on one PR, iterate on it, get scored, merge it, then open the next one.

### Protected Files — Do Not Modify

The following files are managed by the organizers and **cannot be changed**:

- `CLAUDE.md` — used by the evaluation system
- `.github/workflows/` — all workflow files

PRs that modify these files will be **automatically closed** with an explanation. Create a new PR without those changes.

### Commit Messages Matter

Write descriptive commit messages. The AI judge reads them.

- Bad: `fix`, `update`, `stuff`, `wip`, `asdf`
- Good: `Add Bedrock streaming response handler with retry logic`
- Good: `Fix S3 upload error handling for large files`

### PR Descriptions Matter

Fill in your PR description. Explain:
- What you built or changed
- Why you made these choices
- How to test it

An empty PR description hurts your Documentation score.

---

## Evaluation Schedule

| Trigger | When it happens |
|---------|----------------|
| **Scheduled** | Every 6 hours (your cron slot assigned by organizers) |
| **PR events** | When you open a PR, push new commits, or mark a draft as ready |
| **Manual** | Organizers can trigger an evaluation on-demand |

Each evaluation is independent — if you push new commits to your PR, the next evaluation will see the updated code and may score differently.

---

## Leaderboard

Scores are aggregated on a leaderboard with these adjustments:

**Diminishing returns** (to prevent PR spam):
- PRs 1–5: full credit
- PRs 6–10: 80% credit
- PRs 11+: 50% credit

**Time factor** (rewarding early progress):
- First half of hackathon: 1.0x multiplier
- 50–75%: 0.95x
- 75–90%: 0.90x
- Final 10%: 0.75x

**Strategy tip:** Fewer, high-quality PRs early in the hackathon score better than many low-quality PRs at the last minute.

---

## Tips for a High Score

1. **Start with a working feature**, even if small. A working demo beats a half-built ambitious project.
2. **Use AWS Bedrock meaningfully** — don't just import the SDK, actually call it with proper error handling.
3. **Be original** — the judge detects tutorial copies. Add your own twist.
4. **Write good commit messages and PR descriptions** — it's free points.
5. **Fill in your README** — explain your architecture, how to run it, what AWS services you use.
6. **Iterate on one PR** — push improvements, don't open new PRs for the same work.
7. **Don't commit secrets** — use environment variables and `.env` files (already in `.gitignore`).
8. **Don't try to trick the AI** — prompt injection attempts are detected and heavily penalized.

---

## Need Help?

Contact the hackathon organizers if:
- Your repository variables (`TEAM_NAME`, `TEAM_SIZE`) are missing or wrong
- The evaluation workflow isn't running
- You believe a score is incorrect
- You have questions about the rules

Good luck and happy hacking!
