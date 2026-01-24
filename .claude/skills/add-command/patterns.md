# Handler Styles

These are informal patterns, not formal types. See the [wiki](../../../Dippy.wiki/Reference/Handler-Model.md) for full documentation.

All patterns assume `from dippy.cli import Classification, HandlerContext` is imported.

## Subcommand

Multi-level CLIs where safety depends on which subcommand is invoked.

```python
SAFE_ACTIONS = frozenset({"status", "list", "show"})

def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    action = tokens[1] if len(tokens) > 1 else None
    if action in SAFE_ACTIONS:
        return Classification("allow", description=f"cmd {action}")
    return Classification("ask", description="cmd")
```

Examples: `git status` safe, `git push` unsafe

## Flag-check

Commands safe by default but specific flags enable writes or side effects.

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    if "-i" in tokens or "--in-place" in tokens:
        return Classification("ask", description="cmd modifies in place")
    return Classification("allow", description="cmd")
```

Examples: `sed` safe, `sed -i` modifies files

## Delegate

Wrapper commands that execute other commands.

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    inner_tokens = tokens[2:]  # Skip wrapper and flags
    if not inner_tokens:
        return Classification("ask", description="wrapper")
    return Classification("delegate", inner_command=" ".join(inner_tokens))
```

Examples: `xargs rm` delegates to `rm`, `env FOO=bar python` delegates to `python`

## Arg-count

Safety depends on argument count. Typically viewing vs. modifying.

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    if len(tokens) == 2:  # Just command + target
        return Classification("allow", description="cmd view")
    return Classification("ask", description="cmd modify")
```

Examples: `ifconfig eth0` views, `ifconfig eth0 192.168.1.1` modifies

## Ask

Commands with no safe mode. Don't create handlers—they'll default to ask.

Examples: `rm`, `mktemp`, `pbcopy`

## Safety Principles

The core question: **"Could this change something the user would care about?"**

1. When in doubt, require confirmation
2. Harmless side effects are OK (cache dirs, logs, timestamps)
3. User data/state changes are not OK
4. External effects are not OK (emails, APIs, deploys)
5. Interactive commands need confirmation
