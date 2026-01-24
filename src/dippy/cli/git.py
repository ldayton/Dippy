"""
Git command handler for Dippy.

Approves read-only git operations, blocks mutations.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["git"]

# Actions that only read data (no subcommands to check)
SAFE_ACTIONS = frozenset(
    {
        # Status and info
        "status",
        "log",
        "show",
        "diff",
        "blame",
        "annotate",
        "shortlog",
        "describe",
        "rev-parse",
        "rev-list",
        # History navigation
        "reflog",
        "whatchanged",
        # Diff and comparison
        "diff-tree",
        "diff-files",
        "diff-index",
        "range-diff",
        "format-patch",
        "difftool",
        # Search
        "grep",
        # Inspection
        "ls-files",
        "ls-tree",
        "ls-remote",
        "cat-file",
        "verify-commit",
        "verify-tag",
        "name-rev",
        "merge-base",
        "show-ref",
        "show-branch",
        # Read-only utilities
        "check-ignore",
        "cherry",
        "for-each-ref",
        "count-objects",
        "fsck",
        "var",
        "request-pull",
        # Export (read-only, creates archive from repo content)
        "archive",
        # Fetch is read-only (downloads from remote but doesn't merge)
        "fetch",
    }
)


# Actions that modify repository state
UNSAFE_ACTIONS = frozenset(
    {
        # Commits and changes
        "commit",
        "add",
        "rm",
        "mv",
        "restore",
        "reset",
        "revert",
        # Remote operations (push modifies remote)
        "push",
        "pull",  # pull includes merge
        # Branch mutations (checkout can modify working tree)
        "checkout",
        "switch",
        "merge",
        "rebase",
        "cherry-pick",
        # Dangerous operations
        "clean",
        "gc",
        "prune",
        "filter-branch",
        "filter-repo",
        # Submodule mutations
        "submodule",  # Some subcommands mutate
        # Worktree mutations
        "worktree",
    }
)

# Actions where extra context helps (name isn't self-explanatory)
UNCLEAR_ACTION_CONTEXT = {
    "gc": "garbage collect",
    "prune": "remove unreachable objects",
    "filter-branch": "rewrite history",
    "filter-repo": "rewrite history",
}


# Git global flags that take an argument (need to skip the argument)
GLOBAL_FLAGS_WITH_ARG = frozenset(
    {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--super-prefix",
        "--config-env",
    }
)

# Git global flags that don't take an argument
GLOBAL_FLAGS_NO_ARG = frozenset(
    {
        "--no-pager",
        "--paginate",
        "-p",
        "--no-replace-objects",
        "--bare",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
        "--no-optional-locks",
    }
)


def _find_action(tokens: list[str]) -> tuple[int, str | None]:
    """Find the git action (subcommand) accounting for global flags.

    Returns (index, action) or (-1, None) if not found.
    """
    i = 1  # Start after "git"
    while i < len(tokens):
        token = tokens[i]

        # Skip global flags with arguments
        if token in GLOBAL_FLAGS_WITH_ARG:
            i += 2  # Skip flag and its argument
            continue

        # Handle combined form like --git-dir=/path
        if any(token.startswith(f"{flag}=") for flag in GLOBAL_FLAGS_WITH_ARG):
            i += 1
            continue

        # Skip global flags without arguments
        if token in GLOBAL_FLAGS_NO_ARG:
            i += 1
            continue

        # Skip -c key=value form
        if token == "-c" and i + 1 < len(tokens):
            i += 2
            continue

        # Found the action
        if not token.startswith("-"):
            return i, token

        # Unknown flag - might be action-specific, bail
        break

    return -1, None


def get_description(tokens: list[str], include_context: bool = False) -> str:
    """Compute description for git command, skipping global flags."""
    _, action = _find_action(tokens)
    if action:
        if include_context and action in UNCLEAR_ACTION_CONTEXT:
            return f"git {action} ({UNCLEAR_ACTION_CONTEXT[action]})"
        return f"git {action}"
    return "git"


def classify(ctx: HandlerContext) -> Classification:
    """Classify git command."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        return Classification("ask", description="git")

    # Find the actual action, skipping global flags
    action_idx, action = _find_action(tokens)
    if action is None:
        return Classification("ask", description="git")

    rest = tokens[action_idx + 1 :] if action_idx + 1 < len(tokens) else []

    # Handle commands with subcommands that need special checks
    if action == "branch":
        safe = _check_branch(rest)
    elif action == "tag":
        safe = _check_tag(rest)
    elif action == "remote":
        safe = _check_remote(rest)
    elif action == "stash":
        safe = _check_stash(rest)
    elif action == "config":
        safe = _check_config(rest)
    elif action == "notes":
        safe = _check_notes(rest)
    elif action == "bisect":
        safe = _check_bisect(rest)
    elif action == "worktree":
        safe = _check_worktree(rest)
    elif action == "submodule":
        safe = _check_submodule(rest)
    elif action == "apply":
        safe = _check_apply(rest)
    elif action == "sparse-checkout":
        safe = _check_sparse_checkout(rest)
    elif action == "bundle":
        safe = _check_bundle(rest)
    elif action == "lfs":
        safe = _check_lfs(rest)
    elif action == "hash-object":
        safe = _check_hash_object(rest)
    elif action == "symbolic-ref":
        safe = _check_symbolic_ref(rest)
    elif action == "replace":
        safe = _check_replace(rest)
    elif action == "rerere":
        safe = _check_rerere(rest)
    elif action in SAFE_ACTIONS:
        safe = True
    else:
        safe = False

    desc = get_description(tokens, include_context=not safe)
    return Classification("allow" if safe else "ask", description=desc)


