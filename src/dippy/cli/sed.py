"""
Sed command handler for Dippy.

Sed is safe for text processing, but has several unsafe operations:
- -i flag modifies files in place
- w command writes to files (e.g., s/foo/bar/w output.txt)
- e command (GNU sed) executes pattern space as shell command
"""

from __future__ import annotations

import re

from dippy.cli import Classification, HandlerContext

COMMANDS = ["sed"]

# Flags that take a separate argument
FLAGS_WITH_ARG = frozenset({"-e", "--expression", "-f", "--file"})

# Pattern to detect 'w' command writing to a file
# Matches: s/pat/repl/w filename, /pat/w filename, w filename
# The w must be followed by a space and filename
WRITE_PATTERN = re.compile(
    r"""
    (?:
        /w\s+(\S+)          # /w filename (standalone w command or s///w)
        |
        w\s+(\S+)           # w filename at start of command
    )
    """,
    re.VERBOSE,
)

# Pattern to detect 'e' command (GNU sed - executes shell)
# Matches: s/pat/repl/e, /pat/e, e, e command
EXECUTE_PATTERN = re.compile(
    r"""
    (?:
        /e\s*(?:$|;)        # s///e or /pat/e (e flag at end)
        |
        (?:^|;)\s*e\s*(?:$|;|\s)  # standalone e command
    )
    """,
    re.VERBOSE,
)


def _extract_scripts(tokens: list[str]) -> list[str]:
    """Extract sed script strings from command tokens."""
    scripts = []
    i = 1
    found_script_arg = False

    while i < len(tokens):
        t = tokens[i]

        # -e script or --expression=script
        if t == "-e" or t == "--expression":
            if i + 1 < len(tokens):
                scripts.append(tokens[i + 1])
                found_script_arg = True
            i += 2
            continue
        if t.startswith("--expression="):
            scripts.append(t[13:])
            found_script_arg = True
            i += 1
            continue

        # Skip -f (script file - we can't analyze it)
        if t == "-f" or t == "--file":
            i += 2
            continue
        if t.startswith("--file="):
            i += 1
            continue

        # Skip other flags
        if t.startswith("-"):
            # Handle -i with optional suffix
            if t == "-i" or t.startswith("-i") or t.startswith("--in-place"):
                i += 1
                continue
            # Other flags
            i += 1
            continue

        # First non-flag, non -e/-f argument is the script (if no -e was used)
        if not found_script_arg and not scripts:
            scripts.append(t)
            found_script_arg = True
        i += 1

    return scripts


def _extract_write_targets(scripts: list[str]) -> list[str]:
    """Extract file paths from w commands in sed scripts."""
    targets = []
    for script in scripts:
        for match in WRITE_PATTERN.finditer(script):
            # Get whichever group matched
            path = match.group(1) or match.group(2)
            if path:
                targets.append(path)
    return targets


def _has_execute_command(scripts: list[str]) -> bool:
    """Check if any script contains the e command (shell execution)."""
    for script in scripts:
        if EXECUTE_PATTERN.search(script):
            return True
    return False


def _extract_inplace_files(tokens: list[str]) -> list[str]:
    """Extract input files that will be modified by -i flag."""
    files = []
    i = 1
    found_script = False
    has_e_flag = False

    # First pass: check if -e is used
    for t in tokens[1:]:
        if t == "-e" or t == "--expression" or t.startswith("--expression="):
            has_e_flag = True
            break

    # Second pass: extract files
    i = 1
    while i < len(tokens):
        t = tokens[i]

        # Skip flags with arguments
        if t in FLAGS_WITH_ARG:
            i += 2
            continue
        if t.startswith("--expression=") or t.startswith("--file="):
            i += 1
            continue

        # Skip -i variants
        if t == "-i" or t.startswith("-i") or t.startswith("--in-place"):
            i += 1
            continue

        # Skip other flags
        if t.startswith("-"):
            i += 1
            continue

        # Non-flag argument
        if not has_e_flag and not found_script:
            # First non-flag is the script when no -e is used
            found_script = True
            i += 1
            continue

        # This is an input file
        files.append(t)
        i += 1

    return files


def classify(ctx: HandlerContext) -> Classification:
    """Classify sed command for safety."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "sed"

    # Extract scripts for analysis
    scripts = _extract_scripts(tokens)

    # Check for e command (shell execution) - always unsafe
    if _has_execute_command(scripts):
        return Classification("ask", description=f"{base} e (execute)")

    # Check for w command (file writes)
    write_targets = _extract_write_targets(scripts)

    # Check for -i flag (in-place modification)
    has_inplace = False
    for t in tokens[1:]:
        if t == "-i" or t.startswith("-i"):
            has_inplace = True
            break
        if t == "--in-place" or t.startswith("--in-place"):
            has_inplace = True
            break

    # Collect all redirect targets
    redirect_targets = []

    if has_inplace:
        inplace_files = _extract_inplace_files(tokens)
        redirect_targets.extend(inplace_files)

    if write_targets:
        redirect_targets.extend(write_targets)

    # If we have any file writes, return with redirect_targets for rule checking
    if redirect_targets:
        desc = f"{base} -i" if has_inplace else f"{base} w"
        return Classification(
            "allow",
            description=desc,
            redirect_targets=tuple(redirect_targets),
        )

    # If -i flag present but no files found, still need confirmation
    # (could be edge case like -i'suffix' or just missing files)
    if has_inplace:
        return Classification("ask", description=f"{base} -i")

    return Classification("allow", description=base)
