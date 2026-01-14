# AI Coding Assistant Hook System Comparison

A comprehensive comparison of hook/extensibility features across Claude Code, Cursor, Gemini CLI, and Codex CLI.

**Last Updated:** January 2026

---

## Hook Event Support

| Event Type                    | Claude Code          | Cursor                                                     | Gemini CLI                      | Codex CLI          |
| ----------------------------- | -------------------- | ---------------------------------------------------------- | ------------------------------- | ------------------ |
| **Pre-tool execution**        | ✅ PreToolUse         | ✅ beforeShellExecution, beforeMCPExecution, beforeReadFile | ✅ BeforeTool                    | ❌                  |
| **Post-tool execution**       | ✅ PostToolUse        | ✅ afterShellExecution, afterMCPExecution, afterFileEdit    | ✅ AfterTool                     | ❌                  |
| **Tool failure**              | ✅ PostToolUseFailure | ❌                                                          | ❌                               | ❌                  |
| **Permission request**        | ✅ PermissionRequest  | ❌ (use beforeShell)                                        | ✅ Notification (ToolPermission) | ❌                  |
| **User prompt submit**        | ✅ UserPromptSubmit   | ✅ beforeSubmitPrompt (beta)                                | ✅ BeforeAgent                   | ❌                  |
| **Agent stop**                | ✅ Stop               | ✅ stop                                                     | ✅ AfterAgent                    | ❌                  |
| **Subagent start**            | ✅ SubagentStart      | ❌                                                          | ❌                               | ❌                  |
| **Subagent stop**             | ✅ SubagentStop       | ❌                                                          | ❌                               | ❌                  |
| **Session start**             | ✅ SessionStart       | ❌                                                          | ✅ SessionStart                  | ❌                  |
| **Session end**               | ✅ SessionEnd         | ❌                                                          | ✅ SessionEnd                    | ❌                  |
| **Pre-compaction**            | ✅ PreCompact         | ❌                                                          | ✅ PreCompress                   | ❌                  |
| **Notification**              | ✅ Notification       | ❌                                                          | ✅ Notification                  | ✅ notify (limited) |
| **Pre-model (LLM request)**   | ❌                    | ❌                                                          | ✅ BeforeModel                   | ❌                  |
| **Post-model (LLM response)** | ❌                    | ❌                                                          | ✅ AfterModel                    | ❌                  |
| **Tool selection**            | ❌                    | ❌                                                          | ✅ BeforeToolSelection           | ❌                  |
| **Agent thought/reasoning**   | ❌                    | ✅ afterAgentThought                                        | ❌                               | ❌                  |
| **Tab completions**           | ❌                    | ✅ beforeTabFileRead, afterTabFileEdit                      | ❌                               | ❌                  |

**Total Events:** Claude Code: 11 | Cursor: 10 | Gemini CLI: 11 | Codex CLI: 1

---

## Hook Capabilities

| Capability                   | Claude Code                            | Cursor              | Gemini CLI            | Codex CLI |
| ---------------------------- | -------------------------------------- | ------------------- | --------------------- | --------- |
| **Block operations**         | ✅ Exit 2 or JSON deny                  | ✅ permission: deny  | ✅ Exit 2 or JSON deny | ❌         |
| **Allow operations**         | ✅ permissionDecision: allow            | ✅ permission: allow | ✅ decision: allow     | ❌         |
| **Prompt user**              | ✅ permissionDecision: ask              | ✅ permission: ask   | ✅ decision: ask       | ❌         |
| **Modify tool input**        | ✅ updatedInput                         | ❌                   | ✅ (via deny + reason) | ❌         |
| **Inject context to agent**  | ✅ additionalContext (UserPromptSubmit) | ✅ agent_message     | ✅ additionalContext   | ❌         |
| **Message to user only**     | ✅ systemMessage                        | ✅ user_message      | ✅ systemMessage       | ❌         |
| **Force agent continuation** | ✅ Stop hook block                      | ✅ followup_message  | ✅ AfterAgent block    | ❌         |
| **Modify LLM request**       | ❌                                      | ❌                   | ✅ llm_request         | ❌         |
| **Modify LLM response**      | ❌                                      | ❌                   | ✅ llm_response        | ❌         |
| **Filter available tools**   | ❌                                      | ❌                   | ✅ toolConfig          | ❌         |

