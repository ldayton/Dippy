# Dippy Security Model

## Threat Model

**What we protect against:** AI coding assistants making mistakes - running `rm -rf /` when they meant `rm -rf ./build`, force-pushing to main, overwriting important files.

**What we don't protect against:** Malicious actors, compromised AI, adversarial prompt injection. If someone is actively trying to bypass Dippy, they can.

This is stated in [config.md](config.md): "Not adversarial - protecting against AI mistakes, not malicious actors."

## Core Philosophy

**Approve what we know is safe. Ask about everything else.**

Dippy uses a conservative allowlist approach:

1. **Config rules** (highest priority) - User-defined overrides
2. **Built-in allowlist** - Known safe read-only commands
3. **CLI handlers** - Tool-specific logic for git, docker, kubectl, etc.
4. **Default: ask** - Unknown commands always prompt

This means Dippy errs on the side of caution. If we don't recognize a command, we ask. There's no blocklist of "dangerous" patterns - instead, anything not explicitly safe requires approval.

### Built-in Safe Commands

About 90 read-only commands are pre-approved (see `allowlists.py`):

- **File viewing:** cat, head, tail, less, bat
- **Directory listing:** ls, tree, exa, find
- **Search:** grep, rg, ag, ack
- **Info:** stat, file, wc, du, df, pwd
- **Text processing:** cut, sort, uniq, diff, jq
- **System info:** ps, whoami, hostname, uname, date
- **Network diagnostics:** ping, dig, netstat

### CLI Handlers

Complex tools get specialized handlers that understand their subcommands:

| Tool | Safe | Needs Approval |
|------|------|----------------|
| git | status, log, diff, branch | push, commit, reset, rebase |
| docker | ps, images, inspect | run, rm, stop, build |
| kubectl | get, describe, logs | delete, apply, exec |
| aws | s3 ls, ec2 describe-* | s3 rm, ec2 terminate-* |

### Decision Priority

When multiple rules could apply, most restrictive wins:

```
deny > ask > allow
```

If a pipeline has one unsafe command, the whole thing requires approval.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Raw bash string                              │
│              "cd /tmp && rm -rf * > log.txt; echo done"              │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                           Shell Parser                               │
│                                                                      │
│  Extracts:                                                           │
│  - Simple commands (no shell syntax)                                 │
│  - Redirect targets (file paths)                                     │
│  - Pipes, compounds, subshells → broken into parts                   │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│      Simple Commands        │    │      Redirect Targets       │
│                             │    │                             │
│  1. "cd /tmp"     → allow   │    │  1. "log.txt" → ask         │
│  2. "rm -rf *"    → ask     │    │                             │
│  3. "echo done"   → allow   │    │                             │
└─────────────────────────────┘    └─────────────────────────────┘
                    │                              │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │     Combine Decisions       │
                    │                             │
                    │  deny > ask > allow         │
                    │  Result: ASK                │
                    └─────────────────────────────┘
