"""Test cases for Homebrew CLI (brew)."""

import pytest

from dippy.dippy import (
    is_command_safe,
    parse_commands,
    _load_custom_configs,
)

# Load custom configs (normally done in main(), but tests call functions directly)
_load_custom_configs()

# ==========================================================================
# Homebrew CLI (brew)
# ==========================================================================
#
# brew uses first_token parser: brew <action> [args...]
# Safe actions: info, list, search, deps, desc, leaves, uses, outdated, missing,
#               config, doctor, options, formulae, casks, tap-info, log, cat
# Unsafe actions: install, uninstall, reinstall, upgrade, update, tap, untap,
#                 link, unlink, pin, unpin, cleanup, autoremove, edit, create
#

TESTS = [
    #
    # --- brew info (read-only inspection) ---
    #
    ("brew info", True),
    ("brew info python", True),
    ("brew info python@3.11", True),
    ("brew info --json python", True),
    ("brew info --json=v2 python", True),
    ("brew info --installed", True),
    ("brew info --all", True),
    ("brew info --analytics", True),
    ("brew info --cask firefox", True),
    ("brew info --formula python", True),
    ("brew info --github python", True),
    ("brew info --verbose python", True),
    ("brew info -v python", True),
    #
    # --- brew list (read-only listing) ---
    #
    ("brew list", True),
    ("brew ls", True),
    ("brew list python", True),
    ("brew list --formula", True),
    ("brew list --formulae", True),
    ("brew list --cask", True),
    ("brew list --casks", True),
    ("brew list --full-name", True),
    ("brew list --versions", True),
    ("brew list --pinned", True),
    ("brew list --multiple", True),
    ("brew list -1", True),
    ("brew list -l", True),
    ("brew list -r", True),
    ("brew list -t", True),
    ("brew list --installed-on-request", True),
    ("brew list --installed-as-dependency", True),
    ("brew list --poured-from-bottle", True),
    ("brew list --built-from-source", True),
    ("brew list --verbose", True),
    ("brew list -v", True),
    #
    # --- brew search (read-only search) ---
    #
    ("brew search", True),
    ("brew search python", True),
    ("brew search /python/", True),
    ("brew search --formula python", True),
    ("brew search --formulae python", True),
    ("brew search --cask firefox", True),
    ("brew search --casks firefox", True),
    ("brew search --desc python", True),
    ("brew search --eval-all python", True),
    ("brew search --pull-request python", True),
    ("brew search --open python", True),
    ("brew search --closed python", True),
    ("brew -S python", True),
    #
    # --- brew deps (dependency inspection) ---
    #
    ("brew deps", True),
    ("brew deps python", True),
    ("brew deps --tree python", True),
    ("brew deps --graph python", True),
    ("brew deps --dot python", True),
    ("brew deps --installed", True),
    ("brew deps --all", True),
    ("brew deps --direct python", True),
    ("brew deps -1 python", True),
    ("brew deps --union python ruby", True),
    ("brew deps --full-name python", True),
    ("brew deps --topological python", True),
    ("brew deps -n python", True),
    ("brew deps --include-build python", True),
    ("brew deps --include-optional python", True),
    ("brew deps --include-test python", True),
    ("brew deps --skip-recommended python", True),
    ("brew deps --missing python", True),
    ("brew deps --annotate python", True),
    ("brew deps --formula python", True),
    ("brew deps --cask firefox", True),
    ("brew deps --for-each python ruby", True),
    ("brew deps --eval-all", True),
    #
    # --- brew desc (description display) ---
    #
    ("brew desc", True),
    ("brew desc python", True),
    ("brew desc --search python", True),
    ("brew desc -s python", True),
    ("brew desc --name python", True),
    ("brew desc -n python", True),
    ("brew desc --description python", True),
    ("brew desc -d python", True),
    ("brew desc --eval-all", True),
    ("brew desc --formula python", True),
    ("brew desc --cask firefox", True),
    #
    # --- brew leaves (list installed leaf formulae) ---
    #
    ("brew leaves", True),
    ("brew leaves --installed-on-request", True),
    ("brew leaves -r", True),
    ("brew leaves --installed-as-dependency", True),
    ("brew leaves -p", True),
    ("brew leaves --verbose", True),
    ("brew leaves -v", True),
    #
    # --- brew uses (show dependents) ---
    #
    ("brew uses", True),
    ("brew uses python", True),
    ("brew uses --recursive python", True),
    ("brew uses --installed python", True),
    ("brew uses --missing python", True),
    ("brew uses --eval-all python", True),
    ("brew uses --include-build python", True),
    ("brew uses --include-optional python", True),
    ("brew uses --include-test python", True),
    ("brew uses --skip-recommended python", True),
    ("brew uses --formula python", True),
    ("brew uses --cask python", True),
    #
    # --- brew outdated (list outdated packages) ---
    #
    ("brew outdated", True),
    ("brew outdated python", True),
    ("brew outdated --formula", True),
    ("brew outdated --formulae", True),
    ("brew outdated --cask", True),
    ("brew outdated --casks", True),
    ("brew outdated --json", True),
    ("brew outdated --json=v2", True),
    ("brew outdated --greedy", True),
    ("brew outdated -g", True),
    ("brew outdated --greedy-latest", True),
    ("brew outdated --greedy-auto-updates", True),
    ("brew outdated --fetch-HEAD", True),
    ("brew outdated --verbose", True),
    ("brew outdated -v", True),
    ("brew outdated --quiet", True),
    ("brew outdated -q", True),
    #
    # --- brew missing (check for missing dependencies) ---
    #
    ("brew missing", True),
    ("brew missing python", True),
    ("brew missing --hide=python", True),
    ("brew missing --verbose", True),
    ("brew missing -v", True),
    #
    # --- brew config (show configuration) ---
    #
    ("brew config", True),
    ("brew --config", True),
    ("brew config --verbose", True),
    ("brew config -v", True),
    #
    # --- brew doctor (check system health) ---
    #
    ("brew doctor", True),
    ("brew dr", True),
    ("brew doctor --list-checks", True),
    ("brew doctor --audit-debug", True),
    ("brew doctor -D", True),
    ("brew doctor --verbose", True),
    ("brew doctor -v", True),
    #
    # --- brew options (show install options) ---
    #
    ("brew options", True),
    ("brew options python", True),
    ("brew options --installed", True),
    ("brew options --all", True),
    #
    # --- brew tap-info (show tap information) ---
    #
    ("brew tap-info", True),
    ("brew tap-info homebrew/cask", True),
    ("brew tap-info --installed", True),
    ("brew tap-info --json", True),
    ("brew tap-info --json=v1", True),
    #
    # --- brew formulae/casks (list available) ---
    #
    ("brew formulae", True),
    ("brew casks", True),
    #
    # --- Homebrew path commands (read-only) ---
    #
    ("brew --cache", True),
    ("brew --cache python", True),
    ("brew --cache --formula python", True),
    ("brew --cache --cask firefox", True),
    ("brew --cache --build-from-source python", True),
    ("brew --cache -s python", True),
    ("brew --cache --force-bottle python", True),
    ("brew --cache --HEAD python", True),
    ("brew --cellar", True),
    ("brew --cellar python", True),
    ("brew --caskroom", True),
    ("brew --caskroom firefox", True),
    ("brew --prefix", True),
    ("brew --prefix python", True),
    ("brew --prefix --installed python", True),
    ("brew --prefix --unbrewed", True),
    ("brew --repository", True),
    ("brew --repo", True),
    ("brew --version", True),
    ("brew -v", True),
    ("brew --env", True),
    ("brew --taps", True),
    #
    # --- brew log (show git log - developer) ---
    #
    ("brew log", True),
    ("brew log python", True),
    ("brew log -p python", True),
    ("brew log --patch python", True),
    ("brew log --stat python", True),
    ("brew log --oneline python", True),
    ("brew log -1 python", True),
    ("brew log -n 10 python", True),
    ("brew log --max-count 5 python", True),
    ("brew log --formula python", True),
    ("brew log --cask firefox", True),
    #
    # --- brew cat (display formula source - developer) ---
    #
    ("brew cat python", True),
    ("brew cat --formula python", True),
    ("brew cat --cask firefox", True),
    #
    # --- brew commands (list available commands) ---
    #
    ("brew commands", True),
    ("brew commands --quiet", True),
    ("brew commands --include-aliases", True),
    #
    # --- brew help (show help) ---
    #
    ("brew help", True),
    ("brew help install", True),
    ("brew --help", True),
    ("brew -h", True),
    #
    # --- brew fetch (download without installing) ---
    # Note: fetch downloads files but doesn't install, making it read-only in effect
    #
    ("brew fetch python", True),
    ("brew fetch --deps python", True),
    ("brew fetch --force python", True),
    ("brew fetch -f python", True),
    ("brew fetch --retry python", True),
    ("brew fetch --HEAD python", True),
    ("brew fetch --build-from-source python", True),
    ("brew fetch -s python", True),
    ("brew fetch --formula python", True),
    ("brew fetch --cask firefox", True),
    #
    # --- brew home (open homepage - opens browser, no mutations) ---
    #
    ("brew home", True),
    ("brew home python", True),
    ("brew home --formula python", True),
    ("brew home --cask firefox", True),
    ("brew homepage", True),
    ("brew homepage python", True),
    #
    # --- brew docs (open documentation) ---
    #
    ("brew docs", True),
    #
    # --- brew shellenv (print shell environment) ---
    #
    ("brew shellenv", True),
    ("brew shellenv bash", True),
    ("brew shellenv zsh", True),
    ("brew shellenv fish", True),
    #
    # --- brew analytics (view analytics state) ---
    # Note: "brew analytics" with no args just displays state (safe)
    # "brew analytics on/off" modifies state (unsafe)
    #
    ("brew analytics", True),
    ("brew analytics state", True),
    ("brew analytics on", False),
    ("brew analytics off", False),
    #
    # ==========================================================================
    # UNSAFE OPERATIONS (mutations)
    # ==========================================================================
    #
    # --- brew install (installs packages) ---
    #
    ("brew install python", False),
    ("brew install python@3.11", False),
    ("brew install --cask firefox", False),
    ("brew install --formula python", False),
    ("brew install --force python", False),
    ("brew install -f python", False),
    ("brew install --verbose python", False),
    ("brew install -v python", False),
    ("brew install --dry-run python", False),  # dry-run still invokes hooks/checks
    ("brew install -n python", False),
    ("brew install --HEAD python", False),
    ("brew install --build-from-source python", False),
    ("brew install -s python", False),
    ("brew install --interactive python", False),
    ("brew install -i python", False),
    ("brew install --only-dependencies python", False),
    ("brew install --overwrite python", False),
    ("brew install --skip-post-install python", False),
    ("brew install --skip-link python", False),
    ("brew install python ruby node", False),
    #
    # --- brew uninstall/remove/rm (removes packages) ---
    #
    ("brew uninstall python", False),
    ("brew remove python", False),
    ("brew rm python", False),
    ("brew uninstall --force python", False),
    ("brew uninstall -f python", False),
    ("brew uninstall --zap firefox", False),
    ("brew uninstall --ignore-dependencies python", False),
    ("brew uninstall --formula python", False),
    ("brew uninstall --cask firefox", False),
    ("brew uninstall python ruby", False),
    #
    # --- brew reinstall (reinstalls packages) ---
    #
    ("brew reinstall python", False),
    ("brew reinstall --force python", False),
    ("brew reinstall -f python", False),
    ("brew reinstall --cask firefox", False),
    ("brew reinstall --formula python", False),
    ("brew reinstall --build-from-source python", False),
    ("brew reinstall -s python", False),
    ("brew reinstall --interactive python", False),
    ("brew reinstall -i python", False),
    #
    # --- brew upgrade (upgrades packages) ---
    #
    ("brew upgrade", False),
    ("brew upgrade python", False),
    ("brew upgrade --formula", False),
    ("brew upgrade --cask", False),
    ("brew upgrade --force python", False),
    ("brew upgrade -f python", False),
    ("brew upgrade --dry-run", False),
    ("brew upgrade -n python", False),
    ("brew upgrade --greedy", False),
    ("brew upgrade -g", False),
    ("brew upgrade --greedy-latest", False),
    ("brew upgrade --greedy-auto-updates", False),
    ("brew upgrade --fetch-HEAD python", False),
    ("brew upgrade --interactive python", False),
    ("brew upgrade -i python", False),
    #
    # --- brew update (updates Homebrew itself) ---
    #
    ("brew update", False),
    ("brew up", False),
    ("brew update --force", False),
    ("brew update -f", False),
    ("brew update --merge", False),
    ("brew update --auto-update", False),
    ("brew update --verbose", False),
    ("brew update -v", False),
    #
    # --- brew tap (adds repositories) ---
    #
    ("brew tap", False),  # Without args lists taps, but tapping can modify
    ("brew tap homebrew/cask", False),
    ("brew tap homebrew/cask-versions", False),
    ("brew tap user/repo https://github.com/user/repo", False),
    ("brew tap --custom-remote homebrew/cask", False),
    ("brew tap --repair", False),
    ("brew tap --force homebrew/core", False),
    ("brew tap --eval-all homebrew/cask", False),
    #
    # --- brew untap (removes repositories) ---
    #
    ("brew untap homebrew/cask", False),
    ("brew untap --force homebrew/cask", False),
    ("brew untap -f homebrew/cask", False),
    #
    # --- brew link/ln (creates symlinks) ---
    #
    ("brew link python", False),
    ("brew ln python", False),
    ("brew link --overwrite python", False),
    ("brew link --force python", False),
    ("brew link -f python", False),
    ("brew link --dry-run python", False),
    ("brew link -n python", False),
    ("brew link --HEAD python", False),
    #
    # --- brew unlink (removes symlinks) ---
    #
    ("brew unlink python", False),
    ("brew unlink --dry-run python", False),
    ("brew unlink -n python", False),
    #
    # --- brew pin (prevents upgrades) ---
    #
    ("brew pin python", False),
    ("brew pin python ruby", False),
    #
    # --- brew unpin (allows upgrades) ---
    #
    ("brew unpin python", False),
    ("brew unpin python ruby", False),
    #
    # --- brew cleanup (removes old versions) ---
    #
    ("brew cleanup", False),
    ("brew cleanup python", False),
    ("brew cleanup --prune=7", False),
    ("brew cleanup --prune=all", False),
    ("brew cleanup --dry-run", False),
    ("brew cleanup -n", False),
    ("brew cleanup --scrub", False),
    ("brew cleanup -s", False),
    ("brew cleanup --prune-prefix", False),
    #
    # --- brew autoremove (removes orphaned dependencies) ---
    #
    ("brew autoremove", False),
    ("brew autoremove --dry-run", False),
    ("brew autoremove -n", False),
    #
    # --- brew migrate (migrates renamed packages) ---
    #
    ("brew migrate python", False),
    ("brew migrate --force python", False),
    ("brew migrate -f python", False),
    ("brew migrate --dry-run python", False),
    ("brew migrate -n python", False),
    ("brew migrate --formula python", False),
    ("brew migrate --cask firefox", False),
    #
    # --- brew postinstall (runs post-install scripts) ---
    #
    ("brew postinstall python", False),
    ("brew post_install python", False),
    #
    # --- brew edit (opens editor for formula) ---
    #
    ("brew edit", False),
    ("brew edit python", False),
    ("brew edit --formula python", False),
    ("brew edit --cask firefox", False),
    ("brew edit --print-path python", False),
    #
    # --- brew create (creates new formula) ---
    #
    ("brew create https://example.com/package.tar.gz", False),
    ("brew create --no-fetch https://example.com/package.tar.gz", False),
    #
    # --- brew gist-logs (uploads logs to GitHub) ---
    #
    ("brew gist-logs python", False),
    ("brew gist-logs --private python", False),
    ("brew gist-logs -p python", False),
    ("brew gist-logs --new-issue python", False),
    ("brew gist-logs -n python", False),
    #
    # --- brew services (manages services) ---
    #
    ("brew services", False),  # With no args shows list, but services can mutate
    ("brew services list", False),  # list alone might be safe but consistency
    ("brew services info postgresql", False),
    ("brew services start postgresql", False),
    ("brew services stop postgresql", False),
    ("brew services restart postgresql", False),
    ("brew services run postgresql", False),
    ("brew services kill postgresql", False),
    ("brew services cleanup", False),
    ("brew services start --all", False),
    ("brew services stop --all", False),
    ("brew services restart --all", False),
    #
    # --- brew bundle (Brewfile management) ---
    #
    ("brew bundle", False),
    ("brew bundle install", False),
    ("brew bundle upgrade", False),
    ("brew bundle dump", False),
    ("brew bundle dump --force", False),
    ("brew bundle dump --describe", False),
    ("brew bundle cleanup", False),
    ("brew bundle cleanup --force", False),
    ("brew bundle check", True),  # Check is read-only
    ("brew bundle check --verbose", True),
    ("brew bundle list", True),  # List is read-only
    ("brew bundle list --all", True),
    ("brew bundle list --formula", True),
    ("brew bundle list --cask", True),
    ("brew bundle edit", False),
    ("brew bundle add python", False),
    ("brew bundle remove python", False),
    ("brew bundle exec python script.py", False),
    ("brew bundle sh", False),
    ("brew bundle env", False),
    #
    # --- brew developer (developer mode) ---
    #
    ("brew developer", False),
    ("brew developer on", False),
    ("brew developer off", False),
    #
    # --- brew readall (validates formulae) ---
    #
    ("brew readall", False),
    ("brew readall --aliases", False),
    #
    # --- brew audit (audits formulae - developer) ---
    #
    ("brew audit", False),
    ("brew audit python", False),
    ("brew audit --strict python", False),
    ("brew audit --new python", False),
    #
    # --- brew bottle (creates bottles - developer) ---
    #
    ("brew bottle python", False),
    ("brew bottle --no-rebuild python", False),
    #
    # --- brew bump (updates version - developer) ---
    #
    ("brew bump python", False),
    ("brew bump-formula-pr python", False),
    ("brew bump-cask-pr firefox", False),
    #
    # --- brew test (runs tests - developer) ---
    #
    ("brew test python", False),
    ("brew test --HEAD python", False),
    #
    # --- brew style (style checks - can modify with --fix) ---
    #
    ("brew style", False),
    ("brew style --fix", False),
    ("brew style python", False),
    #
    # --- brew vendor-install (vendor installation) ---
    #
    ("brew vendor-install", False),
    #
    # ==========================================================================
    # Edge cases and special handling
    # ==========================================================================
    #
    # --- Help flags on any command ---
    #
    ("brew install --help", True),
    ("brew install -h", True),
    ("brew uninstall --help", True),
    ("brew upgrade --help", True),
    ("brew tap --help", True),
    ("brew services --help", True),
    ("brew bundle --help", True),
    #
    # --- No arguments ---
    #
    ("brew", False),  # Just "brew" with no args shows help but could be unsafe
    #
    # --- Unknown commands (should be unsafe by default) ---
    #
    ("brew unknown-command", False),
    ("brew some-new-command arg1 arg2", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_brew_command(command: str, expected: bool):
    """Test brew command safety classification."""
    result = parse_commands(command)
    assert result.commands is not None, f"Failed to parse: {command}"
    assert len(result.commands) == 1, f"Expected 1 command, got {len(result.commands)}"
    actual = is_command_safe(result.commands[0])
    assert actual == expected, f"Command '{command}': expected {expected}, got {actual}"
