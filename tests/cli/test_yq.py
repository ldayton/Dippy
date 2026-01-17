"""Tests for yq CLI handler."""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Output to stdout ===
    ("yq", True),
    ("yq '.key'", True),
    ("yq '.key' file.yaml", True),
    ("yq -o json file.yaml", True),
    ("yq -p yaml -o json file.yaml", True),
    ("yq eval '.key' file.yaml", True),
    ("yq eval-all '.key' file.yaml", True),
    ("yq --colors '.key' file.yaml", True),
    ("yq -C '.key' file.yaml", True),
    #
    # === UNSAFE: In-place modification ===
    ("yq -i '.key = \"value\"' file.yaml", False),
    ("yq --inplace '.key = \"value\"' file.yaml", False),
    ("yq -i=true '.key = \"value\"' file.yaml", False),
    ("yq --inplace=true '.key = \"value\"' file.yaml", False),
    ("yq '.key = \"value\"' -i file.yaml", False),
    ("yq eval -i '.key = \"value\"' file.yaml", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
