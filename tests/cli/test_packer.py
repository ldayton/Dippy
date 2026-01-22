"""Test cases for packer."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Packer - HashiCorp tool for building machine images
# ==========================================================================
#
TESTS = [
    # Safe - help and version
    ("packer --help", True),
    ("packer -help", True),
    ("packer --version", True),
    ("packer version", True),
    # Safe - validate (checks template without building)
    ("packer validate template.json", True),
    ("packer validate -syntax-only template.json", True),
    ("packer validate -var 'key=value' template.json", True),
    ("packer validate -var-file=vars.json template.json", True),
    ("packer validate -except=amazon-ebs template.json", True),
    ("packer validate -only=docker template.json", True),
    ("packer validate -machine-readable template.json", True),
    ("packer validate .", True),
    # Safe - inspect (shows template components without execution)
    ("packer inspect template.json", True),
    ("packer inspect -machine-readable template.json", True),
    ("packer inspect .", True),
    # Safe - fmt with check/diff/write=false (read-only)
    ("packer fmt -check template.pkr.hcl", True),
    ("packer fmt -diff template.pkr.hcl", True),
    ("packer fmt -write=false template.pkr.hcl", True),
    ("packer fmt -check -diff template.pkr.hcl", True),
    ("packer fmt -check -recursive .", True),
    # Safe - console (interactive testing, doesn't build)
    ("packer console", True),
    ("packer console template.json", True),
    ("packer console -var 'key=value'", True),
    ("packer console -var-file=vars.json", True),
    # Safe - plugins subcommands (read-only)
    ("packer plugins installed", True),
    ("packer plugins required template.json", True),
    # Unsafe - build (creates machine images - major external effect)
    ("packer build template.json", False),
    ("packer build -var 'key=value' template.json", False),
    ("packer build -var-file=vars.json template.json", False),
    ("packer build -only=docker template.json", False),
    ("packer build -except=amazon-ebs template.json", False),
    ("packer build -force template.json", False),
    ("packer build -on-error=abort template.json", False),
    ("packer build -parallel-builds=1 template.json", False),
    ("packer build -debug template.json", False),
    ("packer build .", False),
    # Unsafe - init (installs plugins - downloads external content)
    ("packer init template.json", False),
    ("packer init -upgrade template.json", False),
    ("packer init -force template.json", False),
    ("packer init .", False),
    # Unsafe - fix (modifies templates)
    ("packer fix template.json", False),
    ("packer fix -validate=true template.json", False),
    ("packer fix -validate=false template.json", False),
    # Unsafe - fmt without check flags (modifies files)
    ("packer fmt template.pkr.hcl", False),
    ("packer fmt -recursive .", False),
    ("packer fmt .", False),
    # Unsafe - hcl2_upgrade (writes new files)
    ("packer hcl2_upgrade template.json", False),
    ("packer hcl2_upgrade -output-file=out.pkr.hcl template.json", False),
    ("packer hcl2_upgrade -with-annotations template.json", False),
    # Unsafe - plugins install/remove (modifies system)
    ("packer plugins install github.com/hashicorp/amazon", False),
    ("packer plugins remove github.com/hashicorp/amazon", False),
    # Edge cases
    ("packer", False),  # No subcommand
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_packer(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
