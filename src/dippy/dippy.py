#!/usr/bin/env python3
"""
Dippy - Approval autopilot for Claude Code, Gemini CLI, and Cursor.

A PreToolUse/BeforeTool/beforeShellExecution hook that auto-approves safe
commands while prompting for anything destructive. Stay in the flow.

Usage:
    Claude Code: Add to ~/.claude/settings.json hooks configuration.
    Gemini CLI:  Add to ~/.gemini/settings.json with --gemini flag.
    Cursor:      Add to .cursor/hooks.json with --cursor flag.
    See README.md for details.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dippy.core.config import (
    Config,
    ConfigError,
    configure_logging,
    load_config,
    log_decision,
    match_after_mcp,
    match_after_web,
    match_mcp,
    match_web,
)
from dippy.core.analyzer import analyze


# === Mode Detection ===


def _env_flag(name: str) -> bool:
    """Check if an environment variable is truthy."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _detect_mode_from_flags() -> str | None:
    """Detect mode from command-line flags or env vars. Returns None if not set."""
    if "--claude" in sys.argv or _env_flag("DIPPY_CLAUDE"):
        return "claude"
    if "--gemini" in sys.argv or _env_flag("DIPPY_GEMINI"):
        return "gemini"
    if "--cursor" in sys.argv or _env_flag("DIPPY_CURSOR"):
        return "cursor"
    return None


def _detect_mode_from_input(input_data: dict) -> str:
    """Auto-detect mode from input JSON structure."""
    # Cursor: {"command": "...", "cwd": "..."}
    if "command" in input_data and "tool_name" not in input_data:
        return "cursor"

    # Claude/Gemini: {"tool_name": "...", "tool_input": {...}}
    tool_name = input_data.get("tool_name", "")

    # Gemini uses "shell", "run_shell_command", etc.
    if tool_name in ("shell", "run_shell", "run_shell_command", "execute_shell"):
        return "gemini"

    # Claude uses "Bash" and MCP tools use "mcp__*" prefix
    if tool_name and tool_name != "Bash" and not tool_name.startswith("mcp__"):
        logging.warning(f"Unknown tool_name '{tool_name}', defaulting to Claude mode")
    return "claude"


# Initial mode from flags/env (may be overridden by auto-detect)
_EXPLICIT_MODE = _detect_mode_from_flags()
MODE = _EXPLICIT_MODE or "claude"  # Default for logging setup

# === Logging Setup ===


def _get_log_file() -> Path:
    """Get log file path based on mode."""
    if MODE == "gemini":
        return Path.home() / ".gemini" / "hook-approvals.log"
    if MODE == "cursor":
        return Path.home() / ".cursor" / "hook-approvals.log"
    return Path.home() / ".claude" / "hook-approvals.log"


def setup_logging():
    """Configure logging to file. Fails silently if unable to write."""
    try:
        log_file = _get_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    except (OSError, PermissionError):
        pass  # Logging is optional - don't crash if we can't write


# === Response Helpers ===


def approve(reason: str = "all commands safe") -> dict:
    """Return approval response."""
    logging.info(f"APPROVED: {reason}")
    if MODE == "gemini":
        return {"decision": "allow", "reason": f"🐤 {reason}"}
    if MODE == "cursor":
        # Include both snake_case (v2.0+) and camelCase (v1.7.x) for compatibility
        msg = f"🐤 {reason}"
        return {
            "permission": "allow",
            "user_message": msg,
            "agent_message": msg,
            "userMessage": msg,
            "agentMessage": msg,
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"🐤 {reason}",
        }
    }


def ask(reason: str = "needs approval") -> dict:
    """Return ask response to prompt user for confirmation."""
    logging.info(f"ASK: {reason}")
    if MODE == "gemini":
        return {"decision": "ask", "reason": f"🐤 {reason}"}
    if MODE == "cursor":
        # Include both snake_case (v2.0+) and camelCase (v1.7.x) for compatibility
        msg = f"🐤 {reason}"
        return {
            "permission": "ask",
            "user_message": msg,
            "agent_message": msg,
            "userMessage": msg,
            "agentMessage": msg,
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"🐤 {reason}",
        }
    }


