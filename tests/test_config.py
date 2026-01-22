"""Tests for config loading, merging, and logging."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from dippy.core.config import (
    Config,
    ConfigError,
    Rule,
    SCOPE_ENV,
    SCOPE_PROJECT,
    SCOPE_USER,
    SimpleCommand,
    _find_project_config,
    _merge_configs,
    _tag_rules,
    configure_logging,
    load_config,
    log_decision,
    match_after,
    match_after_mcp,
    match_command,
    match_mcp,
    match_redirect,
    parse_config,
)


def cmd(s: str) -> SimpleCommand:
    """Helper to create SimpleCommand from a string (splits on whitespace)."""
    return SimpleCommand(words=s.split() if s else [])


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
        project = Config(rules=[Rule("ask", "git push *")])
        env = Config(rules=[Rule("allow", "git push --dry-run *")])

        merged = _merge_configs(_merge_configs(user, project), env)
        assert len(merged.rules) == 3
        assert merged.rules[0].pattern == "git *"
        assert merged.rules[1].pattern == "git push *"
        assert merged.rules[2].pattern == "git push --dry-run *"
        assert merged.default == "allow"


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

        def mock_parse(text, source=None):
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

        def mock_parse(text, source=None):
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

        def mock_parse(text, source=None):
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

        def mock_parse(text, source=None):
            return Config(rules=[Rule("allow", text.strip())])

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(tmp_path)
        assert config.rules[0].pattern == "allow tilde"

    def test_env_config_missing_file_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", tmp_path / "nonexistent")
        monkeypatch.setenv("DIPPY_CONFIG", str(tmp_path / "does_not_exist.cfg"))

        config = load_config(tmp_path)
        assert config.rules == []

    def test_invalid_lines_skipped(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("invalid directive\nallow git *\nbad line too")
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        config = load_config(tmp_path)
        # Invalid lines skipped, valid line parsed
        assert len(config.rules) == 1
        assert config.rules[0].pattern == "git *"

    @pytest.mark.skipif(os.name == "nt", reason="Unix permissions only")
    def test_unreadable_user_config(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user.cfg"
        user_cfg.write_text("allow ls")
        user_cfg.chmod(0o000)
        monkeypatch.setattr("dippy.core.config.USER_CONFIG", user_cfg)

        try:
            with pytest.raises(ConfigError, match="permission denied"):
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

        def mock_parse(text, source=None):
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

        def mock_parse(text, source=None):
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

        def mock_parse(text, source=None):
            if "project" in text:
                return Config(log=Path("/project/log"))
            else:
                return Config(log=Path("/env/log"))

        monkeypatch.setattr("dippy.core.config.parse_config", mock_parse)

        config = load_config(proj)

        assert config.log == Path("/env/log")


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


class TestParseConfig:
    """Test config parsing - focus on security-relevant edge cases."""

    def test_unknown_directive_skipped(self):
        cfg = parse_config("yolo rm -rf /")
        assert cfg.rules == []  # invalid line skipped

    def test_unknown_setting_skipped(self):
        cfg = parse_config("set yolo")
        assert cfg.default == "ask"  # no settings applied

    def test_message_extraction_space_before_quote(self):
        # Space before quote = message
        cfg = parse_config('ask rm * "careful"')
        assert cfg.rules[0].pattern == "rm *"
        assert cfg.rules[0].message == "careful"

    def test_message_extraction_no_space_before_quote(self):
        # No space = part of pattern
        cfg = parse_config('ask echo"hello"')
        assert cfg.rules[0].pattern == 'echo"hello"'
        assert cfg.rules[0].message is None

    def test_escaped_quote_in_message(self):
        cfg = parse_config(r'ask rm * "say \"hello\""')
        assert cfg.rules[0].pattern == "rm *"
        assert cfg.rules[0].message == 'say "hello"'

    def test_escaped_backslash_before_quote_in_message(self):
        # User wants message containing literal backslash + quote: C:\"
        # Write \\ for literal backslash, \" for literal quote
        cfg = parse_config(r'ask pattern "C:\\\""')
        assert cfg.rules[0].pattern == "pattern"
        assert cfg.rules[0].message == 'C:\\"'  # C, colon, backslash, quote

    def test_message_ending_with_backslash(self):
        # User wants message ending with backslash: path\
        # Write \\ for literal backslash
        cfg = parse_config(r'ask cmd "path\\"')
        assert cfg.rules[0].pattern == "cmd"
        assert cfg.rules[0].message == "path\\"  # path + single backslash

    def test_multiple_backslashes_in_message(self):
        # User wants: a\\b (a, backslash, backslash, b)
        # Write: \\\\ for two literal backslashes
        cfg = parse_config(r'ask cmd "a\\\\b"')
        assert cfg.rules[0].pattern == "cmd"
        assert cfg.rules[0].message == "a\\\\b"  # a + two backslashes + b

    def test_message_with_escaped_closing_quote_and_real_close(self):
        # "say \"hi\"" - escaped quotes inside, real close at end
        cfg = parse_config(r'ask cmd "say \"hi\""')
        assert cfg.rules[0].pattern == "cmd"
        assert cfg.rules[0].message == 'say "hi"'

    def test_multiple_quoted_sections_takes_rightmost(self):
        # Multiple quoted sections - rightmost should be the message
        cfg = parse_config('ask pattern "not this" "this one"')
        assert cfg.rules[0].pattern == 'pattern "not this"'
        assert cfg.rules[0].message == "this one"

    def test_empty_message(self):
        # Empty quoted string - is this valid?
        cfg = parse_config('ask pattern ""')
        assert cfg.rules[0].pattern == "pattern"
        assert cfg.rules[0].message == ""

    def test_escaped_trailing_quote_no_message(self):
        cfg = parse_config(r"ask echo \"")
        assert cfg.rules[0].pattern == r"echo \""
        assert cfg.rules[0].message is None

    def test_allow_no_message_extraction(self):
        # allow doesn't extract messages - whole thing is pattern
        cfg = parse_config('allow echo "hello"')
        assert cfg.rules[0].pattern == 'echo "hello"'
        assert cfg.rules[0].message is None

    def test_exact_anchor_allow(self):
        cfg = parse_config("allow git add|")
        assert cfg.rules[0].pattern == "git add"
        assert cfg.rules[0].exact is True

    def test_exact_anchor_allow_with_space(self):
        cfg = parse_config("allow git add |")
        assert cfg.rules[0].pattern == "git add"
        assert cfg.rules[0].exact is True

    def test_exact_anchor_ask(self):
        cfg = parse_config("ask git push|")
        assert cfg.rules[0].pattern == "git push"
        assert cfg.rules[0].exact is True

    def test_exact_anchor_ask_with_message(self):
        cfg = parse_config('ask git push| "confirm push"')
        assert cfg.rules[0].pattern == "git push"
        assert cfg.rules[0].exact is True
        assert cfg.rules[0].message == "confirm push"

    def test_exact_anchor_deny(self):
        cfg = parse_config("deny rm|")
        assert cfg.rules[0].pattern == "rm"
        assert cfg.rules[0].exact is True

    def test_exact_anchor_deny_with_message(self):
        cfg = parse_config('deny rm| "use trash instead"')
        assert cfg.rules[0].pattern == "rm"
        assert cfg.rules[0].exact is True
        assert cfg.rules[0].message == "use trash instead"

    def test_no_exact_anchor_default(self):
        cfg = parse_config("allow git add")
        assert cfg.rules[0].pattern == "git add"
        assert cfg.rules[0].exact is False

    def test_empty_pattern_before_message_skipped(self):
        cfg = parse_config('ask "just a message"')
        assert cfg.rules == []  # invalid line skipped

    def test_settings_invalid_skipped(self):
        # Boolean with value = skipped
        cfg = parse_config("set log-full true")
        assert cfg.log_full is False

        # default with bad value = skipped
        cfg = parse_config("set default yolo")
        assert cfg.default == "ask"

        # log without path = skipped
        cfg = parse_config("set log")
        assert cfg.log is None

    def test_full_config(self):
        cfg = parse_config("""
