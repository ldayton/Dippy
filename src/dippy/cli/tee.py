"""tee command handler - writes stdin to files."""

from dippy.cli import Classification

COMMANDS = ["tee"]


def classify(tokens: list[str]) -> Classification:
    """Classify tee command by extracting target files."""
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
        return Classification("approve", description=base)
    desc = (
        f"{base} {targets[0]}" if len(targets) == 1 else f"{base} {len(targets)} files"
    )
    return Classification(
        "approve",
        description=desc,
        redirect_targets=tuple(targets),
    )
