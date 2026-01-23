"""Tests for tee CLI handler."""

from __future__ import annotations

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule


class TestTeeBasic:
    """Basic tee functionality tests without redirect rules."""

    def test_tee_no_files(self, check):
        """tee with no files just passes through - safe."""
        result = check("tee")
        assert is_approved(result)

    def test_tee_only_flags(self, check):
        """tee with only flags and no files - safe."""
        result = check("tee -a")
        assert is_approved(result)

    def test_tee_help(self, check):
        """tee --help should be approved."""
        result = check("tee --help")
        assert is_approved(result)

    def test_tee_version(self, check):
        """tee --version should be approved."""
        result = check("tee --version")
        assert is_approved(result)


class TestTeeNeedsConfirmation:
    """tee with files but no matching redirect rules needs confirmation."""

    def test_tee_single_file(self, check):
        """tee to a file without matching rule needs confirmation."""
        result = check("tee /etc/passwd")
        assert needs_confirmation(result)

    def test_tee_multiple_files(self, check):
        """tee to multiple files without matching rules needs confirmation."""
        result = check("tee file1.txt file2.txt")
        assert needs_confirmation(result)

    def test_tee_with_append_flag(self, check):
        """tee -a to file without matching rule needs confirmation."""
        result = check("tee -a output.log")
        assert needs_confirmation(result)


class TestTeeSafeRedirectTargets:
    """tee to safe targets should be auto-approved without config."""

    def test_tee_to_dev_null(self, check):
        """tee /dev/null should be approved without config."""
        result = check("tee /dev/null")
        assert is_approved(result)

    def test_tee_to_dev_stdout(self, check):
        """tee /dev/stdout should be approved without config."""
        result = check("tee /dev/stdout")
        assert is_approved(result)

    def test_tee_to_dev_stdin(self, check):
        """tee /dev/stdin should be approved without config."""
        result = check("tee /dev/stdin")
        assert is_approved(result)


class TestTeeWithRedirectRules:
    """tee with redirect rules in config."""

    def test_tee_allowed_by_rule(self, check, tmp_path):
        """tee to path allowed by redirect rule should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee /tmp/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_allowed_glob_pattern(self, check, tmp_path):
        """tee to path matching glob pattern should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/**")])
        result = check("tee /tmp/subdir/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_with_append_allowed(self, check, tmp_path):
        """tee -a to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee -a /tmp/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_multiple_files_all_allowed(self, check, tmp_path):
        """tee to multiple files all matching rules should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee /tmp/a.txt /tmp/b.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_multiple_files_one_not_allowed(self, check, tmp_path):
        """tee to files where one doesn't match rule needs confirmation."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee /tmp/a.txt /etc/passwd", config=cfg, cwd=tmp_path)
        assert needs_confirmation(result)

    def test_tee_denied_by_rule(self, check, tmp_path):
        """tee to path denied by redirect rule should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check("tee /etc/config", config=cfg, cwd=tmp_path)
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_tee_ask_rule(self, check, tmp_path):
        """tee to path with ask rule should ask."""
        cfg = Config(redirect_rules=[Rule("ask", ".env*")])
        result = check("tee .env.local", config=cfg, cwd=tmp_path)
        assert needs_confirmation(result)


class TestTeeInPipeline:
    """tee used in pipelines."""

    def test_pipeline_tee_no_files(self, check):
        """echo | tee with no files - safe."""
        result = check("echo hello | tee")
        assert is_approved(result)

    def test_pipeline_tee_needs_confirmation(self, check):
        """echo | tee file without matching rule needs confirmation."""
        result = check("echo hello | tee output.txt")
        assert needs_confirmation(result)

    def test_pipeline_tee_allowed(self, check, tmp_path):
        """echo | tee to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("echo hello | tee /tmp/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)


class TestTeeEdgeCases:
    """Edge cases for tee handler."""

    def test_tee_double_dash(self, check, tmp_path):
        """tee -- file treats everything after -- as files."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee -- /tmp/file.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_long_flags(self, check, tmp_path):
        """tee with long flags should be handled correctly."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee --append /tmp/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_tee_ignore_interrupts(self, check, tmp_path):
        """tee -i (ignore interrupts) with allowed file should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("tee -i /tmp/out.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)
