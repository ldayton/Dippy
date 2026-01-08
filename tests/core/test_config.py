"""Tests for Dippy config system."""

from pathlib import Path

from dippy.core.config import Config, matches_pattern
from dippy.dippy import check_command


class TestMatchesPattern:
    """Tests for pattern matching."""

    def test_simple_command_match(self):
        """Simple command matches exactly."""
        assert matches_pattern("mkdir foo", "mkdir", ["mkdir", "foo"])
        assert matches_pattern("mkdir", "mkdir", ["mkdir"])
        assert not matches_pattern("rmdir foo", "mkdir", ["rmdir", "foo"])

    def test_prefix_match(self):
        """Multi-token patterns match as prefix."""
        assert matches_pattern("git stash pop", "git stash", ["git", "stash", "pop"])
        assert matches_pattern("git stash", "git stash", ["git", "stash"])
        assert not matches_pattern("git status", "git stash", ["git", "status"])

    def test_regex_pattern(self):
        """Regex patterns with re: prefix."""
        assert matches_pattern("make test", "re:^make (test|lint|build)", ["make", "test"])
        assert matches_pattern("make lint", "re:^make (test|lint|build)", ["make", "lint"])
        assert not matches_pattern("make deploy", "re:^make (test|lint|build)", ["make", "deploy"])

    def test_regex_invalid(self):
        """Invalid regex doesn't match."""
        assert not matches_pattern("foo", "re:[invalid", ["foo"])

    def test_script_absolute_path(self, tmp_path):
        """Absolute script paths match exactly."""
        script = tmp_path / "deploy.sh"
        script.touch()

        pattern = str(script)
        cmd = str(script)
        tokens = [cmd]

        assert matches_pattern(cmd, pattern, tokens, project_root=tmp_path)

    def test_script_relative_path(self, tmp_path):
        """Relative script paths resolve against project root."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "deploy.sh"
        script.touch()

        pattern = "./scripts/deploy.sh"
        cmd = "./scripts/deploy.sh"
        tokens = [cmd]

        assert matches_pattern(
            cmd, pattern, tokens,
            project_root=tmp_path,
            cwd=tmp_path
        )

    def test_script_different_paths_no_match(self, tmp_path):
        """Scripts with same name but different paths don't match."""
        # Create two scripts with same name in different dirs
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "script.sh").touch()
        (dir2 / "script.sh").touch()

        pattern = "./dir1/script.sh"
        cmd = "./dir2/script.sh"
        tokens = [cmd]

        assert not matches_pattern(
            cmd, pattern, tokens,
            project_root=tmp_path,
            cwd=tmp_path
        )


class TestConfigMerge:
    """Tests for config merging."""

    def test_merge_combines_lists(self):
        """Merging combines approve and confirm lists."""
        c1 = Config(approve=["a", "b"], confirm=["x"])
        c2 = Config(approve=["c"], confirm=["y"])
        merged = c1.merge(c2)

        assert merged.approve == ["a", "b", "c"]
        assert merged.confirm == ["x", "y"]

    def test_merge_aliases_override(self):
        """Later aliases override earlier ones."""
        c1 = Config(aliases={"k": "kubectl", "g": "git"})
        c2 = Config(aliases={"k": "kind"})
        merged = c1.merge(c2)

        assert merged.aliases == {"k": "kind", "g": "git"}

    def test_merge_project_root(self):
        """Project root comes from later config."""
        c1 = Config(project_root=Path("/a"))
        c2 = Config(project_root=Path("/b"))
        merged = c1.merge(c2)

        assert merged.project_root == Path("/b")


