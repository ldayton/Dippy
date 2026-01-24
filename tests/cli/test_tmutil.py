"""Test cases for tmutil."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("tmutil help", True),
    ("tmutil help startbackup", True),
    ("tmutil version", True),
    ("tmutil destinationinfo", True),
    ("tmutil destinationinfo -X", True),
    ("tmutil isexcluded /path/to/file", True),
    ("tmutil latestbackup", True),
    ("tmutil latestbackup -m", True),
    ("tmutil listbackups", True),
    ("tmutil listbackups -m -t", True),
    ("tmutil listlocalsnapshotdates", True),
    ("tmutil listlocalsnapshotdates /", True),
    ("tmutil listlocalsnapshots /", True),
    ("tmutil machinedirectory", True),
    ("tmutil uniquesize /path/to/backup", True),
    ("tmutil verifychecksums /path/to/backup", True),
    ("tmutil compare /path1 /path2", True),
    ("tmutil compare -a snapshot_path", True),
    ("tmutil calculatedrift /path/to/machine", True),
    # Write operations - unsafe
    ("tmutil enable", False),
    ("tmutil disable", False),
    ("tmutil startbackup", False),
    ("tmutil startbackup -b", False),
    ("tmutil stopbackup", False),
    ("tmutil setdestination /Volumes/Backup", False),
    ("tmutil setdestination -a /Volumes/Backup2", False),
    ("tmutil removedestination ABC123", False),
    ("tmutil setquota ABC123 500", False),
    ("tmutil addexclusion /path/to/exclude", False),
    ("tmutil addexclusion -p /path/to/exclude", False),
    ("tmutil removeexclusion /path/to/include", False),
    ("tmutil delete -d /Volumes/Backup -t 2024-01-01", False),
    ("tmutil deleteinprogress /path/to/machine", False),
    ("tmutil deletelocalsnapshots /", False),
    ("tmutil deletelocalsnapshots 2024-01-01", False),
    ("tmutil localsnapshot", False),
    ("tmutil thinlocalsnapshots / 10000000000 1", False),
    ("tmutil restore /backup/file /destination", False),
    ("tmutil restore -v /backup/file /destination", False),
    ("tmutil inheritbackup /path/to/machine", False),
    ("tmutil associatedisk /Volumes/Mount /path/to/backup", False),
    # No arguments - unsafe
    ("tmutil", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
