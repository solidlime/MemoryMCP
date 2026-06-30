---
name: systematic-debugging
description: Systematic debugging approach - identify root cause before proposing fixes. No guessing.
---

# Skill: systematic-debugging

Use this skill when encountering any bug, test failure, or unexpected behavior.

## Principles

1. **Observe first**: Gather all available information about the failure — error messages, stack traces, logs, reproduction steps.
2. **Form hypotheses**: Based on evidence, list possible root causes. Do not jump to conclusions.
3. **Test hypotheses**: Use targeted queries (grep, logs, debug prints) to confirm or eliminate each hypothesis.
4. **Identify root cause**: Pinpoint the exact location and mechanism of the bug before touching code.
5. **Fix surgically**: Make the minimal change needed to fix the root cause.
6. **Verify**: Run tests to confirm the fix works and nothing is broken.

## Anti-patterns (avoid these)

- Changing code before understanding the root cause
- Fixing symptoms instead of root causes
- Making broad changes that could introduce new bugs
- Assuming without verifying
