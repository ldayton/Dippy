"""Dippy configuration system v1."""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import structlog

USER_CONFIG = Path.home() / ".dippy" / "config"
PROJECT_CONFIG_NAME = ".dippy"
ENV_CONFIG = "DIPPY_CONFIG"


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


# === Config Loading ===


def _find_project_config(cwd: Path) -> Path | None:
    """Walk up from cwd to find .dippy file."""
    current = cwd.resolve()
    while True:
        candidate = current / PROJECT_CONFIG_NAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:  # reached root
            return None
        current = parent


def _merge_configs(base: Config, overlay: Config) -> Config:
    """Merge overlay config into base. Rules concatenate, settings override."""
    return replace(
        base,
        rules=base.rules + overlay.rules,
        redirect_rules=base.redirect_rules + overlay.redirect_rules,
        sticky_session=overlay.sticky_session
        if overlay.sticky_session
        else base.sticky_session,
        suggest_after=overlay.suggest_after
        if overlay.suggest_after is not None
        else base.suggest_after,
        default=overlay.default if overlay.default != "ask" else base.default,
        verbose=overlay.verbose if overlay.verbose else base.verbose,
        log=overlay.log if overlay.log is not None else base.log,
        log_full=overlay.log_full if overlay.log_full else base.log_full,
        warn_banner=overlay.warn_banner if overlay.warn_banner else base.warn_banner,
        disabled=overlay.disabled if overlay.disabled else base.disabled,
    )


def load_config(cwd: Path) -> Config:
    """Load config from ~/.dippy/config, .dippy, and $DIPPY_CONFIG. Last match wins."""
    config = Config()

    # 1. User config
    if USER_CONFIG.is_file():
        user_config = parse_config(USER_CONFIG.read_text())
        config = _merge_configs(config, user_config)

    # 2. Project config (walk up from cwd)
    project_path = _find_project_config(cwd)
    if project_path is not None:
        project_config = parse_config(project_path.read_text())
        config = _merge_configs(config, project_config)

    # 3. Env override (highest precedence)
    env_path = os.environ.get(ENV_CONFIG)
    if env_path:
        env_config_path = Path(env_path).expanduser()
        if env_config_path.is_file():
            env_config = parse_config(env_config_path.read_text())
            config = _merge_configs(config, env_config)

    return config


def parse_config(text: str) -> Config:
    """Parse config text into Config object. Raises on syntax errors."""
    # TODO: implement parser
    # - parse lines, skip comments and blanks
    # - allow/ask <glob> ["message"]
    # - allow-redirect/ask-redirect <glob> ["message"]
    # - set <key> [value]
    # - fail hard on unknown directives
    raise NotImplementedError("parse_config not yet implemented")


# === Matching ===


def match_command(command: str, config: Config, cwd: Path) -> Match | None:
    """Match command against rules. Resolves relative paths against cwd."""
    # TODO: implement matching
    # - parse command to extract base command
    # - resolve relative paths against cwd
    # - iterate rules, last match wins
    raise NotImplementedError("match_command not yet implemented")


def match_redirect(target: str, config: Config, cwd: Path) -> Match | None:
    """Match redirect target against rules. Resolves relative paths against cwd."""
    # TODO: implement matching
    # - resolve relative paths against cwd
    # - iterate redirect_rules, last match wins
    # - use ** glob for recursive matching
    raise NotImplementedError("match_redirect not yet implemented")


# === Logging ===

_logger: structlog.BoundLogger | None = None


def configure_logging(config: Config) -> None:
    """Configure logging based on config settings. Call once at startup."""
    global _logger
    if config.log is None:
        _logger = None
        return

    # Ensure log directory exists
    config.log.parent.mkdir(parents=True, exist_ok=True)

    # Configure structlog for JSON output to file
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Create file handler logger
    _logger = structlog.get_logger()
    _logger = _logger.bind(_log_path=str(config.log), _log_full=config.log_full)


def log_decision(
    decision: str,
    cmd: str,
    rule: str | None = None,
    message: str | None = None,
    command: str | None = None,
) -> None:
    """Log a decision. No-op if logging not configured."""
    if _logger is None:
        return

    log_path = _logger._context.get("_log_path")
    log_full = _logger._context.get("_log_full", False)

    # Build log entry
    entry: dict[str, str | None] = {"decision": decision, "cmd": cmd}
    if rule is not None:
        entry["rule"] = rule
    if message is not None:
        entry["message"] = message
    if log_full and command is not None:
        entry["command"] = command

    # Write JSON line to log file
    if log_path:
        import json
        from datetime import datetime, timezone

        entry["ts"] = datetime.now(timezone.utc).isoformat()
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
