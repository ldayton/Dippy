"""
CLI-specific command handlers for Dippy.

Each handler module exports:
- check(tokens: list[str]) -> bool
    Returns True to approve, False to ask user.
"""

import importlib
from functools import lru_cache
from typing import Optional, Protocol


class CLIHandler(Protocol):
    """Protocol for CLI handler modules."""

    def check(self, tokens: list[str]) -> bool:
        """Check if command should be approved.

        Returns True to approve, False to ask user.
        """
        ...


# How many tokens to include in description (base + action + ...)
# Default is 2 (e.g., "git status", "docker ps")
DESCRIPTION_DEPTH = {
    "aws": 3,      # aws s3 ls
    "gcloud": 3,   # gcloud compute instances
    "gsutil": 2,   # gsutil ls
    "az": 3,       # az vm list
}


def get_description(tokens: list[str], handler_name: str = None) -> str:
    """Compute description from tokens based on handler type."""
    if not tokens:
        return "unknown"
    depth = DESCRIPTION_DEPTH.get(handler_name or tokens[0], 2)
    return " ".join(tokens[:depth])


# Known CLI handlers - maps command name to module name
KNOWN_HANDLERS = {
    "git": "git",
    "aws": "aws",
    "kubectl": "kubectl",
    "k": "kubectl",  # Common alias
    "gcloud": "gcloud",
    "gsutil": "gcloud",
    "terraform": "terraform",
    "tf": "terraform",
    "docker": "docker",
    "docker-compose": "docker",
    "podman": "docker",  # Similar interface
    "podman-compose": "docker",
    "az": "azure",
    "brew": "brew",
    "npm": "npm",
    "yarn": "npm",
    "pnpm": "npm",
    "pip": "pip",
    "pip3": "pip",
    "cargo": "cargo",
    "gh": "gh",
    "curl": "curl",
    "xargs": "xargs",
    "find": "find",
    "sed": "sed",
    "sort": "sort",
    "wget": "wget",
    "tar": "tar",
    "unzip": "7z",
    "7z": "7z",
    "7za": "7z",
    "7zr": "7z",
    "7zz": "7z",
    "cdk": "cdk",
    "auth0": "auth0",
    "bash": "shell",
    "sh": "shell",
    "zsh": "shell",
    "dash": "shell",
    "ksh": "shell",
    "fish": "shell",
    "awk": "awk",
    "gawk": "awk",
    "mawk": "awk",
    "nawk": "awk",
    "ip": "ip",
    "ifconfig": "ifconfig",
    "uv": "uv",
    "uvx": "uv",
    "openssl": "openssl",
    "env": "env",
    "journalctl": "journalctl",
    "dmesg": "dmesg",
    "ruff": "ruff",
    "helm": "helm",
    "ansible": "ansible",
    "ansible-playbook": "ansible",
    "ansible-vault": "ansible",
    "ansible-galaxy": "ansible",
    "ansible-inventory": "ansible",
    "ansible-doc": "ansible",
    "ansible-pull": "ansible",
    "ansible-config": "ansible",
    "ansible-console": "ansible",
    "ansible-lint": "ansible",
    "ansible-test": "ansible",
}


def get_handler(command_name: str) -> Optional[CLIHandler]:
    """
    Get the handler module for a CLI command.
    
    Returns None if no handler exists for the command.
    """
    # Check if we have a handler for this command
    module_name = KNOWN_HANDLERS.get(command_name)
    if not module_name:
        return None
    
    return _load_handler(module_name)


@lru_cache(maxsize=32)
def _load_handler(module_name: str) -> Optional[CLIHandler]:
    """Load a CLI handler module by name (cached within process)."""
    try:
        return importlib.import_module(f".{module_name}", package="dippy.cli")
    except ImportError:
        return None


def list_handlers() -> list[str]:
    """List all available CLI handler module names."""
    return sorted(set(KNOWN_HANDLERS.values()))
