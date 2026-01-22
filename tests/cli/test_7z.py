"""
Comprehensive tests for 7z archive CLI handlers.

Tests cover unzip, 7z, 7za, 7zr, 7zz commands.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    #
    # === UNZIP ===
    #
    # --- List operations (safe) ---
    ("unzip -l archive.zip", True),
    ("unzip -l foo.zip bar.zip", True),
    ("unzip -lv archive.zip", True),
    ("unzip -lq archive.zip", True),
    ("unzip -v archive.zip", True),  # verbose list / version info
    #
    # --- Test archive (safe) ---
    ("unzip -t archive.zip", True),
    ("unzip -tq archive.zip", True),
    #
    # --- Zipinfo mode (safe) ---
    ("unzip -Z archive.zip", True),
    ("unzip -Z -1 archive.zip", True),
    ("unzip -Zl archive.zip", True),
    #
    # --- Archive comment only (safe) ---
    ("unzip -z archive.zip", True),
    #
    # --- Extract operations (unsafe) ---
    ("unzip archive.zip", False),
    ("unzip foo.zip bar.zip", False),
    ("unzip archive.zip -d /tmp", False),
    ("unzip -d /tmp archive.zip", False),
    ("unzip -o archive.zip", False),  # overwrite without prompt
    ("unzip -n archive.zip", False),  # never overwrite (still extracts)
    ("unzip -f archive.zip", False),  # freshen existing
    ("unzip -u archive.zip", False),  # update
    ("unzip -p archive.zip", False),  # pipe to stdout
    ("unzip -c archive.zip", False),  # extract to stdout with names
    ("unzip -j archive.zip", False),  # junk paths
    ("unzip archive.zip file.txt", False),  # extract specific file
    ("unzip archive.zip -x excluded.txt", False),  # extract with exclusion
    ("unzip -q archive.zip", False),  # quiet extract
    ("unzip -qq archive.zip", False),  # quieter extract
    #
    # --- Combined flags ---
    ("unzip -oq archive.zip", False),  # overwrite quiet
    ("unzip -tl archive.zip", True),  # test + list (both safe)
    ("unzip -lv archive.zip", True),  # list verbose
    #
    # --- Edge cases ---
    ("unzip -T archive.zip", False),  # timestamp (modifies archive)
    ("unzip -a archive.zip", False),  # auto-convert text (extracts)
    ("unzip --help", True),
    ("unzip -h", True),
    ("unzip -hh", True),  # extended help
    #
    # === 7Z / 7ZA / 7ZR / 7ZZ ===
    #
    # --- List operations (safe) ---
    ("7z l archive.7z", True),
    ("7za l archive.7z", True),
    ("7zr l archive.7z", True),
    ("7zz l archive.7z", True),
    ("7z l -slt archive.7z", True),  # technical listing
    ("7zz l -slt archive.7z", True),
    #
    # --- Test archive (safe) ---
    ("7z t archive.7z", True),
    ("7za t archive.7z", True),
    ("7zz t archive.7z", True),
    ("7z t -p archive.7z", True),  # test with password prompt
    ("7zz t -scrcSHA256 archive.7z", True),  # test with specific hash
    #
    # --- Hash (safe) ---
    ("7z h archive.7z", True),
    ("7z h -scrcSHA256 archive.7z", True),
    ("7zz h file.txt", True),
    ("7zz h -scrcSHA256 file.txt", True),
    ("7zz h -scrcCRC32 file.txt", True),
    ("7zz h -scrc* file.txt", True),  # all hashes
    #
    # --- Benchmark (safe) ---
    ("7z b", True),
    ("7z b -mmt=4", True),
    ("7zz b", True),
    ("7zz b -mmt=8", True),
    ("7zz b -mm=LZMA2", True),  # benchmark specific method
    #
    # --- Info (safe) ---
    ("7z i", True),
    ("7zz i", True),
    #
    # --- Add/create archive (unsafe) ---
    ("7z a archive.7z file.txt", False),
    ("7za a archive.7z folder/", False),
    ("7zz a archive.7z file.txt", False),
    ("7z a -tzip archive.zip file.txt", False),
    ("7z a -p archive.7z file.txt", False),  # with password
    ("7z a -mx=9 archive.7z file.txt", False),  # max compression
    ("7z a -mhe=on archive.7z file.txt", False),  # encrypt headers
    ("7zz a -t7z -mx=9 -mfb=64 archive.7z folder/", False),  # complex compression
    ("7zz a -sdel archive.7z file.txt", False),  # delete after compression
    ("7zz a -v100m archive.7z largefile", False),  # create volumes
    #
    # --- Extract operations (unsafe) ---
    ("7z x archive.7z", False),
    ("7za x archive.7z", False),
    ("7zr x archive.7z", False),
    ("7zz x archive.7z", False),
    ("7z x archive.7z -o/tmp", False),
    ("7z x -p archive.7z", False),  # password
    ("7z x -y archive.7z", False),  # assume yes
    ("7z e archive.7z", False),  # extract flat
    ("7z e archive.7z -o/tmp", False),
    ("7zz e archive.7z", False),
    ("7zz x -aoa archive.7z", False),  # overwrite all
    ("7zz x -aos archive.7z", False),  # skip existing
    ("7zz x -so archive.7z", False),  # extract to stdout
    #
    # --- Delete from archive (unsafe) ---
    ("7z d archive.7z file.txt", False),
    ("7zz d archive.7z *.bak", False),
    #
    # --- Update archive (unsafe) ---
    ("7z u archive.7z file.txt", False),
    ("7zz u archive.7z newfile.txt", False),
    #
    # --- Rename in archive (unsafe) ---
    ("7z rn archive.7z old.txt new.txt", False),
    ("7zz rn archive.7z oldname newname", False),
    #
    # --- Help (safe) ---
    ("7z --help", True),
    ("7z -h", True),
    ("7z", True),  # shows help
    ("7zz --help", True),
    ("7zz -h", True),
    ("7zz", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
