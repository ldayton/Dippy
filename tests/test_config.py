"""Tests for config loading, merging, and logging."""

import json
import os
import stat
from pathlib import Path

import pytest

from dippy.core.config import (
    Config,
    Rule,
    SCOPE_ENV,
    SCOPE_PROJECT,
    SCOPE_USER,
    _find_project_config,
    _merge_configs,
    _tag_rules,
    configure_logging,
    load_config,
    log_decision,
)


class TestFindProjectConfig:
    """Test walking up to find .dippy."""

    def test_finds_in_cwd(self, tmp_path):
        (tmp_path / ".dippy").write_text("allow ls")
        assert _find_project_config(tmp_path) == tmp_path / ".dippy"

    def test_finds_in_parent(self, tmp_path):
        (tmp_path / ".dippy").write_text("allow ls")
        child = tmp_path / "src" / "deep"
        child.mkdir(parents=True)
        assert _find_project_config(child) == tmp_path / ".dippy"

    def test_stops_at_first(self, tmp_path):
        (tmp_path / ".dippy").write_text("root")
        child = tmp_path / "project"
        child.mkdir()
        (child / ".dippy").write_text("project")
        assert _find_project_config(child) == child / ".dippy"

    def test_not_found(self, tmp_path):
        child = tmp_path / "no" / "config" / "here"
        child.mkdir(parents=True)
        assert _find_project_config(child) is None

    def test_ignores_directory(self, tmp_path):
        (tmp_path / ".dippy").mkdir()
        assert _find_project_config(tmp_path) is None

    def test_symlink_to_file(self, tmp_path):
        real_config = tmp_path / "real_config"
        real_config.write_text("allow ls")
        (tmp_path / "project").mkdir()
        (tmp_path / "project" / ".dippy").symlink_to(real_config)
        assert (
            _find_project_config(tmp_path / "project")
            == tmp_path / "project" / ".dippy"
        )


class TestMergeConfigs:
    """Test config merging logic."""

    def test_rules_concatenate(self):
        base = Config(rules=[Rule("allow", "ls")])
        overlay = Config(rules=[Rule("ask", "rm *", message="careful")])
        merged = _merge_configs(base, overlay)
        assert len(merged.rules) == 2
        assert merged.rules[0].pattern == "ls"
        assert merged.rules[1].pattern == "rm *"
        assert merged.rules[1].message == "careful"

    def test_redirect_rules_concatenate(self):
        base = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        overlay = Config(redirect_rules=[Rule("ask", ".env*", message="secrets")])
        merged = _merge_configs(base, overlay)
        assert len(merged.redirect_rules) == 2

    def test_settings_override(self):
        base = Config(sticky_session=True, suggest_after=5, verbose=True)
        overlay = Config(suggest_after=10, warn_banner=True)
        merged = _merge_configs(base, overlay)
        assert merged.sticky_session is True
        assert merged.suggest_after == 10
        assert merged.verbose is True
        assert merged.warn_banner is True

    def test_default_only_overrides_if_changed(self):
        base = Config(default="allow")
        overlay = Config(default="ask")  # ask is the default, shouldn't override
        merged = _merge_configs(base, overlay)
        assert merged.default == "allow"

    def test_log_path_override(self):
        base = Config(log=Path("/base/log"))
        overlay = Config()
        merged = _merge_configs(base, overlay)
        assert merged.log == Path("/base/log")

        overlay2 = Config(log=Path("/overlay/log"))
        merged2 = _merge_configs(base, overlay2)
        assert merged2.log == Path("/overlay/log")

    def test_triple_merge_preserves_order(self):
        user = Config(rules=[Rule("allow", "git *")], default="allow")
        project = Config(rules=[Rule("ask", "git push *")], verbose=True)
        env = Config(rules=[Rule("allow", "git push --dry-run *")], disabled=True)

        merged = _merge_configs(_merge_configs(user, project), env)
        assert len(merged.rules) == 3
        assert merged.rules[0].pattern == "git *"
        assert merged.rules[1].pattern == "git push *"
        assert merged.rules[2].pattern == "git push --dry-run *"
        assert merged.default == "allow"
        assert merged.verbose is True
        assert merged.disabled is True


