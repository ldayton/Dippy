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

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dippy.core.parser import (
    get_command_substitutions,
    has_command_list,
    has_output_redirect,
    is_piped,
    split_command_list,
    split_pipeline,
    tokenize,
)
from dippy.core.patterns import (
    PREFIX_COMMANDS,
    SIMPLE_SAFE,
    UNSAFE_PATTERNS,
)
from dippy.cli import get_handler, get_description


# === Mode Detection ===


def _env_flag(name: str) -> bool:
    """Check if an environment variable is truthy."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _detect_mode_from_flags() -> Optional[str]:
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

    # Claude uses "Bash" - warn if unexpected tool_name
    if tool_name and tool_name != "Bash":
        logging.warning(f"Unknown tool_name '{tool_name}', defaulting to Claude mode")
    return "claude"


# Initial mode from flags/env (may be overridden by auto-detect)
_EXPLICIT_MODE = _detect_mode_from_flags()
MODE = _EXPLICIT_MODE or "claude"  # Default for logging setup
GEMINI_MODE = MODE == "gemini"  # Backwards compat
CURSOR_MODE = MODE == "cursor"


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


# === Safety Checks ===


def check_unsafe_patterns(command: str) -> bool:
    """Check if command matches any unsafe patterns."""
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(command):
            return True
    return False


def is_version_or_help(tokens: list[str]) -> bool:
    """Check if command is a version/help check.

    Only considers explicit --version/--help flags as universal.
    Short flags like -v and -V are ambiguous (could be verbose).

    To avoid false positives (e.g., "cargo install --version 1.0.0"),
    only match if:
    - It's the only argument after the command (e.g., "foo --help")
    - It's "help" or "version" as a subcommand in position 1 (e.g., "cargo help")
    """
    if len(tokens) < 2:
        return False

    # "cmd help" or "cmd version" as subcommand (with no additional args)
    # "npm version" shows versions, but "npm version minor" modifies
    if len(tokens) == 2 and tokens[1] in ("help", "version"):
        return True

    # "cmd --help" or "cmd --version" or "cmd -h" as the ONLY argument
    if len(tokens) == 2 and tokens[1] in ("--version", "--help", "-h"):
        return True

    # Also allow "cmd subcmd --help" pattern where --help is the last arg
    if tokens[-1] in ("--help", "-h") and len(tokens) <= 4:
        return True

    return False


# === Main Logic ===


def check_simple_command(
    cmd: str, tokens: list[str]
) -> tuple[Optional[str], Optional[str]]:
    """
    Check simple commands that don't need CLI-specific handling.

    Returns (decision, description) where decision is "approve" or None.
    Returns (None, None) if not handled by this function.
    """
    if not tokens:
        return (None, None)

    # Skip environment variable assignments (FOO=bar)
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1

    if i >= len(tokens):
        return (None, None)  # Only env vars, no command

    base = tokens[i]
    rest = tokens[i:]

    # Handle prefix commands (time, env, timeout, etc.)
    if base in PREFIX_COMMANDS and len(rest) > 1:
        # Special case: "command -v" and "command -V" are safe lookups
        if base == "command" and len(rest) > 1 and rest[1] in ("-v", "-V"):
            return ("approve", "command -v")

        # Some prefix commands take arguments (e.g., timeout 5)
        # Skip numeric arguments and flags until we find the actual command
        j = 1
        while j < len(rest):
            token = rest[j]
            # Skip numeric arguments
            if token.isdigit() or token.replace(".", "").isdigit():
                j += 1
                continue
            # Skip flags (but stop at -- which ends flag processing)
            if token.startswith("-") and token != "--":
                j += 1
                continue
            # -- ends flag processing, skip it and use next token
            if token == "--":
                j += 1
            # Found the actual command
            break

        if j < len(rest):
            # Use full check for inner command (it might need a handler)
            inner_cmd = " ".join(rest[j:])
            return _check_single_command(inner_cmd)
        return (None, base)

    # Simple safe commands
    if base in SIMPLE_SAFE:
        return ("approve", base)

    # Version/help checks are always safe
    if is_version_or_help(rest):
        return ("approve", base)

    return (None, None)


def _check_command_substitutions(command: str) -> Optional[dict]:
    """
    Check command substitutions in a command.

    Returns None if all cmdsubs are safe, or a response dict if blocked.

    Rules:
    - Inner commands must be safe (recursively checked)
    - Pure cmdsubs ($(cmd) as entire arg) in subcommand position are blocked
      for CLIs with handlers (git, docker, etc.) to prevent injection
    - Embedded cmdsubs (foo-$(cmd)) only need inner command to be safe
    - SIMPLE_SAFE commands allow pure cmdsubs in any position
    """
    cmdsubs = get_command_substitutions(command)
    if not cmdsubs:
        return None

    tokens = tokenize(command)
    if not tokens:
        return None

    base = tokens[0]
    has_handler = get_handler(base) is not None
    is_simple_safe = base in SIMPLE_SAFE

    for inner_cmd, is_pure, position in cmdsubs:
        # Recursively check inner command's cmdsubs first
        inner_cmdsub_result = _check_command_substitutions(inner_cmd)
        if inner_cmdsub_result is not None:
            return inner_cmdsub_result

        # Check inner command itself is safe
        inner_decision, inner_desc = _check_single_command(inner_cmd)
        if inner_decision != "approve":
            return ask(f"cmdsub: {inner_desc}")

        # For pure cmdsubs in arg positions of handler-based CLIs, block
        # (they could inject subcommands like git $(echo rm))
        if is_pure and has_handler and not is_simple_safe and position >= 1:
            return ask(f"cmdsub injection risk: {inner_cmd}")

    return None


def check_command(command: str) -> dict:
    """
    Main entry point: check if a command should be approved.

    Returns a hook response dict.
    """
    command = command.strip()
    if not command:
        return ask("empty command")

    # Check for output redirects
    if has_output_redirect(command):
        return ask("output redirect")

    # Check command substitutions - inner commands must be safe
    cmdsub_result = _check_command_substitutions(command)
    if cmdsub_result is not None:
        return cmdsub_result

    # Handle command lists (&&, ||) - each command must be safe
    if has_command_list(command):
        commands = split_command_list(command)
        unsafe = []
        safe = []
        for cmd in commands:
            decision, desc = _check_single_command(cmd.strip())
            if decision != "approve":
                unsafe.append(desc)
            else:
                safe.append(desc)
        if unsafe:
            return ask(", ".join(unsafe))
        return approve(", ".join(safe))

    # Handle pipelines - each command must be safe
    if is_piped(command):
        commands = split_pipeline(command)
        unsafe = []
        safe = []
        for cmd in commands:
            decision, desc = _check_single_command(cmd.strip())
            if decision != "approve":
                unsafe.append(desc)
            else:
                safe.append(desc)
        if unsafe:
            return ask(", ".join(unsafe))
        return approve(", ".join(safe))

    # Single command
    decision, desc = _check_single_command(command)

    if decision == "approve":
        return approve(desc)
    return ask(desc)


def _check_single_command(command: str) -> tuple[Optional[str], str]:
    """
    Check a single (non-pipeline) command.

    Returns (decision, description) where decision is "approve" or None.
    """
    tokens = tokenize(command)
    if not tokens:
        return (None, command)

    base = tokens[0]

    # Try simple command check first (fast path)
    decision, desc = check_simple_command(command, tokens)
    if decision is not None or desc is not None:
        # check_simple_command handled this command
        return (decision, desc if desc else base)

    # Try CLI-specific handler
    handler = get_handler(base)
    if handler:
        desc = get_description(tokens, base)
        approved = handler.check(tokens)
        return ("approve", desc) if approved else (None, desc)

    # Check unsafe patterns (fallback for unknown commands)
    # This comes after handlers so they can approve things like "aws s3 rm --help"
    if check_unsafe_patterns(command):
        return (None, base)  # Ask user

    # Unknown command - ask user
    return (None, base)


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
    global MODE, GEMINI_MODE, CURSOR_MODE

    setup_logging()

    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)

        # Auto-detect mode from input if no explicit flag/env was set
        if _EXPLICIT_MODE is None:
            MODE = _detect_mode_from_input(input_data)
            GEMINI_MODE = MODE == "gemini"
            CURSOR_MODE = MODE == "cursor"
            logging.info(f"Auto-detected mode: {MODE}")

        # Extract command based on mode
        # Cursor: {"command": "...", "cwd": "..."}
        # Claude/Gemini: {"tool_name": "...", "tool_input": {"command": "..."}}
        if MODE == "cursor":
            # Cursor sends command directly (beforeShellExecution hook)
            command = input_data.get("command", "")
        else:
            # Claude Code and Gemini CLI use tool_name/tool_input format
            tool_name = input_data.get("tool_name", "")
            tool_input = input_data.get("tool_input", {})

            # Only handle shell/bash commands
            if tool_name not in SHELL_TOOL_NAMES:
                print(json.dumps({}))
                return

            command = tool_input.get("command", "")

        logging.info(f"Checking: {command}")
        result = check_command(command)
        print(json.dumps(result))

    except json.JSONDecodeError:
        logging.error("Invalid JSON input")
        print(json.dumps({}))
    except Exception as e:
        logging.error(f"Error: {e}")
        print(json.dumps({}))


if __name__ == "__main__":
    main()
