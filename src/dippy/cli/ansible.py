"""
Ansible command handlers for Dippy.

Handles ansible, ansible-playbook, ansible-vault, ansible-galaxy,
ansible-inventory, ansible-doc, ansible-pull, ansible-config,
ansible-console, ansible-lint, and ansible-test commands.
"""

from dippy.cli import Classification

COMMANDS = [
    "ansible",
    "ansible-playbook",
    "ansible-vault",
    "ansible-galaxy",
    "ansible-inventory",
    "ansible-doc",
    "ansible-pull",
    "ansible-config",
    "ansible-console",
    "ansible-lint",
    "ansible-test",
]

# Commands that are entirely safe (read-only)
SAFE_COMMANDS = frozenset(
    {
        "ansible-doc",  # Documentation viewer
        "ansible-lint",  # Linter (read-only)
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify ansible command."""
    if len(tokens) < 1:
        return Classification("ask", description="ansible")

    cmd = tokens[0]

    # Check for help/version flags anywhere
    if "-h" in tokens or "--help" in tokens or "--version" in tokens:
        return Classification("approve", description=cmd)

    # Entirely safe commands
    if cmd in SAFE_COMMANDS:
        return Classification("approve", description=cmd)

    # Route to specific handlers - returns (safe, action) tuple
    if cmd == "ansible":
        safe, action = _check_ansible(tokens), "run"
    elif cmd == "ansible-playbook":
        safe, action = _check_ansible_playbook(tokens), "run"
    elif cmd == "ansible-vault":
        safe, action = _check_ansible_vault(tokens), _get_vault_action(tokens)
    elif cmd == "ansible-galaxy":
        safe, action = _check_ansible_galaxy(tokens), _get_galaxy_action(tokens)
    elif cmd == "ansible-inventory":
        safe, action = _check_ansible_inventory(tokens), "write"
    elif cmd == "ansible-pull":
        safe, action = _check_ansible_pull(tokens), "run"
    elif cmd == "ansible-config":
        safe, action = _check_ansible_config(tokens), _get_config_action(tokens)
    elif cmd == "ansible-console":
        safe, action = _check_ansible_console(tokens), "interactive"
    elif cmd == "ansible-test":
        safe, action = _check_ansible_test(tokens), _get_test_action(tokens)
    else:
        safe, action = False, "run"

    if safe:
        return Classification("approve", description=cmd)
    return Classification("ask", description=f"{cmd} {action}")


def _check_ansible(tokens: list[str]) -> bool:
    """Check ansible ad-hoc command safety.

    Safe if: --list-hosts or --check/-C mode
    """
    if "--list-hosts" in tokens:
        return True
    if "--check" in tokens or "-C" in tokens:
        return True
    return False


def _check_ansible_playbook(tokens: list[str]) -> bool:
    """Check ansible-playbook command safety.

    Safe if: --syntax-check, --list-hosts, --list-tasks, --list-tags, or --check/-C
    """
    safe_flags = {
        "--syntax-check",
        "--list-hosts",
        "--list-tasks",
        "--list-tags",
        "--check",
        "-C",
    }
    for flag in safe_flags:
        if flag in tokens:
            return True
    return False


def _check_ansible_vault(tokens: list[str]) -> bool:
    """Check ansible-vault command safety.

    Safe if: view subcommand only
    """
    if len(tokens) < 2:
        return False

    # Find subcommand (skip flags)
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        # First non-flag is the subcommand
        return token == "view"

    return False


def _check_ansible_galaxy(tokens: list[str]) -> bool:
    """Check ansible-galaxy command safety.

    Safe if: list, search, info, verify actions
    """
    if len(tokens) < 2:
        return False

    # Find type (role/collection) and action
    type_token = None
    action_token = None

    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        if type_token is None:
            type_token = token
        elif action_token is None:
            action_token = token
            break

    if type_token not in ("role", "collection"):
        return False

    safe_actions = {"list", "search", "info", "verify"}
    return action_token in safe_actions


def _check_ansible_inventory(tokens: list[str]) -> bool:
    """Check ansible-inventory command safety.

    Safe if: --list, --host, or --graph WITHOUT --output
    """
    # --output makes it unsafe (writes to file)
    if "--output" in tokens:
        return False

    safe_flags = {"--list", "--host", "--graph"}
    for flag in safe_flags:
        if flag in tokens:
            return True

    # Check for --host with value
    for i, token in enumerate(tokens):
        if token == "--host":
            return True

    return False


def _check_ansible_pull(tokens: list[str]) -> bool:
    """Check ansible-pull command safety.

    Safe if: --list-hosts or --check (NOT -C which is --checkout)
    """
    if "--list-hosts" in tokens:
        return True
    if "--check" in tokens:
        return True
    return False


def _check_ansible_config(tokens: list[str]) -> bool:
    """Check ansible-config command safety.

    Safe if: list, dump, view, validate subcommands
    """
    if len(tokens) < 2:
        return False

    # Find subcommand
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        safe_actions = {"list", "dump", "view", "validate"}
        return token in safe_actions

    return False


def _check_ansible_console(tokens: list[str]) -> bool:
    """Check ansible-console command safety.

    Safe if: --list-hosts only
    """
    return "--list-hosts" in tokens


def _check_ansible_test(tokens: list[str]) -> bool:
    """Check ansible-test command safety.

    Safe if: env, sanity, units subcommands
    """
    if len(tokens) < 2:
        return False

    # Find subcommand
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        safe_actions = {"env", "sanity", "units"}
        return token in safe_actions

    return False


def _get_subcommand(tokens: list[str]) -> str:
    """Extract first non-flag token as subcommand."""
    for token in tokens[1:]:
        if not token.startswith("-"):
            return token
    return ""


def _get_vault_action(tokens: list[str]) -> str:
    """Get ansible-vault action (encrypt, decrypt, view, etc.)."""
    return _get_subcommand(tokens) or "run"


def _get_galaxy_action(tokens: list[str]) -> str:
    """Get ansible-galaxy action (install, list, etc.)."""
    # Format: ansible-galaxy role/collection action
    parts = [t for t in tokens[1:] if not t.startswith("-")]
    if len(parts) >= 2:
        return parts[1]  # action is second non-flag
    return "run"


def _get_config_action(tokens: list[str]) -> str:
    """Get ansible-config action."""
    return _get_subcommand(tokens) or "run"


def _get_test_action(tokens: list[str]) -> str:
    """Get ansible-test action."""
    return _get_subcommand(tokens) or "run"
