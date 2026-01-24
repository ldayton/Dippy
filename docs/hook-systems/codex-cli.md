# OpenAI Codex CLI: Exhaustive Reference

This document provides a comprehensive reference for OpenAI's Codex CLI, covering configuration, sandbox modes, approval policies, notification hooks, execpolicy, MCP integration, and comparison with other AI coding assistants.

**Last Updated:** January 2026
**Codex CLI Versions Covered:** v0.65 through v0.80.x

---

## Table of Contents

1. [Overview](#overview)
2. [Installation and Authentication](#installation-and-authentication)
3. [Configuration](#configuration)
4. [Sandbox Modes](#sandbox-modes)
5. [Approval Policies](#approval-policies)
6. [Notification Hooks](#notification-hooks)
7. [Execpolicy (Command Filtering)](#execpolicy-command-filtering)
8. [Tools](#tools)
9. [MCP Server Integration](#mcp-server-integration)
10. [Skills System](#skills-system)
11. [Command Line Reference](#command-line-reference)
12. [Shell Environment Policy](#shell-environment-policy)
13. [Feature Flags](#feature-flags)
14. [Version History and Changelog](#version-history-and-changelog)
15. [Known Issues and Limitations](#known-issues-and-limitations)
16. [Comparison with Claude Code, Cursor, and Gemini CLI](#comparison-with-claude-code-cursor-and-gemini-cli)
17. [Sources and References](#sources-and-references)

---

## Overview

Codex CLI is OpenAI's locally-run coding agent that operates from your terminal. It can read, change, and run code on your machine within the selected directory.

**Key Characteristics:**
- Open source, built in Rust for speed and efficiency
- Available on macOS, Linux, and Windows (experimental)
- Included with ChatGPT Plus, Pro, Business, Edu, and Enterprise plans
- Supports MCP (Model Context Protocol) for third-party tool integration
- **No full hook system** - uses notification callbacks and policy controls instead

**Repository:** [github.com/openai/codex](https://github.com/openai/codex)
**License:** Apache-2.0
**Stars:** 56k+ (as of January 2026)

**Sources:**
- [Codex CLI Documentation](https://developers.openai.com/codex/cli/)
- [GitHub Repository](https://github.com/openai/codex)

---

## Installation and Authentication

### Installation Methods

| Method | Command |
| ------ | ------- |
| npm | `npm i -g @openai/codex` |
| Homebrew | `brew install openai/tap/codex` |
| Direct Download | Platform binaries from [GitHub Releases](https://github.com/openai/codex/releases) |

### Platform Support

| Platform | Status |
| -------- | ------ |
| macOS (arm64, x86_64) | Full support |
| Linux (x86_64, arm64) | Full support |
| Windows | Experimental (WSL recommended) |

### Authentication Options

1. **ChatGPT Account** (recommended): Integrates with Plus, Pro, Team, Edu, or Enterprise plans
2. **API Key**: Requires `OPENAI_API_KEY` environment variable

```bash
codex login          # Interactive login
codex logout         # Remove credentials
```

### Configuration Options

| Option | Type | Description |
| ------ | ---- | ----------- |
| `forced_login_method` | string | `chatgpt` or `api` |
| `cli_auth_credentials_store` | string | `file`, `keyring`, or `auto` |

---

## Configuration

### File Locations

| Priority | Location | Description |
| -------- | -------- | ----------- |
| 1 | CLI flags | Highest priority |
| 2 | Profile-specific values | `[profiles.<name>]` in config.toml |
| 3 | Project config | `.codex/config.toml` in project root |
| 4 | User config | `~/.codex/config.toml` |
| 5 | Built-in defaults | Lowest priority |

### Configuration Format

Codex uses TOML format (not JSON like Claude Code):

```toml
# ~/.codex/config.toml

model = "gpt-5.2-codex"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_reasoning_effort = "high"

[shell_environment_policy]
include_only = ["PATH", "HOME", "USER"]

[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "..." }
```

### Profiles

Named configuration sets for different workflows:

```toml
[profiles.safe]
approval_policy = "untrusted"
sandbox_mode = "read-only"

[profiles.yolo]
approval_policy = "never"
sandbox_mode = "danger-full-access"
```

Usage: `codex --profile safe`

### Admin-Enforced Settings (requirements.toml)

Administrators can constrain settings via `requirements.toml`:

```toml
allowed_approval_policies = ["untrusted", "on-failure"]
allowed_sandbox_modes = ["read-only", "workspace-write"]
```

**Source:** [Advanced Configuration](https://developers.openai.com/codex/config-advanced/)

---

## Sandbox Modes

Codex provides three sandbox modes controlling filesystem and network access:

| Mode | Description | Use Case |
| ---- | ----------- | -------- |
| `read-only` | No write access; browsing only | Code review, exploration |
| `workspace-write` | Write access within workspace | Normal development (default) |
| `danger-full-access` | Full machine access | System administration |

### Setting Sandbox Mode

```bash
# CLI flag
codex --sandbox workspace-write

# Config file
sandbox_mode = "workspace-write"
```

### workspace-write Options

Fine-tune workspace-write behavior:

| Option | Type | Description |
| ------ | ---- | ----------- |
| `sandbox_workspace_write.network_access` | boolean | Allow outbound network |
| `sandbox_workspace_write.writable_roots` | array | Additional writable directories |
| `sandbox_workspace_write.exclude_slash_tmp` | boolean | Exclude `/tmp` from writable |
| `sandbox_workspace_write.exclude_tmpdir_env_var` | boolean | Exclude `$TMPDIR` from writable |

### Platform Implementation

| Platform | Technology |
| -------- | ---------- |
| macOS | Seatbelt (sandbox-exec) |
| Linux | Landlock LSM |
| Windows | Experimental (elevated sandbox) |

### Sandbox CLI Command

Test sandbox behavior independently:

```bash
codex sandbox "ls -la"
```

---

## Approval Policies

Controls when Codex pauses for human approval before executing commands:

| Policy | Behavior | Risk Level |
| ------ | -------- | ---------- |
| `untrusted` | Always ask before any action | Safest |
| `on-failure` | Ask only after command fails | Moderate |
| `on-request` | Ask only when agent requests | Balanced |
| `never` | Never ask for approval | Dangerous |

### Setting Approval Policy

```bash
# CLI flag
codex --ask-for-approval on-request

# Shortcut for on-request + workspace-write
codex --full-auto

# Config file
approval_policy = "on-request"
```

### Dangerous Mode

Bypass all safety mechanisms (use with extreme caution):

```bash
codex --dangerously-bypass-approvals-and-sandbox
# or
codex --yolo
```

**Warning:** Only use in isolated environments (VMs, containers).

---

## Notification Hooks

Codex has a **limited hook system** compared to Claude Code. Currently, only notification callbacks are supported.

### Configuration

```toml
# ~/.codex/config.toml
notify = ["bash", "-lc", "afplay /System/Library/Sounds/Blow.aiff"]
```

### Supported Events

| Event | Description |
| ----- | ----------- |
| `agent-turn-complete` | Agent finishes a turn |
| `approval-requested` | Agent requests user approval |

### TUI Notifications

```toml
[tui]
notifications = true                    # All notifications
notifications = ["agent-turn-complete"] # Filtered
```

### Notification Payload

The notify command receives a JSON payload via stdin:

```json
{
  "event": "agent-turn-complete",
  "session_id": "abc123",
  "timestamp": "2026-01-14T10:30:00Z"
}
```

### Hook Feature Request

The community has requested a full hook system similar to Claude Code. See [Discussion #2150](https://github.com/openai/codex/discussions/2150).

Requested features:
- Pre/post tool execution hooks
- Exit code handling
- Ability to block/modify operations
- Additional event types

**Status:** Under consideration; maintainers direct users to upvote [Issue #2109](https://github.com/openai/codex/issues/2109).

---

## Execpolicy (Command Filtering)

Execpolicy is an **experimental** feature for filtering shell commands before execution.

### Enabling Execpolicy

```toml
[features]
exec_policy = true  # Default: on
```

### CLI Command

Test whether a command would be allowed:

```bash
codex execpolicy "rm -rf /"
```

### TUI Whitelist

When a command is approved in the TUI, it can be added to a whitelist for future auto-approval (v0.66.0+).

**Note:** Execpolicy documentation is sparse. The feature is experimental and APIs may change.

---

## Tools

Codex provides built-in tools for file operations, shell execution, and web access.

### Core Tools

| Tool | Description | Feature Flag |
| ---- | ----------- | ------------ |
| Shell | Execute shell commands | `features.shell_tool` (default: on) |
| File Read | Read file contents | Built-in |
| File Write | Write/create files | Built-in |
| Apply Patch | Apply code patches | `features.apply_patch_freeform` |
| Web Search | Search the web | `features.web_search_request` |

### Shell Tool Behavior

| Platform | Execution Method |
| -------- | ---------------- |
| Windows | `powershell.exe -NoProfile -Command` |
| Linux/macOS | `bash -c` |

Environment variable `CODEX_CLI=1` is set in subprocesses.

### Tool Configuration

```toml
[features]
shell_tool = true
web_search_request = true
apply_patch_freeform = false  # Experimental
```

### MCP Tools

MCP tools follow the naming pattern: `mcp__<server>__<tool>`

Example: `mcp__github__create_issue`

---

## MCP Server Integration

Codex supports Model Context Protocol (MCP) for third-party tool integration.

### Configuration

```toml
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "..." }

[mcp_servers.remote]
url = "https://mcp.example.com"
bearer_token_env_var = "MCP_TOKEN"
```

### STDIO Server Options

| Option | Type | Description |
| ------ | ---- | ----------- |
| `command` | string | Startup command (required) |
| `args` | array | Command arguments |
| `env` | map | Environment variables |
| `cwd` | string | Working directory |

### HTTP Server Options

| Option | Type | Description |
| ------ | ---- | ----------- |
| `url` | string | Server endpoint (required) |
| `bearer_token_env_var` | string | Auth token env var |
| `http_headers` | map | Static headers |
| `env_http_headers` | map | Headers from env vars |

### Common Options

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `enabled` | boolean | true | Enable/disable without deletion |
| `enabled_tools` | array | - | Tool allowlist |
| `disabled_tools` | array | - | Tool denylist |
| `startup_timeout_sec` | number | 10 | Server startup timeout |
| `tool_timeout_sec` | number | 60 | Per-tool execution timeout |

### MCP CLI Commands

```bash
codex mcp add <server-name>    # Add server
codex mcp list                 # List servers
codex mcp remove <server-name> # Remove server
```

### Recommended MCP Servers

- **Context7**: Developer documentation
- **Figma**: Design access
- **Playwright**: Browser automation
- **GitHub**: Repository management
- **Sentry**: Error logs

**Source:** [MCP Documentation](https://developers.openai.com/codex/mcp/)

---

## Skills System

Skills extend Codex with task-specific capabilities, following the [Agent Skills Standard](https://agentskills.io).

### Skill Structure

```
skill-name/
├── SKILL.md          # Required: Instructions and metadata
├── scripts/          # Optional: Executable code
├── references/       # Optional: Documentation
└── assets/           # Optional: Templates
```

### SKILL.md Format

```markdown
---
name: skill-name
description: Description for skill selection
---

Skill instructions here...
```

### Skill Locations (Priority Order)

| Scope | Location | Use Case |
| ----- | -------- | -------- |
| REPO | `.codex/skills` | Project-specific |
| USER | `~/.codex/skills` | Personal |
| ADMIN | `/etc/codex/skills` | System-level |
| SYSTEM | Bundled | Default skills |

### Invoking Skills

1. **Explicit**: `/skills` command or `$skill-name` mention
2. **Implicit**: Codex auto-selects based on task match

### Built-in Skills

| Skill | Description |
| ----- | ----------- |
| `$skill-creator` | Guide skill creation |
| `$skill-installer` | Download skills from repositories |
| `$create-plan` | Research and plan features (experimental) |

**Source:** [Skills Documentation](https://developers.openai.com/codex/skills/)

---

## Command Line Reference

### Main Commands

| Command | Status | Description |
| ------- | ------ | ----------- |
| `codex` | Stable | Launch interactive TUI |
| `codex exec` | Stable | Non-interactive execution |
| `codex apply` | Stable | Apply Codex Cloud diffs locally |
| `codex resume` | Stable | Continue previous session |
| `codex login` | Stable | Authenticate |
| `codex logout` | Stable | Remove credentials |
| `codex completion` | Stable | Generate shell completions |
| `codex cloud` | Experimental | Interact with cloud tasks |
| `codex mcp` | Experimental | Manage MCP servers |
| `codex sandbox` | Experimental | Run commands in sandbox |
| `codex execpolicy` | Experimental | Evaluate command policies |

### Global Flags

| Flag | Type | Description |
| ---- | ---- | ----------- |
| `--model, -m` | string | Override model |
| `--sandbox, -s` | string | Sandbox mode |
| `--ask-for-approval, -a` | string | Approval policy |
| `--cd, -C` | path | Set working directory |
| `--add-dir` | path | Additional writable directory |
| `--config, -c` | key=value | Override config value |
| `--profile, -p` | string | Load config profile |
| `--image, -i` | path | Attach image(s) |
| `--search` | boolean | Enable web search |
| `--full-auto` | boolean | on-request + workspace-write |
| `--yolo` | boolean | Bypass all safety |
| `--enable` | feature | Enable feature flag |
| `--disable` | feature | Disable feature flag |
| `--oss` | boolean | Use local Ollama |

### codex exec Flags

| Flag | Type | Description |
| ---- | ---- | ----------- |
| `--json` | boolean | Output JSONL events |
| `--color` | string | ANSI color control |
| `--output-last-message, -o` | path | Write final message to file |
| `--output-schema` | path | JSON Schema for validation |
| `--skip-git-repo-check` | boolean | Allow non-git directories |

### Slash Commands (TUI)

| Command | Description |
| ------- | ----------- |
| `/model` | Switch models |
| `/review` | Code review mode |
| `/skills` | Manage skills |
| `/resume` | Resume session |
| `/ps` | Process status |
| `/feedback` | Submit feedback |
| `/experimental` | Test experimental features |
| `/elevate-sandbox` | Upgrade sandbox mode |

### Keyboard Shortcuts (TUI)

| Shortcut | Action |
| -------- | ------ |
| `Ctrl+G` | Open external editor |
| `Ctrl+P/N` | Navigate history |
| `@` | File fuzzy search |
| `!` | Execute shell command |
| `$` | Mention skill |

**Source:** [Command Line Reference](https://developers.openai.com/codex/cli/reference/)

---

## Shell Environment Policy

Control which environment variables are passed to subprocesses:

```toml
[shell_environment_policy]
inherit = "core"              # all | core | none
include_only = ["PATH", "HOME", "USER"]
exclude = ["*SECRET*", "*KEY*", "*TOKEN*"]
set = { MY_VAR = "value" }
ignore_default_excludes = false
```

### Options

| Option | Type | Description |
| ------ | ---- | ----------- |
| `inherit` | string | Base inheritance: `all`, `core`, `none` |
| `include_only` | array | Whitelist patterns (glob) |
| `exclude` | array | Blacklist patterns (glob) |
| `set` | map | Explicit overrides |
| `ignore_default_excludes` | boolean | Keep KEY/SECRET/TOKEN vars |

### Default Excludes

By default, Codex excludes variables matching:
- `*KEY*`
- `*SECRET*`
- `*TOKEN*`
- `*PASSWORD*`

---

## Feature Flags

Toggle experimental and optional capabilities:

```toml
[features]
shell_tool = true              # Stable (default: on)
web_search_request = true      # Stable
exec_policy = true             # Experimental (default: on)
shell_snapshot = false         # Beta
unified_exec = false           # Beta
remote_compaction = true       # Experimental (default: on)
tui2 = false                   # Experimental
apply_patch_freeform = false   # Experimental
elevated_windows_sandbox = false
powershell_utf8 = false
remote_models = false
```

### Enabling via CLI

```bash
codex --enable shell_snapshot
codex --disable web_search_request
```

---

## Version History and Changelog

### January 2026

**0.80.0** (2026-01-09)
- Thread forking endpoints for branching sessions
- Metrics capabilities with additional counters
- Elevated sandbox onboarding prompts
- **Bug fix:** Subprocesses inherit `LD_LIBRARY_PATH` (was causing 10x+ performance regressions)

**0.79.0** (2026-01-07)
- Multi-conversation agent control
- `thread/rollback` API for undoing turns
- `web_search_cached` flag

**0.78.0** (2026-01-06)
- `Ctrl+G` opens external editor
- Project-aware config layering (`.codex/config.toml`)
- Enterprise MDM configuration (macOS)

### December 2025

**0.77.0** (2025-12-21)
- TUI mouse/trackpad scrolling improvements
- `allowed_sandbox_modes` in requirements.toml
- MCP OAuth login

**Agent Skills Launch** (2025-12-19)
- Folder-based skills following agentskills.io spec
- Built-in `$skill-creator` and `$skill-installer`

**GPT-5.2-Codex** (2025-12-18)
- Most advanced agentic coding model
- Context compaction improvements
- Default model for signed-in users

**0.73.0** (2025-12-15)
- Ghost snapshot v2
- SkillsManager
- OpenTelemetry tracing

**0.72.0** (2025-12-13)
- Remote compact for API-key users
- PowerShell parsing improvements
- Elevated Sandbox updates

**0.71.0** (2025-12-11)
- GPT-5.2 frontier model launch

**0.66.0** (2025-12-09)
- Execpolicy TUI whitelist after approval
- Shell MCP execpolicy enforcement

### November 2025

**GPT-5.1-Codex-Max** (2025-11-18)
- Extra High (`xhigh`) reasoning effort option

**GPT-5.1-Codex Variants** (2025-11-13)
- `gpt-5.1-codex-mini` and `gpt-5.1-codex`

**GPT-5-Codex-Mini** (2025-11-07)
- Cost-effective smaller model (4x more usage)

**GPT-5-Codex Update** (2025-11-06)
- More reliable file edits with `apply_patch`
- Fewer destructive actions

### October 2025

**General Availability** (2025-10-06)
- Slack integration (`@Codex`)
- Codex SDK (TypeScript)
- Admin tools and analytics

### September 2025

**GPT-5-Codex Launch** (2025-09-15)
- GPT-5 optimized for agentic coding
- Image output support
- `codex resume` for session continuation
- Context compaction

### August 2025

**IDE Extension** (2025-08-27)
- VS Code, Cursor, Windsurf support
- ChatGPT sign-in authentication
- Code review capability

**Image Input** (2025-08-21)
- PNG/JPEG support for visual context
- Container caching (90% faster startup)

### Earlier 2025

**June 2025**
- Best of N response generation
- Agent internet access
- Voice dictation

**May 2025**
- iOS support in ChatGPT app
- Environment setup redesign

**Source:** [Codex Changelog](https://developers.openai.com/codex/changelog/)

---

## Known Issues and Limitations

### No Full Hook System

Unlike Claude Code, Cursor, and Gemini CLI, Codex does **not** have a comprehensive hook system for intercepting tool execution.

**Available:** Notification callbacks (`notify` setting)
**Missing:**
- PreToolUse / PostToolUse hooks
- Permission interception
- Tool input/output modification
- Session lifecycle hooks

**Feature Request:** [Discussion #2150](https://github.com/openai/codex/discussions/2150)

### Environment Variable Inheritance Bug (Fixed)

**Versions affected:** Pre-0.80.0
**Issue:** Subprocesses didn't inherit `LD_LIBRARY_PATH`/`DYLD_LIBRARY_PATH`, causing 10x+ performance regressions.
**Status:** Fixed in 0.80.0

### Windows Support Limitations

- Experimental status
- WSL recommended for full functionality
- PowerShell-specific parsing issues
- Elevated sandbox still experimental

### Exit Command Behavior

**Issue:** The exit command shows "Goodbye" but may not terminate the session on Windows.

### MCP OAuth

Requires feature flag in some versions; login flow may have edge cases.

---

## Comparison with Claude Code, Cursor, and Gemini CLI

### Hook System Comparison

| Feature | Codex CLI | Claude Code | Cursor | Gemini CLI |
| ------- | --------- | ----------- | ------ | ---------- |
| Pre-tool hooks | ❌ | ✅ PreToolUse | ✅ beforeShellExecution | ✅ BeforeTool |
| Post-tool hooks | ❌ | ✅ PostToolUse | ✅ afterFileEdit | ✅ AfterTool |
| Permission hooks | ❌ | ✅ PermissionRequest | ✅ (via beforeShell) | ✅ Notification |
| Session hooks | ❌ | ✅ SessionStart/End | ❌ | ✅ SessionStart/End |
| Model hooks | ❌ | ❌ | ❌ | ✅ BeforeModel/AfterModel |
| Notification | ✅ notify | ✅ Notification | ❌ | ✅ Notification |
| Input modification | ❌ | ✅ updatedInput | ✅ (limited) | ✅ |
| Exit code blocking | ❌ | ✅ Exit 2 | ❌ | ✅ Exit 2 |

### Configuration Comparison

| Aspect | Codex CLI | Claude Code | Cursor | Gemini CLI |
| ------ | --------- | ----------- | ------ | ---------- |
| Config format | TOML | JSON | JSON | JSON |
| Config location | `~/.codex/config.toml` | `~/.claude/settings.json` | `~/.cursor/hooks.json` | `~/.gemini/settings.json` |
| Project config | `.codex/config.toml` | `.claude/settings.json` | `.cursor/hooks.json` | `.gemini/settings.json` |
| Tool matchers | N/A | Regex patterns | N/A (global) | Regex patterns |

### Sandbox/Approval Comparison

| Aspect | Codex CLI | Claude Code | Cursor | Gemini CLI |
| ------ | --------- | ----------- | ------ | ---------- |
| Sandbox modes | 3 levels | Permission modes | Sandbox mode | Policy engine |
| Approval policies | 4 levels | Built into permission | ask/allow/deny | Similar to Claude |
| Admin enforcement | requirements.toml | Enterprise settings | MDM | System settings |

### Unique Codex CLI Features

1. **TOML Configuration**: More readable than JSON for complex configs
2. **Skills System**: Structured task-specific capabilities with agentskills.io standard
3. **Profiles**: Named configuration sets for workflow switching
4. **Ghost Snapshots**: Session state capture for debugging
5. **Codex Cloud**: Remote task execution with local diff application
6. **Built-in Code Review**: `/review` command with multiple modes

### Unique Features in Other Tools

**Claude Code:**
- Full hook system with 11 event types
- Tool matchers with regex patterns
- SubagentStart/SubagentStop hooks
- Prompt-type hooks (LLM-evaluated)

**Cursor:**
- IDE-native integration
- Tab completion hooks
- afterAgentThought hooks

**Gemini CLI:**
- BeforeModel/AfterModel hooks for LLM request modification
- BeforeToolSelection for tool filtering
- NPM plugin hooks with dependency injection
- Built-in Claude Code migration

---

## Sources and References

### Official Documentation

- [Codex CLI Overview](https://developers.openai.com/codex/cli/)
- [Codex CLI Features](https://developers.openai.com/codex/cli/features/)
- [Command Line Reference](https://developers.openai.com/codex/cli/reference/)
- [Basic Configuration](https://developers.openai.com/codex/config-basic/)
- [Advanced Configuration](https://developers.openai.com/codex/config-advanced/)
- [Configuration Reference](https://developers.openai.com/codex/config-reference/)
- [MCP Integration](https://developers.openai.com/codex/mcp/)
- [Skills Documentation](https://developers.openai.com/codex/skills/)
- [Codex Changelog](https://developers.openai.com/codex/changelog/)

### GitHub Resources

- [GitHub Repository](https://github.com/openai/codex)
- [Releases](https://github.com/openai/codex/releases)
- [Hook Feature Request (Discussion #2150)](https://github.com/openai/codex/discussions/2150)
- [Hook Feature Request (Issue #2109)](https://github.com/openai/codex/issues/2109)

### Related Documentation

- [Codex GitHub Action](https://developers.openai.com/codex/github-action/)
- [Codex Cloud](https://developers.openai.com/codex/cloud/)
- [Agent Skills Standard](https://agentskills.io)

---

## Appendix: Configuration Reference

### Complete config.toml Example

```toml
# ~/.codex/config.toml

# Core settings
model = "gpt-5.2-codex"
model_provider = "openai"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_reasoning_effort = "high"

# Notifications
notify = ["bash", "-c", "osascript -e 'display notification \"Codex finished\" with title \"Codex\"'"]

# Sandbox fine-tuning
[sandbox_workspace_write]
network_access = true
writable_roots = ["/tmp/codex-scratch"]
exclude_slash_tmp = false

# Shell environment
[shell_environment_policy]
inherit = "core"
include_only = ["PATH", "HOME", "USER", "LANG"]
exclude = ["*SECRET*", "*KEY*", "*TOKEN*"]

# Feature flags
[features]
shell_tool = true
web_search_request = true
exec_policy = true
shell_snapshot = false

# MCP servers
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GITHUB_TOKEN}" }
enabled_tools = ["create_issue", "list_issues", "create_pull_request"]
tool_timeout_sec = 30

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]

# TUI settings
[tui]
animations = true
notifications = ["agent-turn-complete", "approval-requested"]
show_tooltips = true

# Profiles
[profiles.safe]
approval_policy = "untrusted"
sandbox_mode = "read-only"

[profiles.fast]
approval_policy = "never"
model_reasoning_effort = "low"

# History
[history]
persistence = "save-all"
max_bytes = 10485760  # 10MB

# Telemetry (opt-out)
[analytics]
enabled = false

[feedback]
enabled = true
```

### Notification Script Example

```bash
#!/bin/bash
# ~/.codex/notify.sh

INPUT=$(cat)
EVENT=$(echo "$INPUT" | jq -r '.event')

case "$EVENT" in
  "agent-turn-complete")
    osascript -e 'display notification "Task complete" with title "Codex"'
    afplay /System/Library/Sounds/Glass.aiff
    ;;
  "approval-requested")
    osascript -e 'display notification "Approval needed" with title "Codex"'
    afplay /System/Library/Sounds/Ping.aiff
    ;;
esac
```

Configure with:
```toml
notify = ["bash", "~/.codex/notify.sh"]
```

---

*This document was compiled from official OpenAI documentation, GitHub repository, community discussions, and comparison with other AI coding assistants. For the most up-to-date information, consult the official sources linked above.*
