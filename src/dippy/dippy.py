#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "bashlex>=0.18",
#   "structlog>=25.5.0",
# ]
# ///
"""Claude Code PreToolUse hook for auto-approving safe bash commands.

This hook runs before Claude executes any Bash tool call. It parses the command
using bashlex (bash AST parser) and checks if all commands are "safe" - meaning
read-only operations that don't modify the filesystem, network state, or system
configuration.

Design assumptions:
- Commands come from Claude, which is well-intentioned and follows instructions.
  This is NOT a security sandbox for adversarial input.
- The goal is to reduce approval friction for common read-only operations while
  still prompting for potentially destructive commands.
- When in doubt, defer to user approval (fail open to "ask", not "allow").

Hook behavior:
- Safe commands: auto-approved with permissionDecision="allow"
- Unsafe commands: deferred to user with permissionDecision="ask"
- Parse failures or redirects: deferred to user (conservative)

All decisions are logged to ~/.claude/hook-approvals.log for auditing.

PreToolUse hook response options (via hookSpecificOutput JSON):
┌─────────────────────┬────────────────────────────────────────────────────────┐
│ permissionDecision  │ Behavior                                               │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "allow"             │ Auto-approve, skip user prompt. Reason shown to user.  │
│ "deny"              │ Block tool call. Reason shown to Claude for feedback.  │
│ "ask"               │ Prompt user for approval. Reason shown to user.        │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ (no JSON output)    │ Equivalent to "allow" - command proceeds silently.     │
└─────────────────────┴────────────────────────────────────────────────────────┘

Exit codes:
- 0: Success. JSON in stdout is parsed for decision.
- 2: Blocking error. stderr shown to Claude. JSON ignored.
- Other: Non-blocking error. stderr shown in verbose mode. Continues.

Optional fields: updatedInput (modify params), systemMessage (user warning),
continue (false halts Claude entirely, takes precedence over permissionDecision),
suppressOutput (hide from verbose).
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import json
import logging
import os
import re
import sys

import bashlex
import structlog

try:
    import tomllib
except ImportError:
    import tomli as tomllib

HOME = Path.home()
LOG_FILE = HOME / ".claude" / "hook-approvals.log"
_PROJECT_ROOT = Path(__file__).parent.parent.parent
CUSTOM_CONFIG = _PROJECT_ROOT / "dippy-local.toml"
TEST_CONFIG = _PROJECT_ROOT / "tests" / "dippy-local-test.toml"


def setup_logging():
    """Configure structlog to write JSON to log file. Silently fails if logging unavailable."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.INFO)
        logging.basicConfig(
            format="%(message)s", handlers=[file_handler], level=logging.INFO
        )
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            logger_factory=structlog.PrintLoggerFactory(file=file_handler.stream),
        )
    except Exception:
        pass  # Logging is optional - don't fail the hook


log = None


def _log(level: str, **kwargs) -> None:
    """Log a message, silently ignoring errors."""
    try:
        if log:
            getattr(log, level)(**kwargs)
    except Exception:
        pass


# === Data: What commands are safe ===

SAFE_COMMANDS = {
    # File viewing
    "bat", "cat", "head", "less", "more", "tail", "tac",
    # File info/metadata
    "dir", "file", "ls", "lsof", "stat", "tree", "vdir",
    # Path utilities
    "basename", "dirname", "pwd", "readlink", "realpath", "which", "whereis",
    # Text processing
    "ack", "col", "comm", "cut", "diff", "expand", "fmt", "fold",
    "grep", "join", "nl", "paste", "rg", "tr", "tsort", "unexpand", "uniq", "wc",
    # Search
    "fd",
    # Checksums & hashing
    "b2sum", "cksum", "md5sum", "sha1sum", "sha256sum", "sha512sum",
    # Encoding
    "base32", "base64", "basenc", "iconv",
    # Binary inspection
    "hexdump", "od", "strings",
    # Archive inspection
    "lsar", "zipinfo",
    # Documentation
    "apropos", "info", "man", "whatis",
    # System info
    "arch", "date", "df", "du", "free", "hostname", "hostid", "nproc", "uname", "uptime",
    # User info
    "getent", "groups", "id", "logname", "pinky", "users", "who", "whoami",
    # Process info
    "htop", "ps", "tty",
    # Network inspection
    "dig", "host", "netstat", "nslookup", "ping", "ss", "traceroute", "whois",
    # Math/calculators
    "bc", "cal", "dc", "expr", "factor", "seq", "units",
    # Output/control
    "echo", "false", "printf", "sleep", "true", "yes",
    # Data processing
    "jq",
    # Dev tools
    "cloc", "pytest",
    # Auth
    "aws-azure-login",
    # Shell builtins
    "cd", "env", "printenv", "type",
}

