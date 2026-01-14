"""Dippy configuration system v1."""

import fnmatch
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

# Cache home directory at module load - fails fast if HOME is unset
_HOME = Path.home()

USER_CONFIG = _HOME / ".dippy" / "config"
PROJECT_CONFIG_NAME = ".dippy"
ENV_CONFIG = "DIPPY_CONFIG"


class ConfigError(Exception):
    """Raised when config loading fails due to I/O or parse errors."""

    pass


# Config scopes in priority order (lowest to highest)
SCOPE_USER = "user"
SCOPE_PROJECT = "project"
SCOPE_ENV = "env"


@dataclass
class Rule:
    """A single config rule with origin tracking."""

    decision: str  # 'allow' | 'ask' | 'deny'
    pattern: str
    message: str | None = None
    source: str | None = None  # file path
    scope: str | None = None  # user/project/env


@dataclass
class Config:
    """Parsed configuration."""

    rules: list[Rule] = field(default_factory=list)
    """Command rules in load order."""

    redirect_rules: list[Rule] = field(default_factory=list)
    """Redirect rules in load order."""

    default: str = "ask"  # 'allow' | 'ask'
    log: Path | None = None  # None = no logging
    log_full: bool = False  # log full command (requires log path)


@dataclass
class Match:
    """Result of matching against config rules."""

    decision: str  # 'allow' | 'ask' | 'deny'
    pattern: str  # the glob pattern that matched
    message: str | None = None  # shown to AI on ask/deny
    source: str | None = None  # file path where rule was defined
    scope: str | None = None  # user/project/env


@dataclass
class SimpleCommand:
    """A simple command extracted from parsed bash.

    This is the intermediate representation passed to the rule engine.
    Dippy parses raw bash with Parable, walks the AST, and constructs
    SimpleCommand instances for each command node.
    """

    words: list[str]
    """Command words, e.g. ["git", "add", "."]."""

    redirects: list[str] = field(default_factory=list)
    """Redirect target paths, e.g. ["/tmp/log.txt", "~/.cache/out"]."""


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
    """Merge overlay config into base. Rules accumulate in order, settings override."""
    return replace(
        base,
        # Rules accumulate in load order (like git)
        rules=base.rules + overlay.rules,
        redirect_rules=base.redirect_rules + overlay.redirect_rules,
        # Settings: overlay wins if set
        default=overlay.default if overlay.default != "ask" else base.default,
        log=overlay.log if overlay.log is not None else base.log,
        log_full=overlay.log_full if overlay.log_full else base.log_full,
    )


def _tag_rules(config: Config, source: str, scope: str) -> Config:
    """Tag all rules in config with source file and scope."""
    return replace(
        config,
        rules=[replace(r, source=source, scope=scope) for r in config.rules],
        redirect_rules=[
            replace(r, source=source, scope=scope) for r in config.redirect_rules
        ],
    )


def _load_config_file(path: Path) -> Config:
    """Read and parse a config file. Raises ConfigError on I/O failure."""
    try:
        text = path.read_text()
    except PermissionError:
        raise ConfigError(f"permission denied reading config: {path}") from None
    except OSError as e:
        raise ConfigError(f"cannot read config {path}: {e}") from None
    return parse_config(text, source=str(path))


def load_config(cwd: Path) -> Config:
    """Load config from ~/.dippy/config, .dippy, and $DIPPY_CONFIG.

    Raises ConfigError if any config file exists but cannot be read or parsed.
    Missing files are silently skipped.
    """
    config = Config()

    # 1. User config (lowest priority)
    try:
        if USER_CONFIG.is_file():
            user_config = _load_config_file(USER_CONFIG)
            user_config = _tag_rules(user_config, str(USER_CONFIG), SCOPE_USER)
            config = _merge_configs(config, user_config)
    except PermissionError:
        raise ConfigError(f"permission denied accessing {USER_CONFIG}") from None

    # 2. Project config (walk up from cwd)
    project_path = _find_project_config(cwd)
    if project_path is not None:
        project_config = _load_config_file(project_path)
        project_config = _tag_rules(project_config, str(project_path), SCOPE_PROJECT)
        config = _merge_configs(config, project_config)

    # 3. Env override (highest priority)
    env_path = os.environ.get(ENV_CONFIG)
    if env_path:
        env_config_path = Path(env_path).expanduser()
        try:
            if env_config_path.is_file():
                env_config = _load_config_file(env_config_path)
                env_config = _tag_rules(env_config, str(env_config_path), SCOPE_ENV)
                config = _merge_configs(config, env_config)
        except PermissionError:
            raise ConfigError(
                f"permission denied accessing {env_config_path}"
            ) from None

    return config


