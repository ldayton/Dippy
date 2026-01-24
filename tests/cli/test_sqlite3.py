"""Test cases for sqlite3."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Help/version - safe
    ("sqlite3 --help", True),
    ("sqlite3 -help", True),
    ("sqlite3 -version", True),
    # Read-only mode - always safe
    ("sqlite3 -readonly mydb.db", True),
    ("sqlite3 -readonly mydb.db 'DROP TABLE users'", True),  # readonly flag wins
    # Safe mode - always safe
    ("sqlite3 -safe mydb.db", True),
    ("sqlite3 -safe mydb.db 'DROP TABLE users'", True),  # safe flag wins
    # Read-only SQL
    ("sqlite3 mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 mydb.db 'SELECT * FROM users;'", True),
    ("sqlite3 mydb.db 'EXPLAIN SELECT * FROM users'", True),
    ("sqlite3 :memory: 'SELECT 1'", True),
    # Read-only with output options
    ("sqlite3 -json mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 -csv mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 -table mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 -line mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 -column mydb.db 'SELECT * FROM users'", True),
    ("sqlite3 -header mydb.db 'SELECT * FROM users'", True),
    # Read-only with -cmd
    ("sqlite3 -cmd 'SELECT 1' mydb.db", True),
    # Write SQL - unsafe
    ("sqlite3 mydb.db 'INSERT INTO users VALUES (1)'", False),
    ("sqlite3 mydb.db 'UPDATE users SET name = 1'", False),
    ("sqlite3 mydb.db 'DELETE FROM users'", False),
    ("sqlite3 mydb.db 'DROP TABLE users'", False),
    ("sqlite3 mydb.db 'CREATE TABLE users (id INT)'", False),
    ("sqlite3 mydb.db 'ALTER TABLE users ADD COLUMN x INT'", False),
    # SQLite-specific write operations
    ("sqlite3 mydb.db 'PRAGMA foreign_keys = ON'", False),
    ("sqlite3 mydb.db 'ATTACH DATABASE other.db AS other'", False),
    ("sqlite3 mydb.db 'DETACH DATABASE other'", False),
    ("sqlite3 mydb.db 'VACUUM'", False),
    ("sqlite3 mydb.db 'REINDEX'", False),
    ("sqlite3 mydb.db 'ANALYZE'", False),
    # Write with -cmd
    ("sqlite3 -cmd 'DROP TABLE users' mydb.db", False),
    # Interactive mode - unsafe (could do anything)
    ("sqlite3", False),
    ("sqlite3 mydb.db", False),
    ("sqlite3 -json mydb.db", False),
    # Multiple SQL statements - unsafe (unknown)
    ("sqlite3 mydb.db 'SELECT 1; SELECT 2'", False),
    # File input - unsafe (unknown content)
    ("sqlite3 mydb.db < script.sql", False),
    ("sqlite3 -init script.sql mydb.db", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