SAFE_SCRIPTS: set[str] = set()
CURL_WRAPPERS: set[str] = set()
CUSTOM_PATTERNS: list[re.Pattern] = []


def _load_config_file(config_path: Path) -> dict:
    """Load patterns from a config file. Returns parsed config or empty dict."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {config_path}: {e}", file=sys.stderr)
        return {}


def _load_custom_configs() -> None:
    """Load custom patterns from config files into global state."""
    global \
        SAFE_SCRIPTS, \
        CURL_WRAPPERS, \
        CUSTOM_PATTERNS, \
        SAFE_COMMANDS, \
        CLI_ALIASES, \
        PREFIX_COMMANDS, \
        WRAPPERS
    for config_path in [TEST_CONFIG, CUSTOM_CONFIG]:
        config = _load_config_file(config_path)
        if not config:
            continue
        SAFE_SCRIPTS.update(config.get("safe_scripts", {}).get("scripts", []))
        CURL_WRAPPERS.update(config.get("curl_wrappers", {}).get("scripts", []))
        SAFE_COMMANDS.update(config.get("safe_commands", {}).get("commands", []))
        CLI_ALIASES.update(config.get("cli_aliases", {}).get("aliases", {}))
        PREFIX_COMMANDS.update(config.get("prefix_commands", {}).get("commands", []))
        for pattern in config.get("safe_patterns", {}).get("patterns", []):
            expanded = pattern.replace("~", re.escape(str(HOME)))
            CUSTOM_PATTERNS.append(re.compile(expanded))
        for cli, actions in config.get("cli_safe_actions", {}).items():
            if cli in CLI_CONFIGS:
                CLI_CONFIGS[cli]["safe_actions"] = CLI_CONFIGS[cli][
                    "safe_actions"
                ] | set(actions)
        # New CLI tools
        for cli, cli_config in config.get("cli_tools", {}).items():
            if cli not in CLI_CONFIGS:
                CLI_CONFIGS[cli] = {
                    "safe_actions": COMMON_SAFE_ACTIONS
                    | set(cli_config.get("safe_actions", [])),
                    "safe_prefixes": tuple(cli_config.get("safe_prefixes", [])),
                    "parser": cli_config.get("parser", "first_token"),
                }
                if "flags_with_arg" in cli_config:
                    CLI_CONFIGS[cli]["flags_with_arg"] = set(
                        cli_config["flags_with_arg"]
                    )
        # Wrappers
        for name, wrapper_config in config.get("wrappers", {}).items():
            prefix = wrapper_config.get("prefix", [name])
            skip = wrapper_config.get("skip", 0)
            if skip == "flags":
                skip = None
            flags = set(wrapper_config.get("flags_with_arg", []))
            WRAPPERS[name] = (prefix, skip, flags)


PREFIX_COMMANDS = {
    "git config --get",
    "git config --list",
    "git stash list",
    "node --version",
    "python --version",
}

# Wrapper commands that just modify how the inner command runs
# Value is (prefix_tokens, skip_count, flags_with_arg) where skip_count can be:
#   int: skip that many args after prefix
#   None: skip flags and VAR=val pairs
#   "nice": skip -n N style flags
# flags_with_arg is optional set of flags that consume the next token
WRAPPERS = {
    "time": (["time"], 0, set()),
    "nice": (["nice"], "nice", set()),
    "timeout": (["timeout"], 1, set()),
    "env": (["env"], None, {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}),
    "uv": (
        ["uv", "run"],
        None,
        {"--group", "--project", "-p", "--package", "--with", "--python"},
    ),
}

# === Data: CLI configurations ===

# Common read-only actions shared across most CLI tools
COMMON_SAFE_ACTIONS = {
    "describe",
    "diff",
    "export",
    "get",
    "help",
    "info",
    "list",
    "logs",
    "search",
    "show",
    "status",
    "version",
    "view",
}

# CLI tools with action-based checks
# parser types:
#   "aws": action is second token (aws <service> <action>)
#   "first_token": action is first non-flag token
#   "second_token": action is second non-flag token
#   "variable_depth": action depth varies by service (see action_depth, service_depths)
CLI_CONFIGS = {
    "aws": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "filter-log-events",
            "lookup-events",
            "ls",
            "query",
            "scan",
            "tail",
            "transact-get-items",
            "wait",
        },
        "safe_prefixes": (
            "batch-get-",
            "describe-",
            "get-",
            "head-",
            "list-",
            "validate-",
        ),
        "parser": "aws",
    },
    "az": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"query"},
        "safe_prefixes": ("get-", "list-", "show-"),
        "parser": "variable_depth",
        "action_depth": 1,
        "service_depths": {
            "cognitiveservices": 2,  # az cognitiveservices model list
            "deployment": 2,  # az deployment group show
            "devops": 2,  # az devops team list
            "keyvault": 2,  # az keyvault secret list
            "ml": 2,  # az ml workspace list
            "monitor": 2,  # az monitor log-analytics query
            "network": 2,
            "role": 2,  # az role assignment list
            "storage": 2,
        },
        # Subgroups that need different depths
        "subservice_depths": {
            ("acr", "repository"): 2,  # az acr repository list
            ("boards", "area"): 3,  # az boards area project list
            ("boards", "iteration"): 3,  # az boards iteration team list
            ("boards", "work-item"): 2,  # az boards work-item show
            (
                "cognitiveservices",
                "account",
                "deployment",
            ): 3,  # az cognitiveservices account deployment list
            ("containerapp", "logs"): 2,  # az containerapp logs show
            ("containerapp", "revision"): 2,  # az containerapp revision list
            ("deployment", "operation"): 3,  # az deployment operation group list
        },
        "flags_with_arg": {
            "-g",
            "-o",
            "--output",
            "--query",
            "--resource-group",
            "--subscription",
        },
    },
    "gcloud": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"get-iam-policy", "get-value", "read"},
        "safe_prefixes": ("get-", "list-", "describe-"),
        "parser": "variable_depth",
        "action_depth": 2,
        "service_depths": {
            "artifacts": 3,  # gcloud artifacts docker images list
            "auth": 1,  # gcloud auth list
            "beta": 3,  # gcloud beta run services describe
            "certificate-manager": 2,  # gcloud certificate-manager trust-configs describe
            "components": 1,
            "compute": 2,  # gcloud compute backend-services list
            "config": 1,  # gcloud config get-value
            "container": 2,  # gcloud container images list-tags
            "dns": 2,  # gcloud dns record-sets list
            "functions": 1,  # gcloud functions list
            "iam": 2,  # gcloud iam service-accounts list
            "iap": 2,  # gcloud iap web get-iam-policy
            "logging": 1,  # gcloud logging read
            "network-security": 2,  # gcloud network-security server-tls-policies describe
            "projects": 1,  # gcloud projects list/describe
            "run": 2,  # gcloud run services describe
            "secrets": 1,  # gcloud secrets list
            "storage": 2,  # gcloud storage buckets describe
            "topic": 1,
        },
        "flags_with_arg": {
            "--account",
            "--configuration",
            "--format",
            "--project",
            "--region",
            "--zone",
        },
    },
    "gh": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"checks"},
        "safe_prefixes": (),
        "parser": "second_token",
        "flags_with_arg": {"-R", "--repo"},
    },
    "docker": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"events", "history", "images", "inspect", "port", "ps", "stats", "top"},
        "safe_prefixes": (),
        "parser": "first_token",
        "flags_with_arg": {
            "-c",
            "--config",
            "--context",
            "-H",
            "--host",
            "-l",
            "--log-level",
        },
    },
    "auth0": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"search-by-email", "stats", "tail"},
        "safe_prefixes": (),
        "parser": "second_token",
        "flags_with_arg": {"--tenant"},
    },
    "brew": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"config", "deps", "desc", "doctor", "leaves", "options", "outdated", "uses"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "git": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "blame",
            "cat-file",
            "check-ignore",
            "cherry",
            "fetch",
            "for-each-ref",
            "grep",
            "log",
            "ls-files",
            "ls-tree",
            "merge-base",
            "name-rev",
            "reflog",
            "rev-list",
            "rev-parse",
            "shortlog",
        },
        "safe_prefixes": (),
        "parser": "first_token",
        "flags_with_arg": {"-C", "-c", "--git-dir", "--work-tree"},
    },
    "kubectl": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"api-resources", "api-versions", "cluster-info", "explain", "top"},
        "safe_prefixes": (),
        "parser": "first_token",
        "flags_with_arg": {
            "-n",
            "--namespace",
            "--context",
            "--cluster",
            "--kubeconfig",
            "-o",
            "--output",
        },
    },
    "cdk": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"doctor", "docs", "ls", "metadata", "notices", "synth"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "pre-commit": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"sample-config", "validate-config", "validate-manifest"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "ruff": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"check"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "uv": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"lock", "tree"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "terraform": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"fmt", "graph", "output", "plan", "providers", "state", "validate"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
}

CLI_ALIASES: dict[str, str] = {}

# === Simple token rejection checks ===
# Commands that are safe unless they contain specific tokens.
# Format: command -> (exact_reject, prefix_reject)
# - exact_reject: set of tokens that must match exactly
# - prefix_reject: tuple of prefixes to match with startswith()

SIMPLE_CHECKS: dict[str, tuple[set[str], tuple[str, ...]]] = {
    "dmesg": ({"-c", "-C", "--clear"}, ()),
    "find": ({"-exec", "-execdir", "-ok", "-okdir", "-delete"}, ()),
    "journalctl": (
        {"--rotate", "--flush", "--sync", "--relinquish-var"},
        ("--vacuum",),
    ),
    "sed": (set(), ("-i", "--in-place")),
    "sort": (set(), ("-o",)),
}


def check_simple(
    tokens: list[str], reject_exact: set[str], reject_prefixes: tuple[str, ...]
) -> bool:
    """Check if command is safe by rejecting specific tokens."""
    for t in tokens:
        if t in reject_exact:
            return False
        if reject_prefixes and t.startswith(reject_prefixes):
            return False
    return True


# === Custom validators ===


def check_awk(tokens: list[str]) -> bool:
    """Approve awk if no -f flag and no dangerous patterns in script."""
    for t in tokens:
        if t == "-f" or t.startswith("-f") or t == "--file":
            return False
        if not t.startswith("-"):
            if ">" in t or "|" in t or "system" in t:
                return False
    return True


def check_ifconfig(tokens: list[str]) -> bool:
    """Approve ifconfig if no modifying arguments (up/down/address changes)."""
    dangerous = {"up", "down", "add", "del", "delete", "tunnel", "promisc"}
    if dangerous & set(tokens):
        return False
    for t in tokens:
        if t.startswith("netmask") or t.startswith("broadcast"):
            return False
    return True


def check_ip(tokens: list[str]) -> bool:
    """Approve ip if using read-only subcommands."""
    if len(tokens) < 2:
        return False
    obj = None
    for t in tokens[1:]:
        if t.startswith("-"):
            continue
        obj = t
        break
    if not obj:
        return False
    safe_objects = {
        "addr",
        "address",
        "link",
        "route",
        "neigh",
        "neighbor",
        "rule",
        "maddr",
        "mroute",
        "tunnel",
    }
    if obj not in safe_objects:
        return False
    dangerous = {"add", "del", "delete", "change", "replace", "set", "flush", "exec"}
    if dangerous & set(tokens):
        return False
    return True


def check_openssl(tokens: list[str]) -> bool:
    """Approve openssl x509 if -noout is present (read-only display)."""
    if len(tokens) < 2:
        return False
    subcommand = tokens[1]
    if subcommand == "x509" and "-noout" in tokens:
        return True
    return False


# Curl flags that send data (imply POST or upload)
CURL_DATA_FLAGS = {
    "-d",
    "--data",
    "--data-binary",
    "--data-raw",
    "--data-ascii",
    "--data-urlencode",
    "-F",
    "--form",
    "--form-string",
    "-T",
    "--upload-file",
}


def check_curl(tokens: list[str]) -> bool:
    """Approve curl if GET/HEAD only (no data-sending or method-changing flags)."""
    for i, t in enumerate(tokens):
        # Block data/upload flags (and --flag=value variants)
        if t in CURL_DATA_FLAGS:
            return False
        for flag in CURL_DATA_FLAGS:
            if t.startswith(flag + "="):
                return False
        # Check -X/--request for non-safe methods
        if t in {"-X", "--request"}:
            if i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                if method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                    return False
        # Also catch --request=METHOD
        if t.startswith("-X=") or t.startswith("--request="):
            method = t.split("=", 1)[1].upper()
            if method not in {"GET", "HEAD"}:
                return False
    return True


def check_shell_c(tokens: list[str]) -> bool:
    """Approve bash/sh/zsh -c if the inner command is safe."""
    # tokens: ['bash', '-c', 'echo hello'] or ['bash', '-lc', 'echo hello']
    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break
    if c_idx is None:
        return False
    if c_idx + 1 >= len(tokens):
        return False
    inner_cmd = tokens[c_idx + 1]
    result = parse_commands(inner_cmd)
    if result.error or not result.commands:
        return False
    return all(is_command_safe(cmd) for cmd in result.commands)


XARGS_FLAGS_WITH_ARG = {
    "-a",
    "--arg-file",
    "-d",
    "--delimiter",
    "-E",
    "-e",
    "--eof",
    "-I",
    "-i",
    "--replace",
    "-L",
    "-l",
    "--max-lines",
    "-n",
    "--max-args",
    "-P",
    "--max-procs",
    "-s",
    "--max-chars",
    "--process-slot-var",
}


def check_xargs(tokens: list[str]) -> bool:
    """Approve xargs if the command it runs is safe."""
    i = 1 + skip_flags(tokens[1:], XARGS_FLAGS_WITH_ARG, stop_at_double_dash=True)
    if i >= len(tokens):
        return False
    return is_command_safe(tokens[i:])


def check_auth0_api(tokens: list[str]) -> bool:
    """Approve auth0 api if it's a GET request (no mutation method or data flags)."""
    # tokens: ['auth0', 'api', 'get', 'path'] or ['auth0', 'api', 'path'] (defaults to GET)
    args = tokens[2:]
    for arg in args:
        if arg in {"post", "put", "patch", "delete"}:
            return False
        if arg in {"-d", "--data"}:
            return False
    return True