def parse_config(text: str, source: str | None = None) -> Config:
    """Parse config text into Config object. Logs and skips invalid lines."""
    import logging

    rules: list[Rule] = []
    redirect_rules: list[Rule] = []
    settings: dict[str, bool | int | str | Path] = {}
    prefix = f"{source}: " if source else ""

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split(None, 1)
        directive = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        try:
            if directive == "allow":
                if not rest:
                    raise ValueError("requires a pattern")
                rules.append(Rule("allow", rest))

            elif directive == "ask":
                if not rest:
                    raise ValueError("requires a pattern")
                pattern, message = _extract_message(rest)
                rules.append(Rule("ask", pattern, message=message))

            elif directive == "deny":
                if not rest:
                    raise ValueError("requires a pattern")
                pattern, message = _extract_message(rest)
                rules.append(Rule("deny", pattern, message=message))

            elif directive == "allow-redirect":
                if not rest:
                    raise ValueError("requires a pattern")
                redirect_rules.append(Rule("allow", rest))

            elif directive == "ask-redirect":
                if not rest:
                    raise ValueError("requires a pattern")
                pattern, message = _extract_message(rest)
                redirect_rules.append(Rule("ask", pattern, message=message))

            elif directive == "deny-redirect":
                if not rest:
                    raise ValueError("requires a pattern")
                pattern, message = _extract_message(rest)
                redirect_rules.append(Rule("deny", pattern, message=message))

            elif directive == "set":
                _apply_setting(settings, rest)

            else:
                raise ValueError(f"unknown directive '{directive}'")

        except ValueError as e:
            logging.warning(f"{prefix}line {lineno}: {e} (skipped)")

    return Config(
        rules=rules,
        redirect_rules=redirect_rules,
        default=settings.get("default", "ask"),
        log=settings.get("log"),
        log_full=settings.get("log_full", False),
    )


