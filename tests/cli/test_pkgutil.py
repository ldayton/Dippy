"""Test cases for pkgutil (macOS package utility)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (query commands)
    ("pkgutil --packages", True),
    ("pkgutil --pkgs", True),
    ("pkgutil --pkgs-plist", True),
    ("pkgutil --pkgs=com.apple.*", True),
    ("pkgutil --files com.apple.pkg.Safari", True),
    ("pkgutil --export-plist com.apple.pkg.Safari", True),
    ("pkgutil --pkg-info com.apple.pkg.Safari", True),
    ("pkgutil --pkg-info-plist com.apple.pkg.Safari", True),
    ("pkgutil --pkg-groups com.apple.pkg.Safari", True),
    ("pkgutil --groups", True),
    ("pkgutil --groups-plist", True),
    ("pkgutil --group-pkgs com.apple.base", True),
    ("pkgutil --file-info /usr/bin/zip", True),
    ("pkgutil --file-info-plist /usr/bin/zip", True),
    ("pkgutil --payload-files package.pkg", True),
    ("pkgutil --check-signature package.pkg", True),
    ("pkgutil --help", True),
    ("pkgutil -h", True),
    # Unsafe operations (modify/create)
    ("pkgutil --forget com.example.pkg", False),
    ("pkgutil --learn /path/to/file --edit-pkg com.example.pkg", False),
    ("pkgutil --expand package.pkg /tmp/expanded", False),
    ("pkgutil --flatten /tmp/expanded package.pkg", False),
    ("pkgutil --bom package.pkg", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_pkgutil(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
