"""Test cases for hdiutil."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("hdiutil help", True),
    ("hdiutil info", True),
    ("hdiutil info -plist", True),
    ("hdiutil verify image.dmg", True),
    ("hdiutil verify -verbose image.dmg", True),
    ("hdiutil checksum -type SHA256 image.dmg", True),
    ("hdiutil imageinfo image.dmg", True),
    ("hdiutil imageinfo -plist image.dmg", True),
    ("hdiutil isencrypted image.dmg", True),
    ("hdiutil plugins", True),
    ("hdiutil pmap image.dmg", True),
    # Write/mount operations - unsafe
    ("hdiutil attach image.dmg", False),
    ("hdiutil attach -readonly image.dmg", False),
    ("hdiutil detach /dev/disk2", False),
    ("hdiutil eject /dev/disk2", False),
    ("hdiutil mount image.dmg", False),
    ("hdiutil mountvol /dev/disk2s1", False),
    ("hdiutil unmount /Volumes/MyDisk", False),
    ("hdiutil create -size 100m output.dmg", False),
    ("hdiutil create -srcfolder /path output.dmg", False),
    ("hdiutil convert -format UDZO -o output.dmg input.dmg", False),
    ("hdiutil compact sparse.sparseimage", False),
    ("hdiutil resize -size 200m image.dmg", False),
    ("hdiutil burn image.dmg", False),
    ("hdiutil makehybrid -o output.iso /path", False),
    ("hdiutil chpass image.dmg", False),
    ("hdiutil erasekeys image.dmg", False),
    ("hdiutil segment -segmentSize 100m -o output image.dmg", False),
    # No arguments - unsafe
    ("hdiutil", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
