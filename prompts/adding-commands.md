# Adding or Revising CLI Command Support

This document describes the process for adding support for a new CLI tool or revising an existing one in Dippy.

## Before You Start

1. **Read the tldr page** for the command at `~/source/tldr/pages/common/<command>.md`
   - Understand common usage patterns and subcommands
   - Note which operations are read-only vs mutations
2. **Read the man page** (`man <command>`) or help output (`<command> --help`)
   - Identify ALL flags, especially those that take arguments
   - Look for platform-specific flags (BSD vs GNU)
3. **Understand the safety model**: Dippy auto-approves commands that won't cause harm or unintended consequences. A command creating a cache directory is fine; a command deleting user files is not. The question is: "Could this change something the user would care about?"

## Process

### 0. Create a Feature Branch

Before making any changes, create a feature branch:

```bash
git checkout -b add-<command>-support
```

### 1. Write Aspirational Tests First

**Important**: Tests describe *desired* behavior, not current behavior. Write tests for how the command *should* work, then implement to make them pass. Do not modify tests to match current (possibly wrong) behavior.

For comprehensively covered commands, create a dedicated test file `tests/test_<command>.py`. For smaller additions, add to `tests/test_dippy.py` under a section header:

```python
#
# ==========================================================================
# <Command Name>
# ==========================================================================
#
# <Brief description of what makes commands safe/unsafe>
("command safe-subcommand", True),
("command unsafe-subcommand", False),
```

Categories to cover:
- **Safe operations**: Listing, describing, querying, local inspection
- **Unsafe operations**: Creating, deleting, or modifying user data; external mutations (push, deploy, send)
- **Flag variations**: Short flags (`-v`), long flags (`--verbose`), combined flags (`-rf`)
- **Global flags**: Flags that appear before the subcommand
- **Edge cases**: No arguments, help flags, version flags

### 2. Run Tests to See Failures

```bash
uv run pytest tests/test_dippy.py -v -k "<command>" 2>&1 | tail -50
```

### 3. Update the Implementation

Edit `src/dippy/dippy.py`. Depending on the command structure:

#### Simple Commands (no subcommands)
Add to `SAFE_COMMANDS` if always safe, or add specific unsafe flags to check.

#### CLI Tools with Service/Action Pattern (aws, gcloud, az, kubectl)
Update or add to `CLI_CONFIGS`:

```python
"<command>": {
    "service_depth": <int>,           # Depth to find the service name
    "subservice_depths": {            # Variable depth for specific services
        ("service",): <int>,
        ("service", "subservice"): <int>,
    },
    "safe_actions": {                 # Actions that are always safe
        "list", "describe", "get", "show",
    },
    "unsafe_prefixes": {              # Action prefixes that are always unsafe
        "create", "delete", "update", "set",
    },
    "flags_with_arg": {               # Flags that consume the next token
        "-o", "--output", "-n", "--namespace",
    },
}
```

#### Commands Requiring Compound Checks
For commands where safety depends on subcommand + flags combination:

```python
def check_<command>_<subcommand>(tokens: list[str]) -> bool:
    """Approve <command> <subcommand> only for safe operations."""
    # Parse flags and arguments
    # Return True only if the specific combination is safe
    return False

# Add to COMPOUND_CHECKS dict:
COMPOUND_CHECKS = {
    "<command>": {
        "<subcommand>": check_<command>_<subcommand>,
    },
}
```

#### Commands with Inner Commands (xargs, shell -c, env)
These need special handling to extract and evaluate the inner command:

```python
def check_<wrapper>(tokens: list[str]) -> bool:
    """Approve <wrapper> if the inner command is safe."""
    # Skip wrapper-specific flags
    # Extract inner command tokens
    # Return is_command_safe(inner_tokens)
```

### 4. Run Tests Until All Pass

```bash
uv run pytest tests/test_dippy.py -v 2>&1 | tail -20
```

### 5. Run Linter

```bash
uv run ruff check src/ tests/
```

### 6. Create a Pull Request

