# Dippy Configuration v1

## Design Principles

- **Not adversarial** - protecting against AI mistakes, not malicious actors
- **Favor expressivity** - let users say what they mean easily
- **Favor simplicity** - no complex syntax to learn
- **Favor familiarity** - use patterns people already know

## Overview

Dippy's config system extends the built-in approval rules. Syntax is inspired by `.gitignore`: line-based, glob patterns, last-match-wins.

## File Locations

| Location          | Purpose          |
| ----------------- | ---------------- |
| `~/.dippy/config` | User global      |
| `.dippy`          | Project-specific |

**Load order** (last match wins):
1. `~/.dippy/config` - user defaults
2. `.dippy` - project overrides
3. `$DIPPY_CONFIG` - env override (highest precedence)

Project config is found by walking up from cwd to filesystem root, stopping at the first `.dippy` found (like `.git` discovery).

## Syntax

```
# Comments start with #

allow <glob>                   # auto-approve matching commands
ask <glob>                     # always prompt user for matching commands
ask <glob> "message"           # prompt with message shown to AI

allow-redirect <glob>          # allow output redirects to matching paths
ask-redirect <glob>            # prompt for output redirects to matching paths
ask-redirect <glob> "message"  # prompt with message shown to AI

set <key> [value]              # settings
```

**Escaping:** Use `[*]`, `[?]`, `[[]` to match literal glob characters. Use `\"` for quotes in messages.

**Tilde expansion:** `~` expands to home directory. Environment variables (`$HOME`) are not expanded.

**One rule per line.** No line continuation.

**Errors fail hard.** Syntax errors, unknown directives, and invalid settings cause Dippy to exit with an error message. No silent misbehavior.

## Ask Messages

When an `ask` or `ask-redirect` rule matches, an optional message can be shown to the AI explaining why approval is needed and what to do instead. This helps the AI learn and adjust.

```
ask git push --force * "Use --force-with-lease instead"
ask rm -rf /* "Too dangerous - be more specific about what to delete"
ask *prod* "Production commands require manual review"
ask-redirect .env* "Don't write secrets to env files"
```

If no message is provided, a default is generated from the pattern (e.g., `"ask: rm -rf /*"`).

Only `ask` supports messages - approval messages don't reliably reach the AI across all platforms.

## Pattern Matching

Patterns match the full command string using globs:

- `*` matches any characters
- `?` matches single character
- `[abc]` matches character class

**Last match wins.** Rules are evaluated top-to-bottom; the last matching rule determines the decision.

**Config wins over built-ins.** If a config rule matches, it takes precedence over Dippy's built-in safety handlers. Config represents explicit user intent.

**Commands are parsed, not string-matched.** The command is parsed as bash would parse it. The first token must be a valid command name (executable, builtin, script path). Patterns match against the parsed command, not arbitrary strings.

**Relative paths are resolved.** Script paths starting with `./`, `../`, or a bare filename are resolved against cwd before matching. Write rules with absolute paths:

```
# Config
allow ~/project/tools/*

# Command: ./build.sh (cwd: ~/project/tools)
# Resolved: ~/project/tools/build.sh → matches!
```

If no rule matches, built-in handlers decide.

## Command Rules

```
# Trust tools
allow just *
allow uv run *
allow python3 *
allow ~/bin/*

# Trust specific git operations
allow git stash pop
allow git stash apply
allow git checkout -- *

# Block dangerous patterns
ask rm -rf /*
ask git push --force *
ask *prod*
```

Inverse patterns via ordering:

```
# Allow all docker EXCEPT rm/rmi
allow docker *
ask docker rm *
ask docker rmi *
```

## Redirect Rules

Redirect patterns match the path as it appears in the command, normalized (no trailing slash).

Supports `**` for recursive matching:

```
# Allow temp paths
allow-redirect /tmp/**
allow-redirect .cache/**
allow-redirect **/*.log

# Protect sensitive files
ask-redirect **/.env*
ask-redirect **/*credential*
```

## Settings

```
set sticky-session       # remember approvals for session
set suggest-after 3      # suggest config after N approvals
set default allow        # YOLO mode (default is ask)
set verbose              # show reason on auto-approve
set log ~/.dippy/audit.log  # enable logging (minimal, best-effort safe)
set log-full             # log full commands (requires log path set)
set warn-banner          # visual warning for prompts
set disabled             # disable Dippy entirely
```

## Logging

**Default: no logging.**

When enabled with `set log <path>`, logs are structured (JSON) with minimal info:

```json
{"ts": "2024-01-15T10:23:45Z", "decision": "allow", "cmd": "git", "rule": "allow git stash *"}
{"ts": "2024-01-15T10:23:52Z", "decision": "ask", "cmd": "git", "rule": "ask git push --force *", "message": "Use --force-with-lease"}
{"ts": "2024-01-15T10:24:01Z", "decision": "ask", "cmd": "rm"}
```

The `cmd` field is best-effort extraction of the base command - may be wrong if parsing fails.

With `set log-full`, a `command` field is added containing the full command string. **Warning: may contain secrets.**

## Example

```
# ~/.dippy/config

allow just *
allow uv run *
allow python3 *
allow ~/bin/*

allow-redirect /tmp/*
allow-redirect .cache/*
ask-redirect .env*

set sticky-session
set suggest-after 3
```

```
# .dippy (project)

allow ./tools/*
allow git stash *
allow git checkout -- *
ask git push --force *

allow-redirect ./build/*
```
