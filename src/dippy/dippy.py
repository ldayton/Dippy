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
    "bat",
    "cat",
    "head",
    "less",
    "more",
    "tail",
    "tac",
    # File info/metadata
    "dir",
    "file",
    "ls",
    "lsof",
    "stat",
    "tree",
    "vdir",
    # Path utilities
    "basename",
    "dirname",
    "pwd",
    "readlink",
    "realpath",
    "which",
    "whereis",
    # Text processing
    "ack",
    "col",
    "comm",
    "cut",
    "diff",
    "expand",
    "fmt",
    "fold",
    "grep",
    "join",
    "nl",
    "paste",
    "rg",
    "tr",
    "tsort",
    "unexpand",
    "uniq",
    "wc",
    # Search
    "fd",
    # Checksums & hashing
    "b2sum",
    "cksum",
    "md5sum",
    "sha1sum",
    "sha256sum",
    "sha512sum",
    # Encoding
    "base32",
    "base64",
    "basenc",
    "iconv",
    # Binary inspection
    "hexdump",
    "od",
    "strings",
    # Archive inspection
    "lsar",
    "zipinfo",
    # Documentation
    "apropos",
    "info",
    "man",
    "whatis",
    # System info
    "arch",
    "date",
    "df",
    "du",
    "free",
    "hostname",
    "hostid",
    "nproc",
    "uname",
    "uptime",
    # User info
    "getent",
    "groups",
    "id",
    "logname",
    "pinky",
    "users",
    "who",
    "whoami",
    # Process info
    "htop",
    "ps",
    "tty",
    # Network inspection
    "dig",
    "host",
    "netstat",
    "nslookup",
    "ping",
    "ss",
    "traceroute",
    "whois",
    # Math/calculators
    "bc",
    "cal",
    "dc",
    "expr",
    "factor",
    "seq",
    "units",
    # Output/control
    "echo",
    "false",
    "printf",
    "sleep",
    "true",
    "yes",
    # Data processing
    "jq",
    # Dev tools
    "cloc",
    "pytest",
    # Auth
    "aws-azure-login",
    # Shell builtins
    "cd",
    "env",
    "printenv",
    "type",
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
            "detect-stack-drift",
            "detect-stack-resource-drift",
            "download-db-log-file-portion",
            "estimate-template-cost",
            "filter-log-events",
            "generate-credential-report",
            "lookup-events",
            "ls",
            "query",
            "receive-message",
            "scan",
            "simulate-principal-policy",
            "start-query",
            "stop-query",
            "tail",
            "test-dns-answer",
            "transact-get-items",
            "wait",
        },
        "safe_prefixes": (
            "admin-get-",
            "admin-list-",
            "batch-get-",
            "check-if-",
            "describe-",
            "get-",
            "head-",
            "list-",
            "validate-",
        ),
        "parser": "aws",
    },
    "az": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "check-health",
            "configure",
            "download",
            "download-batch",
            "exists",
            "get-access-token",
            "get-credentials",
            "get-instance-view",
            "get-upgrades",
            "get-versions",
            "logs",
            "query",
            "summarize",
            "tail",
            "url",
        },
        "safe_prefixes": ("get-", "list-", "show-"),
        "parser": "variable_depth",
        "action_depth": 1,
        "service_depths": {
            "--version": 0,  # az --version
            "ad": 2,  # az ad user list
            "aks": 1,  # az aks list
            "appservice": 2,  # az appservice plan list
            "cognitiveservices": 2,  # az cognitiveservices model list
            "cosmosdb": 1,  # az cosmosdb list (subservices like sql need more)
            "deployment": 2,  # az deployment group show
            "devops": 2,  # az devops team list
            "eventhubs": 2,  # az eventhubs namespace list
            "functionapp": 1,  # az functionapp list
            "keyvault": 1,  # az keyvault list (subservices like secret need more)
            "ml": 2,  # az ml workspace list
            "monitor": 2,  # az monitor log-analytics query
            "network": 1,  # az network list-usages (subservices like vnet need more)
            "pipelines": 1,  # az pipelines list
            "policy": 2,  # az policy definition list
            "repos": 1,  # az repos list
            "role": 2,  # az role assignment list
            "servicebus": 2,  # az servicebus namespace list
            "sql": 2,  # az sql server list
            "storage": 2,
            "version": 0,  # az version (command itself is safe)
            "webapp": 1,  # az webapp list
        },
        # Subgroups that need different depths
        "subservice_depths": {
            ("acr", "credential"): 2,  # az acr credential show
            ("acr", "repository"): 2,  # az acr repository list
            ("ad", "group"): 2,  # az ad group list
            ("ad", "group", "member"): 3,  # az ad group member list
            ("ad", "signed-in-user"): 2,  # az ad signed-in-user show
            ("aks", "nodepool"): 2,  # az aks nodepool list
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
            ("cosmosdb", "keys"): 2,  # az cosmosdb keys list
            ("cosmosdb", "mongodb"): 3,  # az cosmosdb mongodb database list
            ("cosmosdb", "mongodb", "database"): 3,  # az cosmosdb mongodb database list
            ("cosmosdb", "sql"): 3,  # az cosmosdb sql database list
            ("cosmosdb", "sql", "container"): 3,  # az cosmosdb sql container list
            ("cosmosdb", "sql", "database"): 3,  # az cosmosdb sql database list
            ("deployment", "operation"): 3,  # az deployment operation group list
            ("devops", "configure"): 1,  # az devops configure --list
            ("devops", "wiki"): 2,  # az devops wiki list
            ("devops", "wiki", "page"): 3,  # az devops wiki page show
            ("eventhubs", "eventhub"): 2,  # az eventhubs eventhub list
            (
                "eventhubs",
                "eventhub",
                "consumer-group",
            ): 3,  # az eventhubs eventhub consumer-group list
            ("functionapp", "config"): 2,  # az functionapp config show
            (
                "functionapp",
                "config",
                "appsettings",
            ): 3,  # az functionapp config appsettings list
            (
                "functionapp",
                "deployment",
            ): 2,  # az functionapp deployment list-publishing-profiles
            ("functionapp", "function"): 2,  # az functionapp function list
            ("functionapp", "keys"): 2,  # az functionapp keys list
            ("keyvault", "certificate"): 2,  # az keyvault certificate list
            ("keyvault", "key"): 2,  # az keyvault key list
            ("keyvault", "secret"): 2,  # az keyvault secret list
            ("monitor", "log-analytics"): 2,  # az monitor log-analytics query
            (
                "monitor",
                "log-analytics",
                "workspace",
            ): 3,  # az monitor log-analytics workspace list
            (
                "network",
                "application-gateway",
            ): 2,  # az network application-gateway list
            ("network", "dns"): 3,  # az network dns zone list
            ("network", "dns", "record-set"): 3,  # az network dns record-set list
            (
                "network",
                "dns",
                "record-set",
                "a",
            ): 4,  # az network dns record-set a list
            ("network", "lb"): 2,  # az network lb list
            ("network", "nic"): 2,  # az network nic list
            ("network", "nic", "ip-config"): 3,  # az network nic ip-config list
            ("network", "nsg"): 2,  # az network nsg list
            ("network", "nsg", "rule"): 3,  # az network nsg rule list
            ("network", "private-dns"): 3,  # az network private-dns zone list
            ("network", "public-ip"): 2,  # az network public-ip list
            ("network", "vnet"): 2,  # az network vnet list
            ("network", "vnet", "subnet"): 3,  # az network vnet subnet list
            ("pipelines", "agent"): 2,  # az pipelines agent list
            ("pipelines", "build"): 2,  # az pipelines build list
            ("pipelines", "runs"): 2,  # az pipelines runs list
            ("pipelines", "variable-group"): 2,  # az pipelines variable-group list
            ("policy", "state"): 2,  # az policy state list
            ("repos", "policy"): 2,  # az repos policy list
            ("repos", "pr"): 2,  # az repos pr list
            ("repos", "ref"): 2,  # az repos ref list
            ("servicebus", "namespace"): 2,  # az servicebus namespace list
            (
                "servicebus",
                "namespace",
                "authorization-rule",
            ): 3,  # az servicebus namespace authorization-rule list
            (
                "servicebus",
                "namespace",
                "authorization-rule",
                "keys",
            ): 4,  # az servicebus namespace authorization-rule keys list
            ("servicebus", "queue"): 2,  # az servicebus queue list
            ("servicebus", "topic"): 2,  # az servicebus topic list
            (
                "servicebus",
                "topic",
                "subscription",
            ): 3,  # az servicebus topic subscription list
            ("sql", "db"): 2,  # az sql db list
            ("vm", "image"): 2,  # az vm image list
            ("sql", "elastic-pool"): 2,  # az sql elastic-pool list
            ("sql", "failover-group"): 2,  # az sql failover-group list
            ("sql", "server"): 2,  # az sql server list
            ("sql", "server", "firewall-rule"): 3,  # az sql server firewall-rule list
            ("storage", "account", "keys"): 3,  # az storage account keys list
            ("storage", "blob"): 2,  # az storage blob list
            ("storage", "blob", "metadata"): 3,  # az storage blob metadata show
            ("storage", "container"): 2,  # az storage container list
            ("webapp", "config"): 2,  # az webapp config show
            ("webapp", "config", "appsettings"): 3,  # az webapp config appsettings list
            (
                "webapp",
                "config",
                "connection-string",
            ): 3,  # az webapp config connection-string list
            ("webapp", "deployment"): 2,  # az webapp deployment list-*
            ("webapp", "deployment", "source"): 3,  # az webapp deployment source show
            ("webapp", "log"): 2,  # az webapp log show
        },
        "flags_with_arg": {
            "-g",
            "-n",
            "-o",
            "--name",
            "--output",
            "--query",
            "--resource-group",
            "--subscription",
        },
    },
    "gcloud": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "get-iam-policy",
            "get-value",
            "help",
            "info",
            "list-grantable-roles",
            "read",
            "topic",
            "version",
        },
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
            "help": 0,  # gcloud help (the command itself is safe)
            "iam": 2,  # gcloud iam service-accounts list
            "iap": 2,  # gcloud iap web get-iam-policy
            "info": 0,  # gcloud info (the command itself is safe)
            "logging": 1,  # gcloud logging read
            "network-security": 2,  # gcloud network-security server-tls-policies describe
            "projects": 1,  # gcloud projects list/describe
            "run": 2,  # gcloud run services describe
            "secrets": 1,  # gcloud secrets list
            "storage": 2,  # gcloud storage buckets describe
            "topic": 0,  # gcloud topic (the command itself is safe)
            "version": 0,  # gcloud version (the command itself is safe)
        },
        "subservice_depths": {
            ("app",): 1,  # gcloud app describe (top-level app commands)
            ("app", "services"): 2,  # gcloud app services list
            ("app", "versions"): 2,  # gcloud app versions list
            ("artifacts", "repositories"): 2,  # gcloud artifacts repositories list
            ("config", "configurations"): 2,  # gcloud config configurations list
            ("iam",): 1,  # gcloud iam list-grantable-roles (top-level iam commands)
            ("iam", "roles"): 2,  # gcloud iam roles list
            ("iam", "service-accounts"): 2,  # gcloud iam service-accounts list
            (
                "iam",
                "service-accounts",
                "keys",
            ): 3,  # gcloud iam service-accounts keys list
            ("iap", "tcp"): 3,  # gcloud iap tcp tunnels list
            ("logging", "logs"): 2,  # gcloud logging logs list
            ("secrets", "versions"): 2,  # gcloud secrets versions list
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
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            # Core read-only actions
            "checks",
            "download",
            "watch",
            "verify",
            "verify-asset",
            "trusted-root",
            # gh auth
            "token",
            # gh codespace
            "logs",
            "ports",
            # gh project
            "field-list",
            "item-list",
            # gh ruleset
            "check",
        },
        "safe_prefixes": (),
        "parser": "second_token",
        "flags_with_arg": {"-R", "--repo"},
    },
    "docker": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "config",  # docker compose config
            "df",  # docker system df
            "events",
            "export",  # outputs tar to stdout (redirects caught separately)
            "history",
            "images",
            "inspect",
            "ls",  # docker container/image/volume/network ls
            "port",
            "ps",
            "save",  # outputs tar to stdout (redirects caught separately)
            "stats",
            "top",
        },
        "safe_prefixes": (),
        "parser": "variable_depth",
        "action_depth": 0,  # Default: docker ps, docker images, etc.
        "service_depths": {
            # Management commands have action at depth 1
            "buildx": 1,
            "compose": 1,
            "container": 1,
            "context": 1,
            "image": 1,
            "manifest": 1,
            "network": 1,
            "plugin": 1,
            "system": 1,
            "trust": 1,
            "volume": 1,
            # Swarm commands
            "config": 1,
            "node": 1,
            "secret": 1,
            "service": 1,
            "stack": 1,
            "swarm": 1,
        },
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
            "count-objects",
            "fetch",
            "for-each-ref",
            "fsck",
            "grep",
            "log",
            "ls-files",
            "ls-remote",
            "ls-tree",
            "merge-base",
            "name-rev",
            "reflog",
            "rev-list",
            "rev-parse",
            "shortlog",
            "verify-commit",
            "verify-tag",
        },
        "safe_prefixes": (),
        "parser": "first_token",
        "flags_with_arg": {"-C", "-c", "--git-dir", "--work-tree"},
    },
    "kubectl": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "api-resources",
            "api-versions",
            "auth",
            "cluster-info",
            "completion",
            "events",
            "explain",
            "kustomize",
            "plugin",
            "top",
            "wait",
        },
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
        | {
            "acknowledge",
            "doctor",
            "docs",
            "ls",
            "metadata",
            "notices",
            "synth",
            "synthesize",
        },
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
        | {
            "console",
            "fmt",
            "get",
            "graph",
            "metadata",
            "modules",
            "output",
            "plan",
            "providers",
            "refresh",
            "test",
            "validate",
        },
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "npm": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {
            "audit",
            "doctor",
            "explain",
            "find-dupes",
            "fund",
            "ls",
            "outdated",
            "owner",
            "pack",  # creates tarball but doesn't install
            "ping",
            "prefix",
            "root",
            "search",
            "view",
            "why",
        },
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "pip": {
        "safe_actions": COMMON_SAFE_ACTIONS | {"check", "freeze", "index", "inspect"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "yarn": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"audit", "info", "licenses", "outdated", "owner", "why"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
    "pnpm": {
        "safe_actions": COMMON_SAFE_ACTIONS
        | {"audit", "licenses", "ls", "outdated", "why"},
        "safe_prefixes": (),
        "parser": "first_token",
    },
}

# gh has several built-in aliases that map to subcommands
# cs -> codespace, at -> attestation, rs -> ruleset, ext -> extension
GH_SUBCOMMAND_ALIASES: dict[str, str] = {
    "cs": "codespace",
    "at": "attestation",
    "rs": "ruleset",
    "ext": "extension",
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
    "--json",
}

# Curl flags that are always unsafe
CURL_UNSAFE_FLAGS = {
    "-K",
    "--config",
    "--ftp-create-dirs",
    "--mail-from",
    "--mail-rcpt",
}

# Safe HTTP methods (read-only)
CURL_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# FTP commands that are safe (read-only)
CURL_SAFE_FTP_COMMANDS = {
    "PWD",
    "LIST",
    "NLST",
    "STAT",
    "SIZE",
    "MDTM",
    "NOOP",
    "HELP",
    "SYST",
    "TYPE",
    "PASV",
    "CWD",
    "CDUP",
    "FEAT",
}


def check_curl(tokens: list[str]) -> bool:
    """Approve curl if GET/HEAD only (no data-sending or method-changing flags)."""
    for i, t in enumerate(tokens):
        # Block always-unsafe flags
        if t in CURL_UNSAFE_FLAGS:
            return False

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
                if method not in CURL_SAFE_METHODS:
                    return False

        # Also catch --request=METHOD
        if t.startswith("-X=") or t.startswith("--request="):
            method = t.split("=", 1)[1].upper()
            if method not in CURL_SAFE_METHODS:
                return False

        # Check -Q/--quote for FTP commands
        if t in {"-Q", "--quote"}:
            if i + 1 < len(tokens):
                ftp_cmd = tokens[i + 1].strip().strip("'\"").split()[0].upper()
                if ftp_cmd not in CURL_SAFE_FTP_COMMANDS:
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
    "-J",  # BSD: replacement string (like -I but different placement)
    "--replace",
    "-L",
    "-l",
    "--max-lines",
    "-n",
    "--max-args",
    "-P",
    "--max-procs",
    "-R",  # BSD: max replacements with -I
    "-s",
    "-S",  # BSD: replacement size limit
    "--max-chars",
    "--process-slot-var",
}

