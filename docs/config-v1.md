# Dippy Configuration v1

## Design Principles

- **Not adversarial** - protecting against AI mistakes, not malicious actors
- **Favor expressivity** - let users say what they mean easily
- **Favor simplicity** - no complex syntax to learn
- **Favor familiarity** - use patterns people already know

## Overview

Dippy's config system extends the built-in approval rules. Line-based, glob patterns, last-match-wins.

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
# dippy: v1                    # version pragma (must be first line if present)

allow <glob>                   # auto-approve matching commands
ask <glob>                     # always prompt user for matching commands
ask <glob> "message"           # prompt with message shown to AI
deny <glob>                    # reject matching commands (no user prompt)
deny <glob> "message"          # reject with message shown to AI

allow-redirect <glob>          # allow output redirects to matching paths
ask-redirect <glob>            # prompt for output redirects to matching paths
ask-redirect <glob> "message"  # prompt with message shown to AI
deny-redirect <glob>           # reject output redirects to matching paths
deny-redirect <glob> "message" # reject with message shown to AI

set <key> [value]              # settings
```

**Version pragma:** `# dippy: v1` as the first line declares the config version. If missing, defaults to latest. If present but unsupported, Dippy errors.

**Escaping in patterns:** Use `[*]`, `[?]`, `[[]` to match literal glob characters.

**Escaping in messages:** Use `\"` for literal quotes, `\\` for literal backslash.

**Tilde expansion:** `~` expands to home directory in both patterns and commands. Environment variables (`$HOME`) are not expanded.

**One rule per line.** No line continuation.

**Forgiving parsing.** Invalid lines (unknown directives, malformed rules) are logged and skipped. Valid rules in the same file still take effect. Check `~/.claude/hook-approvals.log` for warnings.

## Messages

When an `ask`, `deny`, or their `-redirect` variants match, an optional message can be shown to the AI explaining why approval is needed (or why the command was rejected) and what to do instead. This helps the AI learn and adjust.

```
ask git push --force * "Use --force-with-lease instead"
deny rm -rf /* "Too dangerous - be more specific about what to delete"
ask *prod* "Production commands require manual review"
deny-redirect .env* "Never write secrets to env files"
```

If no message is provided, a default is generated from the pattern (e.g., `"deny: rm -rf /*"`).

Only `ask` and `deny` support messages - approval messages don't reliably reach the AI across all platforms.

## Pattern Matching

Dippy uses two pattern styles depending on context:

### Command Patterns

For `allow`, `ask`, `deny` rules, patterns match the full command string:

- `*` matches any characters (including spaces and none)
- `?` matches exactly one character
- `[abc]` matches any of a, b, or c
- `[a-z]` matches any character in range
- `[!abc]` or `[^abc]` matches any character NOT in set

**Trailing `*` matches bare commands.** The pattern `python *` matches both `python foo` AND bare `python`. To match only commands with arguments, use `?*`:
```
allow python ?*   # matches 'python foo', NOT bare 'python'
allow python *    # matches both 'python foo' AND bare 'python'
```

### Path Patterns

For redirect and file rules (`*-redirect`, `*-edit`, `*-mcp`), patterns match paths:

- `*` matches any characters except `/`
- `**` matches any characters including `/` (recursive)
- `?`, `[abc]`, `[a-z]`, `[!abc]` work as above

```
src/*      # matches src/foo.go, NOT src/sub/foo.go
src/**     # matches src/foo.go AND src/sub/foo.go
**/test.*  # matches test.py, src/test.py, src/sub/test.py
```

**Last match wins.** Rules are evaluated top-to-bottom; the last matching rule determines the decision. This allows broad rules followed by specific exceptions.

**Strictest wins across types.** When a command has both command rules and redirect rules matching, the most restrictive decision wins: `deny` > `ask` > `allow`. This prevents accidentally allowing dangerous redirects just because the command itself was allowed.

**Config wins over built-ins.** If a config rule matches, it takes precedence over Dippy's built-in safety handlers. Config represents explicit user intent.

**Path normalization:**

Both commands and patterns are normalized before matching:
- `~` expands to home directory
- `./foo` and `../foo` resolve against cwd to absolute paths
- Relative paths without `./` (e.g., `bin/foo`) resolve against cwd to absolute paths

```
# Config (cwd: /home/user/project)
allow node bin/*

# Command: node bin/script.js
# Normalized: node /home/user/project/bin/script.js
# Pattern normalized: node /home/user/project/bin/*
# → matches!

# Command: node /home/user/project/bin/script.js
# → also matches (already absolute, pattern normalized)

# Command: node /other/path/bin/script.js
# → does NOT match (different absolute path)
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

# Prompt for review
ask *prod* "Production commands require manual review"

# Hard blocks (no user override)
deny rm -rf /* "Too dangerous"
deny git push --force * "Use --force-with-lease instead"
```

Inverse patterns via ordering (last match wins):

