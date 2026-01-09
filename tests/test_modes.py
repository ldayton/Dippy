"""Test multi-CLI mode support (Claude, Gemini, Cursor) and auto-detection."""

import importlib
import pytest


@pytest.fixture(autouse=True)
def reset_dippy_module(monkeypatch):
    """Reset dippy module after each test to restore Claude mode."""
    yield
    # Reset to Claude mode after each test
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.delenv("DIPPY_GEMINI", raising=False)
    monkeypatch.delenv("DIPPY_CURSOR", raising=False)
    monkeypatch.delenv("DIPPY_CLAUDE", raising=False)
    import dippy.dippy
    importlib.reload(dippy.dippy)


def test_gemini_approve_format(monkeypatch):
    """Test that Gemini mode returns correct JSON format for approval."""
    monkeypatch.setattr("sys.argv", ["dippy", "--gemini"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.approve("git status")

    assert "decision" in result
    assert result["decision"] == "allow"
    assert "reason" in result
    assert "🐤" in result["reason"]
    assert "hookSpecificOutput" not in result


def test_gemini_ask_format(monkeypatch):
    """Test that Gemini mode returns correct JSON format for ask."""
    monkeypatch.setattr("sys.argv", ["dippy", "--gemini"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.ask("rm -rf")

    assert "decision" in result
    assert result["decision"] == "ask"
    assert "reason" in result
    assert "🐤" in result["reason"]
    assert "hookSpecificOutput" not in result


def test_claude_approve_format(monkeypatch):
    """Test that Claude mode returns correct JSON format for approval."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.delenv("DIPPY_GEMINI", raising=False)

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.approve("git status")

    assert "hookSpecificOutput" in result
    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "🐤" in result["hookSpecificOutput"]["permissionDecisionReason"]
    assert "decision" not in result


def test_claude_ask_format(monkeypatch):
    """Test that Claude mode returns correct JSON format for ask."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.delenv("DIPPY_GEMINI", raising=False)

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.ask("rm -rf")

    assert "hookSpecificOutput" in result
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "🐤" in result["hookSpecificOutput"]["permissionDecisionReason"]
    assert "decision" not in result


def test_gemini_env_var(monkeypatch):
    """Test that DIPPY_GEMINI env var enables Gemini mode."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.setenv("DIPPY_GEMINI", "true")

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.approve("ls")

    assert "decision" in result
    assert result["decision"] == "allow"


def test_shell_tool_names():
    """Test that shell tool names include Claude and Gemini variants."""
    from dippy.dippy import SHELL_TOOL_NAMES

    assert "Bash" in SHELL_TOOL_NAMES  # Claude
    assert "shell" in SHELL_TOOL_NAMES  # Gemini
    assert "run_shell_command" in SHELL_TOOL_NAMES  # Gemini official


# === Cursor Tests ===


def test_cursor_approve_format(monkeypatch):
    """Test that Cursor mode returns correct JSON format for approval."""
    monkeypatch.setattr("sys.argv", ["dippy", "--cursor"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.approve("git status")

    assert "permission" in result
    assert result["permission"] == "allow"
    # snake_case (v2.0+)
    assert "user_message" in result
    assert "agent_message" in result
    assert "🐤" in result["user_message"]
    # camelCase (v1.7.x)
    assert "userMessage" in result
    assert "agentMessage" in result
    assert "🐤" in result["userMessage"]
    # Not other formats
    assert "hookSpecificOutput" not in result
    assert "decision" not in result


def test_cursor_ask_format(monkeypatch):
    """Test that Cursor mode returns correct JSON format for ask."""
    monkeypatch.setattr("sys.argv", ["dippy", "--cursor"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.ask("rm -rf")

    assert "permission" in result
    assert result["permission"] == "ask"
    # snake_case (v2.0+)
    assert "user_message" in result
    assert "agent_message" in result
    assert "🐤" in result["user_message"]
    # camelCase (v1.7.x)
    assert "userMessage" in result
    assert "agentMessage" in result
    assert "🐤" in result["userMessage"]
    # Not other formats
    assert "hookSpecificOutput" not in result
    assert "decision" not in result


def test_cursor_env_var(monkeypatch):
    """Test that DIPPY_CURSOR env var enables Cursor mode."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.setenv("DIPPY_CURSOR", "true")

    import dippy.dippy
    importlib.reload(dippy.dippy)

    result = dippy.dippy.approve("ls")

    assert "permission" in result
    assert result["permission"] == "allow"


def test_cursor_mode_detection(monkeypatch):
    """Test that Cursor mode is correctly detected."""
    monkeypatch.setattr("sys.argv", ["dippy", "--cursor"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    assert dippy.dippy.MODE == "cursor"
    assert dippy.dippy.CURSOR_MODE is True
    assert dippy.dippy.GEMINI_MODE is False


# === Claude Flag Tests ===


def test_claude_flag(monkeypatch):
    """Test that --claude flag explicitly sets Claude mode."""
    monkeypatch.setattr("sys.argv", ["dippy", "--claude"])

    import dippy.dippy
    importlib.reload(dippy.dippy)

    assert dippy.dippy.MODE == "claude"
    assert dippy.dippy._EXPLICIT_MODE == "claude"


def test_claude_env_var(monkeypatch):
    """Test that DIPPY_CLAUDE env var enables Claude mode."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.setenv("DIPPY_CLAUDE", "true")

    import dippy.dippy
    importlib.reload(dippy.dippy)

    assert dippy.dippy.MODE == "claude"
    assert dippy.dippy._EXPLICIT_MODE == "claude"


# === Auto-Detection Tests ===


def test_auto_detect_claude_from_input():
    """Test auto-detection of Claude mode from input structure."""
    from dippy.dippy import _detect_mode_from_input

    # Claude sends Bash tool
    input_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert _detect_mode_from_input(input_data) == "claude"


def test_auto_detect_gemini_from_input():
    """Test auto-detection of Gemini mode from input structure."""
    from dippy.dippy import _detect_mode_from_input

    # Gemini sends shell tool (various names)
    for tool_name in ["shell", "run_shell", "run_shell_command", "execute_shell"]:
        input_data = {"tool_name": tool_name, "tool_input": {"command": "ls"}}
        assert _detect_mode_from_input(input_data) == "gemini"


def test_auto_detect_cursor_from_input():
    """Test auto-detection of Cursor mode from input structure."""
    from dippy.dippy import _detect_mode_from_input

    # Cursor sends command directly without tool_name
    input_data = {"command": "ls", "cwd": "/home/user"}
    assert _detect_mode_from_input(input_data) == "cursor"


def test_no_flag_defaults_to_auto_detect(monkeypatch):
    """Test that no flag means auto-detection will be used."""
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.delenv("DIPPY_GEMINI", raising=False)
    monkeypatch.delenv("DIPPY_CURSOR", raising=False)
    monkeypatch.delenv("DIPPY_CLAUDE", raising=False)

    import dippy.dippy
    importlib.reload(dippy.dippy)

    # No explicit mode set, auto-detect will kick in at main()
    assert dippy.dippy._EXPLICIT_MODE is None
