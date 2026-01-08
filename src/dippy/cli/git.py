"""
Git command handler for Dippy.

Approves read-only git operations, blocks mutations.
"""

from typing import Optional


# Actions that only read data (no subcommands to check)
SAFE_ACTIONS = frozenset({
    # Status and info
    "status", "log", "show", "diff", "blame", "annotate",
    "shortlog", "describe", "rev-parse", "rev-list",

    # History navigation
    "reflog", "whatchanged",

    # Diff and comparison
    "diff-tree", "diff-files", "diff-index",
    "range-diff", "format-patch", "difftool",

    # Search
    "grep",

    # Inspection
    "ls-files", "ls-tree", "ls-remote",
    "cat-file", "verify-commit", "verify-tag",
    "name-rev", "merge-base",
    "show-ref", "show-branch",

    # Read-only utilities
    "check-ignore", "cherry", "for-each-ref",
    "count-objects", "fsck",
    "var", "request-pull",

    # Export (read-only, creates archive from repo content)
    "archive",

    # Fetch is read-only (downloads from remote but doesn't merge)
    "fetch",
})


# Actions that modify repository state
UNSAFE_ACTIONS = frozenset({
    # Commits and changes
    "commit", "add", "rm", "mv",
    "restore", "reset", "revert",

    # Remote operations (push modifies remote)
    "push", "pull",  # pull includes merge

    # Branch mutations (checkout can modify working tree)
    "checkout", "switch",
    "merge", "rebase", "cherry-pick",

    # Dangerous operations
    "clean", "gc", "prune",
    "filter-branch", "filter-repo",

    # Submodule mutations
    "submodule",  # Some subcommands mutate

    # Worktree mutations
    "worktree",
})


# Git global flags that take an argument (need to skip the argument)
GLOBAL_FLAGS_WITH_ARG = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--super-prefix", "--config-env",
})

# Git global flags that don't take an argument
GLOBAL_FLAGS_NO_ARG = frozenset({
    "--no-pager", "--paginate", "-p", "--no-replace-objects",
    "--bare", "--literal-pathspecs", "--glob-pathspecs",
    "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks",
})


def _find_action(tokens: list[str]) -> tuple[int, Optional[str]]:
    """
    Find the git action (subcommand) accounting for global flags.

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


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a git command should be approved or denied.

    Returns:
        (decision, description) where decision is "approve", "deny", or None.
    """
    if len(tokens) < 2:
        return None  # Just "git" with no subcommand

    # Find the actual action, skipping global flags
    action_idx, action = _find_action(tokens)
    if action is None:
        return None

    desc = f"git {action}"
    rest = tokens[action_idx + 1:] if action_idx + 1 < len(tokens) else []

    # Handle commands with subcommands that need special checks
    if action == "branch":
        return (_check_branch(rest), desc)
    elif action == "tag":
        return (_check_tag(rest), desc)
    elif action == "remote":
        return (_check_remote(rest), desc)
    elif action == "stash":
        return (_check_stash(rest), desc)
    elif action == "config":
        return (_check_config(rest), desc)
    elif action == "notes":
        return (_check_notes(rest), desc)
    elif action == "bisect":
        return (_check_bisect(rest), desc)
    elif action == "worktree":
        return (_check_worktree(rest), desc)
    elif action == "submodule":
        return (_check_submodule(rest), desc)
    elif action == "apply":
        return (_check_apply(rest), desc)
    elif action == "sparse-checkout":
        return (_check_sparse_checkout(rest), desc)
    elif action == "bundle":
        return (_check_bundle(rest), desc)
    elif action == "lfs":
        return (_check_lfs(rest), desc)
    elif action == "hash-object":
        return (_check_hash_object(rest), desc)
    elif action == "symbolic-ref":
        return (_check_symbolic_ref(rest), desc)
    elif action == "replace":
        return (_check_replace(rest), desc)
    elif action == "rerere":
        return (_check_rerere(rest), desc)

    # Explicitly safe actions
    if action in SAFE_ACTIONS:
        return ("approve", desc)

    # Explicitly unsafe actions
    if action in UNSAFE_ACTIONS:
        return (None, desc)  # Needs confirmation, not outright deny

    # Unknown action - ask user
    return (None, desc)