def check_gh_api(tokens: list[str]) -> bool:
    """Approve gh api if it's a GET request (no mutation flags)."""
    # tokens[0] is 'gh', tokens[1] is 'api'
    args = tokens[2:]

    # First pass: determine the method
    method = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-X", "--method"}:
            if i + 1 < len(args):
                method = args[i + 1].upper()
            i += 2
        elif arg.startswith("-X") and len(arg) > 2:
            method = arg[2:].upper()
            i += 1
        elif arg.startswith("--method="):
            method = arg[9:].upper()
            i += 1
        else:
            i += 1

    # Explicit non-GET method is unsafe
    if method is not None and method != "GET":
        return False

    # Second pass: check for params that imply POST (unless explicit GET)
    has_mutation_flags = False
    for arg in args:
        if arg in {"-f", "--raw-field", "-F", "--field", "--input"}:
            has_mutation_flags = True
            break
        if arg.startswith(("--raw-field=", "--field=", "--input=")):
            has_mutation_flags = True
            break

    # Mutation flags only safe with explicit GET
    if has_mutation_flags and method != "GET":
        return False

    return True


def check_python(tokens: list[str]) -> bool:
    """Approve python if running dippy.py or bashlex one-liners."""
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t == "-c" and i + 1 < len(tokens):
            # Allow bashlex one-liners for debugging
            return "import bashlex" in tokens[i + 1]
        if t.startswith("-"):
            i += 1
            continue
        try:
            return Path(t).resolve() == Path(__file__).resolve()
        except Exception:
            return False
    return False