```

## What the Parser Handles

The parser breaks down bash syntax BEFORE rule matching:

| Syntax | Example | Parser Output |
|--------|---------|---------------|
| Semicolon | `a; b` | commands: `a`, `b` |
| And | `a && b` | commands: `a`, `b` |
| Or | `a \|\| b` | commands: `a`, `b` |
| Pipe | `a \| b` | commands: `a`, `b` |
| Subshell | `(a; b)` | commands: `a`, `b` |
| Command sub | `a $(b)` | commands: `b`, `a $(...)` |
| Redirect | `a > f` | commands: `a`, redirects: `f` |
| Here-doc | `a <<EOF` | commands: `a` |

**The rule engine never sees shell metacharacters.** It only sees simple command strings.

## What the Parser Does NOT Handle

- **Variable expansion:** `$HOME` stays as `$HOME` (shell expands it later)
- **Glob expansion:** `*.txt` stays as `*.txt` (shell expands it later)
- **Alias resolution:** We don't know what aliases exist

These are expanded by the shell AFTER approval. We match the literal string.

## Command Matching

After parsing, each simple command is matched against rules:

```
Command: rm -rf /tmp/build
Pattern: ask rm *
Result:  MATCH → ask for approval
```

Path normalization happens before matching:
- `./foo` → `/absolute/path/foo`
- `~/bar` → `/home/user/bar`
- `../baz` → resolved against cwd

## Redirect Matching

Redirect targets are extracted and matched separately:

```
Command: echo "data" > ~/.ssh/authorized_keys
Redirect: ~/.ssh/authorized_keys
Pattern:  ask-redirect ~/.ssh/*
Result:   MATCH → ask for approval
```

Even if the command itself is allowed, the redirect can trigger review.

## Approval Granularity

Each simple command gets its own approval decision. For:

```bash
cd /tmp && rm -rf * && echo "done"
```

The parser extracts three commands. Each is matched:
1. `cd /tmp` → check rules
2. `rm -rf *` → check rules
3. `echo "done"` → check rules

If ANY command requires approval, the whole pipeline requires approval. We can't partially execute.

## Edge Cases

### Nested Command Substitution

```bash
echo $(cat $(find . -name "*.txt"))
```

Parser extracts innermost first:
1. `find . -name "*.txt"`
2. `cat $(...)`
3. `echo $(...)`

### Redirects in Subshells

```bash
(echo foo > /tmp/a) > /tmp/b
```

Redirects: `/tmp/a`, `/tmp/b` - both checked against redirect rules.

### Here-documents

```bash
cat > /etc/passwd <<EOF
root:x:0:0::/root:/bin/bash
EOF
```

Redirect `/etc/passwd` is extracted and matched. Unquoted heredocs are also scanned for command substitutions:

```bash
cat <<EOF
$(rm -rf /)
EOF
```

This would trigger approval because the cmdsub contains `rm -rf /`. Quoted heredocs (`<<'EOF'`) are not expanded by bash, so they're treated as data.

### Process Substitution

```bash
diff <(cat a) <(cat b)
```

Commands extracted: `cat a`, `cat b`, `diff <(...) <(...)`.

### Arithmetic Expressions

```bash
(( x = $(dangerous_cmd) ))
```

Command substitutions inside `(( ))` arithmetic are analyzed. The inner command is extracted and checked.

### Parameter Expansions

```bash
echo ${x:-$(rm -rf /)}
```

Command substitutions nested in parameter expansions (`${x:-...}`, `${x:=...}`, etc.) are analyzed. This catches cmdsubs in default values.

### C-style For Loops

```bash
for (( i=$(rm foo); i<10; i++ )); do echo $i; done
```

Command substitutions in the init, condition, and increment expressions of `for (( ))` loops are analyzed.

## Trust Assumptions

1. **Parser correctness:** We trust our shell parser to correctly decompose bash syntax. A parser bug could let commands slip through.

2. **AI cooperation:** The AI isn't actively encoding malicious commands in ways designed to evade parsing (base64, eval tricks, etc.).

3. **Single-layer execution:** The command runs in one shell. We don't trace into scripts or binaries that are executed.

## What This Means for Users

### Effective Patterns

```
# These work because parser extracts the rm command
ask rm -rf *
ask rm -rf /*

# Catches dangerous git operations
ask git push --force *
ask git reset --hard *

# Protect sensitive files
ask-redirect /etc/*
ask-redirect ~/.ssh/*
ask-redirect **/.env*
```

### What Patterns Can't Catch

```
# Can't see inside scripts
./malicious-script.sh    # Pattern "ask rm *" won't help

# Can't see after variable expansion
rm -rf $DANGEROUS_PATH   # We see literal "$DANGEROUS_PATH"

# Can't resolve aliases
ll                       # If aliased to "ls -la", we see "ll"
```

## Implementation Notes

### Parser: Parable

Dippy uses **Parable** (`~/source/Parable`), a recursive descent bash parser that produces a full AST.

```python
from parable import parse, ParseError

nodes = parse("echo hi; rm -rf / > log.txt && cat foo | grep bar")
# Returns AST with Command, Pipeline, List, Redirect nodes
```

AST structure:
- `Command` - simple command with `.words` (list of Word) and `.redirects` (list of Redirect)
- `Pipeline` - commands connected by `|`
- `List` - pipelines connected by `;`, `&&`, `||`, `&`
- `Redirect` - has `.op` (`>`, `>>`, `<`, etc.) and `.target` (Word)
- Plus: `Subshell`, `If`, `While`, `For`, `Case`, `Function`, `CommandSubstitution`, etc.

Walking the AST extracts:
1. All simple commands (as word lists, reconstructed to strings)
2. All redirect targets (file paths)

If parsing fails (`ParseError`), fail safe: require approval for the entire raw string.

## Summary

The key insight: **rule matching operates on parsed commands, not raw bash.**

This means:
- `echo hi; rm -rf /` → two commands, each matched separately
- Patterns are simple globs, not shell-aware
- Parser handles the complexity, rule engine stays simple
- Unknown syntax → ask (fail safe)
