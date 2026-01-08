"""
Configuration system for Dippy.

Loads config from:
- ~/.config/dippy/dippy.toml (global defaults)
- .dippy.toml (project override, merged)

Example config:
    # What you want auto-approved
    approve = [
        "mkdir",                      # Simple command
        "git stash",                  # CLI action
        "./scripts/deploy.sh",        # Script (relative to project root)
        "re:^make (lint|test|build)", # Regex (explicit re: prefix)
    ]

    # Override: always ask, even if rules would approve
    confirm = [
        "docker run",
        "git push --force",
    ]

    # Map aliases to CLI handlers
    aliases = { k = "kubectl", tf = "terraform", g = "git" }
"""

import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CURRENT_VERSION = 1


@dataclass
class Config:
    """Dippy configuration."""

    version: int = CURRENT_VERSION
    approve: list[str] = field(default_factory=list)
    confirm: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    project_root: Optional[Path] = None

    def merge(self, other: "Config") -> "Config":
        """Merge another config into this one (other takes precedence)."""
        return Config(
            version=max(self.version, other.version),
            approve=self.approve + other.approve,
            confirm=self.confirm + other.confirm,
            aliases={**self.aliases, **other.aliases},
            project_root=other.project_root or self.project_root,
        )


def load_config(cwd: Optional[str] = None) -> Config:
    """
    Load config from global and project locations.

    Args:
        cwd: Current working directory (for finding project config)

    Returns:
        Merged config (project overrides global)
    """
    config = Config()

    # Load global config
    global_path = Path.home() / ".config" / "dippy" / "dippy.toml"
    if global_path.exists():
        global_config = _load_config_file(global_path)
        config = config.merge(global_config)

    # Load project config
    if cwd:
        project_path = _find_project_config(Path(cwd))
        if project_path:
            project_config = _load_config_file(project_path)
            project_config.project_root = project_path.parent
            config = config.merge(project_config)

    return config


def _load_config_file(path: Path) -> Config:
    """Load a single config file."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        version = data.get("version", 1)
        if version > CURRENT_VERSION:
            logging.warning(
                f"Config {path} has version {version}, "
                f"but dippy only supports version {CURRENT_VERSION}. Skipping."
            )
            return Config()

        return Config(
            version=version,
            approve=data.get("approve", []),
            confirm=data.get("confirm", []),
            aliases=data.get("aliases", {}),
        )
    except Exception as e:
        logging.warning(f"Failed to load config {path}: {e}")
        return Config()


def _find_project_config(cwd: Path) -> Optional[Path]:
    """Walk up from cwd to find .dippy.toml."""
    current = cwd.resolve()
    while current != current.parent:
        config_path = current / ".dippy.toml"
        if config_path.exists():
            return config_path
        current = current.parent
    return None


def matches_pattern(
    command: str,
    pattern: str,
    tokens: list[str],
    project_root: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> bool:
    """
    Check if a command matches a config pattern.

    Pattern types:
    - "re:..." - Regex match against full command
    - "*.sh" or path with / - Script path (resolved against project root)
    - "git stash" - Prefix match on tokens
    - "mkdir" - Simple command match
    """
    # Regex pattern
    if pattern.startswith("re:"):
        regex = pattern[3:]
        try:
            return bool(re.match(regex, command))
        except re.error:
            return False

    # Script path (contains / or ends with script extension)
    script_extensions = (".sh", ".bash", ".py", ".rb", ".pl")
    if "/" in pattern or pattern.endswith(script_extensions):
        return _matches_script_path(command, pattern, tokens, project_root, cwd)

    # Token prefix match
    pattern_tokens = pattern.split()
    if len(pattern_tokens) <= len(tokens):
        return tokens[: len(pattern_tokens)] == pattern_tokens

    return False


def _matches_script_path(
    command: str,
    pattern: str,
    tokens: list[str],
    project_root: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> bool:
    """
    Check if command invokes a script matching the pattern.

    Resolves both pattern and command to absolute paths to ensure
    we're matching the exact file, not just the basename.
    """
    if not tokens:
        return False

    cmd_path_str = tokens[0]

    # Resolve pattern to absolute path
    if pattern.startswith("/"):
        pattern_path = Path(pattern).resolve()
    elif project_root:
        pattern_path = (project_root / pattern).resolve()
    else:
        # No project root, can't safely resolve relative pattern
        return False

    # Resolve command path to absolute
    if cmd_path_str.startswith("/"):
        cmd_path = Path(cmd_path_str).resolve()
    elif cwd:
        cmd_path = (cwd / cmd_path_str).resolve()
    else:
        # No cwd, can't resolve relative command
        return False

    # Match resolved paths
    return cmd_path == pattern_path
