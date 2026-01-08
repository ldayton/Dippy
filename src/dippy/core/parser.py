"""
Bash command parsing utilities using Parable.

Provides safe tokenization and AST inspection for analyzing shell commands.
"""

import shlex

from parable import parse


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
        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
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
                commands.append(_reconstruct_command(cmd))

        return commands if commands else [command]
    except Exception:
        return [cmd.strip() for cmd in command.split("|") if cmd.strip()]
