"""tee command handler - writes stdin to files."""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["tee"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify tee command by extracting target files."""
    tokens = ctx.tokens
    base = "tee"
    targets = []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t == "--":
            # Everything after -- is a file
            targets.extend(tokens[i + 1 :])
            break
        elif t.startswith("-"):
            i += 1
            continue
        else:
            targets.append(t)
        i += 1
    if not targets:
        # tee with no files just copies stdin to stdout
        return Classification("allow", description=base)
    desc = (
        f"{base} {targets[0]}" if len(targets) == 1 else f"{base} {len(targets)} files"
    )
    return Classification(
        "allow",
        description=desc,
        redirect_targets=tuple(targets),
    )
