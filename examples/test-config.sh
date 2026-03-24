#!/usr/bin/env bash
# ==============================================================================
# Test harness for Dippy config rules
#
# Validates that your config produces the expected allow/ask/deny decisions
# by piping JSON hook payloads to Dippy and checking the response.
#
# Usage:
#   1. Copy examples/config to ~/.dippy/config (or set DIPPY_CONFIG)
#   2. Run: bash examples/test-config.sh
#
# The script auto-detects the Dippy binary (dippy or dippy.exe).
# ==============================================================================

set -euo pipefail

# Find Dippy binary
if command -v dippy.exe &>/dev/null; then
    DIPPY="dippy.exe"
elif command -v dippy &>/dev/null; then
    DIPPY="dippy"
else
    echo "Error: dippy not found in PATH"
    exit 1
fi

PASS=0
FAIL=0
CWD="$(pwd)"

green()  { printf "\e[32m%s\e[0m\n" "$1"; }
red()    { printf "\e[31m%s\e[0m\n" "$1"; }
header() { printf "\n\e[1;36m=== %s ===\e[0m\n" "$1"; }

# Send a Bash tool call to Dippy
check_bash() {
    printf '{"tool_name":"Bash","tool_input":{"command":"%s","cwd":"%s"}}' "$1" "$CWD" \
        | $DIPPY 2>/dev/null
}

# Send an MCP tool call to Dippy
check_mcp() {
    printf '{"tool_name":"%s","tool_input":{}}' "$1" \
        | $DIPPY 2>/dev/null
}

# Extract "permissionDecision" value from JSON response
get_decision() {
    echo "$1" | sed 's/.*"permissionDecision" *: *"\([^"]*\)".*/\1/'
}

# Assert that response contains the expected decision
assert() {
    local label="$1" expected="$2" response="$3"

    if [ "$expected" = "defer" ] && [ "$response" = "{}" ]; then
        green "  PASS: $label -> defer"
        PASS=$((PASS + 1))
        return
    fi

    local got
    got=$(get_decision "$response")

    if [ "$got" = "$expected" ]; then
        green "  PASS: $label -> $expected"
        PASS=$((PASS + 1))
    else
        red "  FAIL: $label -> expected '$expected', got '$got'"
        FAIL=$((FAIL + 1))
    fi
}

# ==============================================================================
header "1. MCP Tools"
# ==============================================================================

# Read-only — allow
r=$(check_mcp "mcp__github__get_me");           assert "github get_me"          "allow" "$r"
r=$(check_mcp "mcp__github__list_issues");       assert "github list_issues"     "allow" "$r"
r=$(check_mcp "mcp__filesystem__read_file");     assert "filesystem read_file"   "allow" "$r"
r=$(check_mcp "mcp__github__search_code");       assert "github search_code"     "allow" "$r"
r=$(check_mcp "mcp__myserver__query_data");      assert "myserver query_data"    "allow" "$r"

# Destructive — deny
r=$(check_mcp "mcp__github__delete_branch");     assert "github delete_branch"   "deny"  "$r"
r=$(check_mcp "mcp__db__remove_record");         assert "db remove_record"       "deny"  "$r"
r=$(check_mcp "mcp__db__drop_table");            assert "db drop_table"          "deny"  "$r"

# Mutating — ask
r=$(check_mcp "mcp__github__create_issue");      assert "github create_issue"    "ask"   "$r"
r=$(check_mcp "mcp__github__update_pull_request"); assert "github update_pr"     "ask"   "$r"
r=$(check_mcp "mcp__github__push_files");        assert "github push_files"      "ask"   "$r"

# Unknown tools — ask (catch-all)
r=$(check_mcp "mcp__unknown__do_something");     assert "unknown tool (catch-all)" "ask" "$r"
r=$(check_mcp "mcp__slack__send_message");       assert "slack send_message"      "ask"   "$r"

