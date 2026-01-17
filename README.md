<p align="center">
  <img src="images/dippy.gif" width="200">
</p>

<h1 align="center">🐤 Dippy</h1>
<p align="center"><em>Because <code>ls</code> shouldn't need approval</em></p>

---

> **Stop the permission fatigue.** Claude Code asks for approval on every `ls`, `git status`, and `cat` - destroying your flow state. You check Slack, come back, and your assistant's just sitting there waiting.

Dippy is a shell command hook that auto-approves safe commands while still prompting for anything destructive. When it blocks, your custom deny messages can steer Claude back on track—no wasted turns. Get up to **40% faster development** without disabling permissions entirely.

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
```

Add to `~/.claude/settings.json` (or use `/hooks` interactively); you only need `PostToolUse` if you want `after` rules in your config:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|mcp__.*",
        "hooks": [{ "type": "command", "command": "/path/to/Dippy/bin/dippy-hook" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|mcp__.*",
        "hooks": [{ "type": "command", "command": "/path/to/Dippy/bin/dippy-hook" }]
      }
    ]
  }
}
```

Use `"matcher": "Bash"` if you only want shell command rules (no MCP tool control).

---

## Configuration

⚠️ Configuration is still evolving; syntax and behaviors may change.

Dippy reads config from (lowest to highest priority):

- `~/.dippy/config` (user global)
- `.dippy` in the project tree (walks up from cwd)
- `$DIPPY_CONFIG` (env override)

Sample config:

```
set log ~/.dippy/audit.log             # write audit log to this path
set log-full                           # include full command in audit log

deny docker *                          # block all docker by default
allow docker run nginx:*               # allow nginx runs
deny docker run *--privileged*         # still ban privileged mode, last matching rule wins

deny python "Use uv run python, which runs in project environment"  # remind Claude to use uv

allow-redirect /tmp/**                 # allow temp file writes
deny-redirect **/.env* "Never write secrets, ask me to do it"       # block env writes

allow-mcp mcp__github__get_*           # allow read-only GitHub MCP tools
allow-mcp mcp__github__list_*
deny-mcp mcp__*__delete_* "No deletions"  # block destructive MCP operations

after git commit * "Reread prompts/next-iteration.md"  # after hook keeps Claude on task
```

Configuration reference: `docs/config-v1.md`

---

## Uninstall

Remove the hook entry from `~/.claude/settings.json`.
