"""Test cases for find command."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation

# ==========================================================================
# find
# ==========================================================================
#
# find is safe for all read-only operations (searching, listing, printing)
# Unsafe primaries: -exec, -execdir, -ok, -okdir, -delete
# These execute commands or modify the filesystem
#

TESTS = [
    #
    # --- Basic searches (safe) ---
    #
    ("find .", True),
    ("find /", True),
    ("find ~", True),
    ("find /home/user", True),
    ("find . /tmp /var", True),
    #
    # --- Name matching (safe) ---
    #
    ("find . -name '*.py'", True),
    ("find . -name '*.txt'", True),
    ("find . -name 'README*'", True),
    ("find . -iname '*.PY'", True),
    ("find . -iname '*.TXT'", True),
    ("find . -path '*/src/*.py'", True),
    ("find . -ipath '*/SRC/*.py'", True),
    ("find . -wholename '*/test/*'", True),
    ("find . -iwholename '*/TEST/*'", True),
    ("find . -lname '*.so'", True),
    ("find . -ilname '*.SO'", True),
    ("find . -regex '.*\\.py$'", True),
    ("find . -iregex '.*\\.PY$'", True),
    #
    # --- Type matching (safe) ---
    #
    ("find . -type f", True),
    ("find . -type d", True),
    ("find . -type l", True),
    ("find . -type b", True),
    ("find . -type c", True),
    ("find . -type p", True),
    ("find . -type s", True),
    ("find . -xtype f", True),
    ("find . -xtype l", True),
    #
    # --- Size matching (safe) ---
    #
    ("find . -size +100k", True),
    ("find . -size -1M", True),
    ("find . -size 500c", True),
    ("find . -size +1G", True),
    ("find . -empty", True),
    #
    # --- Time matching (safe) ---
    #
    ("find . -mtime -7", True),
    ("find . -mtime +30", True),
    ("find . -mtime 1", True),
    ("find . -atime -1", True),
    ("find . -atime +7", True),
    ("find . -ctime -1", True),
    ("find . -ctime +7", True),
    ("find . -mmin -60", True),
    ("find . -mmin +120", True),
    ("find . -amin -30", True),
    ("find . -cmin -15", True),
    ("find . -newer reference.txt", True),
    ("find . -anewer reference.txt", True),
    ("find . -cnewer reference.txt", True),
    ("find . -newermt '2024-01-01'", True),
    ("find . -newerat '2024-01-01'", True),
    ("find . -newerct '2024-01-01'", True),
    ("find . -daystart -mtime -1", True),
    #
    # --- Permission matching (safe) ---
    #
    ("find . -perm 644", True),
    ("find . -perm -644", True),
    ("find . -perm /644", True),
    ("find . -perm +644", True),
    ("find . -perm -u=r", True),
    ("find . -perm -u=x", True),
    ("find . -readable", True),
    ("find . -writable", True),
    ("find . -executable", True),
    #
    # --- Owner/group matching (safe) ---
    #
    ("find . -user root", True),
    ("find . -user nobody", True),
    ("find . -group wheel", True),
    ("find . -group staff", True),
    ("find . -uid 0", True),
    ("find . -uid 1000", True),
    ("find . -gid 0", True),
    ("find . -gid 1000", True),
    ("find . -nouser", True),
    ("find . -nogroup", True),
    #
    # --- Depth control (safe) ---
    #
    ("find . -maxdepth 1", True),
    ("find . -maxdepth 3", True),
    ("find . -mindepth 1", True),
    ("find . -mindepth 2", True),
    ("find . -maxdepth 2 -mindepth 1", True),
    ("find . -depth", True),
    ("find . -d", True),
    #
    # --- Link/inode matching (safe) ---
    #
    ("find . -links 1", True),
    ("find . -links +1", True),
    ("find . -inum 12345", True),
    ("find . -samefile original.txt", True),
    #
    # --- Filesystem options (safe) ---
    #
    ("find . -mount", True),
    ("find . -xdev", True),
    ("find . -fstype ext4", True),
    ("find . -fstype nfs", True),
    #
    # --- Print actions (safe) ---
    #
    ("find . -print", True),
    ("find . -print0", True),
    ("find . -printf '%f\\n'", True),
    ("find . -printf '%p %s\\n'", True),
    ("find . -ls", True),
    ("find . -fls /tmp/output.txt", True),
    ("find . -fprint /tmp/output.txt", True),
    ("find . -fprint0 /tmp/output.txt", True),
    ("find . -fprintf /tmp/output.txt '%p\\n'", True),
    #
    # --- Boolean operators (safe) ---
    #
    ("find . -name '*.py' -o -name '*.txt'", True),
    ("find . -name '*.py' -or -name '*.txt'", True),
    ("find . -name '*.py' -a -type f", True),
    ("find . -name '*.py' -and -type f", True),
    ("find . ! -name '*.pyc'", True),
    ("find . -not -name '*.pyc'", True),
    ("find . \\( -name '*.py' -o -name '*.txt' \\)", True),
    ("find . -name '*.py' , -name '*.txt'", True),
    #
    # --- Prune (safe - just skips directories) ---
    #
    ("find . -name '.git' -prune", True),
    ("find . -name 'node_modules' -prune -o -name '*.js' -print", True),
    ("find . -path './.git' -prune -o -type f -print", True),
    #
    # --- Quit (safe - just stops early) ---
    #
    ("find . -name 'target' -quit", True),
    #
    # --- True/False (safe) ---
    #
    ("find . -true", True),
    ("find . -false", True),
    #
    # --- Global options (safe) ---
    #
    ("find -H . -name '*.py'", True),
    ("find -L . -name '*.py'", True),
    ("find -P . -name '*.py'", True),
    ("find -E . -regex '.*'", True),
    ("find -X . -name '*.py'", True),
    ("find -s . -name '*.py'", True),
    ("find -x . -name '*.py'", True),
    ("find -f /path -name '*.py'", True),
    #
    # --- Complex safe queries ---
    #
    ("find . -name '*.py' -type f -size +1k -mtime -7", True),
    ("find . -type f -name '*.log' -size +100M", True),
    ("find /var/log -type f -name '*.log' -mtime +30", True),
    ("find . -type d -empty", True),
    ("find . -type f -empty", True),
    ("find . -maxdepth 2 -type f -name '*.conf'", True),
    ("find . -name '*.tmp' -o -name '*.bak'", True),
    ("find . -user root -type f -perm -4000", True),
    ("find . -type f -name '*.sh' -executable", True),
    ("find /home -type f -size +100M -mtime +365", True),
    ("find . -name '*exec*'", True),  # 'exec' in filename is safe
    ("find . -name 'delete*'", True),  # 'delete' in filename is safe
    #
    # ==========================================================================
    # EXEC OPERATIONS - delegates to inner command
    # ==========================================================================
    #
    # --- -exec with safe commands (approved) ---
    #
    ("find . -exec cat {} \\;", True),
    ("find . -exec ls {} \\;", True),
    ("find . -exec echo {} \\;", True),
    ("find . -name '*.py' -exec wc -l {} \\;", True),
    ("find . -name '*.py' -exec grep TODO {} \\;", True),
    ("find . -type f -exec md5sum {} +", True),
    ("find . -exec head {} \\;", True),
    ("find . -exec file {} \\;", True),
    #
    # --- -exec with unsafe commands (blocked) ---
    #
    ("find . -exec rm {} \\;", False),
    ("find . -exec rm {} +", False),
    ("find . -exec chmod 644 {} \\;", False),
    ("find . -exec chown user {} \\;", False),
    ("find . -exec sh -c 'rm $0' {} \\;", False),  # shell with unsafe inner cmd
    #
    # --- -execdir with safe commands (approved) ---
    #
    ("find . -execdir cat {} \\;", True),
    ("find . -execdir ls {} \\;", True),
    ("find . -name '*.py' -execdir wc -l {} \\;", True),
    ("find . -type f -execdir md5sum {} +", True),
    #
    # --- -execdir with unsafe commands (blocked) ---
    #
    ("find . -execdir rm {} \\;", False),
    #
    # --- -ok (interactive - always ask) ---
    #
    ("find . -ok rm {} \\;", False),
    ("find . -ok cat {} \\;", False),
    ("find . -name '*.tmp' -ok rm {} \\;", False),
    #
    # --- -okdir (interactive - always ask) ---
    #
    ("find . -okdir rm {} \\;", False),
    ("find . -okdir cat {} \\;", False),
    ("find . -name '*.bak' -okdir rm {} \\;", False),
    #
    # --- -delete (deletes files) ---
    #
    ("find . -delete", False),
    ("find . -name '*.tmp' -delete", False),
    ("find . -type f -delete", False),
    ("find . -empty -delete", False),
    ("find . -name '*.bak' -type f -delete", False),
    ("find /tmp -name '*.cache' -delete", False),
    ("find . -mtime +30 -delete", False),
    #
    # --- Combinations with safe exec ---
    #
    ("find . -name '*.py' -print -exec cat {} \\;", True),
    #
    # --- Combinations with unsafe primaries ---
    #
    ("find . -type f -delete -print", False),
    ("find . -name '*.tmp' -o -name '*.bak' -delete", False),
    ("find . \\( -name '*.tmp' -o -name '*.bak' \\) -exec rm {} \\;", False),
    ("find . -name '*.log' -mtime +7 -delete", False),
    ("find . -type f -name '*.py' -exec chmod +x {} \\;", False),
    #
    # ==========================================================================
    # Edge cases
    # ==========================================================================
    #
    # --- Help and version (safe) ---
    #
    ("find --help", True),
    ("find --version", True),
    #
    # --- No path specified (safe - defaults to .) ---
    #
    ("find -name '*.py'", True),
    ("find -type f", True),
    #
    # --- Paths with special characters (safe) ---
    #
    ("find './path with spaces'", True),
    ("find '/path/to/dir'", True),
    #
    # --- Output redirection handled by redirect check, not find check ---
    # These would be caught by redirect detection, not find's SIMPLE_CHECKS
    #
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_find_command(check, command: str, expected: bool):
    """Test find command safety classification."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
