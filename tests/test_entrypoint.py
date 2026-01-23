"""Tests for bin/dippy-hook entry point."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DIPPY_HOOK = REPO_ROOT / "bin" / "dippy-hook"
# Use system Python to avoid venv masking import issues
SYSTEM_PYTHON = "/usr/bin/python3"


def get_decision(output: dict) -> str | None:
    """Extract decision from hook output format."""
    return output.get("hookSpecificOutput", {}).get("permissionDecision")


def run_hook(
    input_data: dict | str | None = None,
    via_symlink: bool = False,
    use_system_python: bool = False,
) -> subprocess.CompletedProcess:
    """Run dippy-hook with given input, optionally via a symlink."""
    if via_symlink:
        # Create a temporary symlink to test symlink resolution
        with tempfile.TemporaryDirectory() as tmpdir:
            symlink_path = Path(tmpdir) / "dippy"
            symlink_path.symlink_to(DIPPY_HOOK)
            return _run(symlink_path, input_data, use_system_python)
    return _run(DIPPY_HOOK, input_data, use_system_python)


def _run(
    script: Path, input_data: dict | str | None, use_system_python: bool = False
) -> subprocess.CompletedProcess:
    """Execute the script with input."""
    if input_data is None:
        stdin_bytes = b""
    elif isinstance(input_data, dict):
        stdin_bytes = json.dumps(input_data).encode()
    else:
        stdin_bytes = input_data.encode()

    python = SYSTEM_PYTHON if use_system_python else sys.executable
    return subprocess.run(
        [python, str(script)],
        input=stdin_bytes,
        capture_output=True,
        timeout=10,
    )


class TestSymlinkResolution:
    """Test that dippy-hook works when invoked via symlink (Homebrew scenario)."""

    def test_direct_invocation(self):
        """Baseline: direct invocation works."""
        input_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        result = run_hook(input_data, via_symlink=False)
        assert result.returncode == 0, f"stderr: {result.stderr.decode()}"
        output = json.loads(result.stdout)
        assert get_decision(output) == "allow"

    def test_symlink_invocation(self):
        """Critical: invocation via symlink must also work.

        Uses system Python to ensure we're testing the script's path resolution,
        not relying on dippy being installed in the venv.
        """
        input_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        result = run_hook(input_data, via_symlink=True, use_system_python=True)
        assert result.returncode == 0, f"stderr: {result.stderr.decode()}"
        output = json.loads(result.stdout)
        assert get_decision(output) == "allow"

    def test_nested_symlink_invocation(self):
        """Symlink in deeply nested unrelated path (simulates Homebrew Cellar)."""
        input_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate: /opt/homebrew/bin/dippy -> /opt/homebrew/Cellar/dippy/0.1/libexec/bin/dippy-hook
            nested = Path(tmpdir) / "opt" / "homebrew" / "bin"
            nested.mkdir(parents=True)
            symlink_path = nested / "dippy"
            symlink_path.symlink_to(DIPPY_HOOK)

            stdin_bytes = json.dumps(input_data).encode()
            result = subprocess.run(
                [SYSTEM_PYTHON, str(symlink_path)],
                input=stdin_bytes,
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, f"stderr: {result.stderr.decode()}"
            output = json.loads(result.stdout)
            assert get_decision(output) == "allow"


class TestEndToEnd:
    """End-to-end tests for JSON input/output."""

    def test_allow_safe_command(self):
        """Safe commands return allow decision."""
        input_data = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        result = run_hook(input_data)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert get_decision(output) == "allow"

    def test_ask_unknown_command(self):
        """Unknown commands return ask decision."""
        input_data = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
        result = run_hook(input_data)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert get_decision(output) == "ask"

    def test_non_bash_tool_passthrough(self):
        """Non-Bash tools should pass through (allow)."""
        input_data = {"tool_name": "Read", "tool_input": {"path": "/etc/passwd"}}
        result = run_hook(input_data)
        assert result.returncode == 0
        output = json.loads(result.stdout)
        # Non-Bash tools return empty object (passthrough)
        assert output == {}


class TestErrorHandling:
    """Test graceful handling of bad input."""

    def test_invalid_json(self):
        """Malformed JSON should not crash."""
        result = run_hook("not valid json {{{")
        # Should not crash - may return error or ask
        assert result.returncode == 0

    def test_empty_stdin(self):
        """Empty stdin should not crash."""
        result = run_hook(None)
        assert result.returncode == 0

    def test_missing_tool_name(self):
        """Missing tool_name field should not crash."""
        result = run_hook({"tool_input": {"command": "ls"}})
        assert result.returncode == 0

    def test_missing_tool_input(self):
        """Missing tool_input field should not crash."""
        result = run_hook({"tool_name": "Bash"})
        assert result.returncode == 0
