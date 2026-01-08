# Adding CLI Command Support

This document describes how to add support for a new CLI tool in Dippy.

## Before You Start

1. **Read the tldr pages** for the command:
   - `~/source/tldr/pages/common/<command>.md` - cross-platform commands
   - `~/source/tldr/pages/linux/<command>.md` - Linux-specific
   - `~/source/tldr/pages/osx/<command>.md` - macOS-specific
   - `~/source/tldr/pages/*/<command>-<subcommand>.md` - subcommand pages (e.g., `git-status.md`)
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
uv run pytest tests/cli/test_<command>.py -v
```

### 4. Create the Handler

Create `src/dippy/cli/<command>.py`:

```python
"""
<Command> handler for Dippy.

<Brief description of what makes commands safe/unsafe>
"""

from typing import Optional

# Actions that only read data
SAFE_ACTIONS = frozenset({
    "list", "show", "get", "describe",
})

# Actions that modify state
UNSAFE_ACTIONS = frozenset({
    "create", "delete", "update", "apply",
})

def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a <command> command should be approved or denied.

    Returns:
        "approve" - Safe read-only operation
        "deny" - Dangerous operation (rarely used)
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return None

    action = tokens[1]

    if action in SAFE_ACTIONS:
        return "approve"

    if action in UNSAFE_ACTIONS:
        return None  # Needs confirmation

    return None  # Unknown - ask user
```

### 5. Register the Handler

Add to `KNOWN_HANDLERS` in `src/dippy/cli/__init__.py`:

```python
KNOWN_HANDLERS = {
    # ...existing handlers...
    "<command>": "<command>",
    "<alias>": "<command>",  # If the command has common aliases
}
```

### 6. Run Tests Until All Pass

```bash
uv run pytest tests/cli/test_<command>.py -v
```

### 7. Run Linter

```bash
uv run ruff check src/ tests/
```

### 8. Create a Pull Request

```bash
git add -A
git commit -m "Add <command> CLI support"
git push -u origin add-<command>-support
gh pr create --title "Add <command> CLI support" --body "$(cat <<'EOF'
## Summary
- Add handler for <command> CLI
- Add tests covering safe/unsafe operations

## Test plan
- [ ] All new tests pass
- [ ] Linter passes
EOF
)"
```

### 9. Merge the PR

```bash
gh pr merge --squash --delete-branch
```

## Handler Patterns

### Simple Action-Based

For CLIs with flat subcommand structure (e.g., `git`, `docker`):

```python
SAFE_ACTIONS = frozenset({"status", "list", "show"})
UNSAFE_ACTIONS = frozenset({"delete", "create", "update"})

def check(command: str, tokens: list[str]) -> Optional[str]:
    action = tokens[1] if len(tokens) > 1 else None
    if action in SAFE_ACTIONS:
        return "approve"
    return None
```

### Nested Subcommands

For CLIs with nested structure (e.g., `aws s3 ls`, `kubectl get pods`):

```python
def check(command: str, tokens: list[str]) -> Optional[str]:
    if len(tokens) < 3:
        return None

    service = tokens[1]
    action = tokens[2]

    if action in {"list", "describe", "get"}:
        return "approve"
    return None
```

### Flag-Dependent Safety

When flags determine safety (e.g., `git apply --check`):

```python
def check(command: str, tokens: list[str]) -> Optional[str]:
    if "--check" in tokens or "--dry-run" in tokens:
        return "approve"
    return None
```

### Commands That Wrap Other Commands

For wrappers like `xargs`, `env`, `time`:

```python
def check(command: str, tokens: list[str]) -> Optional[str]:
    # Skip wrapper flags to find inner command
    inner_tokens = extract_inner_command(tokens)
    if not inner_tokens:
        return None

    # Check the inner command
    from dippy.dippy import _check_single_command
    return _check_single_command(inner_tokens)
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
