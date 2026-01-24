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
