"""Tests for strip_global_flags() in dippy.cli."""

from __future__ import annotations

from dippy.cli import strip_global_flags


class TestStripGlobalFlags:
    """Unit tests for strip_global_flags()."""

    # --- Example 1: Git handler ---

    def test_git_dash_C_with_arg(self):
        result = strip_global_flags(["git", "-C", "/path", "commit", "-m", "test"])
        assert result == ["git", "commit", "-m", "test"]

    def test_git_git_dir_equals(self):
        result = strip_global_flags(["git", "--git-dir=/path", "commit"])
        assert result == ["git", "commit"]

    def test_git_work_tree_equals(self):
        result = strip_global_flags(["git", "--work-tree=/path", "status"])
        assert result == ["git", "status"]

    def test_git_no_pager_and_dash_C(self):
        result = strip_global_flags(["git", "--no-pager", "-C", "/path", "status"])
        assert result == ["git", "status"]

    def test_git_work_tree_with_arg(self):
        result = strip_global_flags(
            ["git", "--work-tree", "/path", "commit", "-m", "test"]
        )
        assert result == ["git", "commit", "-m", "test"]

    def test_git_multiple_global_flags(self):
        result = strip_global_flags(
            [
                "git",
                "--no-pager",
                "-c",
                "core.editor=vim",
                "-C",
                "/path",
                "log",
                "--oneline",
            ]
        )
        assert result == ["git", "log", "--oneline"]

    def test_git_only_no_arg_flag(self):
        result = strip_global_flags(["git", "--no-pager", "status"])
        assert result == ["git", "status"]

    def test_git_no_flags_returns_none(self):
        result = strip_global_flags(["git", "commit", "-m", "test"])
        assert result is None

    def test_git_dash_c_key_value(self):
        result = strip_global_flags(["git", "-c", "user.name=Test", "log"])
        assert result == ["git", "log"]

    # --- Example 2: Docker handler ---

    def test_docker_host_flag(self):
        result = strip_global_flags(["docker", "-H", "tcp://host", "ps"])
        assert result == ["docker", "ps"]

    def test_docker_context_flag(self):
        result = strip_global_flags(["docker", "--context", "myctx", "ps"])
        assert result == ["docker", "ps"]

    def test_docker_no_flags_returns_none(self):
        result = strip_global_flags(["docker", "ps"])
        assert result is None

    # --- No handler / unknown command ---

    def test_unknown_command_returns_none(self):
        result = strip_global_flags(["unknown-cmd", "-C", "/path", "foo"])
        assert result is None

    # --- Edge cases ---

    def test_empty_tokens(self):
        result = strip_global_flags([])
        assert result is None

    def test_single_token(self):
        result = strip_global_flags(["git"])
        assert result is None

    def test_all_global_flags_no_subcommand(self):
        result = strip_global_flags(["git", "--no-pager", "-C", "/path"])
        assert result == ["git"]
