<p align="center">
  <img src="images/dippy.gif" width="200">
</p>

<h1 align="center">🐤 Dippy</h1>
<p align="center"><em>Because <code>ls</code> shouldn't need approval</em></p>

---

> **Stop the permission fatigue.** Claude Code asks for approval on every `ls`, `git status`, and `cat` - destroying your flow state. You check Slack, come back, and your assistant's just sitting there waiting.

Dippy is a shell command hook that auto-approves safe commands while still prompting for anything destructive. Get up to **40% faster development** without disabling permissions entirely.

Built on [Parable](https://github.com/ldayton/Parable), our own hand-written bash parser—no external dependencies, just pure Python. A combined 10,000+ tests.

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

Then configure Claude Code to use the hook.

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

### Customization (experimental)

Dippy supports user and project config files with gitignore-style rules. See [docs/config-v1.md](docs/config-v1.md) for details.

> **Warning:** The config system is experimental and may change without notice.

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

Remove the hook entry from `~/.claude/settings.json`.

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
