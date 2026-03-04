# Evaluation Prompt Templates

Each `.md` file in this directory is a self-contained evaluation rubric for a specific hackathon theme. The filename (without `.md`) is the theme ID passed via the `hackathon_theme` workflow input.

## Available Themes

| Theme | File | Focus |
|-------|------|-------|
| `aws-bedrock` | `aws-bedrock.md` | AWS Bedrock, AI/ML services, cloud-native apps |

## Creating a New Theme

1. Copy an existing template as a starting point:
   ```bash
   cp prompts/aws-bedrock.md prompts/your-theme.md
   ```

2. Follow this required structure (6 steps):
   - **Step 1:** Define project type classifications relevant to the theme
   - **Step 2:** Anti-gaming checks (keep these consistent across themes)
   - **Step 3:** Score 5 dimensions with weights summing to 1.0 and anchored rubric tables (0/2/4/6/8/10)
   - **Step 4:** Compute weighted overall score with penalties, clamped to [0, 10]
   - **Step 5:** Set flags array
   - **Step 6:** Write summary

3. Adjust the scoring dimensions and weights to match the hackathon's focus. For example:
   - A serverless hackathon might weight "AWS Integration" higher
   - A frontend hackathon might replace it with "UX/Design Quality"
   - Weights must always sum to 1.0

4. End with the JSON output instruction referencing `schemas/eval-output.schema.json`

5. Use the theme by setting `hackathon_theme: your-theme` in the team caller workflow

## Naming Convention

- Lowercase, hyphen-separated: `aws-bedrock`, `serverless`, `full-stack`
- Keep names short and descriptive
- The filename is what teams see in their workflow config
