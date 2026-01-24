"""Test cases for sqlcmd (go-sqlcmd)."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Help/version - safe
    ("sqlcmd --help", True),
    ("sqlcmd -h", True),
    ("sqlcmd --version", True),
    ("sqlcmd query --help", True),
    # Config view - safe
    ("sqlcmd config view", True),
    ("sqlcmd config cs", True),
    # Read-only queries
    ("sqlcmd query 'SELECT @@VERSION'", True),
    ("sqlcmd query 'SELECT * FROM users'", True),
    ("sqlcmd query --query 'SELECT 1'", True),
    ("sqlcmd query -q 'SELECT 1'", True),
    ("sqlcmd query --text 'SELECT 1'", True),
    ("sqlcmd query -t 'SELECT 1'", True),
    ("sqlcmd query 'SELECT 1' --database master", True),
    ("sqlcmd query -d master 'SELECT 1'", True),
    ("sqlcmd query 'EXPLAIN SELECT * FROM users'", True),
    # Write queries - unsafe
    ("sqlcmd query 'INSERT INTO users VALUES (1)'", False),
    ("sqlcmd query 'UPDATE users SET name = 1'", False),
    ("sqlcmd query 'DELETE FROM users'", False),
    ("sqlcmd query 'DROP TABLE users'", False),
    ("sqlcmd query 'CREATE TABLE users (id INT)'", False),
    ("sqlcmd query 'ALTER TABLE users ADD x INT'", False),
    ("sqlcmd query 'TRUNCATE TABLE users'", False),
    ("sqlcmd query --query 'DROP TABLE users'", False),
    # Create/delete operations - unsafe
    ("sqlcmd create mssql", False),
    ("sqlcmd create mssql --accept-eula", False),
    ("sqlcmd install mssql", False),
    ("sqlcmd delete", False),
    # Start/stop - unsafe (modifies container state)
    ("sqlcmd start", False),
    ("sqlcmd stop", False),
    # Open tools - safe (just opens external app)
    ("sqlcmd open ads", True),
    # No subcommand - unsafe
    ("sqlcmd", False),
    # Multiple statements - unsafe
    ("sqlcmd query 'SELECT 1; SELECT 2'", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
