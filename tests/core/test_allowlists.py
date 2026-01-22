"""Tests for allowlist invariants."""

from __future__ import annotations

from dippy.cli import KNOWN_HANDLERS
from dippy.core.allowlists import SIMPLE_SAFE, WRAPPER_COMMANDS


def test_no_handler_shadows_simple_safe():
    """No command in SIMPLE_SAFE should have a handler.

    If a command needs special handling for certain flags, it should be
    removed from SIMPLE_SAFE and handled entirely by its handler.
    """
    overlap = SIMPLE_SAFE & set(KNOWN_HANDLERS.keys())
    assert not overlap, f"Commands in both SIMPLE_SAFE and handlers: {overlap}"


def test_no_handler_shadows_wrapper_commands():
    """No command in WRAPPER_COMMANDS should have a handler.

    Wrapper commands are handled specially by the analyzer to delegate
    to their inner command. A handler would shadow this behavior.
    """
    overlap = WRAPPER_COMMANDS & set(KNOWN_HANDLERS.keys())
    assert not overlap, f"Commands in both WRAPPER_COMMANDS and handlers: {overlap}"
