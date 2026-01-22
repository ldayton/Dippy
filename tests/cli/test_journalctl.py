"""
Comprehensive tests for journalctl CLI handler.

Journalctl is safe for viewing logs, but modification flags need confirmation.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing logs ===
    ("journalctl", True),
    ("journalctl -f", True),  # follow
    ("journalctl --follow", True),
    ("journalctl -n 100", True),  # lines
    ("journalctl --lines=100", True),
    ("journalctl -r", True),  # reverse
    ("journalctl --reverse", True),
    ("journalctl -o json", True),  # output format
    ("journalctl --output=json", True),
    ("journalctl -u sshd", True),  # unit
    ("journalctl --unit=nginx", True),
    ("journalctl -b", True),  # boot
    ("journalctl --boot", True),
    ("journalctl -b -1", True),  # previous boot
    ("journalctl -k", True),  # kernel messages
    ("journalctl --dmesg", True),
    ("journalctl -p err", True),  # priority
    ("journalctl --priority=warning", True),
    ("journalctl --since today", True),
    ("journalctl --until now", True),
    ("journalctl -S '2024-01-01' -U '2024-01-31'", True),
    ("journalctl _PID=1234", True),  # field match
    ("journalctl _SYSTEMD_UNIT=sshd.service", True),
    ("journalctl --disk-usage", True),
    ("journalctl --list-boots", True),
    ("journalctl -x", True),  # augment with explanations
    ("journalctl --no-pager", True),
    ("journalctl -u nginx -f -n 50", True),  # multiple safe flags
    #
    # === UNSAFE: Modifying journal ===
    ("journalctl --rotate", False),
    ("journalctl --vacuum-time=1d", False),
    ("journalctl --vacuum-time 2weeks", False),
    ("journalctl --vacuum-size=100M", False),
    ("journalctl --vacuum-size 500M", False),
    ("journalctl --vacuum-files=5", False),
    ("journalctl --vacuum-files 10", False),
    ("journalctl --flush", False),
    ("journalctl --sync", False),
    ("journalctl --relinquish-var", False),
    #
    # === UNSAFE: Combined with modification flags ===
    ("journalctl --rotate --vacuum-time=1d", False),
    ("journalctl -u nginx --rotate", False),  # safe flag + unsafe
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
