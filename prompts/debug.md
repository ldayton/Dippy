Debug a Dippy issue based on user-provided context.

The user's AI assistant encountered unexpected Dippy behavior and will provide:
- The command that was incorrectly approved or blocked
- Expected vs actual behavior
- Any relevant error messages or logs

Your goal is to identify and fix the bug.

Steps:
1. Understand the bug from the provided context
2. Search the codebase to find the relevant handler or pattern
3. Write a failing test FIRST in the appropriate test file (tests/cli/test_*.py or tests/test_*.py)
4. Run `just test` and verify the test fails as expected
5. Fix the bug in the handler or pattern
6. Run `just test` until the test passes

When tests pass:
7. Run `just lint --fix`
8. Run `just fmt --fix`

IMPORTANT: `just check` MUST PASS before you are done.

RESTRICTIONS:
- ONLY modify files directly related to the bug
- Make minimal, targeted fixes
- Do NOT refactor, rename, or "improve" unrelated code
- Do NOT modify files that are not part of the fix

Do not create a git commit or PR.
