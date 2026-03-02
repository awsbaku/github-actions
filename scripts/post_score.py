"""
Post hackathon evaluation score as a formatted PR comment.

Usage:
  python3 post_score.py --result '<json_string>' --repo 'owner/repo' --pr 42
  python3 post_score.py --result-file eval_result.json --repo 'owner/repo' --pr 42
  python3 post_score.py --dry-run --result-file eval_result.json
"""

import argparse
import json
import subprocess
import sys


def score_bar(score: float, max_score: float = 10, width: int = 20) -> str:
    filled = int((score / max_score) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def grade_label(score: float) -> str:
    if score >= 9:
        return "Exceptional"
    if score >= 7:
        return "Strong"
    if score >= 5:
        return "Developing"
    if score >= 3:
        return "Early Stage"
    return "Needs Work"


def format_comment(result: dict) -> str:
    scores = result["scores"]
    anti = result["anti_gaming"]
    flags = result.get("flags", [])
    overall = result["overall_score"]

    flag_str = " ".join(f"`{f}`" for f in flags) if flags else "None"

    rows = [
        ("Functional Value", scores["functional_value"]),
        ("AWS Integration", scores["aws_integration"]),
        ("Innovation", scores["innovation"]),
        ("Code Quality", scores["code_quality"]),
        ("Documentation", scores["documentation"]),
    ]

    table_rows = ""
    for name, dim in rows:
        weighted = dim["score"] * dim["weight"]
        table_rows += f"| {name} | {dim['score']}/10 | {int(dim['weight']*100)}% | {weighted:.1f} |\n"

    reasoning_sections = ""
    for name, dim in rows:
        reasoning_sections += f"**{name}:** {dim['reasoning']}\n\n"

    reviewer_note = ""
    if result.get("reviewer_notes"):
        reviewer_note = f"\n> **Organizer Note:** {result['reviewer_notes']}\n"

    comment = f"""## Hackathon Score Evaluation

**Overall: {overall}/10** ({grade_label(overall)})
`{score_bar(overall)}`

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
{table_rows}
**Anti-gaming penalty:** -{anti['penalty_total']}
**Flags:** {flag_str}

### Dimension Reasoning

{reasoning_sections}
### Summary

{result['summary']}
{reviewer_note}
---
*Evaluation {result.get('evaluation_version', 'v1.0')} | Judge: awsbaku/github-actions*
"""
    return comment.strip()


def post_comment(repo: str, pr_number: int, body: str) -> bool:
    result = subprocess.run(
        ["gh", "pr", "comment", str(pr_number), "--repo", repo, "--body", body],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error posting comment: {result.stderr}", file=sys.stderr)
        return False
    print(f"Score comment posted to {repo}#{pr_number}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Post hackathon eval score as PR comment")
    parser.add_argument("--result", help="JSON string of evaluation result")
    parser.add_argument("--result-file", help="Path to JSON file with evaluation result")
    parser.add_argument("--repo", help="GitHub repo (owner/repo)")
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--dry-run", action="store_true", help="Print comment without posting")
    args = parser.parse_args()

    if args.result_file:
        with open(args.result_file) as f:
            result = json.load(f)
    elif args.result:
        result = json.loads(args.result)
    else:
        print("Error: provide --result or --result-file", file=sys.stderr)
        sys.exit(1)

    comment = format_comment(result)

    if args.dry_run:
        print(comment)
        return

    if not args.repo or not args.pr:
        print("Error: --repo and --pr required (unless --dry-run)", file=sys.stderr)
        sys.exit(1)

    success = post_comment(args.repo, args.pr, comment)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
