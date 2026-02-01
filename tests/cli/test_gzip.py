"""Test cases for gzip/gunzip commands."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # === SAFE: stdout mode (no file modification) ===
    ("gunzip -c file.gz", True),
    ("gunzip --stdout file.gz", True),
    ("gzip -c file.txt", True),
    ("gzip --stdout file.txt", True),
    ("gunzip -c -f file.gz", True),  # -c makes it safe regardless of -f
    #
    # === SAFE: list mode (read-only) ===
    ("gunzip -l file.gz", True),
    ("gunzip --list file.gz", True),
    ("gzip -l file.gz", True),
    ("gzip --list file.gz", True),
    ("gunzip -lv file.gz", True),  # verbose list
    #
    # === SAFE: test mode (read-only) ===
    ("gunzip -t file.gz", True),
    ("gunzip --test file.gz", True),
    ("gzip -t file.gz", True),
    ("gzip --test file.gz", True),
    ("gunzip -tv file.gz", True),  # verbose test
    #
    # === SAFE: help and version ===
    ("gunzip --help", True),
    ("gunzip --version", True),
    ("gzip --help", True),
    ("gzip --version", True),
    #
    # === SAFE: decompress flag with safe flags ===
    ("gzip -dc file.gz", True),  # decompress to stdout
    ("gzip --decompress --stdout file.gz", True),
    ("gzip -dt file.gz", True),  # decompress test
    #
    # === UNSAFE: default decompression (in-place, deletes .gz) ===
    ("gunzip file.gz", False),
    ("gunzip file1.gz file2.gz", False),
    ("gunzip -f file.gz", False),  # force still modifies
    ("gunzip --force file.gz", False),
    ("gunzip -v file.gz", False),  # verbose still modifies
    ("gunzip -k file.gz", False),  # keep original, but still writes
    ("gunzip --keep file.gz", False),
    #
    # === UNSAFE: default compression (in-place, deletes original) ===
    ("gzip file.txt", False),
    ("gzip file1.txt file2.txt", False),
    ("gzip -f file.txt", False),
    ("gzip --force file.txt", False),
    ("gzip -9 file.txt", False),  # compression level still modifies
    ("gzip -k file.txt", False),  # keep but still writes
    ("gzip --keep file.txt", False),
    #
    # === UNSAFE: decompress mode without stdout ===
    ("gzip -d file.gz", False),
    ("gzip --decompress file.gz", False),
    #
    # === UNSAFE: recursive operations ===
    ("gunzip -r dir/", False),
    ("gunzip --recursive dir/", False),
    ("gzip -r dir/", False),
    ("gzip --recursive dir/", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_gzip(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
