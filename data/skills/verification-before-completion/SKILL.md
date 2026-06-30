---
name: verification-before-completion
description: Verify work before claiming completion. Run verification commands before making any success claims.
---

# Skill: verification-before-completion

You must verify your work before claiming it is complete, fixed, or passing.

## Rules

1. **Evidence before assertions**: Never claim success without running verification commands first.
2. **Run the actual tests**: Execute `pytest`, `ruff check`, or whatever verification commands are appropriate for the task.
3. **Report real output**: Show the actual command output in your response. Do not paraphrase or summarize.
4. **Fail honestly**: If verification fails, report the failure and fix it before claiming completion.
5. **No shortcuts**: Skipping verification is not acceptable. Always run the full verification suite.

## Workflow

1. Implement the fix or feature
2. Run verification commands
3. Examine the output
4. If passing → claim completion with evidence
5. If failing → debug and repeat from step 1
