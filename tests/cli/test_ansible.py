"""Test cases for ansible."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Ansible CLI Tools
# ==========================================================================
#
TESTS = [
    # --- ansible (ad-hoc commands) ---
    # Safe: help/version/list-hosts/check mode
    ("ansible --help", True),
    ("ansible -h", True),
    ("ansible --version", True),
    ("ansible all --list-hosts", True),
    ("ansible webservers --list-hosts", True),
    ("ansible all -m ping --check", True),
    ("ansible all -C -m command -a 'uptime'", True),
    ("ansible all --check -m shell -a 'df -h'", True),
    # Unsafe: executing modules/commands on hosts
    ("ansible all -m ping", False),
    ("ansible all -m command -a 'uptime'", False),
    ("ansible all -m shell -a 'df -h'", False),
    ("ansible webservers -m setup", False),
    ("ansible all -b -m apt -a 'name=nginx state=present'", False),
    ("ansible all -i inventory.ini -m ping", False),
    ("ansible all -m debug -a 'var=groups.keys()'", False),
    # --- ansible-playbook ---
    # Safe: help/version/syntax-check/list-*/check mode
    ("ansible-playbook --help", True),
    ("ansible-playbook -h", True),
    ("ansible-playbook --version", True),
    ("ansible-playbook playbook.yml --syntax-check", True),
    ("ansible-playbook playbook.yml --list-hosts", True),
    ("ansible-playbook playbook.yml --list-tasks", True),
    ("ansible-playbook playbook.yml --list-tags", True),
    ("ansible-playbook playbook.yml --check", True),
    ("ansible-playbook playbook.yml -C", True),
    ("ansible-playbook playbook.yml --check --diff", True),
    ("ansible-playbook playbook.yml -C -D", True),
    ("ansible-playbook -i inventory.ini playbook.yml --syntax-check", True),
    # Unsafe: executing playbooks
    ("ansible-playbook playbook.yml", False),
    ("ansible-playbook site.yml -i inventory.ini", False),
    ("ansible-playbook playbook.yml -e 'var=value'", False),
    ("ansible-playbook playbook.yml --tags deploy", False),
    ("ansible-playbook playbook.yml --skip-tags tests", False),
    ("ansible-playbook playbook.yml --start-at-task 'Install nginx'", False),
    ("ansible-playbook playbook.yml --step", False),
    (
        "ansible-playbook playbook.yml --diff",
        False,
    ),  # diff without check still executes
    # --- ansible-vault ---
    # Safe: view/help
    ("ansible-vault --help", True),
    ("ansible-vault -h", True),
    ("ansible-vault view secrets.yml", True),
    ("ansible-vault view --vault-password-file pass.txt secrets.yml", True),
    # Unsafe: create/edit/encrypt/decrypt/rekey
    ("ansible-vault create secrets.yml", False),
    ("ansible-vault create --vault-password-file pass.txt secrets.yml", False),
    ("ansible-vault edit secrets.yml", False),
    ("ansible-vault encrypt secrets.yml", False),
    ("ansible-vault encrypt --vault-password-file pass.txt secrets.yml", False),
    ("ansible-vault encrypt_string", False),
    ("ansible-vault encrypt_string 'secret' --name 'my_secret'", False),
    ("ansible-vault decrypt secrets.yml", False),
    ("ansible-vault rekey secrets.yml", False),
    (
        "ansible-vault rekey --vault-password-file old.txt --new-vault-password-file new.txt secrets.yml",
        False,
    ),
    # --- ansible-galaxy ---
    # Safe: help/list/search/info/verify
    ("ansible-galaxy --help", True),
    ("ansible-galaxy -h", True),
    ("ansible-galaxy role --help", True),
    ("ansible-galaxy collection --help", True),
    ("ansible-galaxy role list", True),
    ("ansible-galaxy role search nginx", True),
    ("ansible-galaxy role search nginx -v", True),
    ("ansible-galaxy role info geerlingguy.nginx", True),
    ("ansible-galaxy collection list", True),
    ("ansible-galaxy collection verify community.general", True),
    # Unsafe: init/install/remove/delete/import/setup/download/build/publish
    ("ansible-galaxy role init my_role", False),
    ("ansible-galaxy role install geerlingguy.nginx", False),
    ("ansible-galaxy role install -r requirements.yml", False),
    ("ansible-galaxy role remove geerlingguy.nginx", False),
    ("ansible-galaxy role delete namespace role_name", False),
    ("ansible-galaxy role import github_user repo_name", False),
    ("ansible-galaxy role setup integration_id github_user secret", False),
    ("ansible-galaxy collection init my_namespace.my_collection", False),
    ("ansible-galaxy collection install community.general", False),
    ("ansible-galaxy collection install -r requirements.yml", False),
    ("ansible-galaxy collection download community.general", False),
    ("ansible-galaxy collection build", False),
    ("ansible-galaxy collection publish ./my_collection-1.0.0.tar.gz", False),
    # --- ansible-inventory ---
    # Safe: list/host/graph (without --output)
    ("ansible-inventory --help", True),
    ("ansible-inventory -h", True),
    ("ansible-inventory --list", True),
    ("ansible-inventory --list -i inventory.ini", True),
    ("ansible-inventory --list --yaml", True),
    ("ansible-inventory --list -y", True),
    ("ansible-inventory --host webserver1", True),
    ("ansible-inventory --graph", True),
    ("ansible-inventory --graph --vars", True),
    ("ansible-inventory --graph all", True),
    # Unsafe: --output writes to file
    ("ansible-inventory --list --output inventory.json", False),
    ("ansible-inventory --list -i hosts --output out.json", False),
    # --- ansible-doc ---
    # All safe (read-only documentation)
    ("ansible-doc --help", True),
    ("ansible-doc -h", True),
    ("ansible-doc -l", True),
    ("ansible-doc --list", True),
    ("ansible-doc -t callback -l", True),
    ("ansible-doc -t connection -l", True),
    ("ansible-doc ping", True),
    ("ansible-doc file", True),
    ("ansible-doc -t callback debug", True),
    ("ansible-doc -s ping", True),
    ("ansible-doc --snippet ping", True),
    ("ansible-doc -j ping", True),
    ("ansible-doc --json ping", True),
    ("ansible-doc -F", True),
    ("ansible-doc --list_files", True),
    # --- ansible-pull ---
    # Safe: list-hosts/check
    ("ansible-pull --help", True),
    ("ansible-pull -h", True),
    ("ansible-pull -U https://github.com/user/repo --list-hosts", True),
    ("ansible-pull -U https://github.com/user/repo --check", True),
    (
        "ansible-pull -U https://github.com/user/repo -C playbook.yml",
        False,
    ),  # -C is checkout, not check!
    # Unsafe: pulls and executes playbooks
    ("ansible-pull -U https://github.com/user/repo", False),
    ("ansible-pull -U https://github.com/user/repo playbook.yml", False),
    ("ansible-pull -U https://github.com/user/repo -C main playbook.yml", False),
    ("ansible-pull -U https://github.com/user/repo -i hosts playbook.yml", False),
    # --- ansible-config ---
    # Safe: list/dump/view/validate
    ("ansible-config --help", True),
    ("ansible-config -h", True),
    ("ansible-config list", True),
    ("ansible-config dump", True),
    ("ansible-config dump --only-changed", True),
    ("ansible-config view", True),
    ("ansible-config validate", True),
    # Unsafe: init creates config file
    ("ansible-config init", False),
    ("ansible-config init --disabled", False),
    # --- ansible-console ---
    # Safe: help/list-hosts
    ("ansible-console --help", True),
    ("ansible-console -h", True),
    ("ansible-console --list-hosts", True),
    ("ansible-console all --list-hosts", True),
    # Unsafe: interactive console for executing tasks
    ("ansible-console", False),
    ("ansible-console all", False),
    ("ansible-console webservers", False),
    ("ansible-console all -i inventory.ini", False),
    # --- ansible-lint ---
    # All safe (read-only linting)
    ("ansible-lint --help", True),
    ("ansible-lint -h", True),
    ("ansible-lint playbook.yml", True),
    ("ansible-lint playbook.yml roles/", True),
    ("ansible-lint -x rule1,rule2 playbook.yml", True),
    ("ansible-lint --exclude-rules rule1 playbook.yml", True),
    ("ansible-lint -o playbook.yml", True),
    ("ansible-lint --offline playbook.yml", True),
    ("ansible-lint -p playbook.yml", True),
    ("ansible-lint --parseable playbook.yml", True),
    ("ansible-lint -r custom_rules/ playbook.yml", True),
    ("ansible-lint .", True),
    # --- ansible-test ---
    # Safe: env/sanity/units
    ("ansible-test --help", True),
    ("ansible-test -h", True),
    ("ansible-test env", True),
    ("ansible-test sanity", True),
    ("ansible-test sanity --test pep8", True),
    ("ansible-test units", True),
    ("ansible-test units --python 3.10", True),
    # Unsafe: integration tests, shell, coverage (can modify state)
    ("ansible-test integration", False),
    ("ansible-test network-integration", False),
    ("ansible-test windows-integration", False),
    ("ansible-test shell", False),
    ("ansible-test coverage", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_ansible(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