CUSTOM_CHECKS: dict[str, Callable[[list[str]], bool]] = {
    "awk": check_awk,
    "bash": check_shell_c,
    "curl": check_curl,
    "ifconfig": check_ifconfig,
    "ip": check_ip,
    "openssl": check_openssl,
    "python": check_python,
    "sh": check_shell_c,
    "xargs": check_xargs,
    "zsh": check_shell_c,
}


# Compound command checks (multi-token prefix -> validator)
def check_uv_pip(tokens: list[str]) -> bool:
    """Approve uv pip if action is read-only."""
    # tokens: ['uv', 'pip', 'list'] or ['uv', 'pip', 'show', 'pkg']
    if len(tokens) < 3:
        return False
    action = tokens[2]
    return action in {"list", "show", "tree", "check"}


COMPOUND_CHECKS: dict[tuple[str, ...], Callable[[list[str]], bool]] = {
    ("auth0", "api"): check_auth0_api,
    ("gh", "api"): check_gh_api,
    ("uv", "pip"): check_uv_pip,
}

# === Wrapper stripping ===


def strip_wrappers(tokens: list[str]) -> list[str]:
    """Strip wrapper commands and return inner command tokens."""
    while tokens and tokens[0] in WRAPPERS:
        prefix, skip, flags_with_arg = WRAPPERS[tokens[0]]
        if tokens[: len(prefix)] != prefix:
            break
        tokens = tokens[len(prefix) :]

        if skip is None:
            i = skip_flags(
                tokens, flags_with_arg, skip_env_vars=True, stop_at_double_dash=True
            )
            tokens = tokens[i:]
        elif skip == "nice":
            while tokens and tokens[0].startswith("-"):
                tokens = tokens[1:]
                if tokens:
                    tokens = tokens[1:]
        elif skip > 0:
            tokens = tokens[skip:]

    return tokens


