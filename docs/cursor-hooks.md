# Cursor IDE Hooks: Exhaustive Technical Reference

> Last updated: January 2026
> Covers: Cursor v1.7 through v2.3.x

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Hook Types](#hook-types)
4. [Input/Output Schemas](#inputoutput-schemas)
5. [Permission System](#permission-system)
6. [Version History and Breaking Changes](#version-history-and-breaking-changes)
7. [Known Bugs and Regressions](#known-bugs-and-regressions)
8. [Platform-Specific Issues](#platform-specific-issues)
9. [Comparison with Claude Code and Gemini](#comparison-with-claude-code-and-gemini)
10. [Security Considerations](#security-considerations)
11. [Edge Cases and Gotchas](#edge-cases-and-gotchas)
12. [Debugging](#debugging)
13. [Enterprise Features](#enterprise-features)
14. [Sources](#sources)

---

## Overview

Cursor Hooks were introduced in **version 1.7** (October 2025) as a mechanism to observe, control, and extend the agent loop using custom scripts. Hooks are spawned as standalone processes that communicate via JSON over stdio.

**Key Characteristics:**
- Hooks are deterministic programs (unlike rules/MCP which are interpreted by the LLM)
- Configuration via JSON files
- Receive structured input on stdin
- Return JSON output on stdout
- Currently in **beta** - APIs may change

**Sources:**
- [Cursor Hooks Documentation](https://cursor.com/docs/agent/hooks)
- [Cursor 1.7 Changelog](https://cursor.com/changelog/1-7)
- [InfoQ: Cursor 1.7 Adds Hooks](https://www.infoq.com/news/2025/10/cursor-hooks/)

---

## Configuration

### File Locations (Priority Order)

1. **Enterprise-managed global directories** (MDM deployment)
2. **Project-level**: `<project-root>/.cursor/hooks.json` (version controlled)
3. **User home**: `~/.cursor/hooks.json` (personal automation)

Cursor runs **all hooks that apply** from each location.

### Basic Structure

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      { "command": "./hooks/script.sh" }
    ],
    "afterFileEdit": [
      { "command": "bun run hooks/format.ts" }
    ]
  }
}
```

### Path Resolution

- Relative paths resolve from the `hooks.json` file's directory, **not** the project root
- Absolute paths are supported
- Scripts must be executable (`chmod +x`)

### JSON Schema

Community-maintained schema available at:
```
https://unpkg.com/cursor-hooks@latest/schema/hooks.schema.json
```

Enable IntelliSense in Cursor settings:
```json
{
  "json.schemas": [
    {
      "fileMatch": [".cursor/hooks.json"],
      "url": "https://unpkg.com/cursor-hooks/schema/hooks.schema.json"
    }
  ]
}
```

**Source:** [cursor-hooks npm package](https://github.com/johnlindquist/cursor-hooks)

---

## Hook Types

### Agent Hooks (Cmd+K / Agent Chat)

| Hook                   | Trigger                         | Can Block? | Can Message Agent?   |
| ---------------------- | ------------------------------- | ---------- | -------------------- |
| `beforeSubmitPrompt`   | Before prompt sent to LLM       | Yes        | No (beta limitation) |
| `beforeShellExecution` | Before shell command runs       | Yes        | Yes                  |
| `afterShellExecution`  | After shell command completes   | No         | No                   |
| `beforeMCPExecution`   | Before MCP tool invocation      | Yes        | Yes                  |
| `afterMCPExecution`    | After MCP tool returns          | No         | No                   |
| `beforeReadFile`       | Before file content sent to LLM | Yes        | No                   |
| `afterFileEdit`        | After agent edits a file        | No         | No                   |
| `afterAgentResponse`   | After agent text response       | No         | No                   |
| `afterAgentThought`    | After agent thinking/reasoning  | No         | No                   |
| `stop`                 | When agent loop completes       | No         | Yes (followup)       |

### Tab Hooks (Inline Completions)

| Hook                | Trigger                              | Can Block? |
| ------------------- | ------------------------------------ | ---------- |
| `beforeTabFileRead` | Before file read for Tab completions | Yes        |
| `afterTabFileEdit`  | After Tab applies an edit            | No         |

**Important:** Tab hooks fire very frequently (on cursor movement) and have performance implications, especially on Windows.

---

## Input/Output Schemas

### Common Input Fields (All Hooks)

```json
{
  "conversation_id": "uuid",
  "generation_id": "uuid",
  "model": "claude-4-sonnet",
  "hook_event_name": "beforeShellExecution",
  "cursor_version": "2.1.46",
  "workspace_roots": ["/path/to/project"],
  "user_email": "user@example.com"
}
```

### beforeShellExecution

**Input:**
```json
{
  "command": "git status",
  "cwd": "/path/to/project"
}
```

**Note:** The `cwd` field may be **empty string** in some cases - this is a known edge case.

**Output:**
```json
{
  "permission": "allow",
  "user_message": "Displayed in UI",
  "agent_message": "Sent to agent context"
}
```

### afterShellExecution

**Input:**
```json
{
  "command": "git status",
  "output": "On branch main...",
  "duration": 1234
}
```

**Note:** `duration` excludes user approval wait time.

### beforeMCPExecution

**Input:**
```json
{
  "tool_name": "github__create_issue",
  "tool_input": "{\"title\": \"...\"}",
  "url": "https://mcp-server.example.com",
  "command": "npx @mcp/server"
}
```

Either `url` or `command` is present depending on server configuration.

**Output:** Same as `beforeShellExecution`.

### afterMCPExecution

**Input:**
```json
{
  "tool_name": "github__create_issue",
  "tool_input": "{...}",
  "result_json": "{...}",
  "duration": 1234
}
```

### beforeReadFile

**Input:**
```json
{
  "file_path": "/absolute/path/to/file.ts",
  "content": "file contents..."
}
```

**Output:**
```json
{
  "permission": "allow"
}
```

**Important:** `beforeReadFile` does **not** support `user_message` or `agent_message`.

### afterFileEdit

**Input:**
```json
{
  "file_path": "/absolute/path/to/file.ts",
  "edits": [
    {
      "old_string": "before",
      "new_string": "after",
      "range": {
        "start_line_number": 10,
        "start_column": 5,
        "end_line_number": 10,
        "end_column": 20
      },
      "old_line": "full line before",
      "new_line": "full line after"
    }
  ]
}
```

**Note:** This is fire-and-forget - you cannot block or communicate with agent.

### beforeSubmitPrompt

**Input:**
```json
{
  "prompt": "user's prompt text",
  "attachments": [
    {
      "type": "file",
      "filePath": "/path/to/attachment.ts"
    },
    {
      "type": "rule",
      "filePath": "/path/to/.cursorrules"
    }
  ]
}
```

**Output:**
```json
{
  "continue": true,
  "user_message": "Shown if blocked"
}
```

**Beta limitation:** Output JSON is currently not fully respected.

### afterAgentResponse / afterAgentThought

**Input:**
```json
{
  "text": "agent response or thinking text",
  "duration_ms": 5000
}
```

### stop

**Input:**
```json
{
  "status": "completed",
  "loop_count": 5
}
```

Status values: `"completed"`, `"aborted"`, `"error"`

**Output:**
```json
{
  "followup_message": "Auto-submitted prompt"
}
```

**Limit:** Maximum 5 automatic follow-ups to prevent infinite loops.

---

## Permission System

### Permission Values

| Value   | Behavior                             |
| ------- | ------------------------------------ |
| `allow` | Execute without user intervention    |
| `deny`  | Block execution, show `user_message` |
| `ask`   | Prompt user for confirmation         |

### Response Fields

| Field              | Description                 | Supported Hooks                          |
| ------------------ | --------------------------- | ---------------------------------------- |
| `permission`       | allow/deny/ask              | beforeShellExecution, beforeMCPExecution |
| `user_message`     | Displayed in Cursor UI      | beforeShellExecution, beforeMCPExecution |
| `agent_message`    | Injected into agent context | beforeShellExecution, beforeMCPExecution |
| `continue`         | Boolean to proceed          | beforeSubmitPrompt                       |
| `followup_message` | Auto-submitted message      | stop                                     |

---

## Version History and Breaking Changes

### v1.7 (October 2025)
- **Initial release** of hooks system
- Introduced: beforeShellExecution, beforeMCPExecution, beforeReadFile, afterFileEdit, stop
- Response fields: `userMessage`, `agentMessage` (camelCase)

### v2.0.x (November 2025)
- Added: beforeSubmitPrompt, afterAgentResponse, afterAgentThought
- Added: Tab hooks (beforeTabFileRead, afterTabFileEdit)
- **Breaking change:** Field names changed to snake_case (`user_message`, `agent_message`)
- Sandbox mode introduced

### v2.0.64
- **Regression:** `user_message` and `agent_message` completely non-functional
- Workaround: Downgrade to v1.7

### v2.1.x (December 2025)
- **v2.1.6:** `agent_message` still broken; `followup_message` works
- **v2.1.25:** Windows hooks stopped working
- **v2.1.46:** Windows hooks still broken

### v2.3.x (January 2026)
- Windows Git Bash / PowerShell injection bug persists
- CLI still has partial hook support (only shell hooks)

**Sources:**
- [Forum: Regression in v2.0.64](https://forum.cursor.com/t/regression-hook-response-fields-usermessage-agentmessage-ignored-in-v2-0-64/141516)
- [Forum: Hooks not working in 2.1.6](https://forum.cursor.com/t/hooks-still-not-working-properly-in-2-1-6/143417)

---

## Known Bugs and Regressions

### Critical: Field Name Case Sensitivity

**Issue:** Documentation specifies snake_case but v1.7 used camelCase.

**Solution:** Always use snake_case in v2.0+:
```json
{
  "permission": "deny",
  "user_message": "correct",
  "agent_message": "correct"
}
```

**Not:**
```json
{
  "userMessage": "wrong in v2.0+",
  "agentMessage": "wrong in v2.0+"
}
```

### Multiple Hooks Bug

**Issue:** When multiple hooks are defined in the same trigger array, only the **first** executes.

```json
{
  "hooks": {
    "beforeShellExecution": [
      { "command": "./hook1.sh" },
      { "command": "./hook2.sh" }
    ]
  }
}
```

Only `hook1.sh` runs.

**Status:** Acknowledged December 2025, closed December 30, 2025 without fix confirmed.

**Source:** [Forum: Multiple Hooks Bug](https://forum.cursor.com/t/cursor-hooks-bug-multiple-hooks-in-array-only-execute-first-hook/141996)

### CLI vs IDE Hook Support

**Issue:** Cursor CLI (`cursor-agent`) only supports a subset of hooks.

| Environment | Supported Hooks                                |
| ----------- | ---------------------------------------------- |
| **IDE**     | All hooks                                      |
| **CLI**     | beforeShellExecution, afterShellExecution only |

**Source:** [Forum: CLI doesn't send all events](https://forum.cursor.com/t/cursor-cli-doesnt-send-all-events-defined-in-hooks/148316)

### agent_message Not Reaching Context

**Issue:** In v2.0.64+, the `agent_message` field is not injected into agent context.

**Status:** Known regression, no timeline for fix.

---

## Platform-Specific Issues

### Windows: General Hook Failures

**Symptoms:**
- `"--: line 1: 3: Bad file descriptor"` error
- Empty output in Hooks panel
- Hooks work in terminal but fail in Cursor

**Affected versions:** v2.0.38, v2.1.25+, v2.1.46

**Workaround:** Use PowerShell scripts instead of bash:

```json
{
  "hooks": {
    "beforeShellExecution": [
      { "command": "powershell.exe -File ./hooks/check.ps1" }
    ]
  }
}
```

**Source:** [Forum: Cursor Hooks On Windows](https://forum.cursor.com/t/cursor-hooks-on-windows/140293)

### Windows: Git Bash / PowerShell Injection

**Issue:** When Git Bash is set as default terminal, Cursor injects PowerShell syntax that Bash cannot parse.

**Error:**
```
"--: eval: line 1: syntax error near unexpected token '[Convert]::FromBase64String'"
```

**Root cause:** Cursor uses `[Convert]::FromBase64String` (PowerShell) to decode hook metadata.

**Workaround:** Set PowerShell as default terminal for Cursor:
```json
{
  "terminal.integrated.defaultProfile.windows": "PowerShell"
}
```

**Source:** [Forum: Project-level hooks fail on Windows with Git Bash](https://forum.cursor.com/t/project-level-hooks-fail-on-windows-with-git-bash-due-to-powershell-injection/148131)

### Windows: beforeTabFileRead Performance

**Issue:** `beforeTabFileRead` is extremely slow on Windows (1+ second vs 0.5 second on macOS), causing event queue buildup.

**Workaround:** Disable `beforeTabFileRead` if not essential:

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [...],
    "afterFileEdit": [...]
  }
}
```

**Source:** [Forum: beforeTabFileRead hook is extremely slow on Windows](https://forum.cursor.com/t/beforetabfileread-hook-is-extremely-slow-on-windows-and-events-get-queued-up-works-fine-on-macos/147211)

---

## Comparison with Claude Code and Gemini

### Claude Code Hooks

| Aspect              | Cursor                     | Claude Code                                                |
| ------------------- | -------------------------- | ---------------------------------------------------------- |
| **Config Location** | `.cursor/hooks.json`       | `.claude/settings.json`                                    |
| **Hook Types**      | 11+ lifecycle events       | PreToolUse, PostToolUse, PermissionRequest, SessionEnd     |
| **Tool Matchers**   | N/A (hooks apply globally) | Per-tool matching (e.g., `"matcher": "Bash"`)              |
| **Input Method**    | stdin JSON                 | `$CLAUDE_TOOL_INPUT` env var                               |
| **Exit Codes**      | Not documented             | Exit 2 = deny with message                                 |
| **Schema**          | Community-maintained       | Official: `json.schemastore.org/claude-code-settings.json` |

**Claude Code Example:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "if [[ \"$CLAUDE_TOOL_INPUT\" == *\"rm -rf\"* ]]; then exit 2; fi",
        "timeout": 180
      }]
    }]
  }
}
```

**Key Differences:**
1. Claude Code has granular tool matching; Cursor hooks apply to all tool invocations of a type
2. Claude Code uses environment variables; Cursor uses stdin
3. Claude Code has official JSON schema; Cursor relies on community
4. Claude Code supports regex matchers (`"Edit|MultiEdit|Write"`); Cursor does not

**Sources:**
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Claude Blog: How to Configure Hooks](https://claude.com/blog/how-to-configure-hooks)

### Gemini Code Assist

As of January 2026, Gemini Code Assist does not have a documented hooks system comparable to Cursor or Claude Code.

---

## Security Considerations

### Workspace Trust

**Important:** Cursor disables VS Code's Workspace Trust by default.

```json
{
  "security.workspace.trust.enabled": true
}
```

Enable via MDM for enterprise deployments.

**Risk:** Without workspace trust, malicious `tasks.json` files can execute automatically when opening a repository.

**Source:** [Oasis Security: Cursor Workspace Trust Vulnerability](https://www.oasis.security/resources/cursor-workspace-trust-vulnerability)

### Sandbox Mode Limitations

Sandbox mode (introduced in v2.0) restricts terminal commands:
- Blocks network access by default
- Limits file access to workspace and `/tmp`

**Critical limitation:** Sandbox allows **reading** sensitive files like `~/.ssh/id_rsa` while blocking writes.

**Source:** [Luca Becker: When Sandboxing Leaks Your Secrets](https://luca-becker.me/blog/cursor-sandboxing-leaks-secrets/)

### .cursorignore Bypass

**Issue:** `.cursorignore` only protects against `file_read` tool, not shell commands.

**Example bypass:**
```bash
cat ~/.npmrc  # Works even if ~/.npmrc is in .cursorignore
```

**Mitigation:** Use `beforeShellExecution` hook to block sensitive file access:

```bash
#!/bin/bash
input=$(cat)
command=$(echo "$input" | jq -r '.command')

# Block access to sensitive dotfiles
if [[ "$command" =~ (cat|less|head|tail|grep).*(\.npmrc|\.aws|\.ssh) ]]; then
  echo '{"permission":"deny","user_message":"Access to sensitive files blocked"}'
  exit 0
fi

echo '{"permission":"allow"}'
```

### Project Hooks Trust

Project-level hooks (`.cursor/hooks.json`) only execute in **trusted workspaces**.

---

## Edge Cases and Gotchas

### 1. Empty `cwd` Field

The `cwd` field in `beforeShellExecution` may be an empty string:

```json
{
  "command": "git status",
  "cwd": ""
}
```

Always handle this case:
```bash
cwd=$(echo "$input" | jq -r '.cwd // empty')
if [[ -z "$cwd" ]]; then
  cwd=$(echo "$input" | jq -r '.workspace_roots[0]')
fi
```

### 2. afterFileEdit Doesn't Block

`afterFileEdit` is fire-and-forget. You cannot:
- Block the edit
- Communicate with the user
- Send messages to the agent

Use case: Logging, auto-formatting (but results won't stop agent).

### 3. beforeSubmitPrompt Beta Limitations

In beta, Cursor doesn't respect output JSON from `beforeSubmitPrompt`. Recording only.

### 4. Tab Hooks Missing Attachments

Tab hooks (`beforeTabFileRead`, `afterTabFileEdit`) don't include the `attachments` field.

### 5. No Hot Reload

Changing `hooks.json` requires **restarting Cursor**.

### 6. Maximum Follow-ups

The `stop` hook's `followup_message` is limited to 5 automatic submissions to prevent infinite loops.

### 7. Duration Excludes Approval Time

The `duration` field in `afterShellExecution` and `afterMCPExecution` excludes time spent waiting for user approval.

### 8. stdout Reserved for Agent Communication

`console.log` doesn't work for debugging - use `console.error` instead:

```typescript
console.error(JSON.stringify(payload, null, 2)); // Visible in Hooks output panel
console.log('{"permission":"allow"}');           // Sent to Cursor
```

### 9. Home Directory Hooks Can't Be Shared

Hooks in `~/.cursor/hooks.json` are user-specific and can't be distributed with a project.

### 10. Tab Hook Frequency

`beforeTabFileRead` fires on every cursor movement, not just file opens. This can cause performance issues.

---

## Debugging

### Hooks Output Channel

1. Open Command Palette (Cmd+Shift+P)
2. Select "Output: Show Output Channels"
3. Choose "Hooks"

This shows:
- JSON parsing errors
- Hook execution attempts
- Return values

### File-Based Logging

```typescript
import { appendFile } from 'fs/promises';
import { join } from 'path';

const logEntry = {
  timestamp: new Date().toISOString(),
  ...input,
  stdout: result.stdout.toString(),
  stderr: result.stderr.toString(),
  exitCode: result.exitCode
};

await appendFile(
  join(input.workspace_roots[0], 'logs', 'hooks.jsonl'),
  JSON.stringify(logEntry) + '\n'
);
```

### Minimal Debug Hook

```bash
#!/bin/bash
cat > /tmp/cursor-hook-debug.json
echo '{"permission":"allow"}'
```

Check `/tmp/cursor-hook-debug.json` to see exact input received.

### Disable Hooks Temporarily

Rename `.cursor/hooks.json` to `.cursor/hooks.json.disabled`.

---

## Enterprise Features

### MDM Deployment

Hooks can be deployed organization-wide via Mobile Device Management:

```json
{
  "security.workspace.trust.enabled": true
}
```

### Dashboard Management

Enterprise admins can:
- Add/edit hooks from web dashboard
- Select OS-specific hooks
- Save hook drafts
- Sync every 30 minutes

### Sandbox Controls

Enterprise can enforce:
- Sandbox availability
- Git access permissions
- Network access permissions

### Audit Logging

19 event types tracked:
- Access events
- Asset edits
- Configuration updates

Export via CSV or view in dashboard.

**Source:** [Cursor Enterprise](https://cursor.com/blog/enterprise)

---

## Sources

### Official Documentation
- [Cursor Hooks Documentation](https://cursor.com/docs/agent/hooks)
- [Cursor 1.7 Changelog](https://cursor.com/changelog/1-7)
- [Cursor Enterprise Blog](https://cursor.com/blog/enterprise)

### Community Resources
- [GitButler: Deep Dive into Cursor Hooks](https://blog.gitbutler.com/cursor-hooks-deep-dive)
- [cursor-hooks npm package](https://github.com/johnlindquist/cursor-hooks)
- [hamzafer/cursor-hooks examples](https://github.com/hamzafer/cursor-hooks)

### Bug Reports
- [Regression: userMessage/agentMessage ignored in v2.0.64](https://forum.cursor.com/t/regression-hook-response-fields-usermessage-agentmessage-ignored-in-v2-0-64/141516)
- [Multiple Hooks Bug](https://forum.cursor.com/t/cursor-hooks-bug-multiple-hooks-in-array-only-execute-first-hook/141996)
- [Hooks on Windows](https://forum.cursor.com/t/cursor-hooks-on-windows/140293)
- [Windows Git Bash PowerShell injection](https://forum.cursor.com/t/project-level-hooks-fail-on-windows-with-git-bash-due-to-powershell-injection/148131)
- [beforeTabFileRead slow on Windows](https://forum.cursor.com/t/beforetabfileread-hook-is-extremely-slow-on-windows-and-events-get-queued-up-works-fine-on-macos/147211)
- [CLI doesn't send all events](https://forum.cursor.com/t/cursor-cli-doesnt-send-all-events-defined-in-hooks/148316)
- [Hooks still not working in 2.1.6](https://forum.cursor.com/t/hooks-still-not-working-properly-in-2-1-6/143417)

### Security Research
- [Luca Becker: When Sandboxing Leaks Your Secrets](https://luca-becker.me/blog/cursor-sandboxing-leaks-secrets/)
- [Oasis Security: Workspace Trust Vulnerability](https://www.oasis.security/resources/cursor-workspace-trust-vulnerability)
- [MintMCP: Cursor Security Guide](https://www.mintmcp.com/blog/cursor-security)

### Comparison Resources
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Qodo: Claude Code vs Cursor](https://www.qodo.ai/blog/claude-code-vs-cursor/)

### Partner Integrations
- [Runlayer Partnership](https://www.runlayer.com/blog/cursor-hooks)
- [MintMCP: MCP Governance for Cursor](https://www.mintmcp.com/blog/mcp-governance-cursor-hooks)
- [Noma Security: Agent Runtime Security](https://noma.security/blog/securing-the-agentic-frontier-noma-unveils-the-first-real-time-agent-runtime-security-for-cursor/)

---

## Appendix: Complete Example Configuration

```json
{
  "$schema": "https://unpkg.com/cursor-hooks/schema/hooks.schema.json",
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt": [
      { "command": "./hooks/log-prompt.sh" }
    ],
    "beforeShellExecution": [
      { "command": "./hooks/block-dangerous-commands.sh" }
    ],
    "afterShellExecution": [
      { "command": "./hooks/audit-commands.sh" }
    ],
    "beforeMCPExecution": [
      { "command": "./hooks/mcp-governance.sh" }
    ],
    "afterMCPExecution": [
      { "command": "./hooks/log-mcp.sh" }
    ],
    "beforeReadFile": [
      { "command": "./hooks/redact-secrets.sh" }
    ],
    "afterFileEdit": [
      { "command": "./hooks/format.sh" }
    ],
    "stop": [
      { "command": "./hooks/notify-complete.sh" }
    ]
  }
}
```

### Example: block-dangerous-commands.sh

```bash
#!/bin/bash
set -euo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.command')

# Block destructive commands
if [[ "$command" =~ (rm\ -rf|sudo\ rm|dd\ if=|mkfs\.) ]]; then
  echo '{"permission":"deny","user_message":"Destructive command blocked","agent_message":"This command was blocked by security policy. Use a safer alternative."}'
  exit 0
fi

# Block access to sensitive files
if [[ "$command" =~ (cat|less|head|tail|grep|awk|sed).*(\.env|\.npmrc|\.aws|\.ssh|credentials|secrets) ]]; then
  echo '{"permission":"deny","user_message":"Access to sensitive files blocked"}'
  exit 0
fi

# Ask for confirmation on git push
if [[ "$command" =~ git\ push ]]; then
  echo '{"permission":"ask","user_message":"Confirm git push?"}'
  exit 0
fi

echo '{"permission":"allow"}'
```

### Example: format.sh (afterFileEdit)

```bash
#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | jq -r '.file_path')

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx)
    npx prettier --write "$file_path" 2>/dev/null || true
    ;;
  *.py)
    black "$file_path" 2>/dev/null || true
    ;;
  *.go)
    gofmt -w "$file_path" 2>/dev/null || true
    ;;
esac

exit 0
```
