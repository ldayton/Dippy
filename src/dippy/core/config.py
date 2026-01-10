"""Dippy configuration system v1."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Parsed configuration."""

    rules: list[tuple[str, str, str | None]] = field(default_factory=list)
    """Command rules: [('allow'|'ask', glob, message|None), ...]"""

    redirect_rules: list[tuple[str, str, str | None]] = field(default_factory=list)
    """Redirect rules: [('allow'|'ask', glob, message|None), ...]"""

    sticky_session: bool = False
    suggest_after: int | None = None
    default: str = "ask"  # 'allow' | 'ask'
    verbose: bool = False
    log: Path | None = None  # None = no logging
    log_full: bool = False  # log full command (requires log path)
    warn_banner: bool = False
    disabled: bool = False


@dataclass
class Match:
    """Result of matching against config rules."""

    decision: str  # 'allow' | 'ask'
    pattern: str  # the glob pattern that matched
    message: str | None = None  # shown to AI on ask


def load_config(cwd: Path) -> Config:
    """Load config from ~/.dippy/config and .dippy (walk up from cwd). Last match wins."""
    ...


def parse_config(text: str) -> Config:
    """Parse config text into Config object. Raises on syntax errors."""
    ...


def match_command(command: str, config: Config, cwd: Path) -> Match | None:
    """Match command against rules. Resolves relative paths against cwd."""
    ...


def match_redirect(target: str, config: Config, cwd: Path) -> Match | None:
    """Match redirect target against rules. Resolves relative paths against cwd."""
    ...


# === Logging ===

_config: Config | None = None


def configure_logging(config: Config) -> None:
    """Configure logging based on config settings. Call once at startup."""
    global _config
    _config = config
    if config.log is None:
        return
    # TODO: configure structlog to write JSON to config.log
    ...


def log_decision(
    decision: str,
    cmd: str,
    rule: str | None = None,
    message: str | None = None,
    command: str | None = None,
) -> None:
    """Log a decision. No-op if logging not configured."""
    if _config is None or _config.log is None:
        return
    # TODO: structlog output
    # - always: ts, decision, cmd, rule (if set), message (if set)
    # - only if log_full: command
    ...