# User config
allow git *
ask rm -rf /* "are you sure?"
allow-redirect /tmp/**
ask-redirect .env* "don't write secrets"

set default allow
set log ~/.dippy/audit.log
""")
        assert len(cfg.rules) == 2
        assert cfg.rules[0].decision == "allow"
        assert cfg.rules[0].pattern == "git *"
        assert cfg.rules[1].decision == "ask"
        assert cfg.rules[1].pattern == "rm -rf /*"
        assert cfg.rules[1].message == "are you sure?"

        assert len(cfg.redirect_rules) == 2
        assert cfg.redirect_rules[0].pattern == "/tmp/**"
        assert cfg.redirect_rules[1].message == "don't write secrets"

        assert cfg.default == "allow"
        assert cfg.log == Path.home() / ".dippy" / "audit.log"

    def test_deny_directive(self):
        cfg = parse_config("deny rm -rf /*")
        assert len(cfg.rules) == 1
        assert cfg.rules[0].decision == "deny"
        assert cfg.rules[0].pattern == "rm -rf /*"

    def test_deny_with_message(self):
        cfg = parse_config('deny rm -rf /* "too dangerous"')
        assert cfg.rules[0].decision == "deny"
        assert cfg.rules[0].pattern == "rm -rf /*"
        assert cfg.rules[0].message == "too dangerous"

    def test_deny_redirect_directive(self):
        cfg = parse_config("deny-redirect /etc/**")
        assert len(cfg.redirect_rules) == 1
        assert cfg.redirect_rules[0].decision == "deny"
        assert cfg.redirect_rules[0].pattern == "/etc/**"

    def test_deny_redirect_with_message(self):
        cfg = parse_config('deny-redirect .env* "never write secrets"')
        assert cfg.redirect_rules[0].decision == "deny"
        assert cfg.redirect_rules[0].pattern == ".env*"
        assert cfg.redirect_rules[0].message == "never write secrets"

    def test_config_with_all_directives(self):
        cfg = parse_config("""
allow git *
ask rm * "careful"
deny rm -rf /* "never"
allow-redirect /tmp/*
ask-redirect .cache/* "check first"
deny-redirect /etc/* "system files"
""")
        assert len(cfg.rules) == 3
        assert cfg.rules[0].decision == "allow"
        assert cfg.rules[1].decision == "ask"
        assert cfg.rules[2].decision == "deny"
        assert len(cfg.redirect_rules) == 3
        assert cfg.redirect_rules[0].decision == "allow"
        assert cfg.redirect_rules[1].decision == "ask"
        assert cfg.redirect_rules[2].decision == "deny"


class TestMatchCommand:
    """Test command matching against config rules."""

    def test_basic_glob_match(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git *")])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("git commit -m 'msg'"), cfg, tmp_path) is not None
        assert match_command(cmd("gitk"), cfg, tmp_path) is None  # no space after git

    def test_prefix_match_default(self, tmp_path):
        """Patterns without wildcards do prefix matching by default."""
        cfg = Config(rules=[Rule("allow", "git status")])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("git statuses"), cfg, tmp_path) is None
        # Prefix matching: "git status" matches "git status --short"
        assert match_command(cmd("git status --short"), cfg, tmp_path) is not None

    def test_exact_anchor(self, tmp_path):
        """Pattern with exact=True only matches exactly, no prefix matching."""
        cfg = Config(rules=[Rule("allow", "git status", exact=True)])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("git status --short"), cfg, tmp_path) is None

    def test_no_match_returns_none(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git *")])
        assert match_command(cmd("ls -la"), cfg, tmp_path) is None

    def test_empty_rules_returns_none(self, tmp_path):
        cfg = Config(rules=[])
        assert match_command(cmd("git status"), cfg, tmp_path) is None

    def test_star_alone_matches_any(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "*")])
        assert match_command(cmd("anything"), cfg, tmp_path) is not None
        assert match_command(cmd("git status"), cfg, tmp_path) is not None

    def test_star_star_matches_with_space(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "* *")])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("ls"), cfg, tmp_path) is None  # no space

    def test_question_mark_matches_single_char(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git ?")])
        assert match_command(cmd("git a"), cfg, tmp_path) is not None
        assert match_command(cmd("git ab"), cfg, tmp_path) is None
        assert match_command(cmd("git"), cfg, tmp_path) is None

    def test_character_class(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "[abc]*")])
        assert match_command(cmd("apt install"), cfg, tmp_path) is not None
        assert match_command(cmd("brew install"), cfg, tmp_path) is not None
        assert match_command(cmd("cargo build"), cfg, tmp_path) is not None
        assert match_command(cmd("docker run"), cfg, tmp_path) is None

    def test_negated_character_class(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "[!r]*")])
        assert match_command(cmd("ls"), cfg, tmp_path) is not None
        assert match_command(cmd("rm -rf"), cfg, tmp_path) is None  # starts with r

    def test_last_match_wins_allow_then_ask(self, tmp_path):
        cfg = Config(
            rules=[
                Rule("ask", "*"),
                Rule("allow", "git *"),
            ]
        )
        m = match_command(cmd("git status"), cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"
        m2 = match_command(cmd("rm -rf /"), cfg, tmp_path)
        assert m2 is not None
        assert m2.decision == "ask"

    def test_last_match_wins_allow_then_ask_specific(self, tmp_path):
        cfg = Config(
            rules=[
                Rule("allow", "*"),
                Rule("ask", "rm *"),
            ]
        )
        m = match_command(cmd("rm -rf /"), cfg, tmp_path)
        assert m.decision == "ask"
        m2 = match_command(cmd("ls"), cfg, tmp_path)
        assert m2.decision == "allow"

    def test_three_rules_last_wins(self, tmp_path):
        cfg = Config(
            rules=[
                Rule("allow", "*"),  # matches everything
                Rule("ask", "rm *"),  # doesn't match git
                Rule("allow", "rm -i *"),  # matches rm -i
            ]
        )
        m = match_command(cmd("rm -i file"), cfg, tmp_path)
        assert m.decision == "allow"  # third rule wins

    def test_deny_last_match_wins(self, tmp_path):
        cfg = Config(
            rules=[
                Rule("allow", "rm *"),
                Rule("deny", "rm -rf /*"),
            ]
        )
        m = match_command(cmd("rm -rf /tmp"), cfg, tmp_path)
        assert m.decision == "deny"
        m2 = match_command(cmd("rm file"), cfg, tmp_path)
        assert m2.decision == "allow"

    def test_allow_can_override_deny_if_last(self, tmp_path):
        cfg = Config(
            rules=[
                Rule("deny", "rm *"),
                Rule("allow", "rm -i *"),
            ]
        )
        m = match_command(cmd("rm -i file"), cfg, tmp_path)
        assert m.decision == "allow"  # allow is last match
        m2 = match_command(cmd("rm file"), cfg, tmp_path)
        assert m2.decision == "deny"  # deny is last match

    def test_deny_with_message(self, tmp_path):
        cfg = Config(rules=[Rule("deny", "rm -rf /*", message="too dangerous")])
        m = match_command(cmd("rm -rf /tmp"), cfg, tmp_path)
        assert m.decision == "deny"
        assert m.message == "too dangerous"

    def test_tilde_expansion(self, tmp_path):
        home = str(Path.home())
        cfg = Config(rules=[Rule("allow", f"{home}/bin/*")])
        assert match_command(cmd("~/bin/tool"), cfg, tmp_path) is not None
        assert match_command(cmd("~/other/tool"), cfg, tmp_path) is None

    def test_relative_path_resolution(self, tmp_path):
        cfg = Config(rules=[Rule("allow", f"{tmp_path}/script.sh")])
        assert match_command(cmd("./script.sh"), cfg, tmp_path) is not None
        assert match_command(cmd("./other.sh"), cfg, tmp_path) is None

    def test_parent_path_resolution(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        cfg = Config(rules=[Rule("allow", f"{tmp_path}/script.sh")])
        assert match_command(cmd("../script.sh"), cfg, subdir) is not None

    def test_pattern_with_wildcards_in_middle(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git commit -m *")])
        assert match_command(cmd("git commit -m 'message'"), cfg, tmp_path) is not None
        assert match_command(cmd("git commit --amend"), cfg, tmp_path) is None

    def test_match_object_fields(self, tmp_path):
        cfg = Config(
            rules=[
                Rule(
                    "ask",
                    "rm *",
                    message="careful!",
                    source="/path/to/config",
                    scope="user",
                )
            ]
        )
        m = match_command(cmd("rm file"), cfg, tmp_path)
        assert m.decision == "ask"
        assert m.pattern == "rm *"
        assert m.message == "careful!"
        assert m.source == "/path/to/config"
        assert m.scope == "user"

    def test_message_none_when_not_set(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "ls *")])
        m = match_command(cmd("ls -la"), cfg, tmp_path)
        assert m.message is None

    def test_pattern_no_wildcards_prefix_match(self, tmp_path):
        """Pattern without wildcards does prefix matching by default."""
        cfg = Config(rules=[Rule("allow", "ls")])
        assert match_command(cmd("ls"), cfg, tmp_path) is not None
        assert match_command(cmd("ls -la"), cfg, tmp_path) is not None  # prefix match
        assert match_command(cmd("lsof"), cfg, tmp_path) is None  # different command

    def test_pattern_exact_anchor_no_prefix(self, tmp_path):
        """Pattern with exact=True only matches exactly."""
        cfg = Config(rules=[Rule("allow", "ls", exact=True)])
        assert match_command(cmd("ls"), cfg, tmp_path) is not None
        assert match_command(cmd("ls -la"), cfg, tmp_path) is None  # no prefix match
        assert match_command(cmd("lsof"), cfg, tmp_path) is None

    def test_commands_with_quotes(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "echo *")])
        assert match_command(cmd('echo "hello world"'), cfg, tmp_path) is not None
        assert match_command(cmd("echo 'single quotes'"), cfg, tmp_path) is not None


class TestMatchCommandWithRedirects:
    """Test integrated command + redirect matching."""

    def test_command_only_no_redirects(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "echo *")])
        c = SimpleCommand(words=["echo", "hello"], redirects=[])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_redirect_only_no_command_match(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("ask", "/etc/*")])
        c = SimpleCommand(words=["echo", "hello"], redirects=["/etc/passwd"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "ask"
        assert m.pattern == "/etc/*"

    def test_both_match_allow(self, tmp_path):
        cfg = Config(
            rules=[Rule("allow", "echo *")],
            redirect_rules=[Rule("allow", "/tmp/*")],
        )
        c = SimpleCommand(words=["echo", "hello"], redirects=["/tmp/out.txt"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_command_allow_redirect_ask(self, tmp_path):
        """Redirect ask should override command allow."""
        cfg = Config(
            rules=[Rule("allow", "echo *")],
            redirect_rules=[Rule("ask", "/etc/*")],
        )
        c = SimpleCommand(words=["echo", "data"], redirects=["/etc/passwd"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "ask"
        assert m.pattern == "/etc/*"  # redirect rule wins

    def test_command_ask_redirect_allow(self, tmp_path):
        """Command ask should win over redirect allow."""
        cfg = Config(
            rules=[Rule("ask", "rm *")],
            redirect_rules=[Rule("allow", "/tmp/*")],
        )
        c = SimpleCommand(words=["rm", "-rf", "/"], redirects=["/tmp/log.txt"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "ask"
        assert m.pattern == "rm *"  # command rule wins

    def test_multiple_redirects_one_asks(self, tmp_path):
        """If any redirect triggers ask, result is ask."""
        cfg = Config(
            rules=[Rule("allow", "cat *")],
            redirect_rules=[
                Rule("allow", "/tmp/*"),
                Rule("ask", "/etc/*"),
            ],
        )
        c = SimpleCommand(
            words=["cat", "file"],
            redirects=["/tmp/safe.txt", "/etc/passwd"],
        )
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "ask"
        assert m.pattern == "/etc/*"

    def test_no_rules_match(self, tmp_path):
        cfg = Config(
            rules=[Rule("allow", "git *")],
            redirect_rules=[Rule("allow", "/tmp/*")],
        )
        c = SimpleCommand(words=["echo", "hello"], redirects=["/var/log/out"])
        m = match_command(c, cfg, tmp_path)
        assert m is None

    def test_command_allow_redirect_deny(self, tmp_path):
        """Redirect deny should override command allow."""
        cfg = Config(
            rules=[Rule("allow", "echo *")],
            redirect_rules=[Rule("deny", "/etc/*")],
        )
        c = SimpleCommand(words=["echo", "data"], redirects=["/etc/passwd"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "deny"
        assert m.pattern == "/etc/*"

    def test_command_deny_redirect_allow(self, tmp_path):
        """Command deny should override redirect allow."""
        cfg = Config(
            rules=[Rule("deny", "rm *")],
            redirect_rules=[Rule("allow", "/tmp/*")],
        )
        c = SimpleCommand(words=["rm", "-rf", "/"], redirects=["/tmp/log.txt"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "deny"
        assert m.pattern == "rm *"

    def test_command_ask_redirect_deny(self, tmp_path):
        """Deny should override ask (deny > ask > allow)."""
        cfg = Config(
            rules=[Rule("ask", "echo *")],
            redirect_rules=[Rule("deny", "/etc/*")],
        )
        c = SimpleCommand(words=["echo", "data"], redirects=["/etc/passwd"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "deny"

    def test_multiple_redirects_one_denies(self, tmp_path):
        """If any redirect triggers deny, result is deny."""
        cfg = Config(
            rules=[Rule("allow", "cat *")],
            redirect_rules=[
                Rule("allow", "/tmp/*"),
                Rule("deny", "/etc/*"),
            ],
        )
        c = SimpleCommand(
            words=["cat", "file"],
            redirects=["/tmp/safe.txt", "/etc/passwd"],
        )
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "deny"
        assert m.pattern == "/etc/*"

    def test_redirect_path_normalization(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("ask", f"{tmp_path}/*")])
        c = SimpleCommand(words=["echo", "x"], redirects=["./out.txt"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "ask"


class TestMatchRedirect:
    """Test redirect target matching against config rules."""

    def test_basic_glob_match(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        assert match_redirect("/tmp/foo", cfg, tmp_path) is not None
        assert match_redirect("/tmp/bar.txt", cfg, tmp_path) is not None
        assert match_redirect("/var/foo", cfg, tmp_path) is None

    def test_no_match_returns_none(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        assert match_redirect("/var/log/test", cfg, tmp_path) is None

    def test_empty_rules_returns_none(self, tmp_path):
        cfg = Config(redirect_rules=[])
        assert match_redirect("/tmp/foo", cfg, tmp_path) is None

    def test_doublestar_matches_any_depth(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/**")])
        assert match_redirect("/tmp/foo", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/b/c", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/b/c/file.txt", cfg, tmp_path) is not None

    def test_doublestar_with_suffix(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/**/*.txt")])
        assert match_redirect("/tmp/file.txt", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/b/file.txt", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/b/file.log", cfg, tmp_path) is None

    def test_doublestar_at_start(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "**/foo")])
        assert match_redirect("/foo", cfg, tmp_path) is not None
        assert match_redirect("/a/foo", cfg, tmp_path) is not None
        assert match_redirect("/a/b/c/foo", cfg, tmp_path) is not None
        assert match_redirect("/a/b/c/bar", cfg, tmp_path) is None

    def test_doublestar_in_middle(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/**/file.txt")])
        assert match_redirect("/tmp/file.txt", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/file.txt", cfg, tmp_path) is not None
        assert match_redirect("/tmp/a/b/c/file.txt", cfg, tmp_path) is not None

    def test_doublestar_alone_matches_everything(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "**")])
        assert match_redirect("/any/path", cfg, tmp_path) is not None
        assert match_redirect("foo", cfg, tmp_path) is not None

    def test_trailing_slash_normalized(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/foo")])
        assert match_redirect("/tmp/foo/", cfg, tmp_path) is not None
        assert match_redirect("/tmp/foo", cfg, tmp_path) is not None

    def test_tilde_expansion(self, tmp_path):
        home = str(Path.home())
        cfg = Config(redirect_rules=[Rule("allow", f"{home}/logs/*")])
        assert match_redirect("~/logs/app.log", cfg, tmp_path) is not None

    def test_relative_path_resolution(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", f"{tmp_path}/output.txt")])
        assert match_redirect("./output.txt", cfg, tmp_path) is not None
        assert match_redirect("output.txt", cfg, tmp_path) is not None

    def test_character_class(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/[a-z]*")])
        assert match_redirect("/tmp/foo", cfg, tmp_path) is not None
        assert match_redirect("/tmp/123", cfg, tmp_path) is None

    def test_last_match_wins(self, tmp_path):
        cfg = Config(
            redirect_rules=[
                Rule("ask", "**"),
                Rule("allow", "/tmp/**"),
            ]
        )
        m = match_redirect("/tmp/foo", cfg, tmp_path)
        assert m.decision == "allow"
        m2 = match_redirect("/var/foo", cfg, tmp_path)
        assert m2.decision == "ask"

    def test_match_object_fields(self, tmp_path):
        cfg = Config(
            redirect_rules=[
                Rule(
                    "ask",
                    "**/.env*",
                    message="secrets!",
                    source="/config",
                    scope="project",
                )
            ]
        )
        m = match_redirect("/app/.env", cfg, tmp_path)
        assert m.decision == "ask"
        assert m.pattern == "**/.env*"
        assert m.message == "secrets!"
        assert m.source == "/config"
        assert m.scope == "project"

    def test_hidden_files_pattern(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("ask", "**/.*")])
        assert match_redirect("/home/user/.bashrc", cfg, tmp_path) is not None
        assert match_redirect("/app/.env", cfg, tmp_path) is not None
        assert match_redirect("/app/config", cfg, tmp_path) is None

    def test_env_file_pattern(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("ask", "**/.env*")])
        assert match_redirect("/app/.env", cfg, tmp_path) is not None
        assert match_redirect("/app/.env.local", cfg, tmp_path) is not None
        assert match_redirect("/app/.envrc", cfg, tmp_path) is not None

    def test_security_etc_passwd(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("ask", "/etc/passwd")])
        assert match_redirect("/etc/passwd", cfg, tmp_path) is not None
        assert match_redirect("/etc/shadow", cfg, tmp_path) is None

    def test_deny_redirect_basic(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("deny", "/etc/**")])
        m = match_redirect("/etc/passwd", cfg, tmp_path)
        assert m is not None
        assert m.decision == "deny"

    def test_deny_redirect_with_message(self, tmp_path):
        cfg = Config(redirect_rules=[Rule("deny", "/etc/**", message="system files")])
        m = match_redirect("/etc/passwd", cfg, tmp_path)
        assert m.decision == "deny"
        assert m.message == "system files"

    def test_deny_redirect_last_match_wins(self, tmp_path):
        cfg = Config(
            redirect_rules=[
                Rule("deny", "/etc/**"),
                Rule("allow", "/etc/hosts"),
            ]
        )
        m = match_redirect("/etc/hosts", cfg, tmp_path)
        assert m.decision == "allow"  # allow is last match
        m2 = match_redirect("/etc/passwd", cfg, tmp_path)
        assert m2.decision == "deny"  # deny is last match