Commit your changes and push the feature branch:

```bash
git add -A
git commit -m "Expand <Command> support with comprehensive coverage"
git push -u origin add-<command>-support
```

Create a PR with a clear title and description:

```bash
gh pr create --title "Expand <Command> support with comprehensive coverage" --body "$(cat <<'EOF'
## Summary
- Add <N>+ tests covering <command> CLI commands
- Add safe actions: <list of safe actions>
- Add compound checks for <subcommands with special handling>

## Test plan
- [ ] All new tests pass
- [ ] Linter passes
- [ ] Existing tests still pass
EOF
)"
```

### 7. Merge the PR

After review, merge the PR:

```bash
gh pr merge --squash --delete-branch
```

## Test Organization

Tests are grouped by CLI tool with section headers:
```python
#
# ==========================================================================
# <Tool Name>
# ==========================================================================
#
```

Within each section, organize tests by:
1. Safe operations (True cases)
2. Unsafe operations (False cases)
3. Edge cases (no args, help, version)
4. Flag combinations

Avoid duplicate tests. When reorganizing, remove duplicates rather than keeping them.

## Safety Principles

The core question: **"Could this change something the user would care about?"**

1. **When in doubt, reject**: Better to require manual approval than auto-approve something harmful
2. **Harmless side effects are OK**: Creating cache dirs, writing logs, updating timestamps - these don't matter
3. **User data/state changes are not OK**: Deleting files, modifying configs, pushing to remote, deploying code
4. **External effects are not OK**: Sending emails, making API calls that mutate state, network requests with side effects
5. **Interactive commands are unsafe**: Commands requiring user input (`-i`, `-p`, `--interactive`) - we can't provide that input
6. **Arbitrary code execution is unsafe**: `source`, `.`, `eval` - we can't know what they'll do
7. **Consider flag combinations**: Some commands are safe by default but unsafe with certain flags

## Common Patterns

### Flags That Make Safe Commands Unsafe
- `--force`, `-f`: Bypasses safety checks
- `--delete`, `-d`: Enables deletion
- `--write`, `-w`: Enables writing
- `--execute`, `-e`: Enables execution
- `--interactive`, `-i`: Requires user input

### Flags That Are Always Safe
- `--help`, `-h`, `-help`: Show help
- `--version`, `-v`, `-V`: Show version
- `--dry-run`, `-n`: Preview without executing
- `--list`, `-l`: List mode
- `--verbose`: More output (doesn't change behavior)

### Commands That Wrap Other Commands
These need to extract and evaluate the inner command:
- `xargs <command>`: Evaluate `<command>`
- `bash -c '<command>'`: Parse and evaluate the shell command
- `env [VAR=val...] <command>`: Evaluate `<command>`
- `time <command>`: Evaluate `<command>`
- `nice <command>`: Evaluate `<command>`

### Commands That Are Never Safe
Some commands execute arbitrary code and cannot be safely auto-approved:
- `source`, `.`: Execute file contents in current shell
- `eval`: Execute arbitrary shell code
- `exec`: Replace current shell with command

## Examples from History

### xargs
- Read the tldr and man page to find ALL flags
- Flags with arguments: `-I`, `-J`, `-L`, `-n`, `-P`, `-R`, `-S`, `-a`, `-d`, `-E`, `-e`, `-s`
- Unsafe flags (interactive): `-p`, `-o` (require user input)
- BSD-specific flags: `-J`, `-R`, `-S`
- Safety depends on the inner command being safe

### git
- Most operations are unsafe (add, commit, push, pull, checkout, reset, etc.)
- Safe operations: status, log, diff, show, blame, branch --list, tag --list, remote -v
- Compound checks needed for: branch, config, notes, remote, stash, tag, worktree

### Cloud CLIs (aws, gcloud, az, kubectl)
- Use `CLI_CONFIGS` with service/action pattern
- Variable depth for nested services (e.g., `az storage account keys`)
- Safe actions typically: list, describe, get, show
- Unsafe prefixes typically: create, delete, update, set, apply, run
