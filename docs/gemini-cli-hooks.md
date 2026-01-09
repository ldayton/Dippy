# Gemini CLI Hook System: Exhaustive Reference

This document provides an exhaustive reference for the Gemini CLI hook system, covering configuration, JSON schemas, tool names, edge cases, version differences, and comparisons with Claude Code.

**Last Updated:** January 2026
**Gemini CLI Versions Covered:** v0.15.x through v0.23.x

---

## Table of Contents

1. [Overview](#overview)
2. [Settings File Locations](#settings-file-locations)
3. [Hook Configuration JSON Schema](#hook-configuration-json-schema)
4. [Hook Events](#hook-events)
5. [Tool Names](#tool-names)
6. [Input JSON Schema](#input-json-schema)
7. [Output JSON Schema](#output-json-schema)
8. [Exit Code Behavior](#exit-code-behavior)
9. [Decision Field Values](#decision-field-values)
10. [Matcher Patterns](#matcher-patterns)
11. [Configuration Merge Strategies](#configuration-merge-strategies)
12. [Environment Variables](#environment-variables)
13. [CLI Commands for Hook Management](#cli-commands-for-hook-management)
14. [Claude Code Migration](#claude-code-migration)
15. [Gemini CLI vs Claude Code Comparison](#gemini-cli-vs-claude-code-comparison)
16. [Version History and Changes](#version-history-and-changes)
17. [Known Bugs and Issues](#known-bugs-and-issues)
18. [Edge Cases and Quirks](#edge-cases-and-quirks)
19. [Best Practices](#best-practices)
20. [Security Considerations](#security-considerations)
21. [Sources and References](#sources-and-references)

---

## Overview

Gemini CLI hooks are scripts or programs executed at specific points in the agentic loop, allowing interception and customization of behavior without modifying CLI source code.

**Key Characteristics:**
- Hooks run **synchronously** within the agent loop
- Communication uses **JSON over stdin/stdout** with exit code signaling
- Hooks mirror the contract used by Claude Code for compatibility
- The system was developed starting in late 2024 and matured through 2025

**Sources:**
- [Gemini CLI Hooks Documentation](https://geminicli.com/docs/hooks/)
- [GitHub Issue #9070: Comprehensive Hooking System](https://github.com/google-gemini/gemini-cli/issues/9070)

---

## Settings File Locations

### Configuration Hierarchy (Lowest to Highest Precedence)

| Priority | Location               | Description                           |
| -------- | ---------------------- | ------------------------------------- |
| 1        | Hardcoded defaults     | Built into Gemini CLI                 |
| 2        | System defaults        | OS-specific location (see below)      |
| 3        | User settings          | ~/.gemini/settings.json               |
| 4        | Project settings       | .gemini/settings.json in project root |
| 5        | System overrides       | /etc/gemini-cli/settings.json         |
| 6        | Environment variables  | Runtime overrides                     |
| 7        | Command-line arguments | Highest priority                      |

### System Default Locations by OS

| OS      | Path                                                        |
| ------- | ----------------------------------------------------------- |
| Linux   | /etc/gemini-cli/system-defaults.json                        |
| macOS   | /Library/Application Support/GeminiCli/system-defaults.json |
| Windows | C:\ProgramData\gemini-cli\system-defaults.json              |

The path can be overridden using GEMINI_CLI_SYSTEM_DEFAULTS_PATH environment variable.

### Format Migration (September 2025)

- **09/10/25**: New nested JSON format supported in stable release
- **09/17/25**: Automatic migration from old format began
- Legacy v1 configuration documented separately

**Source:** [Gemini CLI Configuration](https://geminicli.com/docs/get-started/configuration/)

---

## Hook Configuration JSON Schema

### Basic Structure

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "pattern",
        "hooks": [
          {
            "name": "unique-hook-identifier",
            "type": "command",
            "command": "./path/to/script.sh",
            "description": "Human-readable description",
            "timeout": 30000
          }
        ]
      }
    ],
    "disabled": ["hook-name-1", "hook-name-2"]
  }
}
```

### Hook Object Properties

| Property    | Type   | Required    | Default      | Description                                   |
| ----------- | ------ | ----------- | ------------ | --------------------------------------------- |
| name        | string | Recommended | Command path | Unique identifier for enable/disable commands |
| type        | string | Yes         | -            | Hook type; currently only "command" supported |
| command     | string | Yes         | -            | Path to script; supports $GEMINI_PROJECT_DIR  |
| description | string | No          | -            | Shown in /hooks panel                         |
| timeout     | number | No          | 60000        | Timeout in milliseconds                       |
| matcher     | string | No          | -            | Pattern to filter when hook runs              |

### Extension Hooks (v0.21.0+)

Extensions can include a hooks/hooks.json file:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "WriteFile",
        "hooks": [
          {
            "type": "command",
            "command": "${extensionPath}/scripts/lint.sh"
          }
        ]
      }
    ]
  }
}
```

Extension hooks support ${extensionPath} variable substitution.

**Source:** [GitHub Issue #14449: Hook Support in Extensions](https://github.com/google-gemini/gemini-cli/issues/14449)

---

## Hook Events

### Complete Event List

| Event               | Trigger Point                  | Matcher Applies To                            |
| ------------------- | ------------------------------ | --------------------------------------------- |
| SessionStart        | Session initialization         | startup, resume, clear                        |
| SessionEnd          | Session termination            | exit, clear, logout, prompt_input_exit, other |
| BeforeAgent         | Before planning phase          | N/A                                           |
| AfterAgent          | After agent loop completes     | N/A                                           |
| BeforeModel         | Before LLM request             | N/A                                           |
| AfterModel          | After LLM response             | N/A                                           |
| BeforeToolSelection | Pre-tool filtering             | N/A                                           |
| BeforeTool          | Before tool execution          | Tool names                                    |
| AfterTool           | After tool execution           | Tool names                                    |
| PreCompress         | Before context compression     | manual, auto                                  |
| Notification        | Permission/notification events | ToolPermission                                |

### Event Capabilities

| Event               | Can Block | Can Modify Input        | Can Inject Context      |
| ------------------- | --------- | ----------------------- | ----------------------- |
| BeforeTool          | Yes       | Yes (via deny + reason) | Yes                     |
| AfterTool           | Yes       | N/A                     | Yes (additionalContext) |
| BeforeAgent         | Yes       | N/A                     | Yes (additionalContext) |
| AfterAgent          | Yes       | N/A                     | N/A                     |
| BeforeModel         | Yes       | Yes (llm_request)       | N/A                     |
| AfterModel          | Yes       | Yes (llm_response)      | N/A                     |
| BeforeToolSelection | No        | Yes (toolConfig)        | N/A                     |
| SessionStart        | No        | N/A                     | Yes (additionalContext) |

**Source:** [Hooks Reference](https://geminicli.com/docs/hooks/reference/)

---

## Tool Names

### Core Tool Names for Matchers

| Category        | Tool Names                                      |
| --------------- | ----------------------------------------------- |
| File Operations | read_file, read_many_files, write_file, replace |
| File System     | list_directory, glob, search_file_content       |
| Shell Execution | run_shell_command                               |
| Web/External    | google_web_search, web_fetch                    |
| Agent Features  | write_todos, save_memory, delegate_to_agent     |

### MCP Tool Name Format

MCP tools follow the pattern: mcp__<server_name>__<tool_name>

Example: mcp__github__create_issue

### Shell Tool Details (run_shell_command)

The shell tool executes commands with platform-specific behavior:

| Platform    | Execution Method                   |
| ----------- | ---------------------------------- |
| Windows     | powershell.exe -NoProfile -Command |
| Linux/macOS | bash -c                            |

**Configuration options:**
```json
{
  "tools": {
    "shell": {
      "enableInteractiveShell": true,
      "showColor": true,
      "pager": "cat"
    }
  }
}
```

When run_shell_command executes, it sets GEMINI_CLI=1 environment variable in subprocesses.

**Source:** [Shell Tool Documentation](https://geminicli.com/docs/tools/shell/)

---

## Input JSON Schema

### Base Fields (All Events)

Every hook receives these fields via stdin:

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/path/to/project",
  "hook_event_name": "BeforeTool",
  "timestamp": "2025-12-01T10:30:00Z"
}
```

### Tool Events (BeforeTool, AfterTool)

```json
{
  "session_id": "...",
  "transcript_path": "...",
  "cwd": "...",
  "hook_event_name": "BeforeTool",
  "timestamp": "...",
  "tool_name": "write_file",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": { },
  "mcp_context": {
    "server_name": "github",
    "tool_name": "create_issue",
    "command": "...",
    "args": [],
    "cwd": "...",
    "url": "...",
    "tcp": "..."
  }
}
```

**MCP Context Transport Types:**
- stdio: command, args, cwd
- SSE/HTTP: url
- WebSocket: tcp

### Agent Events (BeforeAgent, AfterAgent)

```json
{
  "session_id": "...",
  "hook_event_name": "BeforeAgent",
  "prompt": "User's submitted text",
  "prompt_response": "Final model response",
  "stop_hook_active": true
}
```

### Model Events (BeforeModel, AfterModel, BeforeToolSelection)

```json
{
  "session_id": "...",
  "hook_event_name": "BeforeModel",
  "llm_request": {
    "model": "gemini-2.0-flash",
    "messages": [
      { "role": "user", "content": "..." },
      { "role": "model", "content": "..." }
    ],
    "config": {
      "temperature": 0.7,
      "maxOutputTokens": 8192,
      "topP": 0.95,
      "topK": 40
    },
    "toolConfig": {
      "mode": "AUTO",
      "allowedFunctionNames": ["read_file", "write_file"]
    }
  },
  "llm_response": { }
}
```

### Session Events

**SessionStart:**
```json
{
  "hook_event_name": "SessionStart",
  "source": "startup"
}
```
Values: "startup" | "resume" | "clear"

**SessionEnd:**
```json
{
  "hook_event_name": "SessionEnd",
  "reason": "exit"
}
```
Values: "exit" | "clear" | "logout" | "prompt_input_exit" | "other"

### Notification Events

```json
{
  "hook_event_name": "Notification",
  "notification_type": "ToolPermission",
  "message": "...",
  "details": { }
}
```

---

## Output JSON Schema

### Common Output Fields

```json
{
  "decision": "allow",
  "reason": "Explanation for agent",
  "systemMessage": "Message for user",
  "continue": true,
  "stopReason": "User-facing termination message",
  "suppressOutput": false,
  "hookSpecificOutput": { }
}
```

### hookSpecificOutput by Event

**SessionStart, BeforeAgent, AfterTool:**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "AfterTool",
    "additionalContext": "Extra context appended to agent"
  }
}
```

**BeforeModel:**
```json
{
  "hookSpecificOutput": {
    "llm_request": { },
    "llm_response": { }
  }
}
```

**AfterModel:**
```json
{
  "hookSpecificOutput": {
    "llm_response": { }
  }
}
```

**BeforeToolSelection:**
```json
{
  "hookSpecificOutput": {
    "toolConfig": {
      "mode": "ANY",
      "allowedFunctionNames": ["read_file", "write_file"]
    }
  }
}
```

### Stable LLMRequest Object

```json
{
  "model": "string",
  "messages": [
    {
      "role": "user | model | system",
      "content": "string or array of parts"
    }
  ],
  "config": {
    "temperature": 0.7,
    "maxOutputTokens": 8192,
    "topP": 0.95,
    "topK": 40
  },
  "toolConfig": {
    "mode": "AUTO | ANY | NONE",
    "allowedFunctionNames": ["tool1", "tool2"]
  }
}
```

### Stable LLMResponse Object

```json
{
  "text": "string",
  "candidates": [
    {
      "content": {
        "role": "model",
        "parts": ["string"]
      },
      "finishReason": "STOP | MAX_TOKENS | SAFETY | RECITATION | OTHER",
      "index": 0,
      "safetyRatings": [
        {
          "category": "HARM_CATEGORY_...",
          "probability": "NEGLIGIBLE | LOW | MEDIUM | HIGH",
          "blocked": false
        }
      ]
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 100,
    "candidatesTokenCount": 200,
    "totalTokenCount": 300
  }
}
```

**Note:** In v1, model hooks are primarily text-focused. Non-text parts in the content array are simplified to string representation.

---

## Exit Code Behavior

| Exit Code | Behavior             | stdout Handling                                        |
| --------- | -------------------- | ------------------------------------------------------ |
| 0         | Success              | Parsed as JSON; falls back to systemMessage if invalid |
| 2         | Blocking error       | stderr shown to agent/user; operation may be blocked   |
| Other     | Non-blocking warning | stderr logged but execution continues                  |

### Exit Code Semantics Comparison

| Aspect   | Gemini CLI          | Claude Code |
| -------- | ------------------- | ----------- |
| Success  | 0                   | 0           |
| Blocking | 2                   | 2           |
| Warning  | Non-zero (except 2) | Non-zero    |

**Source:** [Hooks Reference](https://geminicli.com/docs/hooks/reference/)

---

## Decision Field Values

### Available Decision Values

| Value   | Effect             | Use Case                             |
| ------- | ------------------ | ------------------------------------ |
| allow   | Operation proceeds | Explicitly permit action             |
| deny    | Operation blocked  | Block with reason shown to agent     |
| block   | Operation blocked  | Similar to deny                      |
| ask     | Prompt user        | Request user confirmation            |
| approve | Approve pending    | Approve a previously asked operation |

### Decision Examples

**Deny a tool execution:**
```json
{
  "decision": "deny",
  "reason": "Potential secret detected in file content"
}
```

**Allow with context injection:**
```json
{
  "decision": "allow",
  "hookSpecificOutput": {
    "additionalContext": "Remember to format code with prettier after writing"
  }
}
```

### Simple Exit Code Alternative

Instead of JSON output, hooks can use simple exit codes:
- Exit 0 = allow (stdout shown to user)
- Exit 2 = deny (stderr shown to agent)

---

## Matcher Patterns

### Pattern Types

| Type     | Syntax               | Example             | Matches                          |
| -------- | -------------------- | ------------------- | -------------------------------- |
| Exact    | "tool_name"          | "read_file"         | Only read_file                   |
| Regex    | "pattern1\|pattern2" | "write_.*\|replace" | write_file, write_todos, replace |
| Wildcard | "*" or ""            | "*"                 | All tools                        |

### Session Event Matchers

| Event        | Available Matchers                            |
| ------------ | --------------------------------------------- |
| SessionStart | startup, resume, clear                        |
| SessionEnd   | exit, clear, logout, prompt_input_exit, other |
| PreCompress  | manual, auto                                  |
| Notification | ToolPermission                                |

### Configuration Example

```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "write_file|replace",
        "hooks": [
          {
            "name": "secret-scanner",
            "type": "command",
            "command": "$GEMINI_PROJECT_DIR/.gemini/hooks/scan-secrets.sh"
          }
        ]
      }
    ]
  }
}
```

---

## Configuration Merge Strategies

### UNION Merge Strategy

Used for hooks.disabled array:
- Combines disabled lists from all configuration sources
- A hook disabled in any scope remains disabled
- Cannot override a disabled hook from a lower-priority scope

### CONCAT Merge Strategy

Used for hook event arrays (BeforeTool, AfterTool, etc.):
- Concatenates hook arrays from all sources
- Supports both predefined and custom event types

### Deduplication

If multiple hooks with identical name and command are discovered across layers:
- The hook from the higher-priority layer is kept
- Others are ignored

**Source:** [GitHub PR #14225](https://github.com/google-gemini/gemini-cli/pull/14225)

---

## Environment Variables

### Available to Hooks

| Variable                     | Description                       |
| ---------------------------- | --------------------------------- |
| GEMINI_PROJECT_DIR           | Project root directory            |
| GEMINI_SESSION_ID            | Current session identifier        |
| GEMINI_API_KEY               | API key (if configured)           |
| All parent process variables | Inherited from Gemini CLI process |

### Variable Substitution in Commands

Commands support environment variable substitution:

```json
{
  "command": "$GEMINI_PROJECT_DIR/.gemini/hooks/my-hook.sh"
}
```

Both $VAR_NAME and ${VAR_NAME} syntax are supported.

### Security Note

Hooks inherit the Gemini CLI process environment, which may include sensitive API keys. Gemini CLI attempts to sanitize sensitive variables, but caution is advised.

---

## CLI Commands for Hook Management

### /hooks Command

| Subcommand                 | Description                              |
| -------------------------- | ---------------------------------------- |
| /hooks panel               | Display all configured hooks with status |
| /hooks enable <hook-name>  | Enable a specific hook                   |
| /hooks disable <hook-name> | Disable a specific hook                  |

### gemini hooks CLI Commands

```bash
# Install a plugin hook package
gemini hooks install <package>

# Uninstall plugin hooks
gemini hooks uninstall

# Migrate from Claude Code
gemini hooks migrate --from-claude

# Reload hooks
gemini hooks reload
```

### Disabling Hooks

Add hook names to the hooks.disabled array:

```json
{
  "hooks": {
    "disabled": ["hook-name-1", "hook-name-2"]
  }
}
```

---

## Claude Code Migration

### Migration Command

```bash
gemini hooks migrate --from-claude
```

### Event Name Mappings

| Claude Code      | Gemini CLI   |
| ---------------- | ------------ |
| PreToolUse       | BeforeTool   |
| PostToolUse      | AfterTool    |
| UserPromptSubmit | BeforeAgent  |
| Stop             | AfterAgent   |
| SessionStart     | SessionStart |
| SessionEnd       | SessionEnd   |
| Notification     | Notification |

### Tool Name Mappings

| Claude Code | Gemini CLI          |
| ----------- | ------------------- |
| Bash        | run_shell_command   |
| Read        | read_file           |
| Write       | write_file          |
| Edit        | replace             |
| MultiEdit   | replace             |
| Glob        | glob                |
| Grep        | search_file_content |
| WebFetch    | web_fetch           |
| WebSearch   | google_web_search   |
| Task        | delegate_to_agent   |

### Environment Variable Mappings

| Claude Code        | Gemini CLI         |
| ------------------ | ------------------ |
| CLAUDE_PROJECT_DIR | GEMINI_PROJECT_DIR |
| CLAUDE_SESSION_ID  | GEMINI_SESSION_ID  |

---

## Gemini CLI vs Claude Code Comparison

### Feature Comparison

| Feature             | Gemini CLI                         | Claude Code     |
| ------------------- | ---------------------------------- | --------------- |
| Shell Tool Name     | run_shell_command                  | Bash            |
| File Read Tool      | read_file                          | Read            |
| File Write Tool     | write_file                         | Write           |
| Edit Tool           | replace                            | Edit, MultiEdit |
| Pre-tool Event      | BeforeTool                         | PreToolUse      |
| Post-tool Event     | AfterTool                          | PostToolUse     |
| Pre-model Hook      | BeforeModel                        | Not available   |
| Tool Selection Hook | BeforeToolSelection                | Not available   |
| Plugin Hooks        | NPM packages with geminicli-plugin | Not available   |
| Migration Support   | Yes (--from-claude)                | N/A             |

### Input JSON Differences

**Gemini CLI:**
```json
{
  "hook_event_name": "BeforeTool",
  "tool_name": "write_file",
  "tool_input": { }
}
```

**Claude Code:**
```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": { }
}
```

### Output JSON Differences

**Gemini CLI:**
```json
{
  "decision": "deny",
  "reason": "...",
  "hookSpecificOutput": {
    "additionalContext": "..."
  }
}
```

**Claude Code:**
```json
{
  "decision": "deny",
  "reason": "...",
  "permissionDecision": "deny"
}
```

### Unique Gemini CLI Features

1. **BeforeModel hooks**: Modify LLM requests before they're sent
2. **AfterModel hooks**: Modify LLM responses before processing
3. **BeforeToolSelection**: Filter/prioritize candidate tools
4. **Plugin hooks**: NPM packages with dependency injection (Logger, Config, HttpClient)
5. **Built-in migration**: Convert Claude Code hooks automatically

### Unique Claude Code Features

1. **PermissionRequest hook** (v2.0.45+): Intercept permission dialogs
2. **SubagentStop hook** (v1.0.41+): Hook into Task tool completion
3. **Prompt-type hooks**: Use LLM to evaluate hook conditions
4. **Tool input modification** (v2.0.10+): Modify tool inputs in PreToolUse

**Sources:**
- [Gemini CLI Hooks](https://geminicli.com/docs/hooks/)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)

---

## Version History and Changes

### v0.15.x (November 2024)

- Initial hooks framework implementation
- feat(hooks): Hook Input/Output Contracts (PR #9080)
- feat(hooks): Hook Result Aggregation (PR #9095)

### v0.16.x (November 2024)

- Hook tool execution integration (PR #9108)
- Continued refinement of input/output contracts

### v0.17.x (November 2024)

- Internal version bump with hooks stabilization

### v0.21.0 (Late 2025)

Major hooks release:
- feat(hooks): Hook Session Lifecycle & Compression Integration (PR #14151)
- feat(hooks): Hooks Commands Panel, Enable/Disable, and Migrate (PR #14225)
- feat(hooks): Hook System Documentation (PR #14307)
- feat: Support Extension Hooks with Security Warning (PR #14460)

### v0.22.x (Late 2025)

- Cherry-pick of STOP_EXECUTION feature (PR #15733)
- Bug fixes and stability improvements

### v0.23.x (Late 2025 - Early 2026)

- feat(hooks): implement STOP_EXECUTION and enhance hook decision handling (PR #15685)
- feat(hooks): add support for friendly names and descriptions (PR #15174)

**Source:** [Gemini CLI Releases](https://github.com/google-gemini/gemini-cli/releases)

---

## Known Bugs and Issues

### Issue #13155: Hooks Not Triggering

**Symptoms:**
- AfterTool hooks configured for write_file|replace do not execute
- No error messages in logs even with tracing enabled
- Git commands configured in hooks never run

**Status:** Closed as "COMPLETED" (Nov 2025) with acknowledgment that hooks functionality was still under active development.

**Workaround:** Ensure hooks are properly structured and that the hooks system is explicitly enabled.

**Source:** [GitHub Issue #13155](https://github.com/google-gemini/gemini-cli/issues/13155)

### Exit Code Improvements (PR #13728)

Granular exit codes were introduced:
- 41: FatalAuthenticationError
- 42: FatalInputError
- 52: FatalConfigError
- 130: FatalCancellationError

**Issue identified:** Some process.exit() calls don't execute cleanup logic, potentially causing resource leaks.

**Source:** [GitHub PR #13728](https://github.com/google-gemini/gemini-cli/pull/13728)

### Issue #2728: Exit Command Behavior

The exit command shows "Goodbye" but doesn't terminate the session on Windows. Subsequent commands still route through Gemini CLI.

---

## Edge Cases and Quirks

### JSON Parsing Fallback

When exit code is 0 but stdout isn't valid JSON, the output is treated as a systemMessage string.

### MCP Context Availability

mcp_context only appears in hook input for MCP tool invocations, not standard tools. Check for its presence before accessing.

### Non-Text Content Handling

In v1, model hooks are text-focused. Non-text parts (images, function calls) in the content array are simplified to string representation.

### Hook Deduplication Identity

A hook's identity is determined by its name and command. If a project hook's command changes (e.g., via git pull), it's treated as a new, untrusted hook.

### Tool Filtering Short-Circuit

BeforeToolSelection hooks may skip processing with "Already filtered" if candidate tools are 20 or fewer.

### Timeout Discrepancy

Documentation states default timeout is 60000ms (60 seconds), but some sources mention 10 seconds. Use explicit timeouts to be safe.

### UNION Merge for Disabled

The hooks.disabled array uses UNION merge, meaning:
- If a hook is disabled at user level, /hooks enable in project scope may not work
- The disabled state persists across all scopes

### Hook Chaining Not Supported

There's no built-in hook dependency/chaining. To chain hooks, use a single hook that coordinates multiple scripts internally.

### Interactive Commands

Interactive shell commands (vim, git rebase -i) work only when tools.shell.enableInteractiveShell is true.

### Command Restriction Bypass

Command restrictions in tools.core and tools.exclude use simple string prefix matching. Chained commands with &&, ||, or ; are blocked if any segment violates restrictions, but this is not a security mechanism.

---

## Best Practices

### Performance

1. **Keep hooks fast**: Hooks run synchronously and delay the agent loop
2. **Use Promise.all()**: For parallel operations in JavaScript hooks
3. **Implement caching**: Store computation results between invocations
4. **Choose appropriate events**: Use AfterAgent over AfterModel for final checks (AfterModel fires on every LLM call)
5. **Filter with specific matchers**: Use "write_file|replace" instead of "*"

### Reliability

1. **Use JSON libraries**: Use jq for parsing instead of fragile text patterns
2. **Make scripts executable**: Run chmod +x .gemini/hooks/*.sh
3. **Validate JSON output**: Use jq empty before outputting
4. **Handle errors explicitly**: Use set -e or conditional logic
5. **Set explicit timeouts**: Don't rely on defaults

### Debugging

1. **Log to dedicated files** with timestamps
2. **Direct errors to stderr**: Check exit codes (0 for success, 2 for blocking)
3. **Test hooks independently**: Use sample JSON input
4. **Enable telemetry**: Set "telemetry.logPrompts": true
5. **Use /hooks panel**: Displays execution status and recent output

### Configuration Example

```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "write_file|replace",
        "hooks": [
          {
            "name": "secret-scanner",
            "type": "command",
            "command": "$GEMINI_PROJECT_DIR/.gemini/hooks/scan-secrets.sh",
            "description": "Scans for secrets before file writes",
            "timeout": 5000
          }
        ]
      }
    ],
    "AfterTool": [
      {
        "matcher": "write_file",
        "hooks": [
          {
            "name": "auto-format",
            "type": "command",
            "command": "$GEMINI_PROJECT_DIR/.gemini/hooks/format.sh",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

**Source:** [Hooks Best Practices](https://geminicli.com/docs/hooks/best-practices/)

---

## Security Considerations

### Threat Model (Safest to Riskiest)

1. **System-level hooks**: Controlled by administrators
2. **User-level hooks**: Configured by user
3. **Extension hooks**: Third-party packages
4. **Project-level hooks**: Potentially from untrusted repositories

### Security Warnings

- **First detection warning**: Gemini CLI warns when new project hooks are detected
- **Extension approval**: Required during installation
- **Command identity change**: If a hook's command changes, it's treated as untrusted

### Risks

1. **Data exfiltration**: Hooks can read sensitive files and send to remote servers
2. **System modification**: Delete files, install malware, change settings
3. **Resource consumption**: Infinite loops, system crashes
4. **Secret exposure**: API keys in environment variables

### Mitigations

1. **Validate all inputs**: Hook inputs may originate from LLMs or user prompts
2. **Use timeouts**: Default 60 seconds; use stricter limits
3. **Limit permissions**: Don't run hooks as root
4. **Check file permissions**: Before write operations
5. **Sanitize sensitive data**: Remove API keys before output
6. **Use environment variable redaction**: At system level if needed

### Secret Scanner Example

```bash
#!/bin/bash
# .gemini/hooks/scan-secrets.sh

INPUT=$(cat)
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')

if echo "$CONTENT" | grep -qE '(api[_-]?key|secret|password|token)\s*[:=]'; then
  echo '{"decision":"deny","reason":"Potential secret detected in file content"}' >&2
  exit 2
fi

echo '{"decision":"allow"}'
exit 0
```

---

## Sources and References

### Official Documentation

- [Gemini CLI Hooks Overview](https://geminicli.com/docs/hooks/)
- [Hooks Reference](https://geminicli.com/docs/hooks/reference/)
- [Writing Hooks](https://geminicli.com/docs/hooks/writing-hooks/)
- [Hooks Best Practices](https://geminicli.com/docs/hooks/best-practices/)
- [Gemini CLI Configuration](https://geminicli.com/docs/get-started/configuration/)
- [Shell Tool Documentation](https://geminicli.com/docs/tools/shell/)
- [Policy Engine](https://geminicli.com/docs/core/policy-engine/)

### GitHub Issues and PRs

- [Issue #2779: Initial Hooks Feature Request](https://github.com/google-gemini/gemini-cli/issues/2779)
- [Issue #9070: Comprehensive Hooking System Epic](https://github.com/google-gemini/gemini-cli/issues/9070)
- [Issue #11703: Comprehensive System of Hooks](https://github.com/google-gemini/gemini-cli/issues/11703)
- [Issue #13155: Hooks Not Working Bug](https://github.com/google-gemini/gemini-cli/issues/13155)
- [Issue #14449: Hook Support in Extensions](https://github.com/google-gemini/gemini-cli/issues/14449)
- [PR #14225: Hooks Panel, Enable/Disable, Migrate](https://github.com/google-gemini/gemini-cli/pull/14225)
- [PR #14307: Hook System Documentation](https://github.com/google-gemini/gemini-cli/pull/14307)
- [PR #13728: Exit Code Improvements](https://github.com/google-gemini/gemini-cli/pull/13728)

### Comparison Resources

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Feature Comparison: Claude Code vs Gemini CLI](https://github.com/oneryalcin/gemini-cli-sdk/issues/13)

### Release Notes

- [Gemini CLI Releases](https://github.com/google-gemini/gemini-cli/releases)
- [Gemini CLI Changelog](https://geminicli.com/docs/changelogs/)

---

*This document was compiled from official Gemini CLI documentation, GitHub issues, pull requests, and community resources. For the most up-to-date information, consult the official sources linked above.*
