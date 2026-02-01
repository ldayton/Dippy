"""
Dippy - Approval autopilot for Claude Code.

Auto-approves safe commands while prompting for anything destructive.
"""

from __future__ import annotations

__version__ = "0.2.5"

from dippy.dippy import check_command

__all__ = ["check_command", "__version__"]