class TestTagRules:
    """Test origin tagging for rules."""

    def test_tags_rules_with_source_and_scope(self):
        config = Config(
            rules=[Rule("allow", "ls"), Rule("ask", "rm")],
            redirect_rules=[Rule("allow", "/tmp/*")],
        )
        tagged = _tag_rules(config, "/path/to/config", SCOPE_USER)

        assert all(r.source == "/path/to/config" for r in tagged.rules)
        assert all(r.scope == SCOPE_USER for r in tagged.rules)
        assert tagged.redirect_rules[0].source == "/path/to/config"

    def test_does_not_mutate_original(self):
        original = Config(rules=[Rule("allow", "ls")])
        tagged = _tag_rules(original, "/path", SCOPE_PROJECT)

        assert original.rules[0].source is None
        assert tagged.rules[0].source == "/path"


class TestLoadConfig:
    """Test full config loading from files."""

    def test_loads_user_config(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user" / "config"
        user_cfg.parent.mkdir()
        user_cfg.write_text("allow git *")
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        def mock_parse(text):
            if "git" in text:
                return Config(rules=[Rule("allow", "git *")])
            return Config()

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(tmp_path)
        assert len(config.rules) == 1
        assert config.rules[0].pattern == "git *"

    def test_loads_project_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")

        proj = tmp_path / "project"
        proj.mkdir()
        (proj / ".dippy").write_text("ask rm *")

        def mock_parse(text):
            if "rm" in text:
                return Config(rules=[Rule("ask", "rm *")])
            return Config()

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(proj)
        assert len(config.rules) == 1
        assert config.rules[0].pattern == "rm *"

    def test_loads_env_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")

        env_cfg = tmp_path / "env.cfg"
        env_cfg.write_text("allow docker *")
        monkeypatch.setenv("DIPPY_CONFIG", str(env_cfg))

        def mock_parse(text):
            if "docker" in text:
                return Config(rules=[Rule("allow", "docker *")])
            return Config()

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(tmp_path)
        assert len(config.rules) == 1
        assert config.rules[0].pattern == "docker *"

    def test_empty_when_no_configs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")
        monkeypatch.delenv("DIPPY_CONFIG", raising=False)

        config = load_config(tmp_path)
        assert config.rules == []
        assert config.redirect_rules == []

    def test_env_config_tilde_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")

        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        (fake_home / "my.cfg").write_text("allow tilde")
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DIPPY_CONFIG", "~/my.cfg")

        def mock_parse(text):
            return Config(rules=[Rule("allow", text.strip())])

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(tmp_path)
        assert config.rules[0].pattern == "allow tilde"

    def test_env_config_missing_file_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")
        monkeypatch.setenv("DIPPY_CONFIG", str(tmp_path / "does_not_exist.cfg"))

        config = load_config(tmp_path)
        assert config.rules == []

    def test_parse_error_propagates(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("invalid config")
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        def mock_parse_error(text):
            raise ValueError("syntax error on line 1")

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse_error)

        with pytest.raises(ValueError, match="syntax error"):
            load_config(tmp_path)

    @pytest.mark.skipif(os.name == "nt", reason="Unix permissions only")
    def test_unreadable_user_config(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("allow ls")
        user_cfg.chmod(0o000)
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        try:
            with pytest.raises(PermissionError):
                load_config(tmp_path)
        finally:
            user_cfg.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TestScopeIsolation:
    """Git-style scope isolation and precedence tests."""

    def test_rules_tagged_with_correct_scope(self, tmp_path, monkeypatch):
        """Each scope's rules should be tagged with their origin."""
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("user rule")
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        proj = tmp_path / "project"
        proj.mkdir()
        (proj / ".dippy").write_text("project rule")

        env_cfg = tmp_path / "env.cfg"
        env_cfg.write_text("env rule")
        monkeypatch.setenv("DIPPY_CONFIG", str(env_cfg))

        def mock_parse(text):
            return Config(rules=[Rule("allow", text.strip())])

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(proj)

        assert len(config.rules) == 3
        assert config.rules[0].scope == SCOPE_USER
        assert config.rules[0].source == str(user_cfg)
        assert config.rules[1].scope == SCOPE_PROJECT
        assert config.rules[1].source == str(proj / ".dippy")
        assert config.rules[2].scope == SCOPE_ENV
        assert config.rules[2].source == str(env_cfg)

    def test_scope_order_is_user_project_env(self, tmp_path, monkeypatch):
        """Rules should accumulate in priority order: user < project < env."""
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("first")
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        proj = tmp_path / "project"
        proj.mkdir()
        (proj / ".dippy").write_text("second")

        env_cfg = tmp_path / "env.cfg"
        env_cfg.write_text("third")
        monkeypatch.setenv("DIPPY_CONFIG", str(env_cfg))

        def mock_parse(text):
            return Config(rules=[Rule("allow", text.strip())])

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(proj)

        patterns = [r.pattern for r in config.rules]
        assert patterns == ["first", "second", "third"]

    def test_env_can_override_project_setting(self, tmp_path, monkeypatch):
        """Higher scope can override settings from lower scope."""
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")

        proj = tmp_path / "project"
        proj.mkdir()
        (proj / ".dippy").write_text("project")

        env_cfg = tmp_path / "env.cfg"
        env_cfg.write_text("env")
        monkeypatch.setenv("DIPPY_CONFIG", str(env_cfg))

        def mock_parse(text):
            if "project" in text:
                return Config(verbose=True, disabled=False)
            else:
                return Config(disabled=True)

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(proj)

        assert config.verbose is True
        assert config.disabled is True


class TestLogging:
    """Test structured logging."""

    def test_no_logging_when_disabled(self, tmp_path):
        config = Config(log=None)
        configure_logging(config)
        log_decision("allow", "ls")
        assert not list(tmp_path.glob("*.log"))

    def test_logs_to_file(self, tmp_path):
        log_path = tmp_path / "audit.log"
        config = Config(log=log_path)
        configure_logging(config)

        log_decision("allow", "git", rule="allow git *")

        assert log_path.exists()
        line = json.loads(log_path.read_text().strip())
        assert line["decision"] == "allow"
        assert line["cmd"] == "git"
        assert line["rule"] == "allow git *"
        assert "ts" in line

    def test_log_full_includes_command(self, tmp_path):
        log_path = tmp_path / "audit.log"
        config = Config(log=log_path, log_full=True)
        configure_logging(config)

        log_decision("allow", "git", command="git status --porcelain")

        line = json.loads(log_path.read_text().strip())
        assert line["command"] == "git status --porcelain"

    def test_log_without_full_excludes_command(self, tmp_path):
        log_path = tmp_path / "audit.log"
        config = Config(log=log_path, log_full=False)
        configure_logging(config)

        log_decision("allow", "git", command="git status --porcelain")

        line = json.loads(log_path.read_text().strip())
        assert "command" not in line

    def test_creates_log_directory(self, tmp_path):
        log_path = tmp_path / "nested" / "dir" / "audit.log"
        config = Config(log=log_path)
        configure_logging(config)

        log_decision("allow", "ls")

        assert log_path.exists()

    def test_appends_to_log(self, tmp_path):
        log_path = tmp_path / "audit.log"
        config = Config(log=log_path)
        configure_logging(config)

        log_decision("allow", "ls")
        log_decision("ask", "rm")

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2


class TestConfigImmutability:
    """Test that operations don't mutate inputs."""

    def test_merge_does_not_mutate(self):
        base = Config(rules=[Rule("allow", "ls")])
        overlay = Config(rules=[Rule("ask", "rm")])

        original_base_rules = base.rules.copy()
        original_overlay_rules = overlay.rules.copy()

        _merge_configs(base, overlay)

        assert base.rules == original_base_rules
        assert overlay.rules == original_overlay_rules
