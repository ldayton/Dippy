"""
Comprehensive tests for dmesg CLI handler.

Dmesg is safe for viewing kernel messages, but -c/--clear clears the ring buffer.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing kernel messages ===
    ("dmesg", True),
    ("dmesg -T", True),  # human-readable timestamps
    ("dmesg --ctime", True),
    ("dmesg -H", True),  # human readable
    ("dmesg --human", True),
    ("dmesg -L", True),  # colorize
    ("dmesg --color", True),
    ("dmesg --color=always", True),
    ("dmesg -w", True),  # follow/wait
    ("dmesg --follow", True),
    ("dmesg -l err", True),  # filter by level
    ("dmesg --level=warn,err", True),
    ("dmesg -f kern", True),  # filter by facility
    ("dmesg --facility=kern,daemon", True),
    ("dmesg -n 8", True),  # just sets console level for display
    ("dmesg --console-level=8", True),
    ("dmesg -s 16384", True),  # buffer size
    ("dmesg --buffer-size=16384", True),
    ("dmesg -x", True),  # decode facility/level
    ("dmesg --decode", True),
    ("dmesg -r", True),  # raw output
    ("dmesg --raw", True),
    ("dmesg -t", True),  # no timestamps
    ("dmesg --notime", True),
    ("dmesg -k", True),  # kernel messages
    ("dmesg --kernel", True),
    ("dmesg -u", True),  # userspace messages
    ("dmesg --userspace", True),
    ("dmesg -e", True),  # use time since epoch
    ("dmesg --reltime", True),
    ("dmesg -P", True),  # nopager
    ("dmesg --nopager", True),
    ("dmesg --since '1 hour ago'", True),
    ("dmesg --until now", True),
    ("dmesg | grep error", True),  # piping is handled elsewhere
    ("dmesg -T -H", True),  # multiple safe flags
    ("dmesg -TH", True),  # combined flags
    ("dmesg -THw", True),  # combined with follow
    #
    # === UNSAFE: Modifying ring buffer ===
    #
    ("dmesg -c", False),  # clear after reading
    ("dmesg --clear", False),
    ("dmesg -C", False),  # clear without reading
    ("dmesg --console-off", False),
    ("dmesg -D", False),  # disable console logging
    ("dmesg --console-on", False),
    ("dmesg -E", False),  # enable console logging
    ("dmesg --console-level", False),  # this modifies console level
    ("dmesg -cT", False),  # combined with clear
    ("dmesg -Tc", False),  # clear flag anywhere in combined
    ("dmesg -TcH", False),
    ("dmesg -THc", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