# Flags that make xargs interactive/unsafe regardless of command
XARGS_UNSAFE_FLAGS = {"-p", "--interactive", "-o", "--open-tty"}


def check_xargs(tokens: list[str]) -> bool:
    """Approve xargs if the command it runs is safe."""
    # Check for interactive flags which require user input
    for token in tokens[1:]:
        if token == "--":
            break
        if token in XARGS_UNSAFE_FLAGS:
            return False
        if token.startswith(("--interactive", "--open-tty")):
            return False
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

    # Check for graphql queries vs mutations
    # -f query='query {...}' is safe, -f query='mutation {...}' is not
    is_graphql_query = False
    for i, arg in enumerate(args):
        if arg in {"-f", "--raw-field"} and i + 1 < len(args):
            val = args[i + 1]
            if val.startswith("query="):
                query_content = val[6:]  # Remove "query=" prefix
                if "mutation" in query_content.lower():
                    return False
                # It's a graphql query (not mutation)
                is_graphql_query = "query" in query_content.lower() or "{" in query_content
        if arg.startswith(("--raw-field=query=", "-f=query=")):
            query_content = arg.split("=", 2)[2] if arg.count("=") >= 2 else ""
            if "mutation" in query_content.lower():
                return False
            is_graphql_query = "query" in query_content.lower() or "{" in query_content

    # If it's a graphql query (not mutation), it's safe even with -f flag
    if is_graphql_query:
        return True

    # Check for params that imply POST (unless explicit GET)
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


