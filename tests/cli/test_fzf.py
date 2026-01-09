"""Test cases for fzf command."""

import pytest

from conftest import is_approved, needs_confirmation

# ==========================================================================
# fzf - fuzzy finder
# ==========================================================================
#
# fzf is primarily a read-only interactive filter that reads from stdin
# and outputs selected items to stdout. Most operations are safe.
#
# Safe operations:
# - All search, display, and formatting options
# - Preview commands (read-only by convention)
# - Shell integration scripts
# - Help/version flags
#
# Unsafe operations:
# - --listen-unsafe: Allows remote process execution via HTTP server
# - --bind with execute/execute-silent/become actions: Can run arbitrary commands
#

TESTS = [
    #
    # --- Basic usage (safe) ---
    #
    ("fzf", True),
    ("fzf --help", True),
    ("fzf --version", True),
    ("fzf --man", True),
    #
    # --- Search options (safe) ---
    #
    ("fzf -e", True),
    ("fzf --exact", True),
    ("fzf -i", True),
    ("fzf --ignore-case", True),
    ("fzf +i", True),
    ("fzf --no-ignore-case", True),
    ("fzf --smart-case", True),
    ("fzf --literal", True),
    ("fzf --scheme=path", True),
    ("fzf --scheme=history", True),
    ("fzf --scheme=default", True),
    ("fzf --algo=v1", True),
    ("fzf --algo=v2", True),
    ("fzf -x", True),
    ("fzf --extended", True),
    ("fzf +x", True),
    ("fzf --no-extended", True),
    ("fzf -n 1", True),
    ("fzf --nth=1,2", True),
    ("fzf --with-nth=2..", True),
    ("fzf --accept-nth=2", True),
    ("fzf -d :", True),
    ("fzf --delimiter=:", True),
    ("fzf +s", True),
    ("fzf --no-sort", True),
    ("fzf --tail=1000", True),
    ("fzf --disabled", True),
    ("fzf --tiebreak=length", True),
    ("fzf --tiebreak=length,index", True),
    #
    # --- Input/Output options (safe) ---
    #
    ("fzf --read0", True),
    ("fzf --print0", True),
    ("fzf --ansi", True),
    ("fzf --sync", True),
    ("fzf --no-tty-default", True),
    #
    # --- Display/Style options (safe) ---
    #
    ("fzf --style=minimal", True),
    ("fzf --style=full", True),
    ("fzf --color=dark", True),
    ("fzf --color=light", True),
    ("fzf --color=base16", True),
    ("fzf --no-color", True),
    ("fzf --no-bold", True),
    #
    # --- Layout options (safe) ---
    #
    ("fzf --height=50%", True),
    ("fzf --height=~50%", True),
    ("fzf --height=20", True),
    ("fzf --min-height=10", True),
    ("fzf --tmux", True),
    ("fzf --tmux=center,50%", True),
    ("fzf --layout=reverse", True),
    ("fzf --layout=reverse-list", True),
    ("fzf --margin=1", True),
    ("fzf --padding=1", True),
    ("fzf --border", True),
    ("fzf --border=rounded", True),
    ("fzf --border=sharp", True),
    ("fzf --border-label=Search", True),
    ("fzf --border-label-pos=2", True),
    #
    # --- List options (safe) ---
    #
    ("fzf -m", True),
    ("fzf --multi", True),
    ("fzf --multi=5", True),
    ("fzf --highlight-line", True),
    ("fzf --cycle", True),
    ("fzf --wrap", True),
    ("fzf --no-multi-line", True),
    ("fzf --raw", True),
    ("fzf --track", True),
    ("fzf --tac", True),
    ("fzf --gap", True),
    ("fzf --gap=2", True),
    ("fzf --keep-right", True),
    ("fzf --scroll-off=5", True),
    ("fzf --no-hscroll", True),
    ("fzf --hscroll-off=10", True),
    ("fzf --pointer=▌", True),
    ("fzf --marker=┃", True),
    #
    # --- Query options (safe) ---
    #
    ("fzf -q foo", True),
    ("fzf --query=foo", True),
    ("fzf -1", True),
    ("fzf --select-1", True),
    ("fzf -0", True),
    ("fzf --exit-0", True),
    ("fzf -f pattern", True),
    ("fzf --filter=pattern", True),
    ("fzf --print-query", True),
    ("fzf --expect=enter,ctrl-c", True),
    #
    # --- Header options (safe) ---
    #
    ("fzf --header=Header", True),
    ("fzf --header-lines=2", True),
    ("fzf --header-first", True),
    ("fzf --header-border", True),
    #
    # --- Footer options (safe) ---
    #
    ("fzf --footer=Footer", True),
    ("fzf --footer-border", True),
    #
    # --- Preview options (safe - read-only by convention) ---
    #
    ("fzf --preview='cat {}'", True),
    ("fzf --preview='head -100 {}'", True),
    ("fzf --preview='bat --color=always {}'", True),
    ("fzf --preview-window=right:50%", True),
    ("fzf --preview-window=up:30%:wrap", True),
    ("fzf --preview-border=rounded", True),
    ("fzf --preview-label=Preview", True),
    #
    # --- Directory traversal (safe) ---
    #
    ("fzf --walker=file,dir", True),
    ("fzf --walker-root=/home", True),
    ("fzf --walker-skip=.git,node_modules", True),
    #
    # --- History (safe - writes to user-specified file but expected) ---
    #
    ("fzf --history=/tmp/fzf_history", True),
    ("fzf --history-size=1000", True),
    #
    # --- Shell integration (safe) ---
    #
    ("fzf --bash", True),
    ("fzf --zsh", True),
    ("fzf --fish", True),
    #
    # --- Listen (safe without -unsafe) ---
    #
    ("fzf --listen", True),
    ("fzf --listen=6266", True),
    ("fzf --listen=localhost:6266", True),
    ("fzf --listen=/tmp/fzf.sock", True),
    #
    # --- Safe bind actions (navigation, selection, display) ---
    #
    ("fzf --bind=ctrl-a:select-all", True),
    ("fzf --bind=ctrl-d:deselect-all", True),
    ("fzf --bind=ctrl-t:toggle-all", True),
    ("fzf --bind=ctrl-j:down", True),
    ("fzf --bind=ctrl-k:up", True),
    ("fzf --bind=enter:accept", True),
    ("fzf --bind=esc:abort", True),
    ("fzf --bind=ctrl-c:cancel", True),
    ("fzf --bind=ctrl-l:clear-screen", True),
    ("fzf --bind=ctrl-u:clear-query", True),
    ("fzf --bind=tab:toggle+down", True),
    ("fzf --bind=shift-tab:toggle+up", True),
    ("fzf --bind=ctrl-/:toggle-preview", True),
    ("fzf --bind=ctrl-s:toggle-sort", True),
    ("fzf --bind=ctrl-space:toggle", True),
    ("fzf --bind='ctrl-y:preview-up'", True),
    ("fzf --bind='ctrl-e:preview-down'", True),
    ("fzf --bind=ctrl-f:page-down", True),
    ("fzf --bind=ctrl-b:page-up", True),
    ("fzf --bind=home:first", True),
    ("fzf --bind=end:last", True),
    ("fzf --bind 'ctrl-a:select-all,ctrl-d:deselect-all'", True),
    ("fzf --bind=change:first", True),
    ("fzf --bind=focus:transform-header:echo\\ focused", True),
    #
    # --- Complex safe commands ---
    #
    ("fzf --height=50% --layout=reverse --border", True),
    ("fzf -m --preview='cat {}' --preview-window=right:60%", True),
    ("fzf --ansi --no-sort --tac", True),
    ("fzf -e -i --multi --cycle", True),
    ("fzf --query=foo --select-1 --exit-0", True),
    #
    # ==========================================================================
    # UNSAFE OPERATIONS
    # ==========================================================================
    #
    # --- --listen-unsafe (allows remote process execution) ---
    #
    ("fzf --listen-unsafe", False),
    ("fzf --listen-unsafe=6266", False),
    ("fzf --listen-unsafe=localhost:6266", False),
    ("fzf --listen=6266 --listen-unsafe", False),
    ("fzf --height=50% --listen-unsafe", False),
    #
    # --- --bind with execute action (runs arbitrary commands) ---
    #
    ("fzf --bind='enter:execute(vim {})'", False),
    ("fzf --bind='ctrl-e:execute(code {})'", False),
    ("fzf --bind='ctrl-o:execute(open {})'", False),
    ("fzf --bind=enter:execute:vim\\ {}", False),
    ("fzf --bind 'enter:execute(rm {})'", False),
    ("fzf --bind=ctrl-x:execute(rm -rf {})", False),
    #
    # --- --bind with execute-silent (runs commands without terminal) ---
    #
    ("fzf --bind='enter:execute-silent(rm {})'", False),
    ("fzf --bind='ctrl-d:execute-silent(trash {})'", False),
    ("fzf --bind=enter:execute-silent:echo\\ {}", False),
    #
    # --- --bind with become (replaces fzf process) ---
    #
    ("fzf --bind='enter:become(vim {})'", False),
    ("fzf --bind='ctrl-e:become(code {})'", False),
    ("fzf --bind=enter:become:vim\\ {}", False),
    #
    # --- Combined unsafe patterns ---
    #
    ("fzf --height=50% --bind='enter:execute(vim {})'", False),
    ("fzf --multi --bind='ctrl-o:execute-silent(open {})'", False),
    ("fzf --preview='cat {}' --bind='enter:become(less {})'", False),
    #
    # ==========================================================================
    # Edge cases
    # ==========================================================================
    #
    # --- Flags that look like unsafe but aren't ---
    #
    ("fzf --bind=ctrl-x:abort", True),  # abort is safe
    ("fzf --preview='execute cat {}'", True),  # execute in preview string is safe
    ("fzf --header='Press enter to execute'", True),  # execute in string is safe
    ("fzf --query=execute", True),  # execute as query string is safe
    ("fzf --query=become", True),  # become as query string is safe
    #
    # --- reload action (safe - just refreshes the list) ---
    #
    ("fzf --bind='ctrl-r:reload(find .)'", True),
    ("fzf --bind='change:reload:rg --files'", True),
    #
    # --- transform actions (safe - just transforms display) ---
    #
    ("fzf --bind='focus:transform-preview-label:echo\\ {}'", True),
    ("fzf --bind='focus:transform-header:echo\\ {}'", True),
    ("fzf --bind='focus:transform-query:echo\\ {}'", True),
    ("fzf --bind='focus:transform-prompt:echo\\ {}'", True),
    #
    # --- print actions (safe - just changes output) ---
    #
    ("fzf --bind='enter:print-query'", True),
    ("fzf --bind='ctrl-p:put(text)'", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_fzf_command(check, command: str, expected: bool):
    """Test fzf command safety classification."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