# ==============================================================================
header "2. Shell Redirects"
# ==============================================================================

r=$(check_bash "echo test > ~/Desktop/test.txt");   assert "echo > ~/Desktop"   "deny"  "$r"
r=$(check_bash "echo SECRET=x > .env");              assert "echo > .env"        "deny"  "$r"
r=$(check_bash "echo test > /tmp/test.txt");         assert "echo > /tmp"        "allow" "$r"
r=$(check_bash "echo key > ~/.ssh/authorized_keys"); assert "echo > ~/.ssh"      "deny"  "$r"
r=$(check_bash "echo creds > ~/.aws/credentials");   assert "echo > ~/.aws"      "deny"  "$r"

# ==============================================================================
header "3. System Paths (deny * /path/**)"
# ==============================================================================

r=$(check_bash "cp file /etc/passwd");           assert "cp /etc/passwd"          "deny" "$r"
r=$(check_bash "cp file /etc/apt/sources.list"); assert "cp /etc/apt/sources.list" "deny" "$r"
r=$(check_bash "cp file /usr/share/app/config"); assert "cp /usr/share/app"       "deny" "$r"
r=$(check_bash "cp file ~/.ssh/config");         assert "cp ~/.ssh/config"        "deny" "$r"

# ==============================================================================
header "4. Home Directory Protection"
# ==============================================================================

r=$(check_bash "rm ~/Documents/file.txt");       assert "rm ~/Documents"         "deny"  "$r"
r=$(check_bash "rm ~/repos/project/temp.txt");   assert "rm ~/repos (allow)"     "allow" "$r"
r=$(check_bash "mv ~/file.txt ~/other.txt");     assert "mv ~/file.txt"          "deny"  "$r"
r=$(check_bash "cp file ~/.claude/settings.json"); assert "cp ~/.claude (ask)"   "ask"   "$r"

# ==============================================================================
header "5. Commands"
# ==============================================================================

r=$(check_bash "git status");                    assert "git status"         "allow" "$r"
r=$(check_bash "git log --oneline -10");         assert "git log"            "allow" "$r"
r=$(check_bash "git push origin main");          assert "git push"           "ask"   "$r"
r=$(check_bash "git push --force origin main");  assert "git push --force"   "deny"  "$r"
r=$(check_bash "git reset --hard HEAD~1");       assert "git reset --hard"   "deny"  "$r"
r=$(check_bash "python3 script.py");             assert "python3 (deny)"     "deny"  "$r"
r=$(check_bash "uv run python script.py");       assert "uv run python"      "allow" "$r"
r=$(check_bash "npm list");                      assert "npm list"           "allow" "$r"
r=$(check_bash "npm unpublish my-package");      assert "npm unpublish"      "deny"  "$r"
r=$(check_bash "docker ps -a");                  assert "docker ps"          "allow" "$r"
r=$(check_bash "docker run -it ubuntu bash");    assert "docker run"         "ask"   "$r"
r=$(check_bash "rm -rf ./node_modules");         assert "rm -rf"             "ask"   "$r"
r=$(check_bash "pwsh -Command Get-Process");     assert "pwsh"               "ask"   "$r"

# ==============================================================================
header "6. Pipelines / Compound Commands"
# ==============================================================================

r=$(check_bash "git status && git log --oneline -5");          assert "status && log (safe)"   "allow" "$r"
r=$(check_bash "git add . && git commit -m test && git push"); assert "add && commit && push"  "ask"   "$r"
r=$(check_bash "git status && git push --force origin main");  assert "status && push --force" "deny"  "$r"

# ==============================================================================
echo ""
echo "=============================="
total=$((PASS + FAIL))
if [ $FAIL -eq 0 ]; then
    green "RESULT: $PASS/$total tests PASSED"
else
    red   "RESULT: $PASS PASSED, $FAIL FAILED out of $total tests"
fi
echo "=============================="
exit $FAIL
