"""
Node package manager CLI handler for Dippy.

Handles npm, yarn, and pnpm commands.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["npm", "yarn", "pnpm"]

SAFE_ACTIONS = frozenset(
    {
        "list",
        "ls",
        "ll",
        "la",
        "info",
        "show",
        "view",
        "v",
        "search",
        "s",
        "find",
        "outdated",
        "help",
        "help-search",
        "-v",
        "--version",
        "get",
        "root",
        "prefix",
        "bin",
        "docs",
        "home",
        "bugs",
        "repo",
        "whoami",
        "ping",
        "explain",
        "why",
        "pack",  # Creates tarball but doesn't publish
        "fund",
        "doctor",  # Health check
        "licenses",  # yarn/pnpm licenses list
        "completion",
        "diff",
        "find-dupes",
        "query",
        "stars",
        "sbom",
    }
)


UNSAFE_ACTIONS = frozenset(
    {
        "install",
        "i",
        "add",
        "uninstall",
        "remove",
        "rm",
        "un",
        "r",
        "update",
        "upgrade",
        "up",
        "exec",
        "x",
        "run-script",
        "start",
        "stop",
        "restart",
        "test",
        "t",
        "publish",
        "unpublish",
        "link",
        "unlink",
        "prune",
        "dedupe",
        "ddp",
        "rebuild",
        "rb",
        "build",
        "init",
        "create",
        "set",
        "login",
        "adduser",
        "logout",
        "deprecate",
        "undeprecate",
        "edit",
        "explore",
        "org",
        "team",
        "shrinkwrap",
        "star",
        "unstar",
        "ci",
        "install-ci-test",
        "install-test",
        "global",
        "store",
    }
)


# Commands with subcommands that need special handling
SAFE_SUBCOMMANDS = {
    "config": {"list", "ls", "get"},
    "cache": {"ls", "list"},
    "run": {"--list"},
    "access": {"list", "get"},
    "dist-tag": {"ls"},
    "token": {"list"},
    "profile": {"get"},
    "pkg": {"get"},
    "owner": {"ls"},
}

# Commands with unsafe subcommands
UNSAFE_SUBCOMMANDS = {
    "config": {"set", "delete", "edit"},
    "cache": {"clean", "add", "verify"},
    "access": {"set", "grant", "revoke"},
    "dist-tag": {"add", "rm"},
    "token": {"create", "revoke"},
    "profile": {"set", "enable-2fa", "disable-2fa"},
    "pkg": {"set", "delete", "fix"},
    "owner": {"add", "rm"},
    "audit": {"fix"},
    "version": {
        "major",
        "minor",
        "patch",
        "premajor",
        "preminor",
        "prepatch",
        "prerelease",
    },
}


# Short aliases that need expansion for clarity
ACTION_ALIASES = {
    "i": "install",
    "rm": "remove",
    "un": "uninstall",
    "r": "remove",
    "x": "exec",
    "t": "test",
    "s": "search",
    "ddp": "dedupe",
    "rb": "rebuild",
    "c": "config",
}


def classify(tokens: list[str]) -> Classification:
    """Classify npm/yarn/pnpm command."""
    base = tokens[0] if tokens else "npm"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []
    # Expand short aliases for clarity in description
    display_action = ACTION_ALIASES.get(action, action)
    desc = f"{base} {display_action}"

    # Handle "npm run" without arguments (just lists scripts)
    if action == "run" and not rest:
        return Classification("approve", description=desc)

    # Handle "npm run --list" (safe)
    if action == "run" and "--list" in rest:
        return Classification("approve", description=desc)

    # Handle "npm version" - without arguments shows version, with args modifies
    if action == "version":
        if not rest:
            return Classification("approve", description=desc)
        return Classification("ask", description=desc)

    # Handle "npm audit" - safe for viewing, but "audit fix" is unsafe
    if action == "audit":
        if rest and rest[0] == "fix":
            return Classification("ask", description=f"{desc} fix")
        return Classification("approve", description=desc)

    # Handle "npm config" / "npm c"
    if action in ("config", "c"):
        if rest:
            subaction = rest[0]
            if subaction in SAFE_SUBCOMMANDS.get("config", set()):
                return Classification("approve", description=f"{desc} {subaction}")
            if subaction in UNSAFE_SUBCOMMANDS.get("config", set()):
                return Classification("ask", description=f"{desc} {subaction}")
        return Classification(
            "approve", description=desc
        )  # "npm config" alone shows help

    # Check commands with safe/unsafe subcommands
    if action in SAFE_SUBCOMMANDS:
        if rest:
            subaction = rest[0]
            if subaction in SAFE_SUBCOMMANDS[action]:
                return Classification("approve", description=f"{desc} {subaction}")
            if action in UNSAFE_SUBCOMMANDS and subaction in UNSAFE_SUBCOMMANDS[action]:
                return Classification("ask", description=f"{desc} {subaction}")
        if action in ("owner",):
            return Classification(
                "approve", description=desc
            )  # "npm owner" alone lists
        return Classification("ask", description=desc)

    if action in UNSAFE_SUBCOMMANDS and action not in SAFE_SUBCOMMANDS:
        return Classification("ask", description=desc)

    if action in SAFE_ACTIONS:
        return Classification("approve", description=desc)

    return Classification("ask", description=desc)
