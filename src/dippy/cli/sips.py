"""
Sips command handler for Dippy.

macOS scriptable image processing system.
- -g/--getProperty, --verify are safe read operations
- Most other flags modify images: -s, -d, -e, -r, -f, -c, -p, -z, -Z, -i, etc.
- -o/--out specifies output file for modifications
- -x/--extractProfile extracts embedded profile to specified file
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["sips"]

# Safe read-only flags
SAFE_FLAGS = frozenset(
    {"-g", "--getProperty", "--verify", "-1", "--oneLine", "-h", "--help"}
)

# Flags that take an argument (for skipping during analysis)
FLAGS_WITH_ARG = frozenset(
    {
        "-g",
        "--getProperty",
        "-X",
        "--extractTag",
        "-s",
        "--setProperty",  # takes key and value
        "-d",
        "--deleteProperty",
        "-x",
        "--extractProfile",
        "-e",
        "--embedProfile",
        "-E",
        "--embedProfileIfNone",
        "-m",
        "--matchTo",
        "-M",
        "--matchToWithIntent",
        "-r",
        "--rotate",
        "-f",
        "--flip",
        "-c",
        "--cropToHeightWidth",
        "-p",
        "--padToHeightWidth",
        "-z",
        "--resampleHeightWidth",
        "-Z",
        "--resampleHeightWidthMax",
        "-o",
        "--out",
        "--padColor",
        "--cropOffset",
        "--resampleWidth",
        "--resampleHeight",
        "--deleteTag",
        "--copyTag",
        "--loadTag",
    }
)


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--out flag."""
    for i, t in enumerate(tokens):
        if t in {"-o", "--out"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _extract_profile_file(tokens: list[str]) -> str | None:
    """Extract the profile file from -x/--extractProfile flag."""
    for i, t in enumerate(tokens):
        if t in {"-x", "--extractProfile"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _is_read_only(tokens: list[str]) -> bool:
    """Check if command only uses read-only flags."""
    i = 1
    has_operation = False
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("-"):
            if t in SAFE_FLAGS:
                has_operation = True
                # -g takes one argument
                if t in {"-g", "--getProperty"}:
                    i += 2
                    continue
            else:
                # Any other flag is potentially unsafe
                return False
        i += 1
    return has_operation or len(tokens) == 2  # Just "sips file" queries


def classify(ctx: HandlerContext) -> Classification:
    """Classify sips command."""
    tokens = ctx.tokens
    if _is_read_only(tokens):
        return Classification("allow", description="sips")
    # Check for extractProfile (writes to specified file)
    profile_file = _extract_profile_file(tokens)
    if profile_file:
        return Classification(
            "allow",
            description="sips -x",
            redirect_targets=(profile_file,),
        )
    # Check for output file
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description="sips",
            redirect_targets=(output_file,),
        )
    # Modifying in place
    return Classification("ask", description="sips")