# === CLI action extraction ===

AWS_FLAGS_WITH_ARG = {
    "--ca-bundle",
    "--cli-connect-timeout",
    "--cli-read-timeout",
    "--color",
    "--endpoint-url",
    "--output",
    "--profile",
    "--region",
}


def skip_flags(
    tokens: list[str],
    flags_with_arg: set[str] = frozenset(),
    skip_env_vars: bool = False,
    stop_at_double_dash: bool = False,
) -> int:
    """Return index of first non-flag token, skipping flags and their arguments.

    Args:
        tokens: List of command tokens to scan
        flags_with_arg: Flags that consume the next token as their argument
        skip_env_vars: If True, also skip VAR=value environment variable assignments
        stop_at_double_dash: If True, stop at -- and return index after it
    """
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if stop_at_double_dash and tok == "--":
            return i + 1
        if tok in flags_with_arg:
            i += 2
        elif tok.startswith("-"):
            i += 1
        elif skip_env_vars and "=" in tok:
            i += 1
        else:
            break
    return i


def _get_aws_action(tokens: list[str]) -> str | None:
    """Extract action from aws <service> <action> command."""
    i = skip_flags(tokens, AWS_FLAGS_WITH_ARG)
    # "aws help" - help is the first token
    if i < len(tokens) and tokens[i] == "help":
        return "help"
    if i + 1 < len(tokens):
        return tokens[i + 1]
    return None


