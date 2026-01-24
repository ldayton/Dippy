"""Test cases for mysql."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Help/version - safe
    ("mysql --help", True),
    ("mysql -?", True),
    ("mysql --version", True),
    ("mysql -V", True),
    # Read-only SQL with -e
    ("mysql -e 'SELECT * FROM users'", True),
    ("mysql --execute='SELECT * FROM users'", True),
    ("mysql -e 'SELECT * FROM users' mydb", True),
    ("mysql -D mydb -e 'SELECT * FROM users'", True),
    ("mysql --database=mydb -e 'SELECT 1'", True),
    ("mysql -h localhost -e 'SELECT 1'", True),
    ("mysql -u root -e 'SELECT 1'", True),
    ("mysql -e 'SHOW DATABASES'", True),
    ("mysql -e 'SHOW TABLES'", True),
    ("mysql -e 'DESCRIBE users'", True),
    ("mysql -e 'EXPLAIN SELECT * FROM users'", True),
    # Output format options with read-only
    ("mysql -B -e 'SELECT 1'", True),
    ("mysql --batch -e 'SELECT 1'", True),
    ("mysql -H -e 'SELECT 1'", True),
    ("mysql --html -e 'SELECT 1'", True),
    ("mysql -X -e 'SELECT 1'", True),
    ("mysql --xml -e 'SELECT 1'", True),
    ("mysql -N -e 'SELECT 1'", True),
    # Write SQL - unsafe
    ("mysql -e 'INSERT INTO users VALUES (1)'", False),
    ("mysql -e 'UPDATE users SET name = 1'", False),
    ("mysql -e 'DELETE FROM users'", False),
    ("mysql -e 'DROP TABLE users'", False),
    ("mysql -e 'CREATE TABLE users (id INT)'", False),
    ("mysql -e 'ALTER TABLE users ADD COLUMN x INT'", False),
    ("mysql -e 'TRUNCATE TABLE users'", False),
    ("mysql -e 'GRANT SELECT ON db.* TO user'", False),
    # Interactive mode - unsafe
    ("mysql", False),
    ("mysql mydb", False),
    ("mysql -u root mydb", False),
    ("mysql -h localhost -u root -p mydb", False),
    # Multiple statements - unsafe
    ("mysql -e 'SELECT 1; SELECT 2'", False),
    # LOAD DATA - unsafe (reads files into tables)
    ("mysql -e 'LOAD DATA INFILE \"/tmp/data.csv\" INTO TABLE users'", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
