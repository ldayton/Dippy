"""
Bash command parsing utilities using Parable.

Provides safe tokenization and AST inspection for analyzing shell commands.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from dippy.vendor.parable import parse

if TYPE_CHECKING:
    from dippy.core.config import SimpleCommand

# Output redirect operators that write to files
OUTPUT_REDIRECT_OPS = frozenset({">", ">>", "&>", "&>>", "2>", "2>>"})


def tokenize(command: str) -> list[str]:
    """Tokenize a bash command into a list of tokens."""
    if not command or not command.strip():
        return []

    try:
        nodes = parse(command)
        tokens = _extract_tokens(nodes)
        if tokens:
            return tokens
    except Exception:
        pass

    # Fallback to shlex
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a value."""
    if len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (
            value[0] == "'" and value[-1] == "'"
        ):
            return value[1:-1]
    return value


def _extract_tokens(nodes: list) -> list[str]:
    """Recursively extract word tokens from Parable AST nodes."""
    tokens = []
    for node in nodes:
        if node.kind == "word":
            tokens.append(_strip_quotes(node.value))
        elif node.kind == "command":
            for word in node.words:
                tokens.append(_strip_quotes(word.value))
        elif node.kind == "pipeline":
            if node.commands:
                tokens.extend(_extract_tokens([node.commands[0]]))
        elif node.kind == "list":
            for part in node.parts:
                if part.kind != "operator":
                    tokens.extend(_extract_tokens([part]))
                    break
    return tokens


def has_output_redirect(command: str) -> bool:
    """Check if command contains output redirection (>, >>)."""
    try:
        nodes = parse(command)
        return _check_redirect(nodes)
    except Exception:
        return ">" in command


def _check_redirect(nodes: list) -> bool:
    """Recursively check for output redirects in AST."""
    for node in nodes:
        if node.kind == "command":
            for redirect in node.redirects:
                op = redirect.op
                target = redirect.target.value if redirect.target else ""

                # Safe redirects: to /dev/null or fd duplication (&1, &2, etc)
                if target == "/dev/null" or target.startswith("&"):
                    continue
                # Unsafe: actual file output
                if op in (">", ">>", "&>", "&>>", "2>", "2>>"):
                    return True

            return False

        elif node.kind == "pipeline":
            if _check_redirect(node.commands):
                return True

        elif node.kind == "list":
            for part in node.parts:
                if part.kind != "operator" and _check_redirect([part]):
                    return True

    return False


def is_piped(command: str) -> bool:
    """Check if command is part of a pipeline."""
    try:
        nodes = parse(command)
        for node in nodes:
            if node.kind == "pipeline" and len(node.commands) > 1:
                return True
        return False
    except Exception:
        return "|" in command


def has_command_list(command: str) -> bool:
    """Check if command has && or || operators (command lists)."""
    try:
        nodes = parse(command)
        return _has_list_operator(nodes)
    except Exception:
        return "&&" in command or "||" in command


def _has_list_operator(nodes: list) -> bool:
    """Recursively check for list operators in AST."""
    for node in nodes:
        if node.kind == "list":
            return True
        elif node.kind == "pipeline":
            if _has_list_operator(node.commands):
                return True
    return False


def split_command_list(command: str) -> list[str]:
    """Split a command list on && and || into individual commands."""
    try:
        nodes = parse(command)
        commands = []
        _extract_list_commands(nodes, command, commands)
        return commands if commands else [command]
    except Exception:
        import re

        parts = re.split(r"\s*(?:&&|\|\|)\s*", command)
        return [p.strip() for p in parts if p.strip()]


def _extract_list_commands(nodes: list, source: str, commands: list):
    """Extract individual commands from a command list."""
    for node in nodes:
        if node.kind == "list":
            for part in node.parts:
                if part.kind != "operator":
                    _extract_list_commands([part], source, commands)
        elif node.kind == "pipeline":
            cmd_strs = []
            for cmd in node.commands:
                cmd_strs.append(_reconstruct_command(cmd))
            commands.append(" | ".join(cmd_strs))
        elif node.kind == "command":
            commands.append(_reconstruct_command(node))


def _reconstruct_command(node) -> str:
    """Reconstruct command string from AST node."""
    if node.kind == "command":
        parts = [w.value for w in node.words]
        for redirect in node.redirects:
            target = redirect.target.value if redirect.target else ""
            parts.append(f"{redirect.op}{target}")
        return " ".join(parts)
    return ""