def _get_nth_token(tokens: list[str], n: int, flags_with_arg: set[str]) -> str | None:
    """Extract nth non-flag token (0-indexed)."""
    i = skip_flags(tokens, flags_with_arg)
    if i + n < len(tokens):
        return tokens[i + n]
    return None


def _get_variable_depth_action(tokens: list[str], config: dict[str, Any]) -> str | None:
    """Get action at variable depth based on first token (service/group)."""
    flags_with_arg = config.get("flags_with_arg", set())
    default_depth = config.get("action_depth", 1)
    service_depths = config.get("service_depths", {})
    subservice_depths = config.get("subservice_depths", {})

    i = skip_flags(tokens, flags_with_arg)
    if i >= len(tokens):
        return None

    service = tokens[i]
    depth = service_depths.get(service, default_depth)

    # Check for subservice override (e.g., "boards iteration" -> depth 3)
    if i + 1 < len(tokens):
        subservice = tokens[i + 1]
        subservice_key = (service, subservice)
        if subservice_key in subservice_depths:
            depth = subservice_depths[subservice_key]
        # Check for sub-subservice override (e.g., "cognitiveservices account deployment" -> depth 4)
        if i + 2 < len(tokens):
            subsubservice = tokens[i + 2]
            subsubservice_key = (service, subservice, subsubservice)
            if subsubservice_key in subservice_depths:
                depth = subservice_depths[subsubservice_key]

    target_idx = i + depth
    if target_idx < len(tokens):
        return tokens[target_idx]
    return None


PARSERS: dict[str, Callable[[list[str], dict[str, Any]], str | None]] = {
    "aws": lambda tokens, config: _get_aws_action(tokens),
    "first_token": lambda tokens, config: _get_nth_token(
        tokens, 0, config.get("flags_with_arg", set())
    ),
    "second_token": lambda tokens, config: _get_nth_token(
        tokens, 1, config.get("flags_with_arg", set())
    ),
    "variable_depth": _get_variable_depth_action,
}


