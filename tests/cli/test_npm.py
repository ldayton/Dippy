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
    ("npm s react", True),
    ("npm find react", True),
    ("npm outdated", True),
    ("npm outdated --long", True),
    #
    # === SAFE: Audit (viewing) ===
    ("npm audit", True),
    ("npm audit --json", True),
    ("npm audit --omit=dev", True),
    #
    # === SAFE: Help and version ===
    ("npm help", True),
    ("npm help install", True),
    ("npm help-search install", True),
    ("npm version", True),
    ("npm -v", True),
    ("npm --version", True),
    #
    # === SAFE: Config (reading) ===
    ("npm config list", True),
    ("npm config ls", True),
    ("npm c list", True),
    ("npm config get registry", True),
    ("npm get registry", True),
    #
    # === SAFE: Path info ===
    ("npm root", True),
    ("npm root -g", True),
    ("npm prefix", True),
    ("npm prefix -g", True),
    ("npm bin", True),
    ("npm bin -g", True),
    #
    # === SAFE: Documentation links ===
    ("npm docs lodash", True),
    ("npm home react", True),
    ("npm bugs express", True),
    ("npm repo typescript", True),
    #
    # === SAFE: Owner/access (viewing) ===
    ("npm owner ls lodash", True),
    ("npm access list packages", True),
    ("npm access list collaborators lodash", True),
    ("npm access get status lodash", True),
    #
    # === SAFE: Auth info ===
    ("npm whoami", True),
    ("npm ping", True),
    #
    # === SAFE: Dependency analysis ===
    ("npm explain lodash", True),
    ("npm why lodash", True),
    ("npm find-dupes", True),
    ("npm query ':root > .prod'", True),
    #
    # === SAFE: Pack (local tarball, no publish) ===
    ("npm pack", True),
    ("npm pack --dry-run", True),
    ("npm pack lodash", True),
    #
    # === SAFE: Fund and doctor ===
    ("npm fund", True),
    ("npm fund lodash", True),
    ("npm doctor", True),
    #
    # === SAFE: Cache (viewing) ===
    ("npm cache ls", True),
    ("npm cache list", True),
    #
    # === SAFE: Run (listing only) ===
    ("npm run --list", True),
    ("npm run", True),  # just lists available scripts
    #
    # === SAFE: Completion ===
    ("npm completion", True),
    #
    # === SAFE: Diff (viewing) ===
    ("npm diff", True),
    ("npm diff --diff=lodash@1.0.0 --diff=lodash@2.0.0", True),
    #
    # === SAFE: Dist-tag (viewing) ===
    ("npm dist-tag ls", True),
    ("npm dist-tag ls lodash", True),
    #
    # === SAFE: Token (viewing) ===
    ("npm token list", True),
    #
    # === SAFE: Profile (viewing) ===
    ("npm profile get", True),
    ("npm profile get email", True),
    #
    # === SAFE: Pkg (viewing) ===
    ("npm pkg get", True),
    ("npm pkg get name", True),
    ("npm pkg get name version", True),
    #
    # === SAFE: Stars (viewing) ===
    ("npm stars", True),
    ("npm stars username", True),
    #
    # === SAFE: SBOM ===
    ("npm sbom", True),
    ("npm sbom --sbom-format cyclonedx", True),
    #
    # === UNSAFE: Install/add ===
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
    ("npm ci", False),
    ("npm install-ci-test", False),
    ("npm install-test", False),
    #
    # === UNSAFE: Uninstall/remove ===
    ("npm uninstall lodash", False),
    ("npm remove express", False),
    ("npm rm jest", False),
    ("npm un typescript", False),
    ("npm r lodash", False),
    #
    # === UNSAFE: Update ===
    ("npm update", False),
    ("npm upgrade", False),
    ("npm up lodash", False),
    #
    # === UNSAFE: Run scripts ===
    ("npm run build", False),
    ("npm run test", False),
    ("npm run start", False),
    ("npm run dev", False),
    ("npm run-script build", False),
    #
    # === UNSAFE: Exec ===
    ("npm exec jest", False),
    ("npm x playwright", False),
    #
    # === UNSAFE: Lifecycle scripts ===
    ("npm start", False),
    ("npm stop", False),
    ("npm restart", False),
    ("npm test", False),
    ("npm t", False),
    #
    # === UNSAFE: Publish/unpublish ===
    ("npm publish", False),
    ("npm publish --access public", False),
    ("npm unpublish", False),
    ("npm unpublish lodash@1.0.0", False),
    #
    # === UNSAFE: Link ===
    ("npm link", False),
    ("npm unlink", False),
    ("npm link lodash", False),
    #
    # === UNSAFE: Maintenance ===
    ("npm prune", False),
    ("npm dedupe", False),
    ("npm ddp", False),
    ("npm rebuild", False),
    ("npm rb", False),
    #
    # === UNSAFE: Init/create ===
    ("npm init", False),
    ("npm init -y", False),
    ("npm create react-app my-app", False),
    #
    # === UNSAFE: Cache (modifying) ===
    ("npm cache clean", False),
    ("npm cache clean --force", False),
    ("npm cache add lodash", False),
    ("npm cache verify", False),
    #
    # === UNSAFE: Config (modifying) ===
    ("npm set registry https://example.com", False),
    ("npm config set registry https://example.com", False),
    ("npm config delete registry", False),
    #
    # === UNSAFE: Access (modifying) ===
    ("npm access set status=public lodash", False),
    ("npm access grant read-write myorg:myteam lodash", False),
    ("npm access revoke myorg:myteam lodash", False),
    #
    # === UNSAFE: Auth ===
    ("npm login", False),
    ("npm adduser", False),
    ("npm logout", False),
    #
    # === UNSAFE: Audit fix ===
    ("npm audit fix", False),
    ("npm audit fix --force", False),
    #
    # === UNSAFE: Deprecate ===
    ("npm deprecate lodash@1.0.0 'use v2'", False),
    ("npm undeprecate lodash@1.0.0", False),
    #
    # === UNSAFE: Dist-tag (modifying) ===
    ("npm dist-tag add lodash@1.0.0 latest", False),
    ("npm dist-tag rm lodash latest", False),
    #
    # === UNSAFE: Edit/explore ===
    ("npm edit lodash", False),
    ("npm explore lodash", False),
    ("npm explore lodash -- ls", False),
    #
    # === UNSAFE: Owner (modifying) ===
    ("npm owner add user lodash", False),
    ("npm owner rm user lodash", False),
    #
    # === UNSAFE: Org/team ===
    ("npm org set myorg user developer", False),
    ("npm org rm myorg user", False),
    ("npm team create myorg:myteam", False),
    ("npm team destroy myorg:myteam", False),
    ("npm team add myorg:myteam user", False),
    ("npm team rm myorg:myteam user", False),
    #
    # === UNSAFE: Profile (modifying) ===
    ("npm profile set email new@example.com", False),
    ("npm profile enable-2fa", False),
    ("npm profile disable-2fa", False),
    #
    # === UNSAFE: Shrinkwrap ===
    ("npm shrinkwrap", False),
    #
    # === UNSAFE: Star/unstar ===
    ("npm star lodash", False),
    ("npm unstar lodash", False),
    #
    # === UNSAFE: Token (modifying) ===
    ("npm token create", False),
    ("npm token revoke abc123", False),
    #
    # === UNSAFE: Version (modifying) ===
    ("npm version major", False),
    ("npm version minor", False),
    ("npm version patch", False),
    ("npm version 1.2.3", False),
    #
    # === UNSAFE: Pkg (modifying) ===
    ("npm pkg set name=newname", False),
    ("npm pkg delete scripts.test", False),
    ("npm pkg fix", False),
    #
    # === YARN ===
    ("yarn list", True),
    ("yarn info react", True),
    ("yarn outdated", True),
    ("yarn why lodash", True),
    ("yarn help", True),
    ("yarn version", True),
    ("yarn licenses list", True),
    ("yarn install", False),
    ("yarn add lodash", False),
    ("yarn remove express", False),
    ("yarn run build", False),
    ("yarn start", False),
    ("yarn test", False),
    ("yarn publish", False),
    ("yarn upgrade", False),
    ("yarn cache clean", False),
    ("yarn global add create-react-app", False),
    ("yarn link", False),
    ("yarn unlink", False),
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
    ("pnpm root", True),
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
    ("pnpm link", False),
    ("pnpm unlink", False),
    ("pnpm store prune", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