class TestCheckCommandWithConfig:
    """Tests for check_command with config."""

    def test_approve_pattern(self):
        """Config approve patterns auto-approve commands."""
        config = Config(approve=["mkdir"])
        result = check_command("mkdir foo", config)

        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "config:" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_confirm_overrides_approve(self):
        """Config confirm patterns override approve."""
        config = Config(
            approve=["git push"],
            confirm=["git push --force"],
        )

        # Regular push approved
        result = check_command("git push origin main", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

        # Force push asks
        result = check_command("git push --force origin main", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_confirm_overrides_builtin(self):
        """Config confirm patterns override built-in safe commands."""
        config = Config(confirm=["ls"])
        result = check_command("ls -la", config)

        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert "config confirm:" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_alias_resolution(self):
        """Aliases resolve to their target commands."""
        config = Config(aliases={"k": "kubectl"})

        # k get pods -> kubectl get pods (safe)
        result = check_command("k get pods", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

        # k delete pod -> kubectl delete pod (unsafe)
        result = check_command("k delete pod foo", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_regex_approve(self):
        """Regex patterns in approve work."""
        config = Config(approve=["re:^make (test|lint|build)"])

        result = check_command("make test", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

        result = check_command("make deploy", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_no_config_uses_defaults(self):
        """Without config, uses built-in rules."""
        result = check_command("ls -la")
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

        result = check_command("rm -rf /", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"


class TestConfigWithCmdsubs:
    """Tests for config-approved commands with command substitutions."""

    def test_approve_with_safe_cmdsub(self):
        """Config-approved command with safe cmdsub is allowed."""
        config = Config(approve=["echo"])
        result = check_command("echo $(pwd)", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_with_unsafe_cmdsub(self):
        """Config-approved command with unsafe cmdsub is blocked."""
        config = Config(approve=["echo"])
        result = check_command("echo $(rm -rf /)", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert "cmdsub" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_approve_with_nested_unsafe_cmdsub(self):
        """Config-approved command with nested unsafe cmdsub is blocked."""
        config = Config(approve=["echo"])
        result = check_command("echo $(cat $(rm -rf /))", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_approve_cmdsub_checked_against_config(self):
        """Inner cmdsub commands go through config too."""
        # Both echo and make test are approved
        config = Config(approve=["echo", "re:^make (test|lint)"])
        result = check_command("echo $(make test)", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_cmdsub_blocked_by_confirm(self):
        """Inner cmdsub can be blocked by confirm pattern."""
        config = Config(approve=["echo"], confirm=["pwd"])
        result = check_command("echo $(pwd)", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        # The inner pwd triggers config confirm
        assert "config confirm" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_confirm_still_asks_even_with_safe_cmdsub(self):
        """Confirm pattern always asks, regardless of cmdsubs."""
        config = Config(confirm=["echo"])
        result = check_command("echo $(pwd)", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert "config confirm:" in result["hookSpecificOutput"]["permissionDecisionReason"]


class TestConfigPrecedence:
    """Tests for config precedence ordering."""

    def test_confirm_beats_approve(self):
        """Confirm patterns take precedence over approve."""
        config = Config(
            approve=["git push"],
            confirm=["git push --force"],
        )
        # Approve matches, but confirm matches more specifically
        result = check_command("git push --force", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_confirm_beats_builtin_safe(self):
        """Confirm patterns override built-in safe commands."""
        config = Config(confirm=["pwd"])
        result = check_command("pwd", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_approve_beats_unsafe_handler(self):
        """Approve patterns override handlers that would block."""
        config = Config(approve=["git stash"])
        # git stash drop would normally be blocked by handler
        result = check_command("git stash drop", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_bypasses_redirect_check(self):
        """Approve patterns bypass output redirect checking."""
        # Use regex since tokenizer strips redirects
        config = Config(approve=[r"re:^echo hello > file\.txt$"])
        result = check_command("echo hello > file.txt", config)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_builtin_safe_without_config(self):
        """Built-in safe commands work without any config."""
        result = check_command("ls -la", Config())
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_handler_blocks_without_config(self):
        """Handlers block unsafe commands without config."""
        result = check_command("git push --force", Config())
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
