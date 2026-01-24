"""Test cases for sample."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (default /tmp output)
    ("sample 1234", True),
    ("sample Safari", True),
    ("sample 1234 10", True),
    ("sample 1234 10 1", True),
    ("sample -wait Safari", True),
    ("sample -mayDie 1234", True),
    ("sample -fullPaths 1234", True),
    ("sample -e 1234", True),
    ("sample -wait -mayDie Safari 10", True),
    # Safe: explicit /tmp path
    ("sample -file /tmp/out.txt 1234", True),
    ("sample -file /tmp/foo/bar.sample 1234", True),
    ("sample 1234 -file /tmp/test.txt", True),
    # Unsafe: custom file path
    ("sample -file /home/user/out.txt 1234", False),
    ("sample -file ./output.txt 1234", False),
    ("sample -file ~/samples/out.txt 1234", False),
    ("sample -file output.sample 1234", False),
    ("sample 1234 -file /var/log/sample.txt", False),
    # Edge case: no target
    ("sample", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_sample(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
