"""Test cases for wget command safety checks."""

import pytest

from dippy.dippy import is_command_safe, parse_commands, _load_custom_configs

_load_custom_configs()

#
# ==========================================================================
# wget
# ==========================================================================
#
# wget downloads files to disk by default, so most operations are unsafe.
# Only --spider mode (check availability without downloading) is safe.
#
TESTS = [
    # Safe - spider mode (no download, just check)
    ("wget --spider https://example.com", True),
    ("wget --spider -q https://example.com", True),
    ("wget --spider --quiet https://example.com", True),
    ("wget -q --spider https://example.com", True),
    ("wget --spider -T 10 https://example.com", True),
    ("wget --spider --timeout=10 https://example.com", True),
    # Safe - help/version
    ("wget --help", True),
    ("wget -h", True),
    ("wget --version", True),
    # Unsafe - default download (writes to disk)
    ("wget https://example.com", False),
    ("wget https://example.com/file.tar.gz", False),
    ("wget -q https://example.com", False),
    ("wget --quiet https://example.com", False),
    # Unsafe - explicit output file
    ("wget -O file.txt https://example.com", False),
    ("wget --output-document=file.txt https://example.com", False),
    ("wget -O - https://example.com", False),  # stdout is still a download
    # Unsafe - directory prefix
    ("wget -P /tmp https://example.com", False),
    ("wget --directory-prefix=/tmp https://example.com", False),
    # Unsafe - recursive download
    ("wget -r https://example.com", False),
    ("wget --recursive https://example.com", False),
    ("wget -m https://example.com", False),
    ("wget --mirror https://example.com", False),
    # Unsafe - continue/resume download
    ("wget -c https://example.com/file.iso", False),
    ("wget --continue https://example.com/file.iso", False),
    # Unsafe - input file (bulk downloads)
    ("wget -i urls.txt", False),
    ("wget --input-file=urls.txt", False),
    # Unsafe - POST data
    ("wget --post-data='foo=bar' https://example.com", False),
    ("wget --post-file=data.txt https://example.com", False),
    # Unsafe - custom method with body
    ("wget --method=POST --body-data='test' https://example.com", False),
    ("wget --method=PUT --body-file=data.json https://example.com", False),
    # Unsafe - timestamping (still downloads)
    ("wget -N https://example.com/file.txt", False),
    ("wget --timestamping https://example.com/file.txt", False),
    # Unsafe - page requisites
    ("wget -p https://example.com/page.html", False),
    ("wget --page-requisites https://example.com/page.html", False),
    # Unsafe - convert links (implies download)
    ("wget -k https://example.com", False),
    ("wget --convert-links https://example.com", False),
    # Unsafe - background mode
    ("wget -b https://example.com/large.iso", False),
    ("wget --background https://example.com/large.iso", False),
    # Unsafe - WARC output
    ("wget --warc-file=archive https://example.com", False),
    # Unsafe - save cookies (writes file)
    ("wget --save-cookies=cookies.txt https://example.com", False),
    # Combined flags with spider - safe
    ("wget -q --spider -T 5 https://example.com", True),
    ("wget --spider --no-check-certificate https://example.com", True),
    ("wget --spider --user-agent='Mozilla' https://example.com", True),
    # Spider with multiple URLs - safe
    ("wget --spider https://example.com https://example.org", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_wget(command: str, expected: bool) -> None:
    """Test wget command safety."""
    result = parse_commands(command)
    assert result.commands, f"Failed to parse: {command}"
    assert len(result.commands) == 1
    actual = is_command_safe(result.commands[0])
    assert actual == expected, f"Expected {expected} for: {command}"
