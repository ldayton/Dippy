"""
Comprehensive tests for pip CLI handler.

Pip is safe for viewing packages, but install/uninstall need confirmation.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing packages ===
    ("pip list", True),
    ("pip list --outdated", True),
    ("pip list --uptodate", True),
    ("pip list --format=json", True),
    ("pip list --format=freeze", True),
    ("pip list --format=columns", True),
    ("pip list --user", True),
    ("pip list --local", True),
    ("pip list --not-required", True),
    ("pip list --editable", True),
    ("pip list --exclude requests", True),
    ("pip list --include-editable", True),
    ("pip list --path /path/to/env", True),
    #
    # === SAFE: Freeze ===
    ("pip freeze", True),
    ("pip freeze --local", True),
    ("pip freeze --user", True),
    ("pip freeze --all", True),
    ("pip freeze --exclude-editable", True),
    ("pip freeze --path /path/to/env", True),
    #
    # === SAFE: Show ===
    ("pip show requests", True),
    ("pip show numpy pandas", True),
    ("pip show --verbose requests", True),
    ("pip show --files requests", True),
    ("pip show -f requests", True),
    #
    # === SAFE: Search (deprecated) ===
    ("pip search requests", True),  # deprecated but safe
    #
    # === SAFE: Check ===
    ("pip check", True),
    #
    # === SAFE: Config (viewing) ===
    ("pip config list", True),
    ("pip config list --user", True),
    ("pip config list --global", True),
    ("pip config list --site", True),
    ("pip config get global.index-url", True),
    ("pip config debug", True),
    #
    # === SAFE: Help/version ===
    ("pip help", True),
    ("pip help install", True),
    ("pip -h", True),
    ("pip --help", True),
    ("pip version", True),
    ("pip -V", True),
    ("pip --version", True),
    #
    # === SAFE: Debug ===
    ("pip debug", True),
    ("pip debug --verbose", True),
    #
    # === SAFE: Cache (viewing) ===
    ("pip cache dir", True),
    ("pip cache info", True),
    ("pip cache list", True),
    ("pip cache list requests", True),
    ("pip cache list --format=human", True),
    ("pip cache list --format=abspath", True),
    #
    # === SAFE: Index ===
    ("pip index versions requests", True),
    ("pip index versions requests --pre", True),
    ("pip index versions requests --index-url https://test.pypi.org/simple/", True),
    ("pip index versions requests --platform linux_x86_64", True),
    #
    # === SAFE: Inspect ===
    ("pip inspect", True),
    ("pip inspect --local", True),
    ("pip inspect --user", True),
    ("pip inspect --path /path/to/env", True),
    ("pip inspect --verbose", True),
    #
    # === SAFE: Hash (read-only computation) ===
    ("pip hash package.whl", True),
    ("pip hash package.tar.gz", True),
    ("pip hash -a sha256 package.whl", True),
    ("pip hash --algorithm sha512 package.whl", True),
    ("pip hash package1.whl package2.whl", True),
    #
    # === SAFE: pip3 variants ===
    ("pip3 list", True),
    ("pip3 freeze", True),
    ("pip3 show requests", True),
    ("pip3 --version", True),
    ("pip3 check", True),
    ("pip3 inspect", True),
    ("pip3 hash package.whl", True),
    #
    # === UNSAFE: Install ===
    ("pip install requests", False),
    ("pip install requests==2.28.0", False),
    ("pip install 'requests>=2.28'", False),
    ("pip install requests numpy pandas", False),
    ("pip install -r requirements.txt", False),
    ("pip install --requirement requirements.txt", False),
    ("pip install -e .", False),
    ("pip install --editable .", False),
    ("pip install --upgrade requests", False),
    ("pip install -U pip", False),
    ("pip install --user requests", False),
    ("pip install --target /path requests", False),
    ("pip install --prefix /path requests", False),
    ("pip install git+https://github.com/user/repo.git", False),
    ("pip install https://example.com/package.tar.gz", False),
    ("pip install ./package.whl", False),
    ("pip install --no-deps requests", False),
    ("pip install --force-reinstall requests", False),
    ("pip install --ignore-installed requests", False),
    ("pip install --no-cache-dir requests", False),
    ("pip install --compile requests", False),
    ("pip install --no-compile requests", False),
    ("pip install --dry-run requests", False),  # still unsafe - shows what would happen
    #
    # === UNSAFE: Uninstall ===
    ("pip uninstall requests", False),
    ("pip uninstall -y requests", False),
    ("pip uninstall --yes numpy pandas", False),
    ("pip uninstall -r requirements.txt", False),
    ("pip remove requests", False),  # alias
    #
    # === UNSAFE: Download ===
    ("pip download requests", False),
    ("pip download -d /tmp requests", False),
    ("pip download --dest /tmp requests", False),
    ("pip download --platform linux_x86_64 requests", False),
    ("pip download --only-binary :all: requests", False),
    ("pip download --no-binary :none: requests", False),
    #
    # === UNSAFE: Wheel ===
    ("pip wheel requests", False),
    ("pip wheel -w /tmp requests", False),
    ("pip wheel --wheel-dir /tmp requests", False),
    ("pip wheel --no-deps requests", False),
    ("pip wheel -r requirements.txt", False),
    #
    # === UNSAFE: Lock (experimental) ===
    ("pip lock .", False),
    ("pip lock -e .", False),
    ("pip lock -r requirements.txt", False),
    ("pip lock -o pylock.toml", False),
    ("pip lock requests", False),
    #
    # === UNSAFE: Cache modification ===
    ("pip cache purge", False),
    ("pip cache remove requests", False),
    ("pip cache remove '*'", False),
    #
    # === UNSAFE: Config modification ===
    ("pip config set global.index-url https://pypi.example.com", False),
    ("pip config unset global.index-url", False),
    ("pip config edit", False),
    ("pip config edit --global", False),
    #
    # === pip3 unsafe variants ===
    ("pip3 install requests", False),
    ("pip3 uninstall requests", False),
    ("pip3 install -r requirements.txt", False),
    ("pip3 download requests", False),
    ("pip3 wheel requests", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