def get_cli_action(
    tokens: list[str], parser: str, config: dict[str, Any] | None = None
) -> str | None:
    """Extract action from CLI command based on parser type."""
    return PARSERS[parser](tokens, config)


def get_command_description(tokens: list[str]) -> str:
    """Get a human-readable description of a command for error messages."""
    if not tokens:
        return "empty command"
    tokens = strip_wrappers(tokens)
    if not tokens:
        return "empty command"
    cmd = CLI_ALIASES.get(tokens[0], tokens[0])
    if cmd == "aws" and len(tokens) >= 3:
        # aws <service> <action> - skip global flags
        args = tokens[1:]
        i = 0
        while i < len(args):
            if args[i] in AWS_FLAGS_WITH_ARG:
                i += 2
            elif args[i].startswith("--"):
                i += 1
            else:
                break
        if i + 1 < len(args):
            return f"aws {args[i]} {args[i + 1]}"
    # Check compound commands first (e.g., uv pip install)
    for prefix in COMPOUND_CHECKS:
        if tuple(tokens[: len(prefix)]) == prefix and len(tokens) > len(prefix):
            return " ".join(tokens[: len(prefix) + 1])
    if cmd in CLI_CONFIGS:
        config = CLI_CONFIGS[cmd]
        action = get_cli_action(tokens[1:], config["parser"], config)
        if action:
            # For variable_depth parsers, include service hierarchy
            if config["parser"] == "variable_depth":
                flags_with_arg = config.get("flags_with_arg", set())
                i = skip_flags(tokens[1:], flags_with_arg)
                parts = [cmd]
                for j in range(i, len(tokens) - 1):
                    tok = tokens[1 + j]
                    if tok.startswith("-"):
                        break
                    parts.append(tok)
                    if tok == action:
                        break
                return " ".join(parts)
            # For second_token parsers (gh, auth0), show cmd subcommand action
            if config["parser"] == "second_token":
                flags_with_arg = config.get("flags_with_arg", set())
                i = skip_flags(tokens[1:], flags_with_arg)
                if i + 1 < len(tokens) - 1:
                    return f"{cmd} {tokens[1 + i]} {tokens[2 + i]}"
            return f"{cmd} {action}"
    return tokens[0]


# === Core safety check ===


def is_command_safe(tokens: list[str]) -> bool:
    """Check if a single command (as token list) is safe."""
    if not tokens:
        return False

    tokens = strip_wrappers(tokens)
    if not tokens:
        return False

    if "--help" in tokens:
        return True

    # Allow dippy to run itself (self-executing via uv run)
    try:
        if Path(tokens[0]).resolve() == Path(__file__).resolve():
            return True
    except Exception:
        pass

    cmd = tokens[0]
    args = tokens[1:]

    if cmd in SAFE_COMMANDS:
        return True

    if os.path.basename(cmd) in SAFE_SCRIPTS:
        return True

    for pattern in CUSTOM_PATTERNS:
        if pattern.match(cmd):
            return True

    # Curl wrappers should be checked as curl
    if os.path.basename(cmd) in CURL_WRAPPERS:
        return check_curl(tokens)

    for prefix in PREFIX_COMMANDS:
        prefix_tokens = prefix.split()
        if tokens[: len(prefix_tokens)] == prefix_tokens:
            return True

    if cmd in SIMPLE_CHECKS:
        reject_exact, reject_prefixes = SIMPLE_CHECKS[cmd]
        return check_simple(tokens, reject_exact, reject_prefixes)

    if cmd in CUSTOM_CHECKS:
        return CUSTOM_CHECKS[cmd](tokens)

    for prefix, checker in COMPOUND_CHECKS.items():
        if tuple(tokens[: len(prefix)]) == prefix:
            return checker(tokens)

    cmd = CLI_ALIASES.get(cmd, cmd)

    if cmd in CLI_CONFIGS:
        config = CLI_CONFIGS[cmd]
        action = get_cli_action(args, config["parser"], config)
        if not action:
            return False
        if action in config["safe_actions"]:
            return True
        if config["safe_prefixes"] and action.startswith(config["safe_prefixes"]):
            return True
    return False