---

## Configuration

| Aspect                      | Claude Code               | Cursor                 | Gemini CLI                      | Codex CLI              |
| --------------------------- | ------------------------- | ---------------------- | ------------------------------- | ---------------------- |
| **Config format**           | JSON                      | JSON                   | JSON                            | TOML                   |
| **User config**             | `~/.claude/settings.json` | `~/.cursor/hooks.json` | `~/.gemini/settings.json`       | `~/.codex/config.toml` |
| **Project config**          | `.claude/settings.json`   | `.cursor/hooks.json`   | `.gemini/settings.json`         | `.codex/config.toml`   |
| **Hook type: command**      | ✅                         | ✅                      | ✅                               | ✅ (notify only)        |
| **Hook type: prompt (LLM)** | ✅ (Haiku)                 | ❌                      | ❌                               | ❌                      |
| **Tool matchers**           | ✅ Regex (`Write\|Edit`)   | ❌ Global only          | ✅ Regex (`write_file\|replace`) | N/A                    |
| **Timeout config**          | ✅ Per-hook                | ❌                      | ✅ Per-hook                      | N/A                    |
| **Hot reload**              | ❌ Restart required        | ❌ Restart required     | ❌                               | N/A                    |

---

## Communication Protocol

| Aspect                    | Claude Code               | Cursor              | Gemini CLI                | Codex CLI  |
| ------------------------- | ------------------------- | ------------------- | ------------------------- | ---------- |
| **Input method**          | stdin JSON                | stdin JSON          | stdin JSON                | stdin JSON |
| **Output method**         | stdout JSON               | stdout JSON         | stdout JSON               | N/A        |
| **Exit 0**                | Success, parse JSON       | Success, parse JSON | Success, parse JSON       | N/A        |
| **Exit 2**                | Block with stderr message | Not documented      | Block with stderr message | N/A        |
| **Other exit**            | Non-blocking warning      | Not documented      | Non-blocking warning      | N/A        |
| **Invalid JSON fallback** | Treat as plain text       | Treat as plain text | Treat as systemMessage    | N/A        |

---

## Input JSON Schema (Common Fields)

| Field             | Claude Code          | Cursor                | Gemini CLI      | Codex CLI |
| ----------------- | -------------------- | --------------------- | --------------- | --------- |
| `session_id`      | ✅                    | ✅ conversation_id     | ✅               | ❌         |
| `hook_event_name` | ✅                    | ✅                     | ✅               | ❌         |
| `cwd`             | ✅                    | ✅ (may be empty)      | ✅               | ❌         |
| `tool_name`       | ✅                    | ✅ (in specific hooks) | ✅               | ❌         |
| `tool_input`      | ✅                    | ✅                     | ✅               | ❌         |
| `tool_result`     | ✅ (PostToolUse)      | ✅ result_json         | ✅ tool_response | ❌         |
| `transcript_path` | ✅                    | ❌                     | ✅               | ❌         |
| `timestamp`       | ❌                    | ❌                     | ✅               | ❌         |
| `user_prompt`     | ✅ (UserPromptSubmit) | ✅ prompt              | ✅ prompt        | ❌         |

---

## Output JSON Schema

| Field                   | Claude Code                             | Cursor            | Gemini CLI                             | Codex CLI |
| ----------------------- | --------------------------------------- | ----------------- | -------------------------------------- | --------- |
| **Permission decision** | `hookSpecificOutput.permissionDecision` | `permission`      | `decision`                             | N/A       |
| **Reason for agent**    | `permissionDecisionReason`              | `agent_message`   | `reason`                               | N/A       |
| **Message for user**    | `systemMessage`                         | `user_message`    | `systemMessage`                        | N/A       |
| **Modified input**      | `hookSpecificOutput.updatedInput`       | ❌                 | ❌                                      | N/A       |
| **Context injection**   | `hookSpecificOutput.additionalContext`  | `agent_message`   | `hookSpecificOutput.additionalContext` | N/A       |
| **Stop processing**     | `continue: false`                       | `continue: false` | `continue: false`                      | N/A       |
| **Suppress output**     | `suppressOutput: true`                  | ❌                 | `suppressOutput: true`                 | N/A       |