def _unescape(s: str) -> str:
    """Unescape backslash sequences in a message string."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char in ('"', "\\"):
                result.append(next_char)
                i += 2
                continue
        result.append(s[i])
        i += 1
    return "".join(result)


def _extract_message(s: str) -> tuple[str, str | None]:
    """Extract pattern and optional quoted message from string.

    Message is extracted only if:
    - String ends with unescaped "
    - There's an opening " preceded by whitespace

    Returns (pattern, message) where message may be None.
    """
    s = s.rstrip()
    if not s.endswith('"'):
        return s, None

    # Count trailing backslashes to check if quote is escaped
    j = len(s) - 2
    num_bs = 0
    while j >= 0 and s[j] == "\\":
        num_bs += 1
        j -= 1
    if num_bs % 2 == 1:
        return s, None  # Trailing quote is escaped

    # Find opening quote (must be preceded by whitespace)
    i = len(s) - 2
    while i >= 0:
        if s[i] == '"' and (i == 0 or s[i - 1].isspace()):
            message = _unescape(s[i + 1 : -1])
            pattern = s[:i].rstrip()
            if not pattern:
                raise ValueError("pattern required before message")
            return pattern, message
        i -= 1

    return s, None  # No valid opening quote, treat as pattern


def _apply_setting(settings: dict[str, bool | int | str | Path], rest: str) -> None:
    """Parse and apply a 'set' directive. Raises ValueError on invalid setting."""
    if not rest:
        raise ValueError("'set' requires a setting name")

    parts = rest.split(None, 1)
    key = parts[0].lower()
    value = parts[1] if len(parts) > 1 else None
    key_normalized = key.replace("-", "_")

    # Boolean settings (no value required)
    if key_normalized in ("log_full",):
        if value is not None:
            raise ValueError(f"'{key}' takes no value")
        settings[key_normalized] = True

    # Choice settings
    elif key_normalized == "default":
        if value not in ("allow", "ask"):
            raise ValueError(f"'default' must be 'allow' or 'ask', got '{value}'")
        settings[key_normalized] = value

    # Path settings
    elif key_normalized == "log":
        if value is None:
            raise ValueError("'log' requires a path")
        settings[key_normalized] = Path(value).expanduser()

    else:
        raise ValueError(f"unknown setting '{key}'")


# === Matching ===


def _expand_path(
    path: str, cwd: Path, *, strip_trailing_slash: bool = False, is_path: bool = False
) -> str:
    """Expand a path-like string to an absolute path.

    - ~/... expands to home directory
    - Relative paths (./foo, ../bar, foo/bar) resolve against cwd
    - Absolute paths returned as-is
    - Non-path tokens returned unchanged unless is_path=True

    Args:
        path: The path string to expand
        cwd: Working directory for resolving relative paths
        strip_trailing_slash: If True, strip trailing slashes from result
        is_path: If True, treat as a path even without path indicators (for redirects)
    """
    if strip_trailing_slash:
        path = path.rstrip("/")
    # ~/... expands to home
    if path.startswith("~/"):
        return str(_HOME) + path[1:]
    # Already absolute
    if path.startswith("/"):
        return path
    # Relative path - resolve against cwd
    if is_path or "/" in path or path.startswith("./") or path.startswith(".."):
        return str((cwd / path).resolve())
    # Non-path token (e.g., "git", "node")
    return path


def _normalize_token(token: str, cwd: Path) -> str:
    """Normalize a single token in a command. Delegates to _expand_path."""
    return _expand_path(token, cwd, strip_trailing_slash=False)


def _normalize_words(words: list[str], cwd: Path) -> str:
    """Normalize paths in command words and join into a string for matching."""
    return " ".join(_normalize_token(w, cwd) for w in words)


def _normalize_pattern(pattern: str, cwd: Path) -> str:
    """Normalize paths in a pattern against cwd.

    Splits pattern on spaces (preserving glob chars), normalizes path-like
    tokens, rejoins. This allows patterns like 'node bin/*' to expand to
    'node /cwd/bin/*'.
    """
    tokens = pattern.split()
    return " ".join(_normalize_token(t, cwd) for t in tokens)


def _normalize_path(path: str, cwd: Path) -> str:
    """Normalize a redirect target path. Delegates to _expand_path."""
    return _expand_path(path, cwd, strip_trailing_slash=True, is_path=True)


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Convert a glob pattern with ** support to a regex.

    ** matches zero or more path components (including /)
    * matches anything except /
    ? matches any single character except /
    [abc] matches character class
    """
    regex = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # ** - matches anything including /
                regex.append(".*")
                i += 2
                # Skip trailing / after **
                if i < n and pattern[i] == "/":
                    regex.append("/?")
                    i += 1
            else:
                # * - matches anything except /
                regex.append("[^/]*")
                i += 1
        elif c == "?":
            regex.append("[^/]")
            i += 1
        elif c == "[":
            # Character class - find the closing ]
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                # Unclosed bracket, treat as literal
                regex.append(re.escape(c))
                i += 1
            else:
                # Convert [!...] to [^...]
                cls = pattern[i + 1 : j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                regex.append(f"[{cls}]")
                i = j + 1
        else:
            regex.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(regex) + "$")


def _glob_match(text: str, pattern: str) -> bool:
    """Match text against a glob pattern with ** support.

    For patterns without **, uses fnmatch (faster).
    For patterns with **, converts to regex for proper recursive matching:
    - ** matches zero or more directories
    - foo/**/bar matches foo/bar, foo/x/bar, foo/x/y/bar
    """
    if "**" not in pattern:
        return fnmatch.fnmatch(text, pattern)
    if pattern == "**":
        return True
    try:
        regex = _glob_to_regex(pattern)
        return regex.match(text) is not None
    except re.error:
        return False


def _match_words(words: list[str], config: Config, cwd: Path) -> Match | None:
    """Match command words against rules. Returns last matching rule."""
    normalized_cmd = _normalize_words(words, cwd)
    result: Match | None = None
    for rule in config.rules:
        normalized_pattern = _normalize_pattern(rule.pattern, cwd)
        matched = fnmatch.fnmatch(normalized_cmd, normalized_pattern)
        # Trailing ' *' also matches bare command (no args)
        if not matched and normalized_pattern.endswith(" *"):
            matched = normalized_cmd == normalized_pattern[:-2]
        if matched:
            result = Match(
                decision=rule.decision,
                pattern=rule.pattern,
                message=rule.message,
                source=rule.source,
                scope=rule.scope,
            )
    return result


