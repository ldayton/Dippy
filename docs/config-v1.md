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

**Escaping in patterns:** Use `[*]`, `[?]`, `[[]` to match literal glob characters.

**Escaping in messages:** Use `\"` for literal quotes, `\\` for literal backslash.

**Tilde expansion:** `~` expands to home directory in both patterns and commands. Environment variables (`$HOME`) are not expanded.

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

Patterns match the full command string using fnmatch-style globs:

- `*` matches any characters (including none)
- `?` matches exactly one character
- `[abc]` matches any of a, b, or c
- `[a-z]` matches any character in range
- `[!abc]` or `[^abc]` matches any character NOT in set

**Last match wins.** Rules are evaluated top-to-bottom; the last matching rule determines the decision. This allows broad rules followed by specific exceptions.

**Config wins over built-ins.** If a config rule matches, it takes precedence over Dippy's built-in safety handlers. Config represents explicit user intent.

**Path normalization in commands:**
- `~` at the start of a token expands to home directory
- `./foo` and `../foo` are resolved against cwd to absolute paths
- Bare filenames and other tokens are left unchanged

```
# Config
allow /home/user/project/tools/*

# Command: ./build.sh (cwd: /home/user/project/tools)
# Normalized: /home/user/project/tools/build.sh → matches!

# Command: ~/bin/tool
# Normalized: /home/user/bin/tool
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

Redirect patterns match the target path, normalized:
- Trailing slashes are stripped (`/tmp/foo/` → `/tmp/foo`)
- `~` expands to home directory
- Relative paths are resolved against cwd

Supports `**` for recursive directory matching:

- `**` matches zero or more directories
- `/tmp/**` matches `/tmp/foo`, `/tmp/a/b/c`, etc.
- `**/foo` matches `/foo`, `/a/foo`, `/a/b/c/foo`
- `/tmp/**/file.txt` matches `/tmp/file.txt`, `/tmp/a/file.txt`, `/tmp/a/b/file.txt`

```
# Allow temp paths
allow-redirect /tmp/**
allow-redirect .cache/**
allow-redirect **/*.log

# Protect sensitive files
ask-redirect **/.env*
ask-redirect **/*credential*
ask-redirect **/.*              # all hidden files
```

Note: `**` is only supported in redirect rules. Command rules use standard fnmatch globs.

## Settings

**Boolean flags** (no value):
```
set sticky-session       # remember approvals for session
set verbose              # show reason on auto-approve
set log-full             # log full commands (requires log path set)
set warn-banner          # visual warning for prompts
set disabled             # disable Dippy entirely
```

**Value settings:**
```
set suggest-after 3      # suggest config after N approvals (integer)
set default allow        # YOLO mode: 'allow' or 'ask' (default: ask)
set log ~/.dippy/audit.log  # enable logging to path
```

Settings use kebab-case (`sticky-session`) or snake_case (`sticky_session`) interchangeably.

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
