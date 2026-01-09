<p align="center">
  <img src="images/dippy.gif" width="200">
</p>

<h1 align="center">🐤 Dippy</h1>
<p align="center"><em>Because <code>ls</code> shouldn't need approval</em></p>

---

> **Stop the permission fatigue.** AI coding assistants ask for approval on every `ls`, `git status`, and `cat` - destroying your flow state. You check Slack, come back, and your assistant's just sitting there waiting.

Dippy is a shell command hook that auto-approves safe commands while still prompting for anything destructive. Get up to **40% faster development** without disabling permissions entirely.

Built on [Parable](https://github.com/ldayton/Parable), our own hand-written bash parser—no external dependencies, just pure Python. A combined 10,000+ tests.

**Supports:** Claude Code, Gemini CLI, and Cursor.

![Screenshot](images/screenshot.png)

## ✅ What gets approved

- **Complex pipelines**: `ps aux | grep python | awk '{print $2}' | head -10`
- **Chained reads**: `git status && git log --oneline -5 && git diff --stat`
- **Cloud inspection**: `aws ec2 describe-instances --filters "Name=tag:Environment,Values=prod"`
- **Container debugging**: `docker logs --tail 100 api-server 2>&1 | grep ERROR`
- **Safe redirects**: `grep -r "TODO" src/ 2>/dev/null`, `ls &>/dev/null`
- **Command substitution**: `ls $(pwd)`, `git diff foo-$(date).txt`

## 🚫 What gets blocked

- **Subshell injection**: `git $(echo rm) foo.txt`, `echo $(rm -rf /)`
- **Subtle file writes**: `curl https://example.com > script.sh`, `tee output.log`
- **Hidden mutations**: `git stash drop`, `npm unpublish`, `brew unlink`
- **Cloud danger**: `aws s3 rm s3://bucket --recursive`, `kubectl delete pod`
- **Destructive chains**: `rm -rf node_modules && npm install` (blocks the whole thing)

---

## Installation

```bash
git clone https://github.com/ldayton/Dippy.git
cd Dippy && uv sync
```

Then configure your AI assistant to use the hook. Dippy auto-detects which assistant is calling it.

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "/path/to/Dippy/bin/dippy-hook" }]
      }
    ]
  }
}
```

Or use `/hooks` in Claude Code to add interactively.

Logs: `~/.claude/hook-approvals.log`

### Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "shell",
        "hooks": [{ "type": "command", "command": "/path/to/Dippy/bin/dippy-hook" }]
      }
    ]
  }
}
```

Logs: `~/.gemini/hook-approvals.log`

### Cursor

Add to `.cursor/hooks.json` in your project:

```json
{
  "beforeShellExecution": {
    "command": "/path/to/Dippy/bin/dippy-hook"
  }
}
```

Logs: `~/.cursor/hook-approvals.log`

---

## Configuration

Dippy auto-detects your AI assistant, but you can force a mode:

| Flag       | Env Var             | Mode        |
| ---------- | ------------------- | ----------- |
| `--claude` | `DIPPY_CLAUDE=true` | Claude Code |
| `--gemini` | `DIPPY_GEMINI=true` | Gemini CLI  |
| `--cursor` | `DIPPY_CURSOR=true` | Cursor      |

---

## Configuration

Create `~/.dippy/settings.toml` for global settings, or `dippy.toml` (or `.dippy.toml`) in your project root for project-specific rules.

```toml
version = 1

# What you want auto-approved
approve = [
    "mkdir",                       # Simple command
    "git stash",                   # CLI action (prefix match)
    "./scripts/deploy.sh",         # Script (relative to project root)
    "re:^make (lint|test|build)",  # Regex (explicit re: prefix)
]

# Override: always ask, even if rules would approve
confirm = [
    "docker run",
    "git push --force",
]

# Map aliases to CLI handlers
aliases = { k = "kubectl", tf = "terraform", g = "git" }
```

**Pattern types:**
- `mkdir` — simple command match
- `git stash` — prefix match (matches `git stash`, `git stash pop`, etc.)
- `./scripts/deploy.sh` — script path (resolved against project root)
- `re:^pattern` — regex match against full command

**Precedence:** `confirm` → `approve` → built-in handlers → `SIMPLE_SAFE`

**Script paths:** Relative paths are resolved against the project root (where the config file lives). Only the exact file matches—a script with the same name in a different directory won't be approved.

---

## Development

```bash
just test        # Run tests (Python 3.14)
just test-all    # All Python versions (3.11-3.14)
just lint        # Lint (ruff check)
just fmt         # Format (ruff format)
just check       # All of the above — MUST PASS before committing
```

---

## Contributing

PRs welcome! See [prompts/adding-commands.md](prompts/adding-commands.md) for instructions on adding support for new CLI tools.

---

## Uninstall

Remove the hook entry from your settings file (`~/.claude/settings.json`, `~/.gemini/settings.json`, or `.cursor/hooks.json`).

---

<details>
<summary><strong>Claude Instructions</strong></summary>

Structure:
```
src/dippy/
├── dippy.py          # Main router + entry point
├── cli/              # CLI-specific handlers
│   ├── git.py
│   ├── aws.py
│   ├── kubectl.py
│   └── ...
└── core/
    ├── config.py     # Configuration system
    ├── parser.py     # Parable parsing helpers
    └── patterns.py   # Safe commands and patterns

tests/
├── test_dippy.py     # Integration tests
├── test_simple.py    # Simple command tests
└── cli/              # CLI handler tests
    ├── test_git.py
    ├── test_aws.py
    └── ...
```

Workflow:
1. User pastes "Hook PreToolUse:Bash requires confirmation" output
2. Add pattern to appropriate handler in `src/dippy/cli/`
3. Add test case to `tests/cli/test_*.py`
4. Run `just test` until passing, then `just check` MUST PASS

</details>