def _check_branch(rest: list[str]) -> bool:
    """Check git branch subcommand."""
    unsafe_flags = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy"}
    listing_flags_with_arg = {
        "--list",
        "-l",
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
    }

    for token in rest:
        if token in unsafe_flags:
            return False
        if token.startswith("--set-upstream-to") or token == "-u":
            return False

    has_listing_flag = any(
        t in listing_flags_with_arg or t.startswith("--list") for t in rest
    )
    if has_listing_flag:
        return True

    for token in rest:
        if not token.startswith("-"):
            return False  # Branch name for creation

    return True  # Pure listing


def _check_tag(rest: list[str]) -> bool:
    """Check git tag subcommand."""
    unsafe_flags = {"-d", "--delete"}
    listing_flags = {
        "-l",
        "--list",
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
    }

    for token in rest:
        if token in unsafe_flags:
            return False

    has_listing_flag = any(t in listing_flags or t.startswith("--list") for t in rest)
    if has_listing_flag:
        return True

    for token in rest:
        if not token.startswith("-"):
            return False  # Tag name for creation

    return True  # Pure listing


def _check_remote(rest: list[str]) -> bool:
    """Check git remote subcommand."""
    if not rest:
        return True  # Just "git remote" lists remotes

    subcommand = rest[0]
    safe = {"show", "-v", "--verbose", "get-url"}
    if subcommand in safe:
        return True

    unsafe = {
        "add",
        "remove",
        "rm",
        "rename",
        "set-url",
        "prune",
        "set-head",
        "set-branches",
    }
    if subcommand in unsafe:
        return False

    return True  # Unknown - could be a remote name for listing


def _check_stash(rest: list[str]) -> bool:
    """Check git stash subcommand."""
    if not rest:
        return False  # "git stash" alone creates a stash

    subcommand = rest[0]
    safe = {"list", "show"}
    if subcommand in safe:
        return True

    unsafe = {"push", "pop", "apply", "drop", "clear", "branch", "create", "store"}
    if subcommand in unsafe:
        return False

    if subcommand.startswith("-"):
        return False  # Flag means creating a stash

    return False


def _check_config(rest: list[str]) -> bool:
    """Check git config subcommand."""
    edit_flags = {"-e", "--edit"}
    unsafe_flags = {
        "--unset",
        "--unset-all",
        "--add",
        "--replace-all",
        "--remove-section",
        "--rename-section",
    }

    for token in rest:
        if token in edit_flags or token in unsafe_flags:
            return False

    safe_flags = {
        "--get",
        "--get-all",
        "--list",
        "-l",
        "--get-regexp",
        "--get-urlmatch",
    }
    for token in rest:
        if token in safe_flags:
            return True

    scope_flags = {"--global", "--local", "--system", "--worktree"}
    positional = [t for t in rest if not t.startswith("-") or t in scope_flags]
    actual_positional = [t for t in positional if t not in scope_flags]

    return len(actual_positional) <= 1  # Reading vs writing


def _check_notes(rest: list[str]) -> bool:
    """Check git notes subcommand."""
    if not rest:
        return True  # Lists notes

    subcommand = rest[0]
    safe = {"list", "show"}
    if subcommand in safe:
        return True

    unsafe = {"add", "copy", "append", "edit", "merge", "remove", "prune"}
    return subcommand not in unsafe


def _check_bisect(rest: list[str]) -> bool:
    """Check git bisect subcommand."""
    if not rest:
        return False

    subcommand = rest[0]
    safe = {"log", "visualize", "view"}
    return subcommand in safe


def _check_worktree(rest: list[str]) -> bool:
    """Check git worktree subcommand."""
    if not rest:
        return False
    return rest[0] == "list"


def _check_submodule(rest: list[str]) -> bool:
    """Check git submodule subcommand."""
    if not rest:
        return False

    subcommand = rest[0]
    safe = {"status", "summary", "foreach"}
    return subcommand in safe


def _check_apply(rest: list[str]) -> bool:
    """Check git apply subcommand."""
    return "--check" in rest


def _check_sparse_checkout(rest: list[str]) -> bool:
    """Check git sparse-checkout subcommand."""
    if not rest:
        return False
    return rest[0] == "list"


def _check_bundle(rest: list[str]) -> bool:
    """Check git bundle subcommand."""
    if not rest:
        return False

    subcommand = rest[0]
    safe = {"verify", "list-heads"}
    return subcommand in safe


def _check_lfs(rest: list[str]) -> bool:
    """Check git lfs subcommand."""
    if not rest:
        return False

    subcommand = rest[0]
    safe = {"fetch", "ls-files", "status", "env", "version"}
    return subcommand in safe


def _check_hash_object(rest: list[str]) -> bool:
    """Check git hash-object subcommand."""
    return "-w" not in rest and "--write" not in rest


def _check_symbolic_ref(rest: list[str]) -> bool:
    """Check git symbolic-ref subcommand."""
    positional = [t for t in rest if not t.startswith("-")]
    return len(positional) <= 1


def _check_replace(rest: list[str]) -> bool:
    """Check git replace subcommand."""
    return "-l" in rest or "--list" in rest or not rest


def _check_rerere(rest: list[str]) -> bool:
    """Check git rerere subcommand."""
    if not rest:
        return True

    subcommand = rest[0]
    safe = {"status", "diff"}
    return subcommand in safe
