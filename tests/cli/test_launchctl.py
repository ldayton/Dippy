"""Test cases for launchctl."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("launchctl list", True),
    ("launchctl list com.apple.Finder", True),
    ("launchctl print system", True),
    ("launchctl print gui/501", True),
    ("launchctl print-cache", True),
    ("launchctl print-disabled system", True),
    ("launchctl blame system/com.apple.logd", True),
    ("launchctl plist /Applications/Safari.app", True),
    ("launchctl procinfo 1234", True),
    ("launchctl hostinfo", True),
    ("launchctl resolveport 1234 0x1234", True),
    ("launchctl dumpstate", True),
    ("launchctl dumpjpcategory", True),
    ("launchctl managerpid", True),
    ("launchctl manageruid", True),
    ("launchctl managername", True),
    ("launchctl error posix 2", True),
    ("launchctl variant", True),
    ("launchctl version", True),
    ("launchctl help", True),
    ("launchctl help bootstrap", True),
    ("launchctl getenv PATH", True),
    # Write/control operations - unsafe
    ("launchctl bootstrap gui/501 ~/Library/LaunchAgents/my.plist", False),
    ("launchctl bootout gui/501/my.service", False),
    ("launchctl enable gui/501/my.service", False),
    ("launchctl disable gui/501/my.service", False),
    ("launchctl kickstart gui/501/my.service", False),
    ("launchctl kill SIGTERM gui/501/my.service", False),
    ("launchctl start my.service", False),
    ("launchctl stop my.service", False),
    ("launchctl load ~/Library/LaunchAgents/my.plist", False),
    ("launchctl unload ~/Library/LaunchAgents/my.plist", False),
    ("launchctl remove my.service", False),
    ("launchctl setenv MY_VAR value", False),
    ("launchctl unsetenv MY_VAR", False),
    ("launchctl limit maxfiles 65536 65536", False),
    ("launchctl config system path /usr/local/bin", False),
    ("launchctl reboot system", False),
    ("launchctl submit -l my.job -- /usr/bin/true", False),
    ("launchctl attach gui/501/my.service", False),
    ("launchctl debug gui/501/my.service", False),
    ("launchctl bsexec 1234 /bin/ls", False),
    ("launchctl asuser 501 /bin/ls", False),
    # No arguments - unsafe
    ("launchctl", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