def split_pipeline(command: str) -> list[str]:
    """Split a pipeline into individual commands."""
    try:
        nodes = parse(command)
        commands = []

        for node in nodes:
            if node.kind == "pipeline":
                for cmd in node.commands:
                    commands.append(_reconstruct_command(cmd))
            elif node.kind == "command":
                commands.append(_reconstruct_command(node))

        return commands if commands else [command]
    except Exception:
        return [cmd.strip() for cmd in command.split("|") if cmd.strip()]


def get_command_substitutions(command: str) -> list[tuple[str, bool, int]]:
    """
    Extract command substitutions from a command.

    Returns list of (inner_command, is_pure, position) tuples where:
    - inner_command: the command inside $()
    - is_pure: True if word is entirely $(...), False if embedded like foo-$(...)
    - position: argument position (0=command, 1=first arg, etc.)
    """
    try:
        nodes = parse(command)
        results = []
        _extract_cmdsubs(nodes, results)
        return results
    except Exception:
        return []


def _extract_cmdsubs(nodes: list, results: list):
    """Recursively extract command substitutions from AST."""
    for node in nodes:
        if node.kind == "command":
            for i, word in enumerate(node.words):
                if not word.parts:
                    continue
                for part in word.parts:
                    if part.kind == "cmdsub":
                        inner_cmd = _reconstruct_command(part.command)
                        # Pure if word value starts with $( and ends with )
                        is_pure = word.value.startswith("$(") or word.value.startswith(
                            "`"
                        )
                        results.append((inner_cmd, is_pure, i))
        elif node.kind == "pipeline":
            _extract_cmdsubs(node.commands, results)
        elif node.kind == "list":
            for part in node.parts:
                if part.kind != "operator":
                    _extract_cmdsubs([part], results)


def extract_simple_commands(command: str) -> list[SimpleCommand]:
    """Parse bash and extract SimpleCommand instances for rule matching.

    Returns list of SimpleCommand, one per simple command in the AST.
    Raises ValueError if bash is invalid (Parable parse failure).
    """

    if not command or not command.strip():
        return []

    try:
        nodes = parse(command)
    except Exception:
        raise ValueError("invalid bash") from None

    commands: list[SimpleCommand] = []
    _extract_simple_commands_recursive(nodes, commands)
    return commands


def _extract_simple_commands_recursive(nodes: list, commands: list) -> None:
    """Recursively walk AST extracting Command nodes into SimpleCommand instances."""
    from dippy.core.config import SimpleCommand

    for node in nodes:
        if node.kind == "command":
            words = [_strip_quotes(w.value) for w in node.words]
            redirects = []
            for r in node.redirects:
                # Skip heredocs - they don't have .op attribute
                if r.kind == "heredoc":
                    continue
                if r.op in OUTPUT_REDIRECT_OPS and r.target:
                    target = _strip_quotes(r.target.value)
                    # Skip safe redirects
                    if target != "/dev/null" and not target.startswith("&"):
                        redirects.append(target)
            commands.append(SimpleCommand(words=words, redirects=redirects))

        elif node.kind == "pipeline":
            for cmd in node.commands:
                if hasattr(cmd, "kind") and cmd.kind != "pipe-both":
                    _extract_simple_commands_recursive([cmd], commands)

        elif node.kind == "list":
            for part in node.parts:
                if hasattr(part, "kind") and part.kind != "operator":
                    _extract_simple_commands_recursive([part], commands)


def extract_redirect_targets(command: str) -> list[str]:
    """Extract output redirect target paths from command.

    Returns list of paths that are targets of output redirects.
    Raises ValueError if bash is invalid (Parable parse failure).
    """
    if not command or not command.strip():
        return []

    try:
        nodes = parse(command)
    except Exception:
        raise ValueError("invalid bash") from None

    targets: list[str] = []
    _extract_redirect_targets_recursive(nodes, targets)
    return targets


def _extract_redirect_targets_recursive(nodes: list, targets: list) -> None:
    """Recursively walk AST extracting redirect targets."""
    for node in nodes:
        if node.kind == "command":
            for r in node.redirects:
                # Skip heredocs - they don't have .op attribute
                if r.kind == "heredoc":
                    continue
                if r.op in OUTPUT_REDIRECT_OPS and r.target:
                    target = _strip_quotes(r.target.value)
                    # Skip safe redirects
                    if target != "/dev/null" and not target.startswith("&"):
                        targets.append(target)

        elif node.kind == "pipeline":
            for cmd in node.commands:
                if hasattr(cmd, "kind") and cmd.kind != "pipe-both":
                    _extract_redirect_targets_recursive([cmd], targets)

        elif node.kind == "list":
            for part in node.parts:
                if hasattr(part, "kind") and part.kind != "operator":
                    _extract_redirect_targets_recursive([part], targets)