def _normalize_redirect_pattern(pattern: str, cwd: Path) -> str:
    """Normalize a redirect pattern, handling ** specially.

    For patterns with **, normalize the prefix before ** and keep the rest.
    For example: 'src/**' -> '/abs/path/to/src/**'
    """
    if "**" not in pattern:
        return _normalize_path(pattern, cwd)
    # Split at first **, normalize prefix, rejoin
    idx = pattern.index("**")
    prefix = pattern[:idx].rstrip("/")
    suffix = pattern[idx:]
    if prefix:
        normalized_prefix = _normalize_path(prefix, cwd)
        return f"{normalized_prefix}/{suffix}"
    # Pattern starts with ** (e.g., "**/foo") - no prefix to normalize
    return pattern


def _match_redirect(target: str, config: Config, cwd: Path) -> Match | None:
    """Match redirect target against rules. Returns last matching rule."""
    normalized_target = _normalize_path(target, cwd)
    result: Match | None = None
    for rule in config.redirect_rules:
        normalized_pattern = _normalize_redirect_pattern(rule.pattern, cwd)
        if _glob_match(normalized_target, normalized_pattern):
            result = Match(
                decision=rule.decision,
                pattern=rule.pattern,
                message=rule.message,
                source=rule.source,
                scope=rule.scope,
            )
    return result


def match_command(cmd: SimpleCommand, config: Config, cwd: Path) -> Match | None:
    """Match command and its redirects against config rules.

    Args:
        cmd: SimpleCommand with words and redirects from parsed bash.
        config: Loaded configuration.
        cwd: Current working directory for path resolution.

    Returns:
        Match object for the deciding rule, or None if no rules matched.
        Priority when combining command + redirect matches: deny > ask > allow.
        Returns the first match of the most restrictive decision type.
    """
    matches: list[Match] = []

    # Match command words
    cmd_match = _match_words(cmd.words, config, cwd)
    if cmd_match:
        matches.append(cmd_match)

    # Match each redirect
    for target in cmd.redirects:
        redirect_match = _match_redirect(target, config, cwd)
        if redirect_match:
            matches.append(redirect_match)

    if not matches:
        return None

    # Priority: deny > ask > allow (most restrictive wins)
    for m in matches:
        if m.decision == "deny":
            return m
    for m in matches:
        if m.decision == "ask":
            return m
    return matches[0]


def match_redirect(target: str, config: Config, cwd: Path) -> Match | None:
    """Match a redirect target against redirect rules.

    This is a convenience function for testing and for cases where you
    need to match a redirect target in isolation. Normally, redirects
    are matched as part of match_command() via SimpleCommand.redirects.

    Args:
        target: Redirect target path.
        config: Loaded configuration.
        cwd: Current working directory for path resolution.

    Returns:
        Match object for the last matching rule, or None if no match.
    """
    return _match_redirect(target, config, cwd)


# === Logging ===


@dataclass(frozen=True, slots=True)
class _LogConfig:
    """Internal log configuration."""

    path: Path
    full: bool = False


_log_config: _LogConfig | None = None
_log_disabled: bool = False  # Set on first failure, prevents repeated attempts


def configure_logging(config: Config) -> None:
    """Configure logging based on config settings. Call once at startup."""
    global _log_config, _log_disabled
    _log_disabled = False

    if config.log is None:
        _log_config = None
        return

    try:
        config.log.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        _log_config = None
        _log_disabled = True
        return

    _log_config = _LogConfig(path=config.log, full=config.log_full)


def log_decision(
    decision: str,
    cmd: str,
    rule: str | None = None,
    message: str | None = None,
    command: str | None = None,
) -> None:
    """Log a decision. No-op if logging not configured or disabled."""
    global _log_disabled
    import json
    from datetime import datetime, timezone

    if _log_config is None or _log_disabled:
        return

    entry: dict[str, str | None] = {"decision": decision, "cmd": cmd}
    if rule is not None:
        entry["rule"] = rule
    if message is not None:
        entry["message"] = message
    if _log_config.full and command is not None:
        entry["command"] = command
    entry["ts"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(_log_config.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        _log_disabled = True
