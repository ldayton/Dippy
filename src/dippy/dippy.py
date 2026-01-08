#!/usr/bin/env python3
"""
Dippy - Approval autopilot for Claude Code.

A PreToolUse hook that auto-approves safe commands while prompting for
anything destructive. Stay in the flow.

Usage:
    Add to ~/.claude/settings.json hooks configuration.
    See README.md for details.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from dippy.core.parser import (
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
from dippy.cli import get_handler


# === Logging Setup ===

LOG_FILE = Path.home() / ".claude" / "hook-approvals.log"


def setup_logging():
    """Configure logging to file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# === Response Helpers ===

def approve(reason: str = "") -> dict:
    """Return approval response."""
    logging.info(f"APPROVED: {reason}")
    return {"decision": "approve"}


def deny(reason: str = "") -> dict:
    """Return denial response."""
    logging.info(f"DENIED: {reason}")
    return {"decision": "deny", "reason": reason}


def ask() -> dict:
    """Return ask-user response (no decision, prompts user)."""
    return {}


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

def check_simple_command(cmd: str, tokens: list[str]) -> Optional[str]:
    """
    Check simple commands that don't need CLI-specific handling.

    Returns "approve", "deny", or None for further processing.
    """
    if not tokens:
        return None

    # Skip environment variable assignments (FOO=bar)
    i = 0
    while i < len(tokens) and '=' in tokens[i] and not tokens[i].startswith('-'):
        i += 1

    if i >= len(tokens):
        return None  # Only env vars, no command

    base = tokens[i]
    rest = tokens[i:]

    # Handle prefix commands (time, env, timeout, etc.)
    if base in PREFIX_COMMANDS and len(rest) > 1:
        # Special case: "command -v" and "command -V" are safe lookups
        if base == "command" and len(rest) > 1 and rest[1] in ("-v", "-V"):
            return "approve"

        # Some prefix commands take arguments (e.g., timeout 5)
        # Skip numeric arguments and flags until we find the actual command
        j = 1
        while j < len(rest):
            token = rest[j]
            # Skip numeric arguments
            if token.isdigit() or token.replace('.', '').isdigit():
                j += 1
                continue
            # Skip flags (but stop at -- which ends flag processing)
            if token.startswith('-') and token != '--':
                j += 1
                continue
            # -- ends flag processing, skip it and use next token
            if token == '--':
                j += 1
            # Found the actual command
            break

        if j < len(rest):
            # Use full check for inner command (it might need a handler)
            inner_cmd = " ".join(rest[j:])
            return _check_single_command(inner_cmd)
        return None

    # Simple safe commands
    if base in SIMPLE_SAFE:
        return "approve"

    # Version/help checks are always safe
    if is_version_or_help(rest):
        return "approve"

    return None


def check_command(command: str) -> dict:
    """
    Main entry point: check if a command should be approved.

    Returns a hook response dict.
    """
    command = command.strip()

    if not command:
        return ask()

    # Check for output redirects first (always unsafe)
    if has_output_redirect(command):
        return ask()  # Let user decide

    # Handle command lists (&&, ||) - each command must be safe
    if has_command_list(command):
        commands = split_command_list(command)
        for cmd in commands:
            # Each part might itself be a pipeline
            result = check_command(cmd.strip())
            if result.get("decision") != "approve":
                return ask()
        return approve(f"list: {command[:50]}")

    # Handle pipelines - each command must be safe
    if is_piped(command):
        commands = split_pipeline(command)
        for cmd in commands:
            result = _check_single_command(cmd.strip())
            if result != "approve":
                return ask()
        return approve(f"pipeline: {command[:50]}")

    # Single command
    result = _check_single_command(command)

    if result == "approve":
        return approve(command[:80])
    elif result == "deny":
        return deny(f"blocked: {command[:50]}")
    else:
        return ask()


def _check_single_command(command: str) -> Optional[str]:
    """
    Check a single (non-pipeline) command.

    Returns "approve", "deny", or None.
    """
    tokens = tokenize(command)
    if not tokens:
        return None

    # Try simple command check first (fast path)
    result = check_simple_command(command, tokens)
    if result:
        return result

    # Get base command
    base = tokens[0]

    # Try CLI-specific handler
    handler = get_handler(base)
    if handler:
        return handler.check(command, tokens)

    # Check unsafe patterns (fallback for unknown commands)
    # This comes after handlers so they can approve things like "aws s3 rm --help"
    if check_unsafe_patterns(command):
        return None  # Ask user

    # Unknown command - ask user
    return None


# === Hook Entry Point ===

def main():
    """Main entry point for the hook."""
    setup_logging()
    
    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
        
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        
        # Only handle Bash commands
        if tool_name != "Bash":
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
