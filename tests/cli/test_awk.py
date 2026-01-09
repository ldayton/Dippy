"""
Comprehensive tests for awk CLI handler.

Tests cover awk, gawk, mawk, nawk commands.
Awk is safe for text processing but can execute shell commands.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    #
    # === BASIC TEXT PROCESSING (safe) ===
    #
    # --- Print columns ---
    ("awk '{print $1}' file.txt", True),
    ("awk '{print $1, $2}' file.txt", True),
    ("awk '{print $NF}' file.txt", True),  # last column
    ("awk '{print $0}' file.txt", True),  # entire line
    ("gawk '{print $1}' file.txt", True),
    ("mawk '{print $1}' file.txt", True),
    ("nawk '{print $1}' file.txt", True),
    #
    # --- Field separator ---
    ("awk -F, '{print $1}' file.txt", True),
    ("awk -F ',' '{print $1}' file.txt", True),
    ("awk -F: '{print $1}' /etc/passwd", True),
    ("awk -F '\\t' '{print $1}' file.txt", True),
    ("gawk --field-separator=',' '{print $1}' file.txt", True),
    #
    # --- Pattern matching ---
    ("awk '/pattern/ {print}' file.txt", True),
    ("awk '/foo/ {print $1}' file.txt", True),
    ("awk '$1 == \"foo\" {print}' file.txt", True),
    ("awk '$1 ~ /pattern/ {print}' file.txt", True),
    ("awk 'NR > 1 {print}' file.txt", True),  # skip header
    ("awk 'NR == 1 || /pattern/' file.txt", True),
    #
    # --- BEGIN/END blocks ---
    ("awk 'BEGIN {print \"header\"} {print}' file.txt", True),
    ("awk '{sum += $1} END {print sum}' file.txt", True),
    ("awk 'BEGIN {FS=\":\"} {print $1}' file.txt", True),
    ("awk 'BEGIN {OFS=\",\"} {print $1,$2}' file.txt", True),
    #
    # --- Variables ---
    ("awk -v var=value '{print var, $1}' file.txt", True),
    ("awk -v n=10 'NR <= n' file.txt", True),
    ("gawk -v OFS='\\t' '{print $1,$2}' file.txt", True),
    #
    # --- String functions ---
    ("awk '{print length($1)}' file.txt", True),
    ("awk '{print substr($1, 1, 3)}' file.txt", True),
    ("awk '{gsub(/foo/, \"bar\"); print}' file.txt", True),
    ("awk '{print tolower($1)}' file.txt", True),
    ("awk '{print toupper($1)}' file.txt", True),
    #
    # --- Math functions ---
    ("awk '{print int($1)}' file.txt", True),
    ("awk '{print sqrt($1)}' file.txt", True),
    ("awk 'BEGIN {print sin(0.5)}'", True),
    #
    # --- Aggregation ---
    ("awk '{s+=$1} END {print s}' file.txt", True),
    ("awk '{s+=$1; n++} END {print s/n}' file.txt", True),  # average
    (
        "awk 'NR==1 {min=max=$1} {if($1<min)min=$1;if($1>max)max=$1} END{print min,max}' file.txt",
        True,
    ),
    #
    # --- Conditionals ---
    ("awk '{if ($1 > 10) print}' file.txt", True),
    ("awk '$1 > 10 {print}' file.txt", True),
    ('awk \'{print ($1 > 0 ? "positive" : "non-positive")}\' file.txt', True),
    #
    # --- Multiple input files ---
    ("awk '{print}' file1.txt file2.txt", True),
    ("awk 'FNR==1 {print FILENAME}' *.txt", True),
    #
    # --- Reading from stdin (typically via pipe) ---
    ("awk '{print $1}'", True),  # reads stdin
    ("awk 'NR==1'", True),
    #
    # === UNSAFE: SCRIPT FILE (-f flag) ===
    #
    ("awk -f script.awk file.txt", False),
    ("gawk -f script.awk file.txt", False),
    ("awk -f /path/to/script.awk data.txt", False),
    ("awk -fscript.awk file.txt", False),  # -f without space
    ("gawk --file=script.awk file.txt", False),
    ("gawk --file script.awk file.txt", False),
    #
    # === UNSAFE: OUTPUT REDIRECTION ===
    #
    # --- Simple file redirection ---
    ("awk '{print > \"output.txt\"}' file.txt", False),
    ("awk '{print >> \"output.txt\"}' file.txt", False),
    ("awk '{print $1 > \"out.txt\"}' file.txt", False),
    ('awk \'BEGIN {print "test" > "file.txt"}\'', False),
    #
    # --- Dynamic file redirection ---
    ("awk '{print > $1\".txt\"}' file.txt", False),
    ("awk '{print >> (\"log_\" NR)}' file.txt", False),
    #
    # === UNSAFE: PIPE OUTPUT ===
    #
    ("awk '{print | \"sort\"}' file.txt", False),
    ("awk '{print | \"mail user@example.com\"}' file.txt", False),
    ("awk '{print $1 | \"wc -l\"}' file.txt", False),
    #
    # === UNSAFE: SYSTEM() CALLS ===
    #
    ("awk '{system(\"ls\")}' file.txt", False),
    ("awk 'BEGIN {system(\"rm -rf /\")}'", False),
    ("awk '{system(\"echo \" $1)}' file.txt", False),
    ("gawk '{system(\"date\")}' file.txt", False),
    #
    # === EDGE CASES ===
    #
    # --- Comparison operators with > that are NOT redirects ---
    ("awk '$1 > 10' file.txt", True),  # Comparison, not redirect
    ("awk '{if ($1 > 10) print}' file.txt", True),  # Comparison in condition
    ("awk 'NR > 5' file.txt", True),  # Comparison, not redirect
    #
    # --- Print to stderr (special case, generally safe) ---
    ("awk '{print > \"/dev/stderr\"}' file.txt", False),  # Still detected as redirect
    ("awk '{print > \"/dev/null\"}' file.txt", False),
    #
    # --- Complex programs ---
    ('awk \'BEGIN {FS=":"; OFS=","} NR>1 {print $1,$2}\' file.txt', True),
    ("awk '{arr[$1]+=$2} END {for (k in arr) print k, arr[k]}' file.txt", True),
    #
    # --- Help/version flags ---
    ("gawk --help", True),
    ("gawk --version", True),
    ("gawk -V", True),
    ("mawk -W version", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