def _check_branch(rest: list[str]) -> Optional[str]:
    """Check git branch subcommand."""
    # Unsafe flags
    unsafe_flags = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy"}

    # Listing/query flags that take an argument
    listing_flags_with_arg = {"--list", "-l", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}

    for token in rest:
        if token in unsafe_flags:
            return None
        # --set-upstream-to modifies tracking
        if token.startswith("--set-upstream-to") or token == "-u":
            return None

    # If we have listing flags that consume the next argument, it's a read operation
    has_listing_flag = any(t in listing_flags_with_arg or t.startswith("--list") for t in rest)
    if has_listing_flag:
        return "approve"

    # If there's a non-flag argument, it's creating a branch
    for token in rest:
        if not token.startswith("-"):
            # This is a branch name for creation, not safe
            return None

    # Pure listing is safe
    return "approve"


def _check_tag(rest: list[str]) -> Optional[str]:
    """Check git tag subcommand."""
    # Unsafe flags for deletion
    unsafe_flags = {"-d", "--delete"}

    # Listing/query flags (that take an argument, so next non-flag is not a tag name)
    listing_flags = {"-l", "--list", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}

    for token in rest:
        if token in unsafe_flags:
            return None

    # If we have listing flags, it's a read operation
    has_listing_flag = any(t in listing_flags or t.startswith("--list") for t in rest)
    if has_listing_flag:
        return "approve"

    # If there's a non-flag argument, it's creating a tag
    for token in rest:
        if not token.startswith("-"):
            # This is a tag name for creation
            return None

    # Pure listing is safe
    return "approve"


