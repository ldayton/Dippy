# Handler Patterns

All patterns assume `from dippy.cli import Classification, HandlerContext` is imported.

## Nested Subcommands

For CLIs with nested structure (e.g., `aws s3 ls`, `kubectl get pods`):

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    if len(tokens) < 3:
        return Classification("ask", description="cmd")
    action = tokens[2]
    if action in {"list", "describe", "get"}:
        return Classification("allow", description=f"cmd {tokens[1]} {action}")
    return Classification("ask", description=f"cmd {tokens[1]}")
```

## Flag-Dependent Safety

When flags determine safety (e.g., `git apply --check`):

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    if "--check" in tokens or "--dry-run" in tokens:
        return Classification("allow", description="cmd --dry-run")
    return Classification("ask", description="cmd")
```

## Delegation

For wrappers like `xargs`, `env`:

```python
def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    inner_cmd = extract_inner_command(tokens)
    if not inner_cmd:
        return Classification("ask", description="wrapper")
    return Classification("delegate", inner_command=inner_cmd)
```

## Safety Principles

The core question: **"Could this change something the user would care about?"**

1. When in doubt, require confirmation
2. Harmless side effects are OK (cache dirs, logs, timestamps)
3. User data/state changes are not OK
4. External effects are not OK (emails, APIs, deploys)
5. Interactive commands need confirmation

### Flags That Make Commands Unsafe
- `--force`, `-f`: Bypasses safety checks
- `--delete`, `-d`: Enables deletion
- `--write`, `-w`: Enables writing
- `--execute`, `-e`: Enables execution

### Flags That Are Always Safe
- `--help`, `-h`: Show help
- `--version`, `-v`: Show version
- `--dry-run`, `-n`: Preview without executing
- `--list`, `-l`: List mode