class TestMatchEdgeCases:
    """Edge cases from Git's wildmatch tests."""

    def test_trailing_star_matches_bare_command(self, tmp_path):
        """Pattern 'python *' should match both 'python foo' AND bare 'python'.

        This is the errata case: users expect 'python *' to match any python
        invocation, but the space before * is literal, so bare 'python' fails.
        """
        cfg = Config(rules=[Rule("deny", "python *", message="use uv run python")])
        # This works - has arguments
        assert match_command(cmd("python foo"), cfg, tmp_path) is not None
        assert match_command(cmd("python -c 'print(1)'"), cfg, tmp_path) is not None
        # This should also work but currently fails - bare command
        assert match_command(cmd("python"), cfg, tmp_path) is not None

    def test_trailing_question_star_requires_arguments(self, tmp_path):
        """Pattern 'python ?*' requires at least one argument character.

        Use ?* instead of * when you want to match only commands WITH args,
        not bare commands. This is the escape hatch for the old behavior.
        """
        cfg = Config(rules=[Rule("allow", "python ?*")])
        # Matches - has arguments
        assert match_command(cmd("python foo"), cfg, tmp_path) is not None
        assert match_command(cmd("python -c 'print(1)'"), cfg, tmp_path) is not None
        # Does NOT match - bare command
        assert match_command(cmd("python"), cfg, tmp_path) is None

    def test_empty_pattern_empty_text(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "")])
        # Empty pattern should only match empty command
        assert match_command(cmd(""), cfg, tmp_path) is not None
        assert match_command(cmd("foo"), cfg, tmp_path) is None

    def test_escaped_star_in_pattern(self, tmp_path):
        # fnmatch uses [] for escaping, not backslash
        cfg = Config(rules=[Rule("allow", "foo[*]bar")])
        assert match_command(cmd("foo*bar"), cfg, tmp_path) is not None
        assert match_command(cmd("fooXbar"), cfg, tmp_path) is None

    def test_bracket_literal(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "[[]ab]")])
        assert match_command(cmd("[ab]"), cfg, tmp_path) is not None

    def test_range_in_character_class(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "t[a-g]n")])
        assert match_command(cmd("tan"), cfg, tmp_path) is not None
        assert match_command(cmd("ten"), cfg, tmp_path) is not None
        assert match_command(cmd("tin"), cfg, tmp_path) is None  # i > g

    def test_negated_range(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "t[!a-g]n")])
        assert match_command(cmd("ton"), cfg, tmp_path) is not None  # o > g
        assert match_command(cmd("tan"), cfg, tmp_path) is None

    def test_close_bracket_in_class(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "a[]]b")])
        assert match_command(cmd("a]b"), cfg, tmp_path) is not None

    def test_complex_pattern(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "*ob*a*r*")])
        assert match_command(cmd("foobar"), cfg, tmp_path) is not None
        assert match_command(cmd("foobazbar"), cfg, tmp_path) is not None

    def test_trailing_star_matches_rest(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git *")])
        assert (
            match_command(cmd("git status --short --branch"), cfg, tmp_path) is not None
        )

    def test_performance_not_exponential(self, tmp_path):
        """Ensure matching doesn't exhibit exponential behavior."""
        import time

        cfg = Config(rules=[Rule("allow", "*a*a*a*a*a*a*a*a")])
        start = time.time()
        # This should complete quickly, not hang
        match_command(cmd("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaab"), cfg, tmp_path)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Matching took too long: {elapsed}s"


class TestPatternNormalization:
    """Test that patterns are normalized against cwd for matching."""

    def test_relative_pattern_matches_absolute_command(self, tmp_path):
        """Pattern 'bin/*' should match 'node /cwd/bin/script' when cwd is /cwd."""
        cfg = Config(rules=[Rule("allow", "node bin/*")])
        # Command with absolute path that's inside cwd/bin
        assert (
            match_command(cmd(f"node {tmp_path}/bin/script.js"), cfg, tmp_path)
            is not None
        )

    def test_relative_pattern_matches_relative_command(self, tmp_path):
        """Pattern 'bin/*' should match 'node bin/script'."""
        cfg = Config(rules=[Rule("allow", "node bin/*")])
        assert match_command(cmd("node bin/script.js"), cfg, tmp_path) is not None

    def test_relative_pattern_no_match_different_cwd(self, tmp_path):
        """Pattern 'bin/*' should NOT match '/other/path/bin/script'."""
        cfg = Config(rules=[Rule("allow", "node bin/*")])
        assert (
            match_command(cmd("node /other/path/bin/script.js"), cfg, tmp_path) is None
        )

    def test_absolute_pattern_still_works(self, tmp_path):
        """Absolute patterns should work as before."""
        cfg = Config(rules=[Rule("allow", f"node {tmp_path}/bin/*")])
        assert (
            match_command(cmd(f"node {tmp_path}/bin/script.js"), cfg, tmp_path)
            is not None
        )
        assert match_command(cmd("node bin/script.js"), cfg, tmp_path) is not None

    def test_dotslash_pattern_normalized(self, tmp_path):
        """Pattern './bin/*' should match same as 'bin/*'."""
        cfg = Config(rules=[Rule("allow", "node ./bin/*")])
        assert (
            match_command(cmd(f"node {tmp_path}/bin/script.js"), cfg, tmp_path)
            is not None
        )
        assert match_command(cmd("node bin/script.js"), cfg, tmp_path) is not None

    def test_pattern_normalization_with_glob(self, tmp_path):
        """Wildcards in pattern should still work after normalization."""
        cfg = Config(rules=[Rule("allow", "node scripts/*.js")])
        assert (
            match_command(cmd(f"node {tmp_path}/scripts/test.js"), cfg, tmp_path)
            is not None
        )
        assert (
            match_command(cmd(f"node {tmp_path}/scripts/build.js"), cfg, tmp_path)
            is not None
        )
        assert (
            match_command(cmd(f"node {tmp_path}/scripts/test.py"), cfg, tmp_path)
            is None
        )

    def test_redirect_pattern_normalization(self, tmp_path):
        """Redirect patterns should also be normalized against cwd."""
        cfg = Config(redirect_rules=[Rule("allow", "output/*")])
        assert match_redirect(f"{tmp_path}/output/file.txt", cfg, tmp_path) is not None
        assert match_redirect("output/file.txt", cfg, tmp_path) is not None
        assert match_redirect("/other/output/file.txt", cfg, tmp_path) is None

    def test_redirect_pattern_normalization_with_globstar(self, tmp_path):
        """Redirect patterns with ** should also be normalized against cwd."""
        cfg = Config(redirect_rules=[Rule("allow", "src/**")])
        assert match_redirect("src/foo.go", cfg, tmp_path) is not None
        assert match_redirect(f"{tmp_path}/src/foo.go", cfg, tmp_path) is not None
        assert match_redirect("/other/src/foo.go", cfg, tmp_path) is None

    def test_nested_relative_path(self, tmp_path):
        """Pattern 'src/lib/*' should match nested paths."""
        cfg = Config(rules=[Rule("allow", "node src/lib/*")])
        assert (
            match_command(cmd(f"node {tmp_path}/src/lib/util.js"), cfg, tmp_path)
            is not None
        )

    def test_parent_dir_in_command(self, tmp_path):
        """Command '../script.js' should resolve and match pattern."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        cfg = Config(rules=[Rule("allow", f"node {tmp_path}/script.js")])
        assert match_command(cmd("node ../script.js"), cfg, subdir) is not None

    def test_mixed_absolute_and_relative_tokens(self, tmp_path):
        """Command with some absolute, some relative tokens."""
        cfg = Config(rules=[Rule("allow", f"cp {tmp_path}/src/* {tmp_path}/dest/*")])
        assert (
            match_command(cmd(f"cp {tmp_path}/src/a.txt dest/b.txt"), cfg, tmp_path)
            is not None
        )


class TestPathExpansionBugs:
    """Tests for path expansion edge cases (bugs)."""

    def test_bare_tilde_expanded_in_command(self, tmp_path):
        """Bare ~ should expand to home directory."""
        home = str(Path.home())
        cfg = Config(rules=[Rule("allow", f"cd {home}")])
        # Bare ~ should expand to home and match
        assert match_command(cmd("cd ~"), cfg, tmp_path) is not None

    def test_bare_tilde_expanded_in_pattern(self, tmp_path):
        """Pattern with bare ~ should expand to home directory."""
        cfg = Config(rules=[Rule("allow", "cd ~")])
        home = str(Path.home())
        # Command with absolute home path should match pattern with ~
        assert match_command(cmd(f"cd {home}"), cfg, tmp_path) is not None

    def test_tilde_user_not_mangled(self, tmp_path):
        """~user/path should not be turned into a relative path under cwd."""
        cfg = Config(rules=[Rule("allow", "cat ~bob/file")])
        # The pattern should stay as ~bob/file, not become /cwd/~bob/file
        # So a command with literal ~bob/file should match
        assert match_command(cmd("cat ~bob/file"), cfg, tmp_path) is not None
        # And a command under cwd should NOT match (proving it wasn't mangled)
        assert match_command(cmd(f"cat {tmp_path}/~bob/file"), cfg, tmp_path) is None

    def test_shell_variable_not_mangled(self, tmp_path):
        """$VAR/path should not be turned into a relative path under cwd."""
        cfg = Config(rules=[Rule("allow", "cat $HOME/.bashrc")])
        # The pattern should stay as $HOME/.bashrc, not become /cwd/$HOME/.bashrc
        # So a command with literal $HOME/.bashrc should match
        assert match_command(cmd("cat $HOME/.bashrc"), cfg, tmp_path) is not None
        # And a command under cwd should NOT match (proving it wasn't mangled)
        assert (
            match_command(cmd(f"cat {tmp_path}/$HOME/.bashrc"), cfg, tmp_path) is None
        )

    def test_tilde_expansion_consistency(self, tmp_path):
        """Tilde expands consistently in both settings and rule patterns."""
        cfg = parse_config("""
set log ~/audit.log
allow cd ~
""")
        home = Path.home()
        # Settings expand tilde correctly
        assert cfg.log == home / "audit.log"
        # Rule patterns also expand tilde consistently
        assert cfg.rules[0].pattern == f"cd {home}"

    def test_url_not_mangled(self, tmp_path):
        """URLs should not be turned into paths under cwd."""
        cfg = Config(rules=[Rule("allow", "curl https://example.com/foo")])
        # The pattern should stay as-is, not become curl /cwd/https:/example.com/foo
        # So a command with the literal URL should match
        assert (
            match_command(cmd("curl https://example.com/foo"), cfg, tmp_path)
            is not None
        )
        # And a mangled path should NOT match
        assert (
            match_command(cmd(f"curl {tmp_path}/https:/example.com/foo"), cfg, tmp_path)
            is None
        )

    def test_single_dot_resolved_to_cwd(self, tmp_path):
        """Single . should resolve to cwd, like .. resolves to parent."""
        cfg = Config(rules=[Rule("allow", f"ls {tmp_path}")])
        # . means current directory, should resolve to cwd and match
        assert match_command(cmd("ls ."), cfg, tmp_path) is not None

    def test_single_dot_in_pattern(self, tmp_path):
        """Pattern with . should resolve to cwd."""
        cfg = Config(rules=[Rule("allow", "ls .")])
        # Command with absolute cwd path should match pattern with .
        assert match_command(cmd(f"ls {tmp_path}"), cfg, tmp_path) is not None


class TestParseConfigAfterRules:
    """Test parsing of after rules for PostToolUse."""

    def test_after_with_message(self):
        cfg = parse_config('after git push * "Check deployment status"')
        assert len(cfg.after_rules) == 1
        assert cfg.after_rules[0].decision == "after"
        assert cfg.after_rules[0].pattern == "git push *"
        assert cfg.after_rules[0].message == "Check deployment status"

    def test_after_pattern_only(self):
        cfg = parse_config("after npm *")
        assert len(cfg.after_rules) == 1
        assert cfg.after_rules[0].pattern == "npm *"
        assert cfg.after_rules[0].message is None

    def test_after_empty_message(self):
        cfg = parse_config('after npm install * ""')
        assert len(cfg.after_rules) == 1
        assert cfg.after_rules[0].pattern == "npm install *"
        assert cfg.after_rules[0].message == ""

    def test_after_requires_pattern(self):
        cfg = parse_config("after")
        assert cfg.after_rules == []

    def test_after_mixed_with_other_rules(self):
        cfg = parse_config("""
allow git *
after git push * "Check CI"
deny rm -rf /*
after make test * "Review failures"
""")
        assert len(cfg.rules) == 2
        assert len(cfg.after_rules) == 2
        assert cfg.after_rules[0].pattern == "git push *"
        assert cfg.after_rules[1].pattern == "make test *"


class TestMergeConfigsAfterRules:
    """Test after rules merging."""

    def test_after_rules_concatenate(self):
        base = Config(after_rules=[Rule("after", "git *", message="msg1")])
        overlay = Config(after_rules=[Rule("after", "npm *", message="msg2")])
        merged = _merge_configs(base, overlay)
        assert len(merged.after_rules) == 2
        assert merged.after_rules[0].pattern == "git *"
        assert merged.after_rules[1].pattern == "npm *"


class TestMatchAfter:
    """Test after rule matching for PostToolUse feedback."""

    def test_basic_match(self, tmp_path):
        cfg = Config(after_rules=[Rule("after", "git push *", message="Done pushing")])
        result = match_after(["git", "push", "origin", "main"], cfg, tmp_path)
        assert result == "Done pushing"

    def test_no_match(self, tmp_path):
        cfg = Config(after_rules=[Rule("after", "git push *", message="Done pushing")])
        result = match_after(["git", "status"], cfg, tmp_path)
        assert result is None

    def test_last_match_wins(self, tmp_path):
        cfg = Config(
            after_rules=[
                Rule("after", "npm *", message="Check npm output"),
                Rule("after", "npm install *", message="Dependencies installed"),
            ]
        )
        result = match_after(["npm", "install", "lodash"], cfg, tmp_path)
        assert result == "Dependencies installed"

    def test_silent_override(self, tmp_path):
        """Empty message should override earlier match (silent)."""
        cfg = Config(
            after_rules=[
                Rule("after", "npm *", message="Check npm output"),
                Rule("after", "npm install *", message=""),
            ]
        )
        result = match_after(["npm", "install", "lodash"], cfg, tmp_path)
        assert result == ""

    def test_pattern_only_is_silent(self, tmp_path):
        """Pattern without message (message=None) should return empty string."""
        cfg = Config(after_rules=[Rule("after", "make *")])
        result = match_after(["make", "build"], cfg, tmp_path)
        assert result == ""

    def test_trailing_star_matches_bare_command(self, tmp_path):
        cfg = Config(after_rules=[Rule("after", "python *", message="Python ran")])
        result = match_after(["python"], cfg, tmp_path)
        assert result == "Python ran"

    def test_path_normalization(self, tmp_path):
        home = str(Path.home())
        cfg = Config(after_rules=[Rule("after", f"{home}/bin/*", message="custom bin")])
        result = match_after(["~/bin/script"], cfg, tmp_path)
        assert result == "custom bin"


class TestParseConfigMcpRules:
    """Test parsing of MCP tool rules."""

    def test_allow_mcp(self):
        cfg = parse_config("allow-mcp mcp__github__*")
        assert len(cfg.mcp_rules) == 1
        assert cfg.mcp_rules[0].decision == "allow"
        assert cfg.mcp_rules[0].pattern == "mcp__github__*"

    def test_ask_mcp_with_message(self):
        cfg = parse_config('ask-mcp mcp__filesystem__write_* "File writes need review"')
        assert len(cfg.mcp_rules) == 1
        assert cfg.mcp_rules[0].decision == "ask"
        assert cfg.mcp_rules[0].pattern == "mcp__filesystem__write_*"
        assert cfg.mcp_rules[0].message == "File writes need review"

    def test_deny_mcp_with_message(self):
        cfg = parse_config('deny-mcp mcp__*__delete_* "No deletions"')
        assert len(cfg.mcp_rules) == 1
        assert cfg.mcp_rules[0].decision == "deny"
        assert cfg.mcp_rules[0].pattern == "mcp__*__delete_*"
        assert cfg.mcp_rules[0].message == "No deletions"

    def test_allow_mcp_no_pattern_skipped(self):
        cfg = parse_config("allow-mcp")
        assert cfg.mcp_rules == []

    def test_ask_mcp_no_pattern_skipped(self):
        cfg = parse_config("ask-mcp")
        assert cfg.mcp_rules == []

    def test_deny_mcp_no_pattern_skipped(self):
        cfg = parse_config("deny-mcp")
        assert cfg.mcp_rules == []

    def test_mcp_rules_mixed_with_other_rules(self):
        cfg = parse_config("""
allow git *
allow-mcp mcp__github__get_*
deny rm -rf /*
ask-mcp mcp__github__create_* "Creating resources"
deny-mcp mcp__*__delete_* "No deletions"
""")
        assert len(cfg.rules) == 2
        assert len(cfg.mcp_rules) == 3
        assert cfg.mcp_rules[0].decision == "allow"
        assert cfg.mcp_rules[0].pattern == "mcp__github__get_*"
        assert cfg.mcp_rules[1].decision == "ask"
        assert cfg.mcp_rules[1].pattern == "mcp__github__create_*"
        assert cfg.mcp_rules[2].decision == "deny"
        assert cfg.mcp_rules[2].pattern == "mcp__*__delete_*"


class TestParseConfigAfterMcpRules:
    """Test parsing of after-mcp rules for PostToolUse."""

    def test_after_mcp_with_message(self):
        cfg = parse_config('after-mcp mcp__github__create_* "PR created"')
        assert len(cfg.after_mcp_rules) == 1
        assert cfg.after_mcp_rules[0].decision == "after"
        assert cfg.after_mcp_rules[0].pattern == "mcp__github__create_*"
        assert cfg.after_mcp_rules[0].message == "PR created"

    def test_after_mcp_pattern_only(self):
        cfg = parse_config("after-mcp mcp__github__*")
        assert len(cfg.after_mcp_rules) == 1
        assert cfg.after_mcp_rules[0].pattern == "mcp__github__*"
        assert cfg.after_mcp_rules[0].message is None

    def test_after_mcp_no_pattern_skipped(self):
        cfg = parse_config("after-mcp")
        assert cfg.after_mcp_rules == []


class TestMergeConfigsMcpRules:
    """Test MCP rules merging."""

    def test_mcp_rules_concatenate(self):
        base = Config(mcp_rules=[Rule("allow", "mcp__github__*")])
        overlay = Config(mcp_rules=[Rule("ask", "mcp__github__create_*")])
        merged = _merge_configs(base, overlay)
        assert len(merged.mcp_rules) == 2
        assert merged.mcp_rules[0].pattern == "mcp__github__*"
        assert merged.mcp_rules[1].pattern == "mcp__github__create_*"

    def test_after_mcp_rules_concatenate(self):
        base = Config(after_mcp_rules=[Rule("after", "mcp__github__*", message="msg1")])
        overlay = Config(after_mcp_rules=[Rule("after", "mcp__fs__*", message="msg2")])
        merged = _merge_configs(base, overlay)
        assert len(merged.after_mcp_rules) == 2


class TestTagRulesMcp:
    """Test origin tagging for MCP rules."""

    def test_tags_mcp_rules_with_source_and_scope(self):
        config = Config(
            mcp_rules=[Rule("allow", "mcp__github__*")],
            after_mcp_rules=[Rule("after", "mcp__fs__*")],
        )
        tagged = _tag_rules(config, "/path/to/config", SCOPE_USER)
        assert tagged.mcp_rules[0].source == "/path/to/config"
        assert tagged.mcp_rules[0].scope == SCOPE_USER
        assert tagged.after_mcp_rules[0].source == "/path/to/config"
        assert tagged.after_mcp_rules[0].scope == SCOPE_USER


class TestMatchMcp:
    """Test MCP tool matching against config rules."""

    def test_basic_glob_match(self):
        cfg = Config(mcp_rules=[Rule("allow", "mcp__github__*")])
        m = match_mcp("mcp__github__get_issue", cfg)
        assert m is not None
        assert m.decision == "allow"
        assert m.pattern == "mcp__github__*"

    def test_no_match_returns_none(self):
        cfg = Config(mcp_rules=[Rule("allow", "mcp__github__*")])
        m = match_mcp("mcp__filesystem__read_file", cfg)
        assert m is None

    def test_empty_rules_returns_none(self):
        cfg = Config(mcp_rules=[])
        m = match_mcp("mcp__github__get_issue", cfg)
        assert m is None

    def test_last_match_wins(self):
        cfg = Config(
            mcp_rules=[
                Rule("allow", "mcp__github__*"),
                Rule("ask", "mcp__github__create_*", message="Creating resources"),
            ]
        )
        # First rule matches but second is more specific and wins
        m = match_mcp("mcp__github__create_issue", cfg)
        assert m is not None
        assert m.decision == "ask"
        assert m.message == "Creating resources"

    def test_deny_with_message(self):
        cfg = Config(mcp_rules=[Rule("deny", "*__delete_*", message="No deletions")])
        m = match_mcp("mcp__filesystem__delete_file", cfg)
        assert m is not None
        assert m.decision == "deny"
        assert m.message == "No deletions"

    def test_wildcard_in_middle(self):
        cfg = Config(mcp_rules=[Rule("deny", "mcp__*__delete_*")])
        m = match_mcp("mcp__filesystem__delete_file", cfg)
        assert m is not None
        assert m.decision == "deny"

    def test_match_object_fields(self):
        cfg = Config(
            mcp_rules=[
                Rule(
                    "ask",
                    "mcp__github__*",
                    message="GitHub operation",
                    source="/path/to/config",
                    scope="user",
                )
            ]
        )
        m = match_mcp("mcp__github__get_issue", cfg)
        assert m.decision == "ask"
        assert m.pattern == "mcp__github__*"
        assert m.message == "GitHub operation"
        assert m.source == "/path/to/config"
        assert m.scope == "user"

    def test_complex_pattern_priority(self):
        """Test that the most specific matching rule (last) wins."""
        cfg = Config(
            mcp_rules=[
                Rule("allow", "*"),  # allow everything
                Rule("ask", "mcp__*"),  # ask for all MCP tools
                Rule("allow", "mcp__github__get_*"),  # allow GitHub reads
                Rule("deny", "mcp__github__delete_*"),  # deny GitHub deletes
            ]
        )
        # github get - should be allowed (third rule)
        m = match_mcp("mcp__github__get_issue", cfg)
        assert m.decision == "allow"

        # github delete - should be denied (fourth rule)
        m = match_mcp("mcp__github__delete_repo", cfg)
        assert m.decision == "deny"

        # github create - should ask (second rule)
        m = match_mcp("mcp__github__create_issue", cfg)
        assert m.decision == "ask"


class TestMatchAfterMcp:
    """Test after-mcp rule matching for PostToolUse feedback."""

    def test_basic_match(self):
        cfg = Config(
            after_mcp_rules=[
                Rule("after", "mcp__github__create_*", message="PR created")
            ]
        )
        result = match_after_mcp("mcp__github__create_pr", cfg)
        assert result == "PR created"

    def test_no_match(self):
        cfg = Config(
            after_mcp_rules=[Rule("after", "mcp__github__create_*", message="Created")]
        )
        result = match_after_mcp("mcp__github__get_issue", cfg)
        assert result is None

    def test_last_match_wins(self):
        cfg = Config(
            after_mcp_rules=[
                Rule("after", "mcp__github__*", message="GitHub operation"),
                Rule("after", "mcp__github__create_*", message="Resource created"),
            ]
        )
        result = match_after_mcp("mcp__github__create_issue", cfg)
        assert result == "Resource created"

    def test_pattern_only_is_silent(self):
        cfg = Config(after_mcp_rules=[Rule("after", "mcp__github__*")])
        result = match_after_mcp("mcp__github__get_issue", cfg)
        assert result == ""

    def test_empty_message_is_silent(self):
        cfg = Config(after_mcp_rules=[Rule("after", "mcp__github__*", message="")])
        result = match_after_mcp("mcp__github__get_issue", cfg)
        assert result == ""


class TestMcpEndToEnd:
    """End-to-end tests simulating actual hook JSON input/output."""

    def test_mcp_tool_routed_correctly(self, tmp_path, monkeypatch):
        """Test that main() routes MCP tools through MCP rules, not shell rules."""
        import io
        import json
        import sys

        # Create config with MCP rule
        config_file = tmp_path / ".dippy"
        config_file.write_text("allow-mcp mcp__github__get_*\n")

        # Simulate Claude Code hook input for MCP tool
        hook_input = {
            "tool_name": "mcp__github__get_issue",
            "tool_input": {"owner": "foo", "repo": "bar", "issue_number": 1},
            "hook_event_name": "PreToolUse",
        }

        # Capture stdout and mock stdin
        captured_output = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(sys, "stdout", captured_output)
        monkeypatch.chdir(tmp_path)

        # Reload and run
        import importlib

        import dippy.dippy

        importlib.reload(dippy.dippy)
        dippy.dippy.main()

        # Verify output
        output = json.loads(captured_output.getvalue())
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_mcp_tool_no_match_defers(self, tmp_path, monkeypatch):
        """Test that MCP tool with no matching rules returns empty (defer)."""
        import io
        import json
        import sys

        import dippy.core.config

        # Isolate from user's ~/.dippy/config
        monkeypatch.setattr(
            dippy.core.config, "USER_CONFIG", tmp_path / "no-such-config"
        )

        # Config with rule that won't match
        config_file = tmp_path / ".dippy"
        config_file.write_text("allow-mcp mcp__filesystem__*\n")

        hook_input = {
            "tool_name": "mcp__github__get_issue",
            "tool_input": {},
            "hook_event_name": "PreToolUse",
        }

        captured_output = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(sys, "stdout", captured_output)
        monkeypatch.chdir(tmp_path)

        import importlib

        import dippy.dippy

        importlib.reload(dippy.dippy)
        dippy.dippy.main()

        output = json.loads(captured_output.getvalue())
        assert output == {}  # Empty = defer to Claude's default

    def test_mcp_tool_deny_blocks(self, tmp_path, monkeypatch):
        """Test that deny-mcp rule actually blocks the tool."""
        import io
        import json
        import sys

        config_file = tmp_path / ".dippy"
        config_file.write_text('deny-mcp mcp__*__delete_* "No deletions allowed"\n')

        hook_input = {
            "tool_name": "mcp__github__delete_repo",
            "tool_input": {"owner": "foo", "repo": "bar"},
            "hook_event_name": "PreToolUse",
        }

        captured_output = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(sys, "stdout", captured_output)
        monkeypatch.chdir(tmp_path)

        import importlib

        import dippy.dippy

        importlib.reload(dippy.dippy)
        dippy.dippy.main()

        output = json.loads(captured_output.getvalue())
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
        assert (
            "No deletions" in output["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_bash_tool_not_affected_by_mcp_rules(self, tmp_path, monkeypatch):
        """Test that Bash commands still work and aren't affected by MCP rules."""
        import io
        import json
        import sys

        config_file = tmp_path / ".dippy"
        config_file.write_text("deny-mcp mcp__*\n")  # Deny all MCP

        # Bash tool, not MCP
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "hook_event_name": "PreToolUse",
        }

        captured_output = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(sys, "stdout", captured_output)
        monkeypatch.chdir(tmp_path)

        import importlib

        import dippy.dippy

        importlib.reload(dippy.dippy)
        dippy.dippy.main()

        output = json.loads(captured_output.getvalue())
        # ls is safe, should be approved (not affected by MCP deny rule)
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"


class TestAlias:
    """Test alias directive for mapping wrapper scripts to canonical names."""

    def test_alias_tilde_path(self, tmp_path):
        """alias ~/bin/gh gh + allow gh matches ~/bin/gh pr list."""
        home = str(Path.home())
        cfg = parse_config(f"alias ~/bin/gh gh\nallow gh")
        assert cfg.aliases == {f"{home}/bin/gh": "gh"}
        c = SimpleCommand(words=["~/bin/gh", "pr", "list"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_alias_relative_path(self, tmp_path):
        """alias ./bin/gh gh works."""
        cfg = parse_config("alias ./bin/gh gh\nallow gh")
        # Relative paths are stored as-is at parse time, resolved at match time
        assert cfg.aliases == {"./bin/gh": "gh"}
        c = SimpleCommand(words=["./bin/gh", "pr", "list"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_alias_bare_command(self, tmp_path):
        """alias mygit git + allow git matches mygit status."""
        cfg = parse_config("alias mygit git\nallow git")
        assert cfg.aliases == {"mygit": "git"}
        c = SimpleCommand(words=["mygit", "status"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_alias_preserves_args(self, tmp_path):
        """args passed through after alias resolution."""
        cfg = parse_config("alias mygit git\nallow git commit *")
        c = SimpleCommand(words=["mygit", "commit", "-m", "message"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"

    def test_alias_with_rules(self, tmp_path):
        """alias + allow/deny rules work together."""
        cfg = parse_config(
            "alias mygit git\nallow git status\ndeny git push"
        )
        # Allow status
        c1 = SimpleCommand(words=["mygit", "status"])
        m1 = match_command(c1, cfg, tmp_path)
        assert m1 is not None
        assert m1.decision == "allow"
        # Deny push
        c2 = SimpleCommand(words=["mygit", "push"])
        m2 = match_command(c2, cfg, tmp_path)
        assert m2 is not None
        assert m2.decision == "deny"

    def test_alias_missing_target(self, caplog):
        """alias foo warns and skips."""
        import logging

        with caplog.at_level(logging.WARNING):
            cfg = parse_config("alias foo")
        assert cfg.aliases == {}
        assert "requires exactly two arguments" in caplog.text

    def test_alias_too_many_args(self, caplog):
        """alias foo bar baz warns and skips."""
        import logging

        with caplog.at_level(logging.WARNING):
            cfg = parse_config("alias foo bar baz")
        assert cfg.aliases == {}
        assert "requires exactly two arguments" in caplog.text

    def test_alias_redefined(self, caplog):
        """second alias foo x overwrites first, logs warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            cfg = parse_config("alias foo bar\nalias foo baz")
        assert cfg.aliases == {"foo": "baz"}
        assert "redefined" in caplog.text

    def test_alias_merge(self):
        """later config overrides earlier alias."""
        base = Config(aliases={"foo": "bar", "baz": "qux"})
        overlay = Config(aliases={"foo": "override"})
        merged = _merge_configs(base, overlay)
        assert merged.aliases == {"foo": "override", "baz": "qux"}

    def test_alias_with_after_rules(self, tmp_path):
        """alias works with after rules too."""
        cfg = parse_config('alias mygit git\nafter git push * "Pushed!"')
        result = match_after(["mygit", "push", "origin", "main"], cfg, tmp_path)
        assert result == "Pushed!"

    def test_alias_no_match_without_rule(self, tmp_path):
        """alias alone doesn't create implicit allow."""
        cfg = parse_config("alias mygit git")
        c = SimpleCommand(words=["mygit", "status"])
        m = match_command(c, cfg, tmp_path)
        assert m is None

    def test_alias_absolute_path(self, tmp_path):
        """alias /usr/local/bin/gh gh works."""
        cfg = parse_config("alias /usr/local/bin/gh gh\nallow gh")
        assert cfg.aliases == {"/usr/local/bin/gh": "gh"}
        c = SimpleCommand(words=["/usr/local/bin/gh", "pr", "list"])
        m = match_command(c, cfg, tmp_path)
        assert m is not None
        assert m.decision == "allow"
