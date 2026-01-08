"""
Dippy - Approval autopilot for Claude Code.

Auto-approves safe commands while prompting for anything destructive.
"""

__version__ = "0.2.0"

from dippy.dippy import check_command

__all__ = ["check_command", "__version__"]
