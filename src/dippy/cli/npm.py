"""
Node package manager CLI handler for Dippy.

Handles npm, yarn, and pnpm commands.
"""


SAFE_ACTIONS = frozenset({
    "list", "ls", "ll", "la",
    "info", "show", "view", "v",
    "search", "s", "find",
    "outdated",
    "help", "help-search",
    "-v", "--version",
    "get",
    "root", "prefix", "bin",
    "docs", "home", "bugs", "repo",
    "whoami", "ping",
    "explain", "why",
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
})


UNSAFE_ACTIONS = frozenset({
    "install", "i", "add",
    "uninstall", "remove", "rm", "un", "r",
    "update", "upgrade", "up",
    "exec", "x", "run-script",
    "start", "stop", "restart", "test", "t",
    "publish", "unpublish",
    "link", "unlink",
    "prune", "dedupe", "ddp",
    "rebuild", "rb", "build",
    "init", "create",
    "set",
    "login", "adduser", "logout",
    "deprecate", "undeprecate",
    "edit", "explore",
    "org", "team",
    "shrinkwrap",
    "star", "unstar",
    "ci", "install-ci-test", "install-test",
    "global",
    "store",
})


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
    "version": {"major", "minor", "patch", "premajor", "preminor", "prepatch", "prerelease"},
}


def check(tokens: list[str]) -> bool:
    """Check if npm/yarn/pnpm command is safe."""
    if len(tokens) < 2:
        return False

    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []

    # Handle "npm run" without arguments (just lists scripts)
    if action == "run" and not rest:
        return True

    # Handle "npm run --list" (safe)
    if action == "run" and "--list" in rest:
        return True

    # Handle "npm version" - without arguments shows version, with args modifies
    if action == "version":
        return not rest

    # Handle "npm audit" - safe for viewing, but "audit fix" is unsafe
    if action == "audit":
        return not (rest and rest[0] == "fix")

    # Handle "npm config" / "npm c"
    if action in ("config", "c"):
        if rest:
            subaction = rest[0]
            if subaction in SAFE_SUBCOMMANDS.get("config", set()):
                return True
            if subaction in UNSAFE_SUBCOMMANDS.get("config", set()):
                return False
        return True  # "npm config" alone shows help

    # Check commands with safe/unsafe subcommands
    if action in SAFE_SUBCOMMANDS:
        if rest:
            subaction = rest[0]
            if subaction in SAFE_SUBCOMMANDS[action]:
                return True
            if action in UNSAFE_SUBCOMMANDS and subaction in UNSAFE_SUBCOMMANDS[action]:
                return False
        if action in ("owner",):
            return True  # "npm owner" alone lists
        return False

    if action in UNSAFE_SUBCOMMANDS and action not in SAFE_SUBCOMMANDS:
        return False

    if action in SAFE_ACTIONS:
        return True

    return False
