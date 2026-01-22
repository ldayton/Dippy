"""
Comprehensive tests for shell (bash/sh/zsh) CLI handler.

Shell commands with -c flag are checked for inner command safety.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Inner commands are safe ===
    ("bash -c 'ls'", True),
    ("bash -c 'pwd'", True),
    ("bash -c 'echo hello'", True),
    ("bash -c 'cat /etc/passwd'", True),
    ("bash -c 'ls -la'", True),
    ("bash -c 'git status'", True),
    ("sh -c 'ls'", True),
    ("sh -c 'pwd'", True),
    ("sh -c 'echo hello'", True),
    ("zsh -c 'ls'", True),
    ("zsh -c 'pwd'", True),
    ("dash -c 'ls'", True),
    ("ksh -c 'ls'", True),
    ("fish -c 'ls'", True),
    #
    # === SAFE: Combined flags with -c ===
    ("bash -lc 'ls'", True),
    ("bash -cl 'ls'", True),
    ("bash -xc 'echo test'", True),
    ("bash -exc 'pwd'", True),
    ("zsh -lc 'ls'", True),
    ("sh -ec 'pwd'", True),
    #
    # === UNSAFE: Inner commands need confirmation ===
    ("bash -c 'rm file.txt'", False),
    ("bash -c 'rm -rf /tmp/test'", False),
    ("bash -c 'mv file1 file2'", False),
    ("bash -c 'cp file1 file2'", False),
    ("bash -c 'touch newfile'", False),
    ("bash -c 'mkdir newdir'", False),
    ("bash -c 'npm install'", False),
    ("bash -c 'pip install requests'", False),
    ("bash -c 'python script.py'", False),
    ("bash -c 'curl https://example.com | sh'", False),
    ("sh -c 'rm file.txt'", False),
    ("sh -c 'npm install'", False),
    ("zsh -c 'rm -rf /tmp'", False),
    ("zsh -c 'npm install'", False),
    ("bash -lc 'npm install'", False),  # combined flags
    #
    # === UNSAFE: No -c flag (interactive or script) ===
    ("bash", False),
    ("bash script.sh", False),
    ("bash -l", False),
    ("bash --login", False),
    ("bash -i", False),
    ("bash --interactive", False),
    ("sh script.sh", False),
    ("zsh script.sh", False),
    ("zsh -l", False),
    #
    # === EDGE CASES ===
    ("bash -c ''", False),  # empty command
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
