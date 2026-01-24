---
name: check-coverage
description: Ensure comprehensive test coverage for a CLI handler. Use when adding a new command or auditing existing handler coverage.
argument-hint: <tool>
---

Ensure the handler and tests for `$ARGUMENTS` provide comprehensive coverage.

## 1. Gather Documentation

Find documentation for the tool (need at least one source):

**tldr:**
```
ls ~/source/tldr/pages/*/$ARGUMENTS*.md
cat ~/source/tldr/pages/*/$ARGUMENTS.md
```

**Local CLI:**
```
$ARGUMENTS --help
man $ARGUMENTS
```

Stop if neither source exists.

## 2. Explore Subcommands

For tools with subcommands, recursively explore:
```
$ARGUMENTS <subcommand> --help
$ARGUMENTS help <subcommand>
```

Build a mental model of:
- All subcommands and their actions
- Which operations are read-only (safe) vs mutate state (unsafe)
- Global flags that affect parsing
- Edge cases

## 3. Review Existing Tests

Read `tests/cli/test_$ARGUMENTS.py` and check for:
- Coverage of all subcommands
- Both safe and unsafe variants of each action
- Global flag handling
- Edge cases from the docs

## 4. Add Missing Tests

Add aspirational test cases for anything missing. Follow existing format:
```python
TESTS = [
    # --- Subcommand group ---
    ("$ARGUMENTS <subcommand> <safe-action>", True),
    ("$ARGUMENTS <subcommand> <unsafe-action>", False),
]
```

## 5. Iterate Until Tests Pass

```
just test
```

For each failure, determine if the test expectation is correct:
- If yes, update `src/dippy/cli/$ARGUMENTS.py`
- If no, fix the test

## 6. Verify

`just check` MUST pass before you're done.
