---
name: add-command
description: Add support for a new CLI command. Use when implementing a handler or adding to SIMPLE_SAFE.
argument-hint: <command>
disable-model-invocation: true
---

Add support for `$ARGUMENTS` in Dippy.

## 1. Research

**tldr pages:**
```
ls ~/source/tldr/pages/*/$ARGUMENTS*.md
cat ~/source/tldr/pages/*/$ARGUMENTS.md
```

**CLI docs:**
```
$ARGUMENTS --help
man $ARGUMENTS
```

Note which operations are read-only vs mutations.

## 2. Decide: Handler or SIMPLE_SAFE?

- **SIMPLE_SAFE**: Always safe regardless of arguments (read-only, no destructive flags). Go to step 3A.
- **Handler**: Needs subcommand/flag analysis. Go to step 3B.

## 3A. SIMPLE_SAFE Path

Add to `SIMPLE_SAFE` in `src/dippy/core/allowlists.py` and add tests to `tests/test_simple.py` in the appropriate category. Skip to step 5.

## 3B. Handler Path

Create `tests/cli/test_$ARGUMENTS.py`:

```python
"""Test cases for $ARGUMENTS."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations
    ("$ARGUMENTS <safe-subcommand>", True),
    ("$ARGUMENTS --help", True),
    # Unsafe operations
    ("$ARGUMENTS <unsafe-subcommand>", False),
]

@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
```

## 4. Implement Handler

Create `src/dippy/cli/$ARGUMENTS.py`:

```python
"""$ARGUMENTS handler for Dippy."""

from dippy.cli import Classification, HandlerContext

COMMANDS = ["$ARGUMENTS"]

SAFE_ACTIONS = frozenset({"list", "show", "status"})

def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    action = tokens[1] if len(tokens) > 1 else None
    if action in SAFE_ACTIONS:
        return Classification("allow", description=f"$ARGUMENTS {action}")
    return Classification("ask", description="$ARGUMENTS")
```

For handler patterns (nested subcommands, flag-checking, delegation), see [patterns.md](patterns.md).

## 5. Iterate

```
just test
```

Fix failures until tests pass.

## 6. Verify

`just check` MUST pass before you're done.