```
# Allow all docker EXCEPT rm/rmi
allow docker *
ask docker rm *
ask docker rmi *

# Allow rm but never rm -rf /
allow rm *
deny rm -rf /*
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

# Prompt for review
ask-redirect **/.*              # all hidden files

# Hard blocks (no user override)
deny-redirect **/.env* "Never write secrets to env files"
deny-redirect **/*credential* "Never write credential files"
deny-redirect /etc/** "System config is off-limits"
```

Note: `**` is only supported in redirect rules. Command rules use standard fnmatch globs.

## Settings

**Boolean flags** (no value):
```
set sticky-session       # remember approvals for session
set verbose              # show reason on auto-approve
set log-full             # log full commands (requires log path set)
set warn-banner          # visual warning for prompts
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
{"ts": "2024-01-15T10:24:01Z", "decision": "deny", "cmd": "rm", "rule": "deny rm -rf /*", "message": "Too dangerous"}
{"ts": "2024-01-15T10:24:15Z", "decision": "ask", "cmd": "rm"}
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
deny-redirect .env* "Never write secrets"

set sticky-session
set suggest-after 3
```

```
# .dippy (project)

allow ./tools/*
allow git stash *
allow git checkout -- *
deny git push --force * "Use --force-with-lease"

allow-redirect ./build/*
```

## Proposal: File Operation Rules

Claude Code hooks can match on `Write`, `Edit`, and `MultiEdit` tools, not just `Bash`. This would let Dippy control file modifications with per-project config.

### Proposed Syntax

```
allow-edit <glob>
ask-edit <glob>
ask-edit <glob> "message"
deny-edit <glob>
deny-edit <glob> "message"
```

Applies to Write, Edit, and MultiEdit operations. Globs match file paths using `**` for recursive directory matching (same as redirect rules).

### Example

```
# Allow editing source files
allow-edit src/**

# Prompt for config changes
ask-edit **/config.* "Config changes need review"

# Block sensitive files
deny-edit **/.env* "Use environment variables instead"
deny-edit **/secrets/** "Secrets are managed externally"
```

### Interaction with Built-in Permissions

Claude Code's `settings.json` has a `permissions` section with `allow`/`deny` rules. These systems layer:

1. **Built-in permissions** - global baseline, no per-project config, no messages
2. **Dippy** - per-project overrides with messages

If built-in permissions deny, Dippy never sees the request. If built-in allows, Dippy can still ask or deny.

### Opting In

To enable file operation rules, update your hook matcher in `settings.json`:

```json
"matcher": "Bash|Write|Edit|MultiEdit"
```

**Trade-off:** This replaces Claude's "Allow editing this session" UI with Dippy's `sticky-session`. There's no way for hooks to defer to Claude's native session memory.

## Proposal: MCP Tool Rules

MCP tools follow the pattern `mcp__<server>__<tool>`. Dippy could control which MCP operations are allowed per-project.

### Proposed Syntax

```
allow-mcp <pattern>
ask-mcp <pattern>
ask-mcp <pattern> "message"
deny-mcp <pattern>
deny-mcp <pattern> "message"
```

Patterns use fnmatch globs against the full tool name.

### Example

```
# Allow read-only GitHub operations
allow-mcp mcp__github__get_*
allow-mcp mcp__github__list_*
allow-mcp mcp__github__search_*

# Prompt for writes
ask-mcp mcp__github__create_* "Creating GitHub resources"
ask-mcp mcp__github__update_* "Modifying GitHub resources"

# Block destructive operations
deny-mcp mcp__github__delete_* "No deletions without manual review"
deny-mcp mcp__github__merge_* "Merges need manual approval"
```

### Opting In

To enable MCP rules, update your hook matcher:

```json
"matcher": "Bash|mcp__.*"
```

Or for both file and MCP control:

```json
"matcher": "Bash|Write|Edit|MultiEdit|mcp__.*"
```

## Implementation Notes

**Hook caching:** Claude Code caches hooks at session start. Changes to dippy code or config require restarting the session to take effect.

**Two logging systems:** Dippy has two separate logs:
- `~/.claude/hook-approvals.log` - written by Python's `logging` module, always works
- Audit log (configurable path) - written by `log_decision()`, requires `set log <path>`

**Log path:** The `~/.dippy/` directory may have write issues when running as a Claude Code hook. Using `~/.claude/dippy-audit.log` is more reliable.

**Debugging config rules:** Check `~/.claude/hook-approvals.log` to see which rules matched. Entries show the pattern in parentheses when a config rule matches: `APPROVED: rm (rm /tmp/test-*)` vs just `APPROVED: rm` for built-in approval.

**System Python:** The hook runs with `#!/usr/bin/env python3` (system Python), not the uv virtualenv. System Python may be older and lack dependencies like `structlog`. Dippy must use only stdlib imports, or fail gracefully when optional dependencies are missing.

**VS Code syntax highlighting:** Install the extension from `editors/vscode/`:
```bash
cd editors/vscode
npx @vscode/vsce package
code --install-extension dippy-syntax-*.vsix
```
Highlights `.dippy` files and files named `config` (for `~/.dippy/config`).
