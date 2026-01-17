"""
Bash command parsing utilities using Parable.

Provides safe tokenization for analyzing shell commands.
"""

from __future__ import annotations

import shlex

from dippy.vendor.parable import parse


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
