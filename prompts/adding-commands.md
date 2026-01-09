# Adding CLI Command Support

This document describes how to add support for a new CLI tool in Dippy.

## Before You Start

1. **Read the tldr pages** for the command:
   - `~/tldr/pages/common/<command>.md` - cross-platform commands
   - `~/tldr/pages/linux/<command>.md` - Linux-specific
   - `~/tldr/pages/osx/<command>.md` - macOS-specific
   - `~/tldr/pages/*/<command>-<subcommand>.md` - subcommand pages (e.g., `git-status.md`)
   - Note which operations are read-only vs mutations
2. **Read the man pages** and help output:
   - `man <command>` for the main page
   - `man <command>-<subcommand>` for subcommand pages (e.g., `man git-status`)
   - `<command> --help` and `<command> <subcommand> --help`
   - Identify ALL flags, especially those that take arguments
   - Look for platform-specific flags (BSD vs GNU)
3. **Understand the safety model**: Dippy auto-approves commands that won't cause harm. The question is: "Could this change something the user would care about?"

## Process

### 1. Create a Feature Branch

```bash
git checkout -b add-<command>-support
```

### 2. Write Tests First

Create `tests/cli/test_<command>.py`:

```python
"""Test cases for <command>."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations
    ("command read-subcommand", True),
    ("command --help", True),
    # Unsafe operations
    ("command write-subcommand", False),
    ("command --delete", False),
]

@pytest.fixture
def check():
    from dippy.dippy import check_command
    return check_command

@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation: {command}"
```

Categories to cover:
- **Safe operations**: Listing, describing, querying, local inspection
- **Unsafe operations**: Creating, deleting, modifying data; external mutations
- **Flag variations**: Short flags (`-v`), long flags (`--verbose`), combined flags (`-rf`)
- **Edge cases**: No arguments, help flags, version flags

### 3. Run Tests to See Failures

```bash
just test
```

### 4. Implement Support

**Option A: Add to SIMPLE_SAFE** (for always-safe commands)

If the command is always safe regardless of arguments (read-only, no destructive flags), add it to `SIMPLE_SAFE` in `src/dippy/core/patterns.py`:

```python
SIMPLE_SAFE = frozenset({
    # ...existing commands...
    "<command>",
})
```

**Option B: Create a Handler** (for commands with complex safety logic)

Create `src/dippy/cli/<command>.py`:

```python
"""
<Command> handler for Dippy.

<Brief description of what makes commands safe/unsafe>
"""

# Actions that only read data
SAFE_ACTIONS = frozenset({
    "list", "show", "get", "describe",
})


def check(tokens: list[str]) -> bool:
    """Check if <command> is safe.

    Returns True to approve, False to ask user.
    """
    if len(tokens) < 2:
        return False

    action = tokens[1]
    return action in SAFE_ACTIONS
```

### 5. Run Tests Until All Pass

```bash
just test
```

### 6. Lint and Format

When tests pass:

```bash
just lint --fix
just fmt --fix
```

### 7. IMPORTANT: `just check` MUST PASS

```bash
just check
```

This runs all tests on all Python versions plus lint and format checks. Do not proceed until this passes.

## Handler Patterns

### Simple Action-Based

For CLIs with flat subcommand structure (e.g., `git`, `docker`):

```python
SAFE_ACTIONS = frozenset({"status", "list", "show"})


def check(tokens: list[str]) -> bool:
    action = tokens[1] if len(tokens) > 1 else None
    return action in SAFE_ACTIONS
```

### Nested Subcommands

For CLIs with nested structure (e.g., `aws s3 ls`, `kubectl get pods`):

```python
def check(tokens: list[str]) -> bool:
    if len(tokens) < 3:
        return False

    action = tokens[2]
    return action in {"list", "describe", "get"}
```

### Flag-Dependent Safety

When flags determine safety (e.g., `git apply --check`):

```python
def check(tokens: list[str]) -> bool:
    return "--check" in tokens or "--dry-run" in tokens
```

### Commands That Wrap Other Commands

For wrappers like `xargs`, `env`, `time`:

```python
def check(tokens: list[str]) -> bool:
    # Skip wrapper flags to find inner command
    inner_cmd = extract_inner_command(tokens)
    if not inner_cmd:
        return False

    # Check the inner command
    from dippy.dippy import _check_single_command
    decision, _ = _check_single_command(inner_cmd)
    return decision == "approve"
```

## Safety Principles

The core question: **"Could this change something the user would care about?"**

1. **When in doubt, require confirmation**: Better to ask than auto-approve something harmful
2. **Harmless side effects are OK**: Creating cache dirs, writing logs, updating timestamps
3. **User data/state changes are not OK**: Deleting files, modifying configs, pushing to remote
4. **External effects are not OK**: Sending emails, mutating APIs, deploying code
5. **Interactive commands need confirmation**: `-i`, `-p`, `--interactive` require user input
6. **Consider flag combinations**: Some commands are safe by default but unsafe with certain flags

### Flags That Make Commands Unsafe
- `--force`, `-f`: Bypasses safety checks
- `--delete`, `-d`: Enables deletion
- `--write`, `-w`: Enables writing
- `--execute`, `-e`: Enables execution

### Flags That Are Always Safe
- `--help`, `-h`: Show help
- `--version`, `-v`: Show version
- `--dry-run`, `-n`: Preview without executing
- `--list`, `-l`: List mode