---

## Tool Names

| Tool Type          | Claude Code             | Cursor                     | Gemini CLI                     | Codex CLI               |
| ------------------ | ----------------------- | -------------------------- | ------------------------------ | ----------------------- |
| **Shell**          | `Bash`                  | N/A (beforeShellExecution) | `run_shell_command`            | shell_tool              |
| **Read file**      | `Read`                  | N/A (beforeReadFile)       | `read_file`, `read_many_files` | Built-in                |
| **Write file**     | `Write`                 | N/A (afterFileEdit)        | `write_file`                   | Built-in                |
| **Edit file**      | `Edit`, `MultiEdit`     | N/A (afterFileEdit)        | `replace`                      | apply_patch             |
| **Search files**   | `Glob`                  | N/A                        | `glob`                         | Built-in                |
| **Search content** | `Grep`                  | N/A                        | `search_file_content`          | Built-in                |
| **Web fetch**      | `WebFetch`              | N/A                        | `web_fetch`                    | Built-in                |
| **Web search**     | `WebSearch`             | N/A                        | `google_web_search`            | web_search              |
| **MCP tools**      | `mcp__<server>__<tool>` | `<server>__<tool>`         | `mcp__<server>__<tool>`        | `mcp__<server>__<tool>` |

---

## Execution Model

| Aspect                    | Claude Code                 | Cursor                   | Gemini CLI               | Codex CLI |
| ------------------------- | --------------------------- | ------------------------ | ------------------------ | --------- |
| **Execution**             | Parallel (all matching)     | Sequential (first only*) | Synchronous              | N/A       |
| **Hook ordering**         | Non-deterministic           | First in array           | Concatenated by priority | N/A       |
| **Conflicting decisions** | Last write wins (undefined) | N/A                      | Not documented           | N/A       |
| **Default timeout**       | 60s (command), 30s (prompt) | Not documented           | 60s                      | N/A       |
| **Max timeout**           | Configurable                | Not documented           | Configurable             | N/A       |

*Cursor has a known bug where only the first hook in an array executes.

---

## Platform Support

| Platform    | Claude Code | Cursor                          | Gemini CLI | Codex CLI      |
| ----------- | ----------- | ------------------------------- | ---------- | -------------- |
| **macOS**   | ✅ Full      | ✅ Full                          | ✅ Full     | ✅ Full         |
| **Linux**   | ✅ Full      | ✅ Full                          | ✅ Full     | ✅ Full         |
| **Windows** | ✅ Full      | ⚠️ Issues (Git Bash, PowerShell) | ✅ Full     | ⚠️ Experimental |

---

## Known Issues Summary

| Issue Type             | Claude Code                            | Cursor                            | Gemini CLI   | Codex CLI                          |
| ---------------------- | -------------------------------------- | --------------------------------- | ------------ | ---------------------------------- |
| **Hook not firing**    | Regression v2.0.27-v2.0.31             | Multiple hooks bug                | Issue #13155 | N/A (no hooks)                     |
| **Race conditions**    | PermissionRequest dialog               | N/A                               | N/A          | N/A                                |
| **Field name changes** | Legacy `decision`→`permissionDecision` | camelCase→snake_case (v2.0)       | N/A          | N/A                                |
| **Windows issues**     | None major                             | Git Bash/PowerShell injection     | None major   | WSL recommended                    |
| **Performance**        | Hooks stop after ~2.5h (log growth)    | beforeTabFileRead slow on Windows | N/A          | LD_LIBRARY_PATH regression (fixed) |

---

