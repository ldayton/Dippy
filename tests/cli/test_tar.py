"""
Comprehensive tests for tar CLI handler.

Tar with -t/--list is safe, but -c (create) and -x (extract) need confirmation.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Listing archive contents ===
    ("tar -t -f archive.tar", True),
    ("tar -tf archive.tar", True),
    ("tar tf archive.tar", True),  # old-style no dash
    ("tar --list -f archive.tar", True),
    ("tar -tvf archive.tar", True),  # verbose
    ("tar tvf archive.tar", True),  # old-style
    ("tar -tvzf archive.tar.gz", True),  # gzip
    ("tar tvzf archive.tar.gz", True),  # old-style
    ("tar -tvjf archive.tar.bz2", True),  # bzip2
    ("tar tvjf archive.tar.bz2", True),  # old-style
    ("tar -tvJf archive.tar.xz", True),  # xz
    ("tar -t --file=archive.tar", True),
    ("tar -ztf archive.tar.gz", True),  # z before t
    ("tar ztf archive.tar.gz", True),  # old-style
    ("tar -tf archive.tar file.txt", True),  # specific file
    ("tar -tf archive.tar --wildcards '*.txt'", True),
    #
    # === UNSAFE: Creating archives ===
    ("tar -c -f archive.tar file.txt", False),
    ("tar -cf archive.tar file.txt", False),
    ("tar cf archive.tar file.txt", False),  # old-style
    ("tar --create -f archive.tar file.txt", False),
    ("tar -cvf archive.tar file.txt", False),  # verbose
    ("tar cvf archive.tar file.txt", False),  # old-style
    ("tar -czf archive.tar.gz file.txt", False),  # gzip
    ("tar czf archive.tar.gz file.txt", False),  # old-style
    ("tar -cjf archive.tar.bz2 file.txt", False),  # bzip2
    ("tar cjf archive.tar.bz2 file.txt", False),  # old-style
    ("tar -cJf archive.tar.xz file.txt", False),  # xz
    ("tar -caf archive.tar.gz file.txt", False),  # auto-compress
    ("tar --create --file=archive.tar file.txt", False),
    ("tar -C /path -cf archive.tar .", False),  # with -C
    #
    # === UNSAFE: Extracting archives ===
    ("tar -x -f archive.tar", False),
    ("tar -xf archive.tar", False),
    ("tar xf archive.tar", False),  # old-style
    ("tar --extract -f archive.tar", False),
    ("tar -xvf archive.tar", False),  # verbose
    ("tar xvf archive.tar", False),  # old-style
    ("tar -xzf archive.tar.gz", False),  # gzip
    ("tar xzf archive.tar.gz", False),  # old-style
    ("tar -xjf archive.tar.bz2", False),  # bzip2
    ("tar xjf archive.tar.bz2", False),  # old-style
    ("tar -xJf archive.tar.xz", False),  # xz
    ("tar -xf archive.tar -C /path", False),  # extract to dir
    ("tar -xf archive.tar --directory=/path", False),
    ("tar --extract --file=archive.tar", False),
    ("tar -xf archive.tar file.txt", False),  # specific file
    ("tar -xf archive.tar --wildcards '*.txt'", False),  # pattern
    #
    # === UNSAFE: Update/append ===
    ("tar -r -f archive.tar file.txt", False),  # append
    ("tar rf archive.tar file.txt", False),  # old-style
    ("tar -u -f archive.tar file.txt", False),  # update
    ("tar uf archive.tar file.txt", False),  # old-style
    ("tar --append -f archive.tar file.txt", False),
    ("tar --update -f archive.tar file.txt", False),
    #
    # === UNSAFE: Delete from archive ===
    ("tar --delete -f archive.tar file.txt", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
