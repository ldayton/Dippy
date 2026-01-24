"""Test cases for psql."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Help/version - safe
    ("psql --help", True),
    ("psql --version", True),
    ("psql -V", True),
    # List databases - safe
    ("psql -l", True),
    ("psql --list", True),
    ("psql -l -h localhost", True),
    # Read-only SQL with -c
    ("psql -c 'SELECT * FROM users'", True),
    ("psql --command='SELECT * FROM users'", True),
    ("psql -c 'SELECT * FROM users' mydb", True),
    ("psql -d mydb -c 'SELECT * FROM users'", True),
    ("psql --dbname=mydb -c 'SELECT 1'", True),
    ("psql -h localhost -c 'SELECT 1'", True),
    ("psql -U postgres -c 'SELECT 1'", True),
    ("psql -c 'SHOW search_path'", True),
    ("psql -c 'EXPLAIN SELECT * FROM users'", True),
    # Output format options with read-only
    ("psql -A -c 'SELECT 1'", True),
    ("psql -H -c 'SELECT 1'", True),
    ("psql -t -c 'SELECT 1'", True),
    ("psql -x -c 'SELECT 1'", True),
    # Multiple -c options (all read-only)
    ("psql -c 'SELECT 1' -c 'SELECT 2'", True),
    # Write SQL - unsafe
    ("psql -c 'INSERT INTO users VALUES (1)'", False),
    ("psql -c 'UPDATE users SET name = 1'", False),
    ("psql -c 'DELETE FROM users'", False),
    ("psql -c 'DROP TABLE users'", False),
    ("psql -c 'CREATE TABLE users (id INT)'", False),
    ("psql -c 'ALTER TABLE users ADD COLUMN x INT'", False),
    ("psql -c 'TRUNCATE TABLE users'", False),
    ("psql -c 'GRANT SELECT ON users TO alice'", False),
    # PostgreSQL-specific write operations
    ("psql -c 'COPY users FROM /tmp/data.csv'", False),
    ("psql -c 'VACUUM'", False),
    ("psql -c 'CLUSTER users'", False),
    ("psql -c 'REINDEX TABLE users'", False),
    ("psql -c 'ANALYZE users'", False),
    # Multiple -c with one write - unsafe
    ("psql -c 'SELECT 1' -c 'DROP TABLE users'", False),
    # Interactive mode - unsafe
    ("psql", False),
    ("psql mydb", False),
    ("psql -U postgres mydb", False),
    ("psql -h localhost -U postgres -d mydb", False),
    # File input - unsafe (unknown content)
    ("psql -f script.sql", False),
    ("psql --file=script.sql", False),
    ("psql -f script.sql mydb", False),
    # Multiple statements in one -c - unsafe
    ("psql -c 'SELECT 1; SELECT 2'", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