## Unique Features

| Feature                    | Claude Code          | Cursor                     | Gemini CLI               | Codex CLI                 |
| -------------------------- | -------------------- | -------------------------- | ------------------------ | ------------------------- |
| **LLM-evaluated hooks**    | ✅ type: prompt       | ❌                          | ❌                        | ❌                         |
| **Subagent hooks**         | ✅ SubagentStart/Stop | ❌                          | ❌                        | ❌                         |
| **Model request hooks**    | ❌                    | ❌                          | ✅ BeforeModel/AfterModel | ❌                         |
| **Tool selection hooks**   | ❌                    | ❌                          | ✅ BeforeToolSelection    | ❌                         |
| **Tab completion hooks**   | ❌                    | ✅ beforeTabFileRead        | ❌                        | ❌                         |
| **Agent thought hooks**    | ❌                    | ✅ afterAgentThought        | ❌                        | ❌                         |
| **Automatic follow-up**    | ❌                    | ✅ followup_message (max 5) | ❌                        | ❌                         |
| **Claude Code migration**  | N/A                  | ❌                          | ✅ `gemini hooks migrate` | ❌                         |
| **Skills system**          | ✅ Skills             | ❌                          | ❌                        | ✅ Skills (agentskills.io) |
| **Extension/plugin hooks** | ❌                    | ❌                          | ✅ NPM packages           | ❌                         |

---

## Migration Mapping (Claude Code → Gemini CLI)

| Claude Code      | Gemini CLI          |
| ---------------- | ------------------- |
| PreToolUse       | BeforeTool          |
| PostToolUse      | AfterTool           |
| UserPromptSubmit | BeforeAgent         |
| Stop             | AfterAgent          |
| SessionStart     | SessionStart        |
| SessionEnd       | SessionEnd          |
| Notification     | Notification        |
| Bash             | run_shell_command   |
| Read             | read_file           |
| Write            | write_file          |
| Edit/MultiEdit   | replace             |
| Glob             | glob                |
| Grep             | search_file_content |
| WebFetch         | web_fetch           |
| WebSearch        | google_web_search   |
| Task             | delegate_to_agent   |

---

## Recommendation by Use Case

| Use Case                              | Best Choice                | Reason                               |
| ------------------------------------- | -------------------------- | ------------------------------------ |
| **Pre/post tool validation**          | Claude Code or Gemini CLI  | Full hook support with matchers      |
| **LLM request/response modification** | Gemini CLI                 | Only one with BeforeModel/AfterModel |
| **IDE-integrated hooks**              | Cursor                     | Native IDE support, Tab hooks        |
| **Subagent monitoring**               | Claude Code                | SubagentStart/SubagentStop hooks     |
| **Simple notifications**              | Any (Codex CLI sufficient) | All support basic notifications      |
| **Migrating from Claude Code**        | Gemini CLI                 | Built-in migration command           |
| **No hooks needed**                   | Codex CLI                  | Simpler config, skills system        |

---

## Summary

| Metric                 | Claude Code    | Cursor   | Gemini CLI      | Codex CLI |
| ---------------------- | -------------- | -------- | --------------- | --------- |
| **Hook events**        | 11             | 10       | 11              | 1         |
| **Maturity**           | Stable (v2.1+) | Beta     | Stable (v0.21+) | N/A       |
| **Documentation**      | Comprehensive  | Moderate | Comprehensive   | N/A       |
| **Blocking support**   | ✅              | ✅        | ✅               | ❌         |
| **Input modification** | ✅              | ❌        | ✅ (limited)     | ❌         |
| **LLM hooks**          | ❌              | ❌        | ✅               | ❌         |
| **Overall hook power** | ⭐⭐⭐⭐           | ⭐⭐⭐      | ⭐⭐⭐⭐⭐           | ⭐         |

**Bottom line:** Gemini CLI has the most powerful hook system (including LLM-level hooks), Claude Code has the most mature and well-documented system, Cursor has IDE-specific features, and Codex CLI currently lacks a proper hook system (only notifications).
