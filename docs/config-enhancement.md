# Dippy Pattern Matching: Gaps and Proposed Enhancements

## Current State

Config patterns support three matching modes:

| Mode   | Syntax           | Example                 | Behavior                                   |
| ------ | ---------------- | ----------------------- | ------------------------------------------ |
| Prefix | `cmd args`       | `git stash`             | Matches `git stash`, `git stash pop`, etc. |
| Regex  | `re:pattern`     | `re:^make (test\|lint)` | Full command regex match                   |
| Script | `path/to/script` | `./deploy.sh`           | Exact resolved path match                  |

## Gaps

### 1. No Glob Support

```toml
# Desired
approve = ["scripts/*.sh"]

# Reality: treated as literal path, not glob
# Must use regex instead:
approve = ["re:^\\./scripts/[^/]+\\.sh"]
```

### 2. No Negation

```toml
# Desired
approve = ["git *"]
confirm = ["!git push --force"]  # Exclude specific variant

# Reality: no negation syntax
# Workaround: enumerate everything you DO want
approve = ["git status", "git log", "git diff", ...]
```

### 3. No Flag Matching

CLI handlers distinguish `helm install` (unsafe) from `helm install --dry-run` (safe). Config patterns cannot:

```toml
# Desired
approve = ["helm install --dry-run"]  # Only with this flag

# Reality: prefix match approves ANY helm install
approve = ["helm install"]  # Matches "helm install --force" too
```

### 4. No Wildcard Token Matching

```toml
# Desired
approve = ["git * --help"]  # Any git subcommand with --help

# Reality: must use regex
approve = ["re:^git \\S+ --help$"]
```

### 5. No Position-Independent Flag Matching

```toml
# Desired: approve any command with --dry-run anywhere
approve = ["* --dry-run"]

# Reality: impossible without per-command regex patterns
```

### 6. Prefix-Only Limitation

Token matching only works as prefix:

```toml
approve = ["git stash"]  # Matches "git stash pop" ✓

# Cannot match middle or end:
# "git * pop" - no way to express
# "* --verbose" - no way to express
```

## Proposed Enhancements

### Option A: Extended Pattern Syntax

Add glob-like wildcards to token matching:

```toml
approve = [
    "git *",                    # Any git subcommand
    "git * --help",             # Any git subcommand with --help
    "scripts/*.sh",             # Glob in paths
    "!git push --force",        # Negation
    "helm install +--dry-run",  # Require flag present (+flag)
    "docker run -—privileged",  # Require flag absent (-flag)
]
```

**Syntax:**
- `*` — Match any single token
- `**` — Match zero or more tokens
- `!pattern` — Negation (in confirm list: always ask; in approve list: exclude)
- `+--flag` — Require flag present anywhere
- `-—flag` — Require flag absent

### Option B: Structured Pattern Objects

Replace string patterns with structured objects for complex cases:

```toml
[[approve]]
command = "helm"
action = "install"
require_flags = ["--dry-run"]

[[approve]]
command = "git"
action = "*"
deny_flags = ["--force", "-f"]

[[approve]]
command = "scripts/*.sh"
type = "glob"
```

### Option C: Flag Modifiers on Existing Patterns

Keep string patterns but add flag modifiers:

```toml
approve = [
    "helm install",
    "git push",
]

[flag_modifiers]
"helm install" = { require = ["--dry-run"] }
"git push" = { deny = ["--force", "-f"] }
```

### Option D: Security Toggles

Add project-level toggles for common security checks:

```toml
[security]
allow_redirects = true          # Skip redirect check
allow_redirects_to = ["/tmp/"]  # Allow redirects to specific paths
allow_pipes = true              # Skip pipe validation
allow_cmdsubs = true            # Skip command substitution check
```

## Recommendations

### Minimum Viable Enhancement

Add **Option D** (security toggles) immediately—solves the redirect issue that prompted this research:

```toml
[security]
allow_redirects = true
```

### Short-Term Enhancement

Add basic wildcards from **Option A**:

```toml
approve = [
    "git *",           # Wildcard token
    "scripts/*.sh",    # Glob paths
]
```

### Long-Term Enhancement

Implement flag modifiers (**Option C**) for sophisticated matching without breaking existing configs:

```toml
approve = ["helm install"]

[flag_modifiers]
"helm install" = { require = ["--dry-run"] }
```

## Implementation Notes

### Wildcard Token Matching

```python
def matches_pattern(command: str, pattern: str, tokens: list[str], ...) -> bool:
    # Existing regex handling
    if pattern.startswith("re:"):
        return bool(re.match(pattern[3:], command))

    # NEW: Wildcard token matching
    pattern_tokens = pattern.split()
    return _match_wildcard_tokens(tokens, pattern_tokens)

def _match_wildcard_tokens(tokens: list[str], pattern: list[str]) -> bool:
    """Match tokens against pattern with * and ** wildcards."""
    t_idx, p_idx = 0, 0
    while p_idx < len(pattern):
        pat = pattern[p_idx]
        if pat == "**":
            # Match zero or more tokens
            if p_idx == len(pattern) - 1:
                return True  # ** at end matches everything
            # Try matching rest of pattern at each position
            for i in range(t_idx, len(tokens) + 1):
                if _match_wildcard_tokens(tokens[i:], pattern[p_idx + 1:]):
                    return True
            return False
        elif pat == "*":
            # Match exactly one token
            if t_idx >= len(tokens):
                return False
            t_idx += 1
            p_idx += 1
        else:
            # Exact match
            if t_idx >= len(tokens) or tokens[t_idx] != pat:
                return False
            t_idx += 1
            p_idx += 1
    return t_idx == len(tokens)
```

### Security Toggles

```python
@dataclass
class SecurityConfig:
    allow_redirects: bool = False
    allow_redirects_to: list[str] = field(default_factory=list)
    allow_pipes: bool = False
    allow_cmdsubs: bool = False

def check_command(command: str, config: Config, ...):
    # ...existing confirm/approve checks...

    # Check for output redirects (with toggle)
    if not config.security.allow_redirects:
        if has_output_redirect(command):
            target = get_redirect_target(command)
            if not _redirect_allowed(target, config.security.allow_redirects_to):
                return ask("output redirect")
```

## Migration Path

All enhancements should be backwards-compatible:

1. Existing string patterns continue to work as prefix matches
2. New syntax (`*`, `!`, `+--flag`) only activates when present
3. `[security]` section is optional with safe defaults
4. `[flag_modifiers]` section is optional

## Summary

| Gap                | Solution             | Complexity |
| ------------------ | -------------------- | ---------- |
| No redirect toggle | `[security]` section | Low        |
| No wildcards       | `*` and `**` tokens  | Medium     |
| No negation        | `!pattern` prefix    | Medium     |
| No flag matching   | `[flag_modifiers]`   | Medium     |
| No globs in paths  | Extend path matching | Low        |
