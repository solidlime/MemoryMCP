---
name: test-driven-development
description: TDD workflow - RED→GREEN→REFACTOR cycle. Write the test first, then implement.
---

# Skill: test-driven-development

Follow the RED→GREEN→REFACTOR cycle for all feature implementation and bugfixes.

## Cycle

### RED (Write a failing test)
- Write a test that describes the expected behavior
- Run it to confirm it fails (or doesn't exist yet)
- The test captures the requirement

### GREEN (Make it pass)
- Write the minimum implementation code to make the test pass
- Do not add extra features or refactor yet
- Run the test to confirm it passes
- All existing tests must still pass

### REFACTOR (Improve without changing behavior)
- Clean up the implementation
- Improve naming, structure, performance
- Run all tests to confirm nothing broke

## Rules

1. Never write implementation code before a test exists for it
2. Never change behavior during refactoring
3. Run tests after every step
4. Keep the cycle tight — minutes, not hours
