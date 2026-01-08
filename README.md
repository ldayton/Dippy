# 🐤 Dippy

*Because `ls` shouldn't need approval*

---

> **Stop the permission fatigue.** Claude Code asks for approval on every `ls`, `git status`, and `cat` — destroying your flow state. You check Slack, come back, and Claude's just sitting there waiting.

Dippy is a [PreToolUse hook](https://docs.anthropic.com/en/docs/claude-code/hooks) that auto-approves safe commands while still prompting for anything destructive. Get up to **40% faster development** without `--dangerously-skip-permissions`.

## ✅ What Gets Approved

- **Read-only commands**: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `wc`, `stat`
- **Git reads**: `git status`, `git log`, `git diff`, `git branch`
- **Cloud CLI reads**: `aws s3 ls`, `kubectl get`, `gcloud describe`, `az show`
- **Safe tools**: `jq`, `curl` (GET only), `docker ps`, `brew list`

## 🚫 What Gets Blocked

- **Destructive ops**: `rm`, `mv`, `chmod`, file writes
- **Git mutations**: `git push`, `git commit`, `git reset`
- **Cloud mutations**: `aws s3 rm`, `kubectl delete`, `terraform apply`
- **Anything with output redirects**: `> file.txt`, `>> log`

---

## Installation

```bash
# Clone the repo
git clone https://github.com/ldayton/Dippy.git
cd Dippy

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python -m dippy"
          }
        ]
      }
    ]
  }
}
```

Or use `/hooks` in Claude Code to add interactively.

All decisions are logged to `~/.claude/hook-approvals.log`.

---

## Project Structure

```
src/dippy/
├── dippy.py          # Main router + entry point
├── cli/              # CLI-specific handlers
│   ├── __init__.py   # Dynamic loader
│   ├── git.py
│   ├── aws.py
│   ├── kubectl.py
│   ├── gcloud.py
│   ├── terraform.py
│   ├── docker.py
│   └── ...
└── core/
    ├── parser.py     # bashlex helpers
    └── patterns.py   # Safe commands, patterns, config

tests/
├── conftest.py       # Shared fixtures
├── test_router.py    # Integration tests
├── test_simple.py    # Simple command tests
├── test_parser.py    # Parser tests
├── cli/              # CLI handler tests
│   ├── test_git.py
│   ├── test_aws.py
│   ├── test_kubectl.py
│   └── ...
└── local/            # User's local tests (gitignored)
```

---

## Contributing

PRs welcome! To add support for a new CLI tool:

1. Create `src/dippy/cli/mycli.py` with:
   - `SAFE_ACTIONS`: set of safe action names
   - `UNSAFE_ACTIONS`: set of unsafe action names  
   - `check(command, tokens)`: returns `"approve"`, `"deny"`, or `None`

2. Add to `KNOWN_HANDLERS` in `src/dippy/cli/__init__.py`

3. Create `tests/cli/test_mycli.py` with test cases

4. Run tests: `uv run pytest`

### Workflow for Adding Patterns

1. User reports "Hook PreToolUse:Bash requires confirmation" for a command
2. Use `bin/bashlex-dump.py 'command'` to inspect parsing
3. Add pattern to appropriate handler
4. Add test case
5. Run `uv run pytest`

---

## Uninstall

Remove the hook entry from `~/.claude/settings.json`.

---

## License

MIT
