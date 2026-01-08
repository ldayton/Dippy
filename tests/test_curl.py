"""Test cases for curl."""

import pytest

from dippy.dippy import is_command_safe, parse_commands, _load_custom_configs

_load_custom_configs()

#
# ==========================================================================
# curl
# ==========================================================================
#
TESTS = [
    ("find . -name '*.py'", True),
    ("find . -exec rm {} \\;", False),
    ("find . -delete", False),
    ("sort file.txt", True),
    ("sort -o output.txt file.txt", False),
    ("sed 's/foo/bar/' file.txt", True),
    ("sed -n '1,10p' file.txt", True),
    ("sed -i 's/foo/bar/' file.txt", False),
    ("sed -i.bak 's/foo/bar/' file.txt", False),
    ("sed --in-place 's/foo/bar/' file.txt", False),
    ("awk '{print $1}' file.txt", True),
    ("awk -F: '{print $1}' /etc/passwd", True),
    ("awk -f script.awk file.txt", False),
    ("awk '{print > \"out.txt\"}' file.txt", False),
    ("awk '{system(\"rm file\")}'", False),
    # Curl - safe (GET/HEAD only)
    ("curl https://example.com", True),
    ("curl -I https://example.com", True),
    ("curl --head https://example.com", True),
    ("curl -X GET https://example.com", True),
    ("curl -X HEAD https://example.com", True),
    ("curl -X OPTIONS https://example.com", True),
    ("curl -X TRACE https://example.com", True),
    ("curl -s -o /dev/null -w '%{http_code}' https://example.com", True),
    # Curl - unsafe (POST/PUT/DELETE or data-sending)
    ("curl -X POST https://example.com", False),
    ("curl -X PUT https://example.com", False),
    ("curl -X DELETE https://example.com", False),
    ("curl --request=DELETE https://example.com", False),
    ("curl -d 'data' https://example.com", False),
    ("curl --data='foo=bar' https://example.com", False),
    ("curl -F 'file=@test.txt' https://example.com", False),
    ("curl --form 'file=@test.txt' https://example.com", False),
    ("curl -T file.txt ftp://example.com", False),
    ("curl --upload-file file.txt ftp://example.com", False),
    # Curl wrappers (from tests/dippy-test.toml)
    ("curl-wrapper.sh query foo", True),
    ("/path/to/curl-wrapper.sh get metrics", True),
    ("curl-wrapper.sh --help", True),
    ("curl-wrapper.sh -X POST data", False),
    ("curl-wrapper.sh -d 'data' https://example.com", False),
    ("curl-wrapper.sh --data=foo", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_curl(command: str, expected: bool) -> None:
    """Test command safety."""
    result = parse_commands(command)
    if result.error or not result.commands:
        actual = False
    else:
        actual = all(is_command_safe(cmd) for cmd in result.commands)
    assert actual == expected, f"Expected {expected} for: {command}"
