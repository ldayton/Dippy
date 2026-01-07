<p align="center">
  <img src="images/dippy.gif" width="200">
</p>

<h1 align="center">🐤 Dippy</h1>
<p align="center"><em>Because <code>ls</code> shouldn't need approval</em></p>

---

> **Stop the permission fatigue.** Claude Code asks for approval on every `ls`, `git status`, and `cat` - destroying your flow state. You check Slack, come back, and Claude's just sitting there waiting.

Dippy is a [PreToolUse hook](https://docs.anthropic.com/en/docs/claude-code/hooks) that auto-approves safe commands while still prompting for anything destructive. Get up to **40% faster development** without `--dangerously-skip-permissions`.

![Screenshot](images/screenshot.png)

## ✅ What gets approved

- **Read-only commands**: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `wc`, `stat`
- **Git reads**: `git status`, `git log`, `git diff`, `git branch`
- **Cloud CLI reads**: `aws s3 ls`, `kubectl get`, `gcloud describe`, `az show`
- **Safe tools**: `jq`, `curl` (GET only), `docker ps`, `brew list`

## 🚫 What gets blocked

- **Destructive ops**: `rm`, `mv`, `chmod`, file writes
- **Git mutations**: `git push`, `git commit`, `git reset`
- **Cloud mutations**: `aws s3 rm`, `kubectl delete`, `terraform apply`
- **Anything with output redirects**: `> file.txt`, `>> log`

---

## Add to Claude

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
            "command": "/path/to/Dippy/src/dippy/dippy.py"
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

## Customize

Copy `dippy-local-sample.toml` to `dippy-local.toml` to add your own rules. Changes take effect immediately.

```toml
[safe_commands]
commands = ["mkdir"]           # single commands to auto-approve

[safe_scripts]
scripts = ["my-script.sh"]     # script basenames always safe

[cli_aliases]
aliases = { k = "kubectl" }    # map aliases to CLI tools

[cli_safe_actions]
git = ["stash"]                # add safe actions to existing CLIs

[cli_tools.mycli]              # define entirely new CLI tools
safe_actions = ["status"]
parser = "first_token"
```

See `dippy-local-sample.toml` for all options including `prefix_commands`, `safe_patterns`, `curl_wrappers`, and `wrappers`.

---

<details>
<summary><strong>Claude Instructions</strong></summary>

Structure:
- `src/dippy/dippy.py` - Main hook logic
- `tests/test_dippy.py` - Test cases
- `bin/bashlex-dump.py` - Debug helper for AST inspection
- `dippy-local.toml` - User-specific patterns (gitignored)

Workflow:
1. User pastes "Hook PreToolUse:Bash requires confirmation" output
2. Use `bin/bashlex-dump.py 'command'` to inspect parsing
3. Add pattern to `SAFE_COMMANDS`, `CLI_CONFIGS`, or `CUSTOM_CHECKS` in dippy.py (or `dippy-local.toml` for personal patterns)
4. Add test case to `tests/test_dippy.py` (or `tests/test_dippy_local.py` for personal)
5. Run `uv run pytest`

</details>