# === AST parsing ===

OUTPUT_REDIRECTS = {">", ">>", "&>", ">&"}
SAFE_REDIRECT_TARGETS = {"/dev/null"}


def has_unsafe_output_redirect(node: Any) -> bool:
    """Check if a command node has any unsafe output redirects."""
    if node.kind == "command":
        for part in node.parts:
            if part.kind == "redirect" and part.type in OUTPUT_REDIRECTS:
                if isinstance(part.output, int):
                    continue
                target = (
                    getattr(part.output, "word", None)
                    if hasattr(part, "output")
                    else None
                )
                if target in SAFE_REDIRECT_TARGETS:
                    continue
                return True
    return False


def get_command_nodes(node: Any) -> list[list[str]] | None:
    """Recursively extract command nodes from AST.

    Returns None if any command has output redirects (defer).
    Returns list of command token lists otherwise.
    """
    if node.kind == "command":
        if has_unsafe_output_redirect(node):
            return None
        parts = [p.word for p in node.parts if p.kind == "word"]
        return [parts] if parts else []

    children = getattr(node, "list", None) or getattr(node, "parts", None) or []
    commands = []
    for child in children:
        result = get_command_nodes(child)
        if result is None:
            return None
        commands.extend(result)
    return commands


def preprocess_command(cmd_string: str) -> str:
    """Strip bash constructs that bashlex doesn't handle."""
    # Remove 'time' reserved word
    cmd_string = re.sub(r"\btime\s+(-p\s+)?", "", cmd_string)
    # Replace heredoc in command substitution with placeholder string
    # Matches: "$(cat <<'EOF'...EOF)" or "$(cat <<EOF...EOF)"
    cmd_string = re.sub(
        r'"\$\(cat\s+<<\'?EOF\'?\n.*?\nEOF\n\)"',
        '"HEREDOC_PLACEHOLDER"',
        cmd_string,
        flags=re.DOTALL,
    )
    return cmd_string


class ParseResult:
    """Result of parsing a command string."""

    def __init__(
        self, commands: list[list[str]] | None = None, error: str | None = None
    ):
        self.commands = commands
        self.error = error


def parse_commands(cmd_string: str) -> ParseResult:
    """Parse a bash command string and return list of commands."""
    try:
        cmd_string = preprocess_command(cmd_string)
        parts = bashlex.parse(cmd_string)
        commands = []
        for part in parts:
            result = get_command_nodes(part)
            if result is None:
                return ParseResult(error="Output redirect")
            commands.extend(result)
        return ParseResult(commands=commands)
    except Exception:
        return ParseResult(error="Parse failed")


# === Entry point ===


def get_unsafe_commands(commands: list[list[str]]) -> list[str]:
    """Return deduplicated list of unsafe command descriptions."""
    unsafe_descs = []
    seen = set()
    for cmd_tokens in commands:
        if not is_command_safe(cmd_tokens):
            desc = get_command_description(cmd_tokens)
            if desc not in seen:
                seen.add(desc)
                unsafe_descs.append(desc)
    return unsafe_descs


def main() -> None:
    global log
    setup_logging()
    log = structlog.get_logger()
    _load_custom_configs()

    input_data = json.load(sys.stdin)
    command = input_data.get("tool_input", {}).get("command", "")

    def defer_to_user(reason: str) -> None:
        """Print JSON to defer decision to user and exit."""
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": f"🐤 {reason}",
                    }
                }
            )
        )
        sys.exit(0)

    if not command.strip():
        _log("info", event="deferred", command=command, reason="empty_command")
        defer_to_user("Empty command")

    result = parse_commands(command)

    if result.error:
        _log(
            "info",
            event="deferred",
            command=command,
            reason=result.error.lower().replace(" ", "_"),
        )
        defer_to_user(result.error)

    commands = result.commands
    if not commands:
        _log("info", event="deferred", command=command, reason="no_commands")
        defer_to_user("No commands found")

    unsafe_descs = get_unsafe_commands(commands)
    if unsafe_descs:
        _log(
            "info",
            event="deferred",
            command=command,
            reason="unsafe_command",
            unsafe_commands=unsafe_descs,
        )
        defer_to_user(f"Command requires approval: {', '.join(unsafe_descs)}")

    _log("info", event="approved", command=command)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "all commands safe",
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