def check_gh_status(tokens: list[str]) -> bool:
    """Approve gh status (always read-only)."""
    return True


def check_gh_browse(tokens: list[str]) -> bool:
    """Approve gh browse (opens browser, no mutations)."""
    return True


def check_gh_search(tokens: list[str]) -> bool:
    """Approve gh search (all subcommands are read-only)."""
    # gh search repos, gh search issues, gh search prs, gh search commits, gh search code
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


def check_tar(tokens: list[str]) -> bool:
    """Approve tar if only listing contents (-t/--list)."""
    # tar tvf archive.tar, tar -tf archive.tar, tar --list -f archive.tar
    # Also: tar tf archive.tar (no dash, old-style)
    for t in tokens[1:]:
        if t == "-t" or t == "--list":
            return True
        # Check for combined short flags like -tvf, -tf, -ztf
        if t.startswith("-") and not t.startswith("--") and "t" in t:
            return True
    # Check first arg for old-style (no dash) like "tf", "tvf", "ztf"
    if len(tokens) > 1:
        first_arg = tokens[1]
        if (
            not first_arg.startswith("-")
            and "t" in first_arg
            and not any(c in first_arg for c in "cxru")
        ):
            return True
    return False


def check_unzip(tokens: list[str]) -> bool:
    """Approve unzip if only listing contents (-l)."""
    # unzip -l archive.zip
    for t in tokens[1:]:
        if t == "-l":
            return True
        # Combined flags like -lv
        if t.startswith("-") and not t.startswith("--") and "l" in t:
            # But not if it has extract-related flags
            if any(c in t for c in "xod"):
                return False
            return True
    return False