def deny(reason: str = "denied by config") -> dict:
    """Return deny response to block the command."""
    logging.info(f"DENY: {reason}")
    if MODE == "gemini":
        return {"decision": "deny", "reason": f"🐤 {reason}"}
    if MODE == "cursor":
        # Include both snake_case (v2.0+) and camelCase (v1.7.x) for compatibility
        msg = f"🐤 {reason}"
        return {
            "permission": "deny",
            "user_message": msg,
            "agent_message": msg,
            "userMessage": msg,
            "agentMessage": msg,
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"🐤 {reason}",
        }
    }


# === Main Logic ===


def check_command(command: str, config: Config, cwd: Path) -> dict:
    """
    Main entry point: check if a command should be approved.

    Uses a single recursive walk of the bash AST to analyze all constructs.
    Returns a hook response dict.
    """
    result = analyze(command, config, cwd)

    log_decision(
        "allow" if result.action == "allow" else result.action,
        result.reason,
        command=command,
    )

    if result.action == "allow":
        return approve(result.reason)
    elif result.action == "deny":
        return deny(result.reason)
    else:
        return ask(result.reason)


def post_tool_response(message: str) -> dict:
    """Return PostToolUse response with feedback for Claude."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"🐤 {message}",
        }
    }


def handle_post_tool_use(command: str, config: Config, cwd: Path) -> None:
    """Handle PostToolUse hook - output feedback message if rule matches."""
    from dippy.core.config import match_after
    from dippy.core.parser import tokenize

    words = tokenize(command)
    message = match_after(words, config, cwd)
    if message:  # non-empty string
        print(json.dumps(post_tool_response(message)))
    # empty string or None = silent (no output)


# === MCP Tool Handling ===


def is_mcp_tool(name: str) -> bool:
    """Check if a tool name is an MCP tool."""
    return name.startswith("mcp__")


def check_mcp_tool(tool_name: str, config: Config) -> dict:
    """Check if an MCP tool should be approved based on config rules.

    Args:
        tool_name: MCP tool name (e.g., "mcp__github__get_issue").
        config: Loaded configuration.

    Returns:
        Hook response dict, or empty dict if no rules match (defer to default).
    """
    match = match_mcp(tool_name, config)
    if match is None:
        return {}  # No rules match - defer to Claude's default behavior
    reason = match.message if match.message else f"[{match.pattern}]"
    log_decision(match.decision, reason, rule=match.pattern)
    if match.decision == "allow":
        return approve(reason)
    elif match.decision == "deny":
        return deny(reason)
    else:
        return ask(reason)


def handle_mcp_post_tool_use(tool_name: str, config: Config) -> None:
    """Handle PostToolUse hook for MCP tools - output feedback if rule matches."""
    message = match_after_mcp(tool_name, config)
    if message:  # non-empty string
        print(json.dumps(post_tool_response(message)))
    # empty string or None = silent (no output)


# === WebSearch Tool Handling ===


def check_web_tool(query: str, config: Config) -> dict:
    """Check if a WebSearch tool should be approved based on config rules.

    Args:
        query: WebSearch query string.
        config: Loaded configuration.

    Returns:
        Hook response dict, or empty dict if no rules match (defer to default).
    """
    match = match_web(query, config)
    if match is None:
        return {}  # No rules match - defer to Claude's default behavior
    reason = match.message if match.message else f"[{match.pattern}]"
    log_decision(match.decision, reason, rule=match.pattern)
    if match.decision == "allow":
        return approve(reason)
    elif match.decision == "deny":
        return deny(reason)
    else:
        return ask(reason)


def handle_web_post_tool_use(query: str, config: Config) -> None:
    """Handle PostToolUse hook for WebSearch - output feedback if rule matches."""
    message = match_after_web(query, config)
    if message:  # non-empty string
        print(json.dumps(post_tool_response(message)))
    # empty string or None = silent (no output)


# === Hook Entry Point ===

# Tool names that indicate shell/bash commands
SHELL_TOOL_NAMES = frozenset(
    {
        "Bash",  # Claude Code
        "shell",  # Gemini CLI
        "run_shell",  # Gemini CLI alternate
        "run_shell_command",  # Gemini CLI official name
        "execute_shell",  # Gemini CLI alternate
    }
)


def main():
    """Main entry point for the hook."""
    global MODE

    setup_logging()

    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)

        # Auto-detect mode from input if no explicit flag/env was set
        if _EXPLICIT_MODE is None:
            MODE = _detect_mode_from_input(input_data)
            logging.info(f"Auto-detected mode: {MODE}")

        # Extract cwd from input
        # Cursor: top-level "cwd"
        # Claude Code: may be in tool_input or top-level
        cwd_str = input_data.get("cwd")
        if not cwd_str:
            tool_input = input_data.get("tool_input", {})
            cwd_str = tool_input.get("cwd")
        if cwd_str:
            cwd = Path(cwd_str).resolve()
        else:
            cwd = Path.cwd()

        # Load config (fails hard on errors)
        try:
            config = load_config(cwd)
            configure_logging(config)
        except ConfigError as e:
            logging.error(f"Config error: {e}")
            print(json.dumps(ask(f"config error: {e}")))
            return

        # Detect hook event type (Claude Code only)
        hook_event = input_data.get("hook_event_name", "PreToolUse")

        # Extract command based on mode
        # Cursor: {"command": "...", "cwd": "..."}
        # Claude/Gemini: {"tool_name": "...", "tool_input": {"command": "..."}}
        if MODE == "cursor":
            # Cursor sends command directly (beforeShellExecution hook)
            command = input_data.get("command", "")
            tool_name = None
        else:
            # Claude Code and Gemini CLI use tool_name/tool_input format
            tool_name = input_data.get("tool_name", "")
            tool_input = input_data.get("tool_input", {})

            # Check if this is an MCP tool
            if is_mcp_tool(tool_name):
                # Check for bypass permissions mode first
                if hook_event != "PostToolUse":
                    permission_mode = input_data.get("permission_mode", "default")
                    if permission_mode in ("bypassPermissions", "dontAsk"):
                        logging.info(f"Bypass mode ({permission_mode}): {tool_name}")
                        log_decision("allow", permission_mode)
                        print(json.dumps(approve(permission_mode)))
                        return
                # Handle MCP tool
                if hook_event == "PostToolUse":
                    logging.info(f"PostToolUse MCP: {tool_name}")
                    handle_mcp_post_tool_use(tool_name, config)
                else:
                    logging.info(f"Checking MCP: {tool_name}")
                    result = check_mcp_tool(tool_name, config)
                    print(json.dumps(result))
                return

            # Check if this is a web tool (Claude: WebSearch/WebFetch, Gemini: google_web_search/web_fetch)
            if tool_name in ("WebSearch", "WebFetch", "google_web_search", "web_fetch"):
                # WebSearch/google_web_search use query, WebFetch/web_fetch use url
                match_value = tool_input.get("query") or tool_input.get("url", "")
                # Check for bypass permissions mode first
                if hook_event != "PostToolUse":
                    permission_mode = input_data.get("permission_mode", "default")
                    if permission_mode in ("bypassPermissions", "dontAsk"):
                        logging.info(f"Bypass mode ({permission_mode}): {tool_name}")
                        log_decision("allow", permission_mode)
                        print(json.dumps(approve(permission_mode)))
                        return
                # Handle WebSearch/WebFetch tool
                if hook_event == "PostToolUse":
                    logging.info(f"PostToolUse {tool_name}: {match_value}")
                    handle_web_post_tool_use(match_value, config)
                else:
                    logging.info(f"Checking {tool_name}: {match_value}")
                    result = check_web_tool(match_value, config)
                    print(json.dumps(result))
                return

            # Only handle shell/bash commands
            if tool_name not in SHELL_TOOL_NAMES:
                print(json.dumps({}))
                return

            command = tool_input.get("command", "")

        # Check for bypass permissions mode (Claude Code PreToolUse only)
        if hook_event != "PostToolUse":
            permission_mode = input_data.get("permission_mode", "default")
            if permission_mode in ("bypassPermissions", "dontAsk"):
                logging.info(f"Bypass mode ({permission_mode}): {command}")
                log_decision("allow", permission_mode, command=command)
                print(json.dumps(approve(permission_mode)))
                return

        # Route based on hook event type
        if hook_event == "PostToolUse":
            logging.info(f"PostToolUse: {command}")
            handle_post_tool_use(command, config, cwd)
        else:
            logging.info(f"Checking: {command}")
            result = check_command(command, config, cwd)
            print(json.dumps(result))

    except json.JSONDecodeError:
        logging.error("Invalid JSON input")
        print(json.dumps({}))
    except Exception as e:
        logging.error(f"Error: {e}")
        print(json.dumps({}))


if __name__ == "__main__":
    main()
