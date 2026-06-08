"""
Find command handler for Dippy.

Find is mostly safe for searching, but has dangerous flags:
- -exec, -execdir: Execute arbitrary commands (delegates to inner command)
- -ok, -okdir: Interactive execution (always ask)
- -delete: Delete found files (always ask)
- -fprint, -fprint0, -fprintf, -fls: Write output to a file (checked against
  redirect rules, like a `> file` redirect)
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_join

COMMANDS = ["find"]

# Actions that write find's output to a file (truncating it), same effect as a
# `> file` redirect. The `f` prefix means "file" (vs. -print/-printf/-ls which
# write to stdout and are safe). The file argument follows the flag; we surface
# it as a redirect target so the usual allow-redirect/deny-redirect rules apply.
FILE_WRITE_ACTIONS = frozenset({"-fprint", "-fprint0", "-fprintf", "-fls"})

# Context for flags that aren't self-explanatory
FLAG_CONTEXT = {
    "-ok": "execute with prompt",
    "-okdir": "execute with prompt",
}


def classify(ctx: HandlerContext) -> Classification:
    """Classify find command by examining exec flags and delegating inner commands."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "find"
    write_targets: list[str] = []

    for i, token in enumerate(tokens):
        # -ok/-okdir are interactive - always ask
        if token in ("-ok", "-okdir"):
            context = FLAG_CONTEXT.get(token)
            return Classification("ask", description=f"{base} {token} ({context})")

        # -delete always unsafe
        if token == "-delete":
            return Classification("ask", description=f"{base} -delete")

        # -fprint/-fprintf/-fls write output to the following file; gate the
        # target through redirect rules, exactly like a `> file` redirect.
        if token in FILE_WRITE_ACTIONS:
            if i + 1 >= len(tokens):
                return Classification("ask", description=f"{base} {token}")
            write_targets.append(tokens[i + 1])
            continue

        # -exec/-execdir - extract inner command and delegate
        if token in ("-exec", "-execdir"):
            inner_tokens = []
            for j in range(i + 1, len(tokens)):
                if tokens[j] in (";", "+"):
                    break
                inner_tokens.append(tokens[j])

            if not inner_tokens:
                return Classification("ask", description=f"{base} {token}")

            inner_cmd = bash_join(inner_tokens)
            inner_name = inner_tokens[0]
            return Classification(
                "delegate",
                inner_command=inner_cmd,
                description=f"{base} {token} {inner_name}",
            )

    if write_targets:
        return Classification(
            "allow",
            description=f"{base} (write to file)",
            redirect_targets=tuple(write_targets),
        )

    return Classification("allow", description=base)
