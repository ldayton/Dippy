"""Test cases for diskutil."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("diskutil list", True),
    ("diskutil list -plist", True),
    ("diskutil list internal", True),
    ("diskutil list external", True),
    ("diskutil list disk0", True),
    ("diskutil info disk0", True),
    ("diskutil info -plist disk0", True),
    ("diskutil info --all", True),
    ("diskutil information disk0s1", True),
    ("diskutil activity", True),
    ("diskutil listFilesystems", True),
    ("diskutil listFilesystems -plist", True),
    # Write operations - unsafe
    ("diskutil mount disk0s1", False),
    ("diskutil mountDisk disk0", False),
    ("diskutil unmount disk0s1", False),
    ("diskutil unmountDisk disk0", False),
    ("diskutil eject disk1", False),
    ("diskutil rename disk0s1 NewName", False),
    ("diskutil eraseDisk APFS MyDisk disk1", False),
    ("diskutil partitionDisk disk1 1 GPT APFS MyDisk 0b", False),
    ("diskutil secureErase 0 disk1", False),
    ("diskutil zeroDisk disk1", False),
    ("diskutil appleRAID list", False),
    ("diskutil coreStorage list", False),
    ("diskutil apfs list", False),
    # No arguments - unsafe
    ("diskutil", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
