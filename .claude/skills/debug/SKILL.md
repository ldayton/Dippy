---
name: debug
description: Debug incorrect Dippy approval or block behavior
disable-model-invocation: true
---

Debug a Dippy issue based on user-provided context.

The user will provide:
- The command that was incorrectly approved or blocked
- Expected vs actual behavior
- Any relevant error messages or logs

## Process

1. Understand the bug from the provided context
2. Search the codebase to find the relevant handler or pattern
3. Write a failing test FIRST in the appropriate test file
4. Run `just test` and verify the test fails as expected
5. Fix the bug in the handler or pattern
6. Run `just test` until the test passes

## Finish

When tests pass:
```
uv run ruff check --fix && uv run ruff format
```

`just check` MUST pass before you're done.

## Restrictions

- ONLY modify files directly related to the bug
- Make minimal, targeted fixes
- Do NOT refactor or "improve" unrelated code
- Do NOT create a git commit or PR
