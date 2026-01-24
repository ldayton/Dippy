"""
Find command handler for Dippy.

Find is mostly safe for searching, but has dangerous flags:
- -exec, -execdir: Execute arbitrary commands (delegates to inner command)
- -ok, -okdir: Interactive execution (always ask)
- -delete: Delete found files (always ask)
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_join

COMMANDS = ["find"]

# Context for flags that aren't self-explanatory
FLAG_CONTEXT = {
    "-ok": "execute with prompt",
    "-okdir": "execute with prompt",
}


def classify(ctx: HandlerContext) -> Classification:
    """Classify find command by examining exec flags and delegating inner commands."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "find"

    for i, token in enumerate(tokens):
        # -ok/-okdir are interactive - always ask
        if token in ("-ok", "-okdir"):
            context = FLAG_CONTEXT.get(token)
            return Classification("ask", description=f"{base} {token} ({context})")

        # -delete always unsafe
        if token == "-delete":
            return Classification("ask", description=f"{base} -delete")

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

    return Classification("allow", description=base)
