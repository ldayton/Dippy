"""
Tests for the argument-path resolver.

Covers the path normalization contract from the security model: ``~`` and
relative paths are resolved, while variables are left literal (the shell
expands those after approval).
"""

from __future__ import annotations

from pathlib import Path

from dippy.core.paths import resolve_arg_path


class TestResolveArgPath:
    def test_tilde_expands_to_home(self, tmp_path, monkeypatch):
        """~ resolves to the home directory (security model: ~/bar -> /home/user/bar)."""
        monkeypatch.setenv("HOME", str(tmp_path))
        result = resolve_arg_path("~/script.py", cwd=Path("/some/other/dir"))
        assert result == (tmp_path / "script.py").resolve()
        assert "~" not in str(result)

    def test_dollar_var_left_literal(self, tmp_path, monkeypatch):
        """$VAR is NOT expanded: the shell expands it after approval, so the
        resolver must not read it from the hook's own environment."""
        monkeypatch.setenv("HOME", str(tmp_path))
        result = resolve_arg_path("$HOME/script.py", cwd=tmp_path)
        assert "$HOME" in str(result)
        assert result != (tmp_path / "script.py").resolve()

    def test_relative_anchored_to_cwd(self, tmp_path):
        """Relative paths resolve against cwd."""
        result = resolve_arg_path("sub/script.py", cwd=tmp_path)
        assert result == (tmp_path / "sub" / "script.py").resolve()

    def test_absolute_preserved(self, tmp_path):
        """Absolute paths are not re-anchored to cwd."""
        target = tmp_path / "script.py"
        result = resolve_arg_path(str(target), cwd=Path("/some/other/dir"))
        assert result == target.resolve()

    def test_unknown_user_left_literal_without_raising(self, tmp_path):
        """An unknown ~user must not raise; it stays literal so the path
        simply won't exist and the caller can degrade to ask."""
        result = resolve_arg_path("~nosuchuser12345/script.py", cwd=tmp_path)
        assert "~nosuchuser12345" in str(result)
