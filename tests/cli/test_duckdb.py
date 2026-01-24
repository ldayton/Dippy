"""Test cases for duckdb."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Help/version - safe
    ("duckdb --help", True),
    ("duckdb -help", True),
    ("duckdb -version", True),
    # Read-only mode - always safe
    ("duckdb -readonly mydb.db", True),
    ("duckdb -readonly mydb.db 'DROP TABLE users'", True),  # readonly flag wins
    # Safe mode - always safe
    ("duckdb -safe mydb.db", True),
    ("duckdb -safe mydb.db 'DROP TABLE users'", True),  # safe flag wins
    # Read-only SQL (positional)
    ("duckdb mydb.db 'SELECT * FROM users'", True),
    ("duckdb mydb.db 'SELECT * FROM users;'", True),
    ("duckdb mydb.db 'EXPLAIN SELECT * FROM users'", True),
    ("duckdb :memory: 'SELECT 1'", True),
    # Read-only SQL with -c/-s
    ("duckdb -c 'SELECT 1'", True),
    ("duckdb -s 'SELECT 1'", True),
    ("duckdb mydb.db -c 'SELECT * FROM users'", True),
    # Read-only with output options
    ("duckdb -json mydb.db 'SELECT * FROM users'", True),
    ("duckdb -csv mydb.db 'SELECT * FROM users'", True),
    ("duckdb -table mydb.db 'SELECT * FROM users'", True),
    ("duckdb -line mydb.db 'SELECT * FROM users'", True),
    ("duckdb -column mydb.db 'SELECT * FROM users'", True),
    # Read-only with -cmd
    ("duckdb -cmd 'SELECT 1' mydb.db", True),
    # Write SQL - unsafe
    ("duckdb mydb.db 'INSERT INTO users VALUES (1)'", False),
    ("duckdb mydb.db 'UPDATE users SET name = 1'", False),
    ("duckdb mydb.db 'DELETE FROM users'", False),
    ("duckdb mydb.db 'DROP TABLE users'", False),
    ("duckdb mydb.db 'CREATE TABLE users (id INT)'", False),
    ("duckdb mydb.db 'ALTER TABLE users ADD COLUMN x INT'", False),
    ("duckdb -c 'DROP TABLE users'", False),
    ("duckdb -s 'INSERT INTO t VALUES (1)'", False),
    # DuckDB-specific write operations
    ("duckdb mydb.db 'PRAGMA enable_progress_bar'", False),
    ("duckdb mydb.db 'ATTACH DATABASE other.db'", False),
    ("duckdb mydb.db 'DETACH DATABASE other'", False),
    ("duckdb mydb.db 'VACUUM'", False),
    ("duckdb mydb.db 'COPY users TO /tmp/out.csv'", False),
    ("duckdb mydb.db 'EXPORT DATABASE /tmp/backup'", False),
    ("duckdb mydb.db 'IMPORT DATABASE /tmp/backup'", False),
    # Write with -cmd
    ("duckdb -cmd 'DROP TABLE users' mydb.db", False),
    # Interactive mode - unsafe
    ("duckdb", False),
    ("duckdb mydb.db", False),
    ("duckdb -json mydb.db", False),
    # Multiple SQL statements - unsafe
    ("duckdb mydb.db 'SELECT 1; SELECT 2'", False),
    # File input - unsafe
    ("duckdb -init script.sql mydb.db", False),
    ("duckdb -f script.sql", False),
    # Options with arguments - should parse correctly
    ("duckdb -separator '|' mydb.db 'SELECT 1'", True),
    # -newline takes ONE argument (SEP)
    ("duckdb -newline '\\n' mydb.db 'SELECT 1'", True),
    # -nullvalue takes ONE argument (TEXT)
    ("duckdb -nullvalue NULL mydb.db 'SELECT 1'", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
