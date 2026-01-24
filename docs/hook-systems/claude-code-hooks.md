# Claude Code Hooks: Exhaustive Reference

This document provides a comprehensive reference for the Claude Code hooks system, including all hook event types, JSON schemas, edge cases, known bugs, and undocumented behaviors.

**Last Updated:** January 2026
**Claude Code Version Coverage:** v1.0.38 through v2.1.1

---

## Table of Contents

1. [Hook Event Types](#hook-event-types)
2. [Tool Names and Input Schemas](#tool-names-and-input-schemas)
3. [Configuration Format](#configuration-format)
4. [Hook Input JSON Schema](#hook-input-json-schema)
5. [Hook Output JSON Schema](#hook-output-json-schema)
6. [Permission Decision Types](#permission-decision-types)
7. [Exit Code Behavior](#exit-code-behavior)
8. [Error Handling](#error-handling)
9. [Async and Parallel Execution](#async-and-parallel-execution)
10. [Version History and Changelog](#version-history-and-changelog)
11. [Known Bugs and Issues](#known-bugs-and-issues)
12. [Edge Cases and Gotchas](#edge-cases-and-gotchas)
13. [Undocumented Behavior](#undocumented-behavior)

---

## Hook Event Types

Claude Code provides **11 hook events** covering the complete session lifecycle:

| Event                  | Trigger                          | Matcher Support | Primary Use Cases                           |
| ---------------------- | -------------------------------- | --------------- | ------------------------------------------- |
| **PreToolUse**         | Before tool execution            | Yes             | Validation, modification, approval/denial   |
| **PostToolUse**        | After successful tool completion | Yes             | Logging, formatting, analysis               |
| **PostToolUseFailure** | After tool execution fails       | Yes             | Error handling, retry logic                 |
| **PermissionRequest**  | Before permission dialog shown   | Yes             | Auto-approve/deny permission requests       |
| **UserPromptSubmit**   | When user submits a prompt       | No              | Context injection, prompt validation        |
| **Notification**       | When Claude sends notifications  | Partial         | Logging, custom reactions                   |
| **Stop**               | Main agent finishes responding   | No              | Completeness validation, force continuation |
| **SubagentStop**       | Subagent finishes                | No              | Task validation, output quality checks      |
| **SubagentStart**      | Subagent spawns (v2.0.64+)       | No              | Agent lifecycle tracking                    |
| **PreCompact**         | Before context compaction        | No              | Transcript backup, context preservation     |
| **SessionStart**       | Session begins or resumes        | No              | Environment setup, context loading          |
| **SessionEnd**         | Session terminates               | No              | Cleanup, state saving, logging              |

### Event Details

#### PreToolUse
- **When:** After Claude creates tool parameters, before execution
- **Can:** Block, allow, modify tool inputs, request user confirmation
- **Introduced:** v2.0.38
- **Input modification:** v2.0.10+

#### PostToolUse
- **When:** Immediately after a tool completes successfully
- **Can:** Provide feedback to Claude, log results, trigger follow-up actions
- **Note:** `tool_result` field available in input

#### PostToolUseFailure
- **When:** After a tool execution fails
- **Can:** Handle errors, suggest retries
- **Documentation:** Sparse; mentioned in Agent SDK but not main hooks docs

#### PermissionRequest
- **When:** Before permission dialog is shown to user
- **Can:** Auto-approve or deny on behalf of user
- **Introduced:** v2.0.45
- **Warning:** Race condition bug exists (see [Known Bugs](#known-bugs-and-issues))

#### UserPromptSubmit
- **When:** User submits a prompt, before Claude processes it
- **Can:** Block prompts, inject context via `additionalContext`
- **Note:** stdout is added to context (unlike other hooks)

#### Notification
- **When:** Claude Code sends a notification
- **Matchers:** `permission_prompt` and other notification types
- **Payload includes:** `message`, `notification_type`

#### Stop / SubagentStop
- **When:** Agent/subagent finishes responding
- **Can:** Force continuation, validate completeness
- **Split:** v2.0.42 separated Stop and SubagentStop

#### SubagentStart
- **When:** Subagent spawns via Task tool
- **Introduced:** v2.0.64 (November 19, 2025)
- **Payload:** `agent_id`, `parent_agent_id`, `subagent_type`, `description`

#### PreCompact
- **When:** Before context compaction/summarization
- **Use:** Last chance to preserve critical information
- **Introduced:** v2.0.30

#### SessionStart / SessionEnd
- **When:** Session lifecycle boundaries
- **SessionStart special:** Can persist variables via `$CLAUDE_ENV_FILE`
- **SessionEnd:** Supports `systemMessage` (v2.1.0+)

---

## Tool Names and Input Schemas

Claude Code has **16+ built-in tools**. Hook matchers must use exact tool names (case-sensitive).

### Complete Tool List

#### File Operations
| Tool             | Description                          | Key Input Parameters                                                                                                 |
| ---------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Read**         | Read files (images, PDFs, notebooks) | `file_path`, `offset?`, `limit?`                                                                                     |
| **Write**        | Create/overwrite files               | `file_path`, `content`                                                                                               |
| **Edit**         | Single find-and-replace              | `file_path`, `old_string`, `new_string`, `replace_all?`                                                              |
| **MultiEdit**    | Multiple sequential edits            | `file_path`, `edits[]` (array of edit operations)                                                                    |
| **NotebookEdit** | Edit Jupyter cells                   | `notebook_path`, `new_source`, `cell_id?`, `cell_type?`, `edit_mode?`                                                |
| **LS**           | List directory contents              | `path`, `ignore?`                                                                                                    |
| **Glob**         | File pattern matching                | `pattern`, `path?`                                                                                                   |
| **Grep**         | Content search (ripgrep)             | `pattern`, `path?`, `output_mode?`, `glob?`, `type?`, `-A?`, `-B?`, `-C?`, `-i?`, `-n?`, `multiline?`, `head_limit?` |

#### Execution
| Tool           | Description                 | Key Input Parameters                                        |
| -------------- | --------------------------- | ----------------------------------------------------------- |
| **Bash**       | Shell commands              | `command`, `description?`, `timeout?`, `run_in_background?` |
| **BashOutput** | Get background shell output | `bash_id`, `filter?`                                        |
| **KillShell**  | Terminate background shell  | `shell_id`                                                  |

#### Web
| Tool          | Description            | Key Input Parameters                            |
| ------------- | ---------------------- | ----------------------------------------------- |
| **WebFetch**  | Fetch and analyze URLs | `url`, `prompt`                                 |
| **WebSearch** | Web search             | `query`, `allowed_domains?`, `blocked_domains?` |

#### Task Management
| Tool             | Description                 | Key Input Parameters                               |
| ---------------- | --------------------------- | -------------------------------------------------- |
| **Task**         | Launch subagents            | `subagent_type`, `prompt`, `description`           |
| **TodoWrite**    | Manage task lists           | `todos[]` (with `content`, `status`, `activeForm`) |
| **ExitPlanMode** | Exit planning mode          | `plan`                                             |
| **Skill**        | Execute user-defined skills | `skill`, `args?`                                   |
| **SlashCommand** | Execute slash commands      | `command`                                          |

#### IDE Integration
| Tool               | Description              | Key Input Parameters |
| ------------------ | ------------------------ | -------------------- |
| **getDiagnostics** | VS Code diagnostics      | `uri?`               |
| **executeCode**    | Jupyter kernel execution | `code`               |

### MCP Tool Naming Convention

MCP (Model Context Protocol) tools follow this pattern:
```
mcp__<server_name>__<tool_name>
```

Examples:
- `mcp__github__create_issue`
- `mcp__memory__retrieve_memory`
- `mcp__filesystem__read_file`

Matcher patterns for MCP tools:
```json
"matcher": "mcp__memory__.*"      // All tools from memory server
"matcher": "mcp__.*"              // All MCP tools
"matcher": "mcp__github__create_issue"  // Specific tool
```

---

## Configuration Format

### Configuration Locations (Precedence Order)

1. `.claude/settings.local.json` (local, not committed)
2. `.claude/settings.json` (project-level, shared)
3. `~/.claude/settings.json` (user-level)

### Settings File Format

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/script.sh",
            "timeout": 60
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Verify all tasks are complete: $ARGUMENTS",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Plugin Format (hooks/hooks.json)

```json
{
  "description": "Brief explanation (optional)",
  "hooks": {
    "PreToolUse": [...],
    "Stop": [...]
  }
}
```

### Hook Types

| Type      | Description                  | Default Timeout |
| --------- | ---------------------------- | --------------- |
| `command` | Bash command execution       | 60 seconds      |
| `prompt`  | LLM-based evaluation (Haiku) | 30 seconds      |

### Matcher Syntax

| Pattern             | Matches                          |
| ------------------- | -------------------------------- |
| `"Write"`           | Exact match (case-sensitive)     |
| `"Write\|Edit"`     | Pipe OR: Write or Edit           |
| `"*"` or `""`       | All tools                        |
| `"Bash(npm test*)"` | Argument patterns with wildcards |
| `"mcp__memory__.*"` | Regex patterns                   |

**Important:** Matchers are case-sensitive. `"bash"` will NOT match `"Bash"`.

### Configuration Options

| Field     | Type    | Default  | Description                       |
| --------- | ------- | -------- | --------------------------------- |
| `matcher` | string  | `"*"`    | Tool name pattern                 |
| `hooks`   | array   | required | Array of hook definitions         |
| `type`    | string  | required | `"command"` or `"prompt"`         |
| `command` | string  | -        | Shell command (for type: command) |
| `prompt`  | string  | -        | LLM prompt (for type: prompt)     |
| `timeout` | number  | 60/30    | Seconds before timeout            |
| `once`    | boolean | false    | Run only once per session         |

### Component-Scoped Hooks (v2.1.0+)

Hooks can be defined in Skills, subagents, and slash commands via frontmatter:

```yaml
---
hooks:
  PreToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "./validate.sh"
---
```

These hooks are scoped to the component's lifecycle and auto-cleanup when finished.

---

## Hook Input JSON Schema

All hooks receive JSON via stdin with these common fields:

### Common Fields (All Hooks)

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/lily/project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse"
}
```

| Field             | Type   | Description                                                                |
| ----------------- | ------ | -------------------------------------------------------------------------- |
| `session_id`      | string | Unique session identifier                                                  |
| `transcript_path` | string | Path to conversation JSONL transcript                                      |
| `cwd`             | string | Current working directory                                                  |
| `permission_mode` | string | `"default"`, `"plan"`, `"acceptEdits"`, `"dontAsk"`, `"bypassPermissions"` |
| `hook_event_name` | string | The hook event type                                                        |

### Tool-Related Hooks (PreToolUse, PostToolUse, PermissionRequest)

Additional fields:

```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_use_id": "toolu_abc123"
}
```

### PostToolUse Additional Fields

```json
{
  "tool_result": "Success: file written"
}
```

### UserPromptSubmit

```json
{
  "user_prompt": "The user's submitted text"
}
```

### Stop / SubagentStop

```json
{
  "reason": "Task completed"
}
```

### SubagentStart (v2.0.64+)

```json
{
  "agent_id": "agent_xyz",
  "parent_agent_id": "agent_abc",
  "subagent_type": "general-purpose",
  "description": "Research task"
}
```

### SessionStart Additional

```json
{
  "agent_type": "custom-agent"
}
```

### Notification

```json
{
  "message": "Claude needs your permission to use Bash",
  "notification_type": "permission_prompt"
}
```

### Environment Variables Available

| Variable                 | Description               | Availability      |
| ------------------------ | ------------------------- | ----------------- |
| `CLAUDE_PROJECT_DIR`     | Project root path         | All hooks         |
| `CLAUDE_PLUGIN_ROOT`     | Plugin directory          | Plugin hooks      |
| `CLAUDE_CODE_REMOTE`     | Set if remote context     | All hooks         |
| `CLAUDE_ENV_FILE`        | For persisting variables  | SessionStart only |
| `CLAUDE_CODE_ENTRYPOINT` | Entry point (e.g., "cli") | All hooks         |

---

## Hook Output JSON Schema

Hooks communicate via stdout with optional JSON structure.

### Universal Output Fields

```json
{
  "continue": true,
  "stopReason": "Optional message when continue=false",
  "suppressOutput": false,
  "systemMessage": "Message shown to USER (not Claude)"
}
```

| Field            | Type    | Default | Description                       |
| ---------------- | ------- | ------- | --------------------------------- |
| `continue`       | boolean | true    | If false, halt all processing     |
| `stopReason`     | string  | -       | Message shown when continue=false |
| `suppressOutput` | boolean | false   | Hide stdout from transcript view  |
| `systemMessage`  | string  | -       | Warning shown to user only        |

### PreToolUse Output

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Auto-approved: safe operation",
    "updatedInput": {
      "command": "npm run lint --fix"
    }
  }
}
```

| Field                      | Values                       | Description                       |
| -------------------------- | ---------------------------- | --------------------------------- |
| `permissionDecision`       | `"allow"`, `"deny"`, `"ask"` | Permission control                |
| `permissionDecisionReason` | string                       | Shown to Claude (on deny) or user |
| `updatedInput`             | object                       | Modified tool parameters          |

**Deprecated fields:** `decision` and `reason` (use `hookSpecificOutput` instead)
**Mapping:** `"approve"` -> `"allow"`, `"block"` -> `"deny"`

### PermissionRequest Output

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedInput": {
        "command": "npm run lint"
      }
    }
  }
}
```

### Stop / SubagentStop Output

```json
{
  "decision": "approve",
  "reason": "All tasks verified complete",
  "continue": true
}
```

| Decision    | Effect                                    |
| ----------- | ----------------------------------------- |
| `"approve"` | Allow agent to stop                       |
| `"block"`   | Feed reason to Claude, force continuation |

### UserPromptSubmit Output

```json
{
  "decision": "block",
  "reason": "Prompt blocked: contains sensitive data",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Context injected for Claude to see"
  }
}
```

**Note:** `additionalContext` is shown to Claude; `reason` is shown to user only.

### Prompt Hook Variables

For `type: "prompt"` hooks, these variables are available:

| Variable       | Description             |
| -------------- | ----------------------- |
| `$TOOL_INPUT`  | Tool input JSON         |
| `$TOOL_RESULT` | Tool execution result   |
| `$USER_PROMPT` | User's submitted prompt |
| `$TOOL_NAME`   | Name of the tool        |
| `$ARGUMENTS`   | Generic arguments       |

---

## Permission Decision Types

### Values

| Value     | Behavior                                | Used In                       |
| --------- | --------------------------------------- | ----------------------------- |
| `"allow"` | Auto-approve, bypass permission dialog  | PreToolUse, PermissionRequest |
| `"deny"`  | Block operation, reason shown to Claude | PreToolUse, PermissionRequest |
| `"ask"`   | Show permission dialog to user          | PreToolUse                    |

### Combining with updatedInput

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "updatedInput": { "command": "safe-command" }
  }
}
```

- `"allow"` + `updatedInput`: Modify and auto-approve
- `"ask"` + `updatedInput`: Modify and show to user for confirmation (v2.1.0+)
- `"deny"`: `updatedInput` ignored

---

## Exit Code Behavior

| Exit Code | Type               | Behavior                                                             |
| --------- | ------------------ | -------------------------------------------------------------------- |
| **0**     | Success            | stdout processed as JSON; shown in transcript (Ctrl-R)               |
| **2**     | Blocking Error     | stderr used as error message; JSON in stdout ignored; action blocked |
| **Other** | Non-blocking Error | stderr shown in verbose mode; execution continues                    |

### Important Notes

1. **JSON only processed on exit 0:** If exit code is 2, stdout JSON is completely ignored
2. **stderr for exit 2:** Error message format is `[command]: {stderr}`
3. **Exit 1 behavior:** Non-blocking; stderr shown, execution continues
4. **UserPromptSubmit exception:** stdout added to context even on exit 0

### Example: Blocking with Exit 2

```bash
#!/bin/bash
echo "Error: Path traversal detected" >&2
exit 2
```

### Example: JSON Response with Exit 0

```bash
#!/bin/bash
cat << 'EOF'
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "Path traversal not allowed"
  }
}
EOF
exit 0
```

---

## Error Handling

### What Happens When Hooks Crash

| Scenario              | Behavior                                |
| --------------------- | --------------------------------------- |
| Hook times out        | Hook cancelled; timeout message shown   |
| Invalid JSON output   | Treated as plain text                   |
| Non-zero exit (not 2) | Non-blocking error; execution continues |
| Hook script not found | Error message; hook skipped             |
| Permission denied     | Error message; hook skipped             |

### Timeout Handling

- Default: 60 seconds (command), 30 seconds (prompt)
- Configurable per-hook via `timeout` field
- Timeout affects only that specific hook, not others

### Plugin Hook Crash (v2.0.41)

Fixed: Crash when plugin command hooks timeout during execution.

### Common Error Patterns

**"Stop hook error" false positive ([Issue #10463](https://github.com/anthropics/claude-code/issues/10463)):**
- Hooks producing 0 bytes output may show error
- Async output leak from background processes
- Workaround: Redirect all output to /dev/null, explicit exit 0

**"Hook output does not start with {":**
- Claude Code expects JSON but received plain text
- Empty output (0 bytes) can trigger this
- Solution: Return valid JSON or suppress output

---

## Async and Parallel Execution

### Parallel Hook Execution

- **All matching hooks run simultaneously**
- Non-deterministic ordering
- Hooks cannot see each other's output
- Design hooks for independence

### Implications

1. Don't rely on execution order
2. Don't share state between hooks
3. Each hook should be self-contained
4. Conflicting decisions: Last write wins (undefined)

### PermissionRequest Race Condition

**Bug ([Issue #12176](https://github.com/anthropics/claude-code/issues/12176)):**
- Permission dialog shown before hook completes
- If hook takes >1-2 seconds, dialog appears despite approval
- Workaround: Use PreToolUse instead for blocking decisions

### Background Output Leak

Hooks with background processes (`&`) can leak output after exit:
```bash
# PROBLEMATIC
{
    some_command &
}
exit 0

# SAFER
{
    some_command > /dev/null 2>&1
} > /dev/null 2>&1 &
exit 0
```

---

## Version History and Changelog

### Major Hook-Related Releases

| Version     | Date     | Changes                                                                                                      |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| **v2.1.0**  | Dec 2025 | Hooks in agent/skill/command frontmatter; `systemMessage` for SessionEnd; `updatedInput` with `ask` decision |
| **v2.0.64** | Nov 2025 | `tool_use_id` field; SubagentStart hook                                                                      |
| **v2.0.59** | Nov 2025 | PermissionDecision "ask" exposed; `additionalContext` for UserPromptSubmit                                   |
| **v2.0.54** | Nov 2025 | PermissionRequest hooks process 'always allow'                                                               |
| **v2.0.45** | Oct 2025 | PermissionRequest hook introduced                                                                            |
| **v2.0.42** | Oct 2025 | Split Stop/SubagentStop; timeout per command; `hook_event_name` in input                                     |
| **v2.0.41** | Oct 2025 | `model` parameter for prompt hooks; timeout crash fix                                                        |
| **v2.0.38** | Sep 2025 | **Hooks system released**                                                                                    |
| **v2.0.30** | Sep 2025 | PreCompact hook; `once: true` config                                                                         |
| **v2.0.27** | Aug 2025 | **Regression: hooks broke** (fixed in later versions)                                                        |
| **v2.0.10** | Jul 2025 | PreToolUse input modification (`updatedInput`)                                                               |

### Regression Timeline (v2.0.27-v2.0.31)

- **v2.0.25:** Hooks working correctly
- **v2.0.27:** Hooks broken (hook init in debug-only code path)
- **v2.0.29:** Still broken
- **v2.0.30:** Partial fix
- **v2.0.31:** Regression reintroduced
- **Workaround:** Run with `--debug` or `--debug hooks`

---

## Known Bugs and Issues

### Active/Recent Bugs

#### 1. Stop Hook Error False Positive ([#10463](https://github.com/anthropics/claude-code/issues/10463))
- **Versions:** v2.0.17+
- **Symptom:** "Stop hook error" shown despite successful execution
- **Cause:** Empty output or async output leak
- **Status:** Open

#### 2. Hooks Stop After ~2.5 Hours ([#16047](https://github.com/anthropics/claude-code/issues/16047))
- **Symptom:** Hooks silently stop firing in long sessions
- **Cause:** Log file grows to ~48GB
- **Solution:** Delete `~/.claude/hooks.log`, implement log rotation
- **Status:** Closed (user resolved)

#### 3. PermissionRequest Race Condition ([#12176](https://github.com/anthropics/claude-code/issues/12176))
- **Symptom:** Dialog shown despite hook returning "allow"
- **Cause:** Async execution, dialog added before hook completes
- **Workaround:** Use PreToolUse instead
- **Status:** Closed (won't fix; by design)

#### 4. PreToolUse Exit 2 Doesn't Block Write/Edit ([#13744](https://github.com/anthropics/claude-code/issues/13744))
- **Symptom:** Exit code 2 blocks Bash but not Write/Edit
- **Status:** Closed as duplicate of #3514

#### 5. Plugin vs Direct Hooks Behavior Difference ([#10412](https://github.com/anthropics/claude-code/issues/10412))
- **Symptom:** Exit code 2 works differently in plugins vs `.claude/hooks/`
- **Workaround:** Move hooks to `.claude/hooks/`
- **Status:** Closed

#### 6. Hooks Not Loading from settings.json ([#11544](https://github.com/anthropics/claude-code/issues/11544))
- **Symptom:** `/hooks` shows no hooks despite valid config
- **Status:** Open

#### 7. SessionStart Hooks Skip on First Run ([#10997](https://github.com/anthropics/claude-code/issues/10997))
- **Symptom:** Hooks only work after marketplace cached locally
- **Status:** Open

#### 8. --dangerously-skip-permissions Breaks Hooks ([#10385](https://github.com/anthropics/claude-code/issues/10385))
- **Symptom:** Hooks don't run on first launch with flag
- **Workaround:** Initialize with `--debug` first
- **Status:** Open

#### 9. additionalContext Injected Multiple Times ([#14281](https://github.com/anthropics/claude-code/issues/14281))
- **Symptom:** Hook context duplicated in conversation
- **Status:** Open

### Historical Bugs (Fixed)

| Issue  | Version | Description                                             |
| ------ | ------- | ------------------------------------------------------- |
| #10399 | v2.0.27 | Hooks stopped working entirely                          |
| #2814  | v1.0.38 | Template variables not interpolated; exit codes ignored |

---

## Edge Cases and Gotchas

### 1. Matcher Case Sensitivity
```json
"matcher": "bash"   // WRONG - won't match "Bash"
"matcher": "Bash"   // CORRECT
```

### 2. systemMessage Not Shown to Claude
- `systemMessage`: Shown to user only
- `permissionDecisionReason`: Shown to Claude (on deny)
- `additionalContext`: Shown to Claude (UserPromptSubmit)
- **No field** exists to message Claude while allowing operation

### 3. Hooks Don't Hot-Reload
- Changes require restarting Claude Code
- Editing hooks.json mid-session has no effect
- Invalid JSON prevents hook loading at startup

### 4. SessionStart stdout Added to Context
Unlike other hooks, SessionStart stdout is injected into conversation context, not just shown in transcript.

### 5. Timeout Units
- Hook timeout: **seconds**
- Bash tool timeout: **milliseconds**
- Don't confuse them

### 6. Empty Matchers
```json
"matcher": ""   // Matches all tools
"matcher": "*"  // Matches all tools
// Both are equivalent
```

### 7. Pipe vs Regex
```json
"matcher": "Write|Edit"     // Pipe: OR logic
"matcher": "mcp__.*"        // Regex pattern
```

### 8. PostToolUse Only on Success
- PostToolUse fires only after **successful** tool execution
- Use PostToolUseFailure for failed executions

### 9. Transcript Path JSONL Format
- `transcript_path` points to JSONL file
- Can `tail -f` and pipe to `jq` for real-time monitoring

### 10. Plugin Hooks Require Workspace Trust
Debug log: `Skipping hook execution - workspace trust not accepted`
- Solution: Accept workspace trust or use `--debug` first

---

## Undocumented Behavior

### 1. PostToolUseFailure Event
- Mentioned in Agent SDK docs as valid tool-based hook
- Not documented in main hooks reference
- Fires when tool execution fails

### 2. Parallel Execution Details
- Hooks are fully parallel with no coordination
- Conflicting permission decisions: undefined behavior
- No hook can depend on another's output

### 3. Flag File Activation Pattern
```bash
# Conditionally activate based on flag file
if [ ! -f ".enable-strict-validation" ]; then
    exit 0
fi
# ... validation logic
```

### 4. Prompt Hooks Use Haiku
- `type: "prompt"` hooks use Claude Haiku (fast, cheap)
- Cost: ~$0.0004 per evaluation
- Can specify custom `model` parameter (v2.0.41+)

### 5. once: true Behavior
- Hook runs once per session
- Auto-removed after first successful execution
- Useful for initialization tasks

### 6. Notification Matcher Types
- `permission_prompt`: Permission requests
- Other notification types exist but undocumented

### 7. CLAUDE_ENV_FILE Persistence
```bash
# In SessionStart hook
echo "export PROJECT_TYPE=nodejs" >> "$CLAUDE_ENV_FILE"
# Variable persists across session
```

### 8. Identical Commands Deduplicated
Multiple hooks with identical commands are auto-deduplicated.

### 9. JSON Parsing Fallback
If output doesn't start with `{`, treated as plain text.

### 10. tool_use_id Field
Added v2.0.64 - allows correlation between PreToolUse and PostToolUse for same tool invocation.

---

## Sources and References

### Official Documentation
- [Hooks Reference - Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Claude Code Blog: How to Configure Hooks](https://claude.com/blog/how-to-configure-hooks)
- [CHANGELOG.md](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- [Agent SDK Hooks](https://platform.claude.com/docs/en/agent-sdk/hooks)

### GitHub Issues
- [#2814 - Hooks System Issues (v1.0.38)](https://github.com/anthropics/claude-code/issues/2814)
- [#10399 - Hooks Stopped Working v2.0.27](https://github.com/anthropics/claude-code/issues/10399)
- [#10463 - Stop Hook Error](https://github.com/anthropics/claude-code/issues/10463)
- [#10385 - dangerously-skip-permissions](https://github.com/anthropics/claude-code/issues/10385)
- [#10412 - Plugin vs Direct Hooks](https://github.com/anthropics/claude-code/issues/10412)
- [#11544 - Hooks Not Loading](https://github.com/anthropics/claude-code/issues/11544)
- [#11891 - Missing PermissionRequest Docs](https://github.com/anthropics/claude-code/issues/11891)
- [#12176 - PermissionRequest Race Condition](https://github.com/anthropics/claude-code/issues/12176)
- [#13744 - Exit 2 Doesn't Block Write/Edit](https://github.com/anthropics/claude-code/issues/13744)
- [#14281 - additionalContext Duplicated](https://github.com/anthropics/claude-code/issues/14281)
- [#16047 - Hooks Stop After 2.5 Hours](https://github.com/anthropics/claude-code/issues/16047)

### Community Resources
- [Claude Code Tools Reference](https://www.vtrivedy.com/posts/claudecode-tools-reference/)
- [Claude Code Hooks Mastery](https://github.com/disler/claude-code-hooks-mastery)
- [Internal Tools Implementation Gist](https://gist.github.com/bgauryy/0cdb9aa337d01ae5bd0c803943aa36bd)
- [Tools and System Prompt Gist](https://gist.github.com/wong2/e0f34aac66caf890a332f7b6f9e2ba8f)

---

## Appendix: Quick Reference

### Hook Configuration Template

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "npx prettier --write \"$1\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Verify all requested tasks are complete",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cat .claude/context.md"
          }
        ]
      }
    ]
  }
}
```

### Python Hook Template

```python
#!/usr/bin/env python3
import json
import sys

def main():
    input_data = json.load(sys.stdin)

    tool_name = input_data.get('tool_name', '')
    tool_input = input_data.get('tool_input', {})

    # Your logic here
    if should_block(tool_input):
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Blocked: reason here"
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # Allow
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Bash Hook Template

```bash
#!/bin/bash
set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Validate
if [[ "$FILE_PATH" == *".."* ]]; then
    echo "Error: Path traversal detected" >&2
    exit 2
fi

# Allow
exit 0
```