def _check_remote(rest: list[str]) -> Optional[str]:
    """Check git remote subcommand."""
    if not rest:
        return "approve"  # Just "git remote" lists remotes

    subcommand = rest[0]

    # Safe subcommands
    safe = {"show", "-v", "--verbose", "get-url"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands
    unsafe = {"add", "remove", "rm", "rename", "set-url", "prune", "set-head", "set-branches"}
    if subcommand in unsafe:
        return None

    # Unknown - could be a remote name for listing
    return "approve"


def _check_stash(rest: list[str]) -> Optional[str]:
    """Check git stash subcommand."""
    if not rest:
        return None  # "git stash" alone creates a stash

    subcommand = rest[0]

    # Safe subcommands (read-only)
    safe = {"list", "show"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands (mutate stash or working tree)
    unsafe = {"push", "pop", "apply", "drop", "clear", "branch", "create", "store"}
    if subcommand in unsafe:
        return None

    # If it looks like a flag (e.g., git stash -u), it's creating a stash
    if subcommand.startswith("-"):
        return None

    # Unknown subcommand
    return None


def _check_config(rest: list[str]) -> Optional[str]:
    """Check git config subcommand."""
    # Editing flags
    edit_flags = {"-e", "--edit"}

    # Unsafe flags
    unsafe_flags = {"--unset", "--unset-all", "--add", "--replace-all", "--remove-section", "--rename-section"}

    for token in rest:
        if token in edit_flags:
            return None
        if token in unsafe_flags:
            return None

    # Safe flags (reading)
    safe_flags = {"--get", "--get-all", "--list", "-l", "--get-regexp", "--get-urlmatch"}

    for token in rest:
        if token in safe_flags:
            return "approve"

    # Count non-flag arguments (excluding --global/--local/--system)
    scope_flags = {"--global", "--local", "--system", "--worktree"}
    positional = [t for t in rest if not t.startswith("-") or t in scope_flags]
    actual_positional = [t for t in positional if t not in scope_flags]

    # "git config key" is reading, "git config key value" is writing
    if len(actual_positional) <= 1:
        return "approve"  # Reading a config value

    # Setting a config value
    return None


def _check_notes(rest: list[str]) -> Optional[str]:
    """Check git notes subcommand."""
    if not rest:
        return "approve"  # "git notes" lists notes

    subcommand = rest[0]

    # Safe subcommands
    safe = {"list", "show"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands
    unsafe = {"add", "copy", "append", "edit", "merge", "remove", "prune"}
    if subcommand in unsafe:
        return None

    # Unknown
    return None


def _check_bisect(rest: list[str]) -> Optional[str]:
    """Check git bisect subcommand."""
    if not rest:
        return None  # "git bisect" alone is ambiguous

    subcommand = rest[0]

    # Safe subcommands (read-only)
    safe = {"log", "visualize", "view"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands (modify bisect state)
    unsafe = {"start", "bad", "new", "good", "old", "terms", "skip", "reset", "run"}
    if subcommand in unsafe:
        return None

    return None


def _check_worktree(rest: list[str]) -> Optional[str]:
    """Check git worktree subcommand."""
    if not rest:
        return None

    subcommand = rest[0]

    # Safe subcommands
    if subcommand == "list":
        return "approve"

    # All other subcommands modify worktrees
    return None


def _check_submodule(rest: list[str]) -> Optional[str]:
    """Check git submodule subcommand."""
    if not rest:
        return None  # "git submodule" alone shows status but can be confusing

    subcommand = rest[0]

    # Safe subcommands
    safe = {"status", "summary", "foreach"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands
    unsafe = {"add", "init", "update", "deinit", "set-branch", "set-url", "sync", "absorbgitdirs"}
    if subcommand in unsafe:
        return None

    return None


def _check_apply(rest: list[str]) -> Optional[str]:
    """Check git apply subcommand."""
    # --check is a dry run, safe
    if "--check" in rest:
        return "approve"
    # Without --check, apply modifies working tree
    return None


def _check_sparse_checkout(rest: list[str]) -> Optional[str]:
    """Check git sparse-checkout subcommand."""
    if not rest:
        return None

    subcommand = rest[0]

    # Safe subcommands
    if subcommand == "list":
        return "approve"

    # Unsafe subcommands
    unsafe = {"init", "set", "add", "reapply", "disable"}
    if subcommand in unsafe:
        return None

    return None


def _check_bundle(rest: list[str]) -> Optional[str]:
    """Check git bundle subcommand."""
    if not rest:
        return None

    subcommand = rest[0]

    # Safe subcommands (read-only inspection)
    safe = {"verify", "list-heads"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands
    unsafe = {"create", "unbundle"}
    if subcommand in unsafe:
        return None

    return None


def _check_lfs(rest: list[str]) -> Optional[str]:
    """Check git lfs subcommand."""
    if not rest:
        return None

    subcommand = rest[0]

    # Safe subcommands (read-only)
    safe = {"fetch", "ls-files", "status", "env", "version"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands (modify LFS tracking or repo)
    unsafe = {"install", "uninstall", "track", "untrack", "pull", "push",
              "clone", "migrate", "prune", "dedup", "logs"}
    if subcommand in unsafe:
        return None

    return None


def _check_hash_object(rest: list[str]) -> Optional[str]:
    """Check git hash-object subcommand."""
    # -w writes the object to the database
    if "-w" in rest or "--write" in rest:
        return None
    # Without -w, just computes hash (read-only)
    return "approve"


def _check_symbolic_ref(rest: list[str]) -> Optional[str]:
    """Check git symbolic-ref subcommand."""
    # Count positional arguments (non-flags)
    positional = [t for t in rest if not t.startswith("-")]

    # Reading: git symbolic-ref HEAD (1 positional)
    # Writing: git symbolic-ref HEAD refs/heads/main (2 positional)
    if len(positional) <= 1:
        return "approve"

    return None


def _check_replace(rest: list[str]) -> Optional[str]:
    """Check git replace subcommand."""
    # Listing is safe
    if "-l" in rest or "--list" in rest or not rest:
        return "approve"

    # All other operations modify replace refs
    return None


def _check_rerere(rest: list[str]) -> Optional[str]:
    """Check git rerere subcommand."""
    if not rest:
        return "approve"  # Just "git rerere" shows status

    subcommand = rest[0]

    # Safe subcommands (read-only)
    safe = {"status", "diff"}
    if subcommand in safe:
        return "approve"

    # Unsafe subcommands
    unsafe = {"clear", "forget", "gc"}
    if subcommand in unsafe:
        return None

    return None
