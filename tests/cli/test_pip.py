"""
Comprehensive tests for pip CLI handler.

Pip is safe for viewing packages, but install/uninstall need confirmation.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing packages ===
    ("pip list", True),
    ("pip list --outdated", True),
    ("pip list --uptodate", True),
    ("pip list --format=json", True),
    ("pip list --user", True),
    ("pip list --local", True),
    ("pip freeze", True),
    ("pip freeze --local", True),
    ("pip freeze --user", True),
    ("pip show requests", True),
    ("pip show numpy pandas", True),
    ("pip show --verbose requests", True),
    ("pip search requests", True),  # deprecated but safe
    ("pip check", True),
    ("pip config list", True),
    ("pip config get global.index-url", True),
    ("pip config debug", True),
    ("pip help", True),
    ("pip help install", True),
    ("pip -h", True),
    ("pip --help", True),
    ("pip version", True),
    ("pip -V", True),
    ("pip --version", True),
    ("pip debug", True),
    ("pip debug --verbose", True),
    ("pip cache dir", True),
    ("pip cache info", True),
    ("pip cache list", True),
    ("pip cache list requests", True),
    ("pip index versions requests", True),
    #
    # === SAFE: pip3 variants ===
    ("pip3 list", True),
    ("pip3 freeze", True),
    ("pip3 show requests", True),
    ("pip3 --version", True),
    #
    # === UNSAFE: Install/uninstall ===
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
    ("pip uninstall requests", False),
    ("pip uninstall -y requests", False),
    ("pip uninstall --yes numpy pandas", False),
    ("pip remove requests", False),
    ("pip download requests", False),
    ("pip download -d /tmp requests", False),
    ("pip wheel requests", False),
    ("pip wheel -w /tmp requests", False),
    ("pip hash requests-2.28.0.tar.gz", False),
    #
    # === UNSAFE: Cache modification ===
    ("pip cache purge", False),
    ("pip cache remove requests", False),
    #
    # === UNSAFE: Config modification ===
    ("pip config set global.index-url https://pypi.example.com", False),
    ("pip config unset global.index-url", False),
    #
    # === pip3 unsafe variants ===
    ("pip3 install requests", False),
    ("pip3 uninstall requests", False),
    ("pip3 install -r requirements.txt", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