def check_7z(tokens: list[str]) -> bool:
    """Approve 7z if only listing contents (l command)."""
    # 7z l archive.7z
    if len(tokens) < 2:
        return False
    return tokens[1] == "l"


CUSTOM_CHECKS: dict[str, Callable[[list[str]], bool]] = {
    "7z": check_7z,
    "awk": check_awk,
    "bash": check_shell_c,
    "curl": check_curl,
    "ifconfig": check_ifconfig,
    "ip": check_ip,
    "openssl": check_openssl,
    "python": check_python,
    "sh": check_shell_c,
    "tar": check_tar,
    "unzip": check_unzip,
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


# docker compose flags that take an argument
DOCKER_COMPOSE_FLAGS_WITH_ARG = {
    "-f",
    "--file",
    "-p",
    "--project-name",
    "--project-directory",
    "--profile",
    "--env-file",
    "--progress",
    "--ansi",
    "--parallel",
}

# docker compose safe actions (read-only inspection)
DOCKER_COMPOSE_SAFE_ACTIONS = {
    "config",
    "events",
    "images",
    "logs",
    "ls",
    "port",
    "ps",
    "stats",
    "top",
    "version",
    "volumes",
}


def check_docker_compose(tokens: list[str]) -> bool:
    """Approve docker compose if action is read-only."""
    # tokens: ['docker', 'compose', ...flags..., 'action', ...]
    # Skip 'docker' and 'compose'
    args = tokens[2:]
    # Skip flags to find action
    i = skip_flags(args, DOCKER_COMPOSE_FLAGS_WITH_ARG)
    if i >= len(args):
        return False
    action = args[i]
    return action in DOCKER_COMPOSE_SAFE_ACTIONS


def check_docker_save(tokens: list[str]) -> bool:
    """Approve docker save only if not writing to a file (-o/--output)."""
    # tokens: ['docker', 'save', ...] or ['docker', 'image', 'save', ...]
    # -o/--output means writing to a file (filesystem modification)
    for t in tokens:
        if t in {"-o", "--output"} or t.startswith("-o=") or t.startswith("--output="):
            return False
    return True


def check_docker_image_save(tokens: list[str]) -> bool:
    """Approve docker image save only if not writing to a file."""
    return check_docker_save(tokens)


def _check_aws_action(tokens: list[str]) -> bool:
    """Check if an AWS command is safe using CLI_CONFIGS."""
    config = CLI_CONFIGS["aws"]
    action = get_cli_action(tokens[1:], config["parser"], config)
    if not action:
        return False
    if action in config["safe_actions"]:
        return True
    if config["safe_prefixes"] and action.startswith(config["safe_prefixes"]):
        return True
    return False


def check_aws_ssm(tokens: list[str]) -> bool:
    """Approve aws ssm get-parameter* unless --with-decryption is used."""
    # tokens: ['aws', 'ssm', 'get-parameter', '--name', '/my/param', '--with-decryption']
    # --with-decryption exposes secret values, so it's unsafe
    if "--with-decryption" in tokens:
        return False
    # Otherwise, delegate to normal AWS CLI action checking
    return _check_aws_action(tokens)


def check_aws_secretsmanager(tokens: list[str]) -> bool:
    """Block aws secretsmanager get-secret-value (exposes secret data)."""
    # tokens: ['aws', 'secretsmanager', 'get-secret-value', '--secret-id', 'mysecret']
    action = _get_aws_action(tokens[1:])
    # get-secret-value exposes secret data
    if action == "get-secret-value":
        return False
    # Otherwise, delegate to normal AWS CLI action checking
    return _check_aws_action(tokens)


def check_az_devops_configure(tokens: list[str]) -> bool:
    """Approve az devops configure only for read-only flags (--list)."""
    # tokens: ['az', 'devops', 'configure', ...]
    # --defaults modifies configuration, so it's unsafe
    # --list just shows configuration, so it's safe
    if "--defaults" in tokens:
        return False
    if "--list" in tokens:
        return True
    return False


def check_terraform_state(tokens: list[str]) -> bool:
    """Approve terraform state only for read-only subcommands."""
    # tokens: ['terraform', 'state', 'list'] or ['terraform', 'state', 'show', 'resource']
    if len(tokens) < 3:
        return False
    subcommand = tokens[2]
    # Safe subcommands: list, show, pull
    # Unsafe: mv, rm, push, replace-provider
    return subcommand in {"list", "show", "pull"}


def check_terraform_workspace(tokens: list[str]) -> bool:
    """Approve terraform workspace only for read-only subcommands."""
    # tokens: ['terraform', 'workspace', 'list'] or ['terraform', 'workspace', 'select', 'dev']
    if len(tokens) < 3:
        return False
    subcommand = tokens[2]
    # Safe subcommands: list, show, select
    # Unsafe: new, delete
    return subcommand in {"list", "show", "select"}


def check_cdk_context(tokens: list[str]) -> bool:
    """Approve cdk context only for read-only operations (no --reset/--clear)."""
    # tokens: ['cdk', 'context'] or ['cdk', 'context', '--json']
    # --reset and --clear modify context, so they're unsafe
    for t in tokens:
        if t in {"--reset", "--clear"}:
            return False
    return True


def check_kubectl_config(tokens: list[str]) -> bool:
    """Approve kubectl config only for read-only subcommands."""
    # tokens: ['kubectl', 'config', 'view'] or ['kubectl', ...flags..., 'config', 'subcommand']
    # Need to find the config subcommand after skipping flags
    config = CLI_CONFIGS["kubectl"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1  # +1 for 'kubectl'
    if i >= len(tokens) or tokens[i] != "config":
        return False
    if i + 1 >= len(tokens):
        return False
    subcommand = tokens[i + 1]
    # Safe subcommands: view, get-contexts, get-clusters, get-users, current-context
    # Unsafe: use-context, use, set-context, set-cluster, set-credentials, set,
    #         delete-context, delete-cluster, delete-user, rename-context
    safe_subcommands = {
        "view",
        "get-contexts",
        "get-clusters",
        "get-users",
        "current-context",
    }
    return subcommand in safe_subcommands


def check_kubectl_rollout(tokens: list[str]) -> bool:
    """Approve kubectl rollout only for read-only subcommands."""
    # tokens: ['kubectl', 'rollout', 'status', ...] or ['kubectl', ...flags..., 'rollout', ...]
    config = CLI_CONFIGS["kubectl"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1  # +1 for 'kubectl'
    if i >= len(tokens) or tokens[i] != "rollout":
        return False
    if i + 1 >= len(tokens):
        return False
    subcommand = tokens[i + 1]
    # Safe subcommands: status, history
    # Unsafe: restart, undo, pause, resume
    return subcommand in {"status", "history"}


def check_git_branch(tokens: list[str]) -> bool:
    """Approve git branch only for listing operations."""
    # tokens: ['git', 'branch'] or ['git', ...flags..., 'branch', ...]
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1  # +1 for 'git'
    if i >= len(tokens) or tokens[i] != "branch":
        return False
    # Get remaining args after 'branch'
    args = tokens[i + 1 :]
    # Unsafe flags: -d, -D, --delete, -m, -M, --move, -c, -C, --copy, --set-upstream-to,
    # --unset-upstream, --edit-description, --track, --no-track
    unsafe_flags = {
        "-d",
        "-D",
        "--delete",
        "-m",
        "-M",
        "--move",
        "-c",
        "-C",
        "--copy",
        "--set-upstream-to",
        "--unset-upstream",
        "--edit-description",
        "--track",
        "--no-track",
    }
    for arg in args:
        if arg.startswith("-"):
            # Check for =value suffix
            flag = arg.split("=")[0]
            if flag in unsafe_flags:
                return False
        else:
            # Non-flag argument after branch - could be creating a branch
            # Check if this is a pattern for --list or a ref for --contains/--merged
            # If no safe listing flags present, this is likely branch creation
            if not any(
                f in args
                for f in {
                    "--list",
                    "--contains",
                    "--merged",
                    "--no-merged",
                    "--points-at",
                }
            ):
                return False
    return True


def check_git_tag(tokens: list[str]) -> bool:
    """Approve git tag only for listing operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "tag":
        return False
    args = tokens[i + 1 :]
    # Safe flags: -l, --list, -n, --contains, --merged, --no-merged, --sort, --format,
    # --points-at, --column, --no-column
    # Unsafe flags: -a, --annotate, -s, --sign, -d, --delete, -v, --verify, -f, --force
    unsafe_flags = {
        "-a",
        "--annotate",
        "-s",
        "--sign",
        "-d",
        "--delete",
        "-v",
        "--verify",
        "-f",
        "--force",
        "-m",
        "--message",
        "-F",
        "--file",
        "-u",
        "--local-user",
    }
    has_list_flag = False
    for arg in args:
        if arg.startswith("-"):
            flag = arg.split("=")[0]
            if flag in unsafe_flags:
                return False
            if flag in {
                "-l",
                "--list",
                "-n",
                "--contains",
                "--merged",
                "--no-merged",
                "--points-at",
            }:
                has_list_flag = True
        else:
            # Non-flag argument - if no list flag present, this is tag creation
            if not has_list_flag:
                return False
    return True


def check_git_remote(tokens: list[str]) -> bool:
    """Approve git remote only for read-only operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "remote":
        return False
    args = tokens[i + 1 :]
    if not args:
        return True  # Just 'git remote' lists remotes
    # Check first non-flag argument for subcommand
    for arg in args:
        if arg.startswith("-"):
            continue
        # Safe subcommands: show, get-url
        # Unsafe: add, remove, rm, rename, set-url, set-head, set-branches, prune, update
        if arg in {"show", "get-url"}:
            return True
        return False
    # Only flags (like -v) - safe for listing
    return True


def check_git_config(tokens: list[str]) -> bool:
    """Approve git config only for read operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "config":
        return False
    args = tokens[i + 1 :]
    # Safe flags: --get, --get-all, --get-regexp, --list, -l, --show-origin, --show-scope,
    # --name-only, --type, --default
    # Unsafe flags: --unset, --unset-all, --add, --replace-all, --edit, -e, --rename-section,
    # --remove-section
    safe_flags = {
        "--get",
        "--get-all",
        "--get-regexp",
        "--list",
        "-l",
        "--show-origin",
        "--show-scope",
        "--name-only",
    }
    unsafe_flags = {
        "--unset",
        "--unset-all",
        "--add",
        "--replace-all",
        "--edit",
        "-e",
        "--rename-section",
        "--remove-section",
    }
    has_safe_flag = False
    for arg in args:
        if arg.startswith("-"):
            flag = arg.split("=")[0]
            if flag in unsafe_flags:
                return False
            if flag in safe_flags:
                has_safe_flag = True
    # If we have a safe flag, allow it
    if has_safe_flag:
        return True
    # If only scope flags (--global, --local, --system) with a key name, that's setting
    return False


def check_git_stash(tokens: list[str]) -> bool:
    """Approve git stash only for list/show operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "stash":
        return False
    args = tokens[i + 1 :]
    if not args:
        return False  # Just 'git stash' pushes a stash
    # Check first non-flag argument for subcommand
    for arg in args:
        if arg.startswith("-"):
            continue
        # Safe subcommands: list, show
        # Unsafe: push, pop, apply, drop, clear, branch, create, store
        return arg in {"list", "show"}
    return False


def check_git_notes(tokens: list[str]) -> bool:
    """Approve git notes only for list/show operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "notes":
        return False
    args = tokens[i + 1 :]
    if not args:
        return False  # Just 'git notes' - unclear intent
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg in {"list", "show"}
    return False


def check_git_worktree(tokens: list[str]) -> bool:
    """Approve git worktree only for list operations."""
    config = CLI_CONFIGS["git"]
    flags_with_arg = config.get("flags_with_arg", set())
    i = skip_flags(tokens[1:], flags_with_arg) + 1
    if i >= len(tokens) or tokens[i] != "worktree":
        return False
    args = tokens[i + 1 :]
    if not args:
        return False
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg == "list"
    return False


COMPOUND_CHECKS: dict[tuple[str, ...], Callable[[list[str]], bool]] = {
    ("auth0", "api"): check_auth0_api,
    ("aws", "secretsmanager"): check_aws_secretsmanager,
    ("aws", "ssm"): check_aws_ssm,
    ("az", "devops", "configure"): check_az_devops_configure,
    ("cdk", "context"): check_cdk_context,
    ("docker", "compose"): check_docker_compose,
    ("docker", "image", "save"): check_docker_image_save,
    ("docker", "save"): check_docker_save,
    ("gh", "api"): check_gh_api,
    ("gh", "browse"): check_gh_browse,
    ("gh", "search"): check_gh_search,
    ("gh", "status"): check_gh_status,
    ("git", "branch"): check_git_branch,
    ("git", "config"): check_git_config,
    ("git", "notes"): check_git_notes,
    ("git", "remote"): check_git_remote,
    ("git", "stash"): check_git_stash,
    ("git", "tag"): check_git_tag,
    ("git", "worktree"): check_git_worktree,
    ("kubectl", "config"): check_kubectl_config,
    ("kubectl", "rollout"): check_kubectl_rollout,
    ("terraform", "state"): check_terraform_state,
    ("terraform", "workspace"): check_terraform_workspace,
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

    # Check for subservice overrides (most specific first)
    # e.g., ("servicebus", "namespace", "authorization-rule", "keys") -> depth 4
    if i + 3 < len(tokens):
        key4 = (service, tokens[i + 1], tokens[i + 2], tokens[i + 3])
        if key4 in subservice_depths:
            depth = subservice_depths[key4]
        else:
            key3 = (service, tokens[i + 1], tokens[i + 2])
            if key3 in subservice_depths:
                depth = subservice_depths[key3]
            else:
                key2 = (service, tokens[i + 1])
                if key2 in subservice_depths:
                    depth = subservice_depths[key2]
                elif (service,) in subservice_depths:
                    depth = subservice_depths[(service,)]
    elif i + 2 < len(tokens):
        key3 = (service, tokens[i + 1], tokens[i + 2])
        if key3 in subservice_depths:
            depth = subservice_depths[key3]
        else:
            key2 = (service, tokens[i + 1])
            if key2 in subservice_depths:
                depth = subservice_depths[key2]
            elif (service,) in subservice_depths:
                depth = subservice_depths[(service,)]
    elif i + 1 < len(tokens):
        key2 = (service, tokens[i + 1])
        if key2 in subservice_depths:
            depth = subservice_depths[key2]
        elif (service,) in subservice_depths:
            depth = subservice_depths[(service,)]
    elif (service,) in subservice_depths:
        depth = subservice_depths[(service,)]

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

    if (
        "--help" in tokens
        or "-help" in tokens
        or "-h" in tokens
        or "--version" in tokens
    ):
        return True

    # Allow dippy to run itself (self-executing via uv run)
    try:
        if Path(tokens[0]).resolve() == Path(__file__).resolve():
            return True
    except Exception:
        pass

    cmd = tokens[0]
    args = tokens[1:]

    # Expand gh subcommand aliases (cs -> codespace, at -> attestation, etc.)
    if cmd == "gh" and args:
        # Skip global flags to find the subcommand
        config = CLI_CONFIGS.get("gh", {})
        flags_with_arg = config.get("flags_with_arg", set())
        i = skip_flags(args, flags_with_arg)
        if i < len(args) and args[i] in GH_SUBCOMMAND_ALIASES:
            expanded = GH_SUBCOMMAND_ALIASES[args[i]]
            args = args[:i] + [expanded] + args[i + 1 :]
            tokens = [cmd] + args

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
        # For gh, also check after skipping global flags like -R
        if prefix[0] == "gh" and cmd == "gh" and len(prefix) >= 2:
            config = CLI_CONFIGS.get("gh", {})
            flags_with_arg = config.get("flags_with_arg", set())
            i = skip_flags(args, flags_with_arg)
            if i > 0 and i < len(args) and args[i] == prefix[1]:
                # Reconstruct tokens with flags removed for the check
                return checker([cmd] + args[i:])

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
