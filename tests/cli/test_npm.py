"""
Comprehensive tests for npm/yarn/pnpm CLI handler.

Package managers need confirmation for install/publish/run operations.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Viewing package info ===
    ("npm list", True),
    ("npm ls", True),
    ("npm ll", True),
    ("npm la", True),
    ("npm list --depth=0", True),
    ("npm list --all", True),
    ("npm list --json", True),
    ("npm info react", True),
    ("npm show lodash", True),
    ("npm view express versions", True),
    ("npm v typescript", True),
    ("npm search lodash", True),
    ("npm find react", True),
    ("npm outdated", True),
    ("npm outdated --long", True),
    ("npm audit", True),
    ("npm audit --json", True),
    ("npm help", True),
    ("npm help install", True),
    ("npm version", True),
    ("npm -v", True),
    ("npm --version", True),
    ("npm config list", True),
    ("npm config get registry", True),
    ("npm get registry", True),
    ("npm root", True),
    ("npm prefix", True),
    ("npm bin", True),
    ("npm docs lodash", True),
    ("npm home react", True),
    ("npm bugs express", True),
    ("npm repo typescript", True),
    ("npm owner ls lodash", True),
    ("npm whoami", True),
    ("npm ping", True),
    ("npm explain lodash", True),
    ("npm why lodash", True),
    ("npm pack", True),  # creates tarball locally
    ("npm fund", True),
    ("npm doctor", True),
    ("npm cache ls", True),
    ("npm cache list", True),
    ("npm run --list", True),  # just lists scripts
    #
    # === UNSAFE: Install/modify ===
    ("npm install", False),
    ("npm i", False),
    ("npm install lodash", False),
    ("npm i express", False),
    ("npm install --save lodash", False),
    ("npm install --save-dev jest", False),
    ("npm i -D typescript", False),
    ("npm install -g npm", False),
    ("npm i --global create-react-app", False),
    ("npm add lodash", False),
    ("npm uninstall lodash", False),
    ("npm remove express", False),
    ("npm rm jest", False),
    ("npm un typescript", False),
    ("npm update", False),
    ("npm upgrade", False),
    ("npm up lodash", False),
    ("npm run build", False),
    ("npm run test", False),
    ("npm run start", False),
    ("npm run dev", False),
    ("npm exec jest", False),
    ("npm x playwright", False),
    ("npm start", False),
    ("npm stop", False),
    ("npm restart", False),
    ("npm test", False),
    ("npm t", False),
    ("npm publish", False),
    ("npm unpublish", False),
    ("npm link", False),
    ("npm unlink", False),
    ("npm prune", False),
    ("npm dedupe", False),
    ("npm rebuild", False),
    ("npm build", False),
    ("npm init", False),
    ("npm init -y", False),
    ("npm create react-app my-app", False),
    ("npm cache clean", False),
    ("npm cache clean --force", False),
    ("npm set registry https://example.com", False),
    #
    # === YARN ===
    ("yarn list", True),
    ("yarn info react", True),
    ("yarn outdated", True),
    ("yarn why lodash", True),
    ("yarn help", True),
    ("yarn version", True),
    ("yarn install", False),
    ("yarn add lodash", False),
    ("yarn remove express", False),
    ("yarn run build", False),
    ("yarn start", False),
    ("yarn test", False),
    ("yarn publish", False),
    ("yarn upgrade", False),
    ("yarn cache clean", False),
    #
    # === PNPM ===
    ("pnpm list", True),
    ("pnpm ls", True),
    ("pnpm info react", True),
    ("pnpm outdated", True),
    ("pnpm audit", True),
    ("pnpm why lodash", True),
    ("pnpm help", True),
    ("pnpm -v", True),
    ("pnpm install", False),
    ("pnpm i", False),
    ("pnpm add lodash", False),
    ("pnpm remove express", False),
    ("pnpm rm jest", False),
    ("pnpm run build", False),
    ("pnpm start", False),
    ("pnpm test", False),
    ("pnpm publish", False),
    ("pnpm update", False),
    ("pnpm prune", False),
    ("pnpm rebuild", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
