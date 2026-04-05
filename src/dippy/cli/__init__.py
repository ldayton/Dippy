"""
CLI-specific command handlers for Dippy.

Each handler module exports:
- COMMANDS: list[str] - command names this handler supports
- classify(ctx: HandlerContext) -> Classification - classify command for approval
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, Protocol


@dataclass(frozen=True)
class HandlerContext:
    """Context passed to handlers."""

    tokens: list[str]


@dataclass(frozen=True)
class Classification:
    """Result of classifying a command.

    Handlers return this to indicate:
    - allow: command is safe, no further checking needed
    - ask: command needs user confirmation
    - delegate: check inner_command to determine safety
    """

    action: Literal["allow", "ask", "delegate"]
    inner_command: str | None = None  # Required when action="delegate"
    description: str | None = None  # Optional, overrides default description
    redirect_targets: tuple[
        str, ...
    ] = ()  # File targets to check against redirect rules
    remote: bool = False  # Inner command runs in remote context (container, ssh, etc.)


class CLIHandler(Protocol):
    """Protocol for CLI handler modules."""

    def classify(self, ctx: HandlerContext) -> Classification:
        """Classify command for approval.

        Args:
            ctx: Handler context containing command tokens

        Returns Classification with action and optional description.
        """
        ...


# How many tokens to include in description (base + action + ...)
# Default is 2 (e.g., "git status", "docker ps")
DESCRIPTION_DEPTH = {
    "aws": 3,  # aws s3 ls
    "gcloud": 3,  # gcloud compute instances
    "gsutil": 2,  # gsutil ls
    "az": 3,  # az vm list
}


def get_description(tokens: list[str], handler_name: str = None) -> str:
    """Compute description from tokens based on handler type."""
    if not tokens:
        return "unknown"

    # Check if handler has its own get_description function
    base = tokens[0]
    handler = get_handler(handler_name or base)
    if handler and hasattr(handler, "get_description"):
        return handler.get_description(tokens)

    depth = DESCRIPTION_DEPTH.get(handler_name or base, 2)
    return " ".join(tokens[:depth])


def strip_global_flags(tokens: list[str]) -> list[str] | None:
    """Strip handler-recognized global flags from command tokens.

    Used by the analyzer to retry config matching when raw tokens don't match.
    Looks up the handler for tokens[0] and uses GLOBAL_FLAGS_WITH_ARG and
    GLOBAL_FLAGS_NO_ARG constants to remove global flags.

    Returns cleaned tokens, or None if no handler, no flags stripped, or
    tokens is too short.
    """
    if len(tokens) < 2:
        return None

    handler = get_handler(tokens[0])
    if handler is None:
        return None

    flags_with_arg: frozenset[str] = getattr(
        handler, "GLOBAL_FLAGS_WITH_ARG", frozenset()
    )
    flags_no_arg: frozenset[str] = getattr(handler, "GLOBAL_FLAGS_NO_ARG", frozenset())

    if not flags_with_arg and not flags_no_arg:
        return None

    result = [tokens[0]]
    i = 1
    changed = False

    while i < len(tokens):
        token = tokens[i]

        # --flag=value form for flags with arg
        if any(token.startswith(f"{flag}=") for flag in flags_with_arg):
            changed = True
            i += 1
            continue

        # Flags with argument (consume flag + next token)
        if token in flags_with_arg:
            changed = True
            i += 2
            continue

        # Flags without argument
        if token in flags_no_arg:
            changed = True
            i += 1
            continue

        # Not a global flag — keep rest as-is
        result.extend(tokens[i:])
        break

    return result if changed else None


def _discover_handlers() -> dict[str, str]:
    """Discover handler modules and build command -> module mapping."""
    handlers = {}
    cli_dir = Path(__file__).parent
    for file in cli_dir.glob("*.py"):
        if file.name.startswith("_"):
            continue
        module_name = file.stem
        try:
            module = importlib.import_module(f".{module_name}", package="dippy.cli")
            for cmd in getattr(module, "COMMANDS", []):
                handlers[cmd] = module_name
        except ImportError:
            continue
    return handlers


# Build handler mapping at import time
KNOWN_HANDLERS = _discover_handlers()


def get_handler(command_name: str) -> Optional[CLIHandler]:
    """
    Get the handler module for a CLI command.

    Returns None if no handler exists for the command.
    """
    module_name = KNOWN_HANDLERS.get(command_name)
    if not module_name:
        return None

    return _load_handler(module_name)


@lru_cache(maxsize=32)
def _load_handler(module_name: str) -> Optional[CLIHandler]:
    """Load a CLI handler module by name (cached within process)."""
    try:
        return importlib.import_module(f".{module_name}", package="dippy.cli")
    except ImportError:
        return None
