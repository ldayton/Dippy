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
    SimpleCommand,
    _find_project_config,
    _merge_configs,
    _tag_rules,
    configure_logging,
    load_config,
    log_decision,
    match_command,
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


class TestParseConfig:
    """Test config parsing - focus on security-relevant edge cases."""

    def test_unknown_directive_fails(self):
        with pytest.raises(ValueError, match="unknown directive 'yolo'"):
            parse_config("yolo rm -rf /")

    def test_unknown_setting_fails(self):
        with pytest.raises(ValueError, match="unknown setting 'yolo'"):
            parse_config("set yolo")

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

    def test_empty_pattern_before_message_fails(self):
        with pytest.raises(ValueError, match="pattern required"):
            parse_config('ask "just a message"')

    def test_settings_strict_validation(self):
        # Boolean with value = error
        with pytest.raises(ValueError, match="takes no value"):
            parse_config("set verbose true")

        # Integer without value = error
        with pytest.raises(ValueError, match="requires a number"):
            parse_config("set suggest-after")

        # Integer with non-number = error
        with pytest.raises(ValueError, match="requires a number"):
            parse_config("set suggest-after foo")

        # default with bad value = error
        with pytest.raises(ValueError, match="must be 'allow' or 'ask'"):
            parse_config("set default yolo")

        # log without path = error
        with pytest.raises(ValueError, match="requires a path"):
            parse_config("set log")

    def test_full_config(self):
        cfg = parse_config("""
# User config
allow git *
ask rm -rf /* "are you sure?"
allow-redirect /tmp/**
ask-redirect .env* "don't write secrets"

set sticky-session
set suggest-after 5
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

        assert cfg.sticky_session is True
        assert cfg.suggest_after == 5
        assert cfg.default == "allow"
        assert cfg.log == Path.home() / ".dippy" / "audit.log"


class TestMatchCommand:
    """Test command matching against config rules."""

    def test_basic_glob_match(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git *")])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("git commit -m 'msg'"), cfg, tmp_path) is not None
        assert match_command(cmd("gitk"), cfg, tmp_path) is None  # no space after git

    def test_exact_match(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "git status")])
        assert match_command(cmd("git status"), cfg, tmp_path) is not None
        assert match_command(cmd("git statuses"), cfg, tmp_path) is None
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

    def test_pattern_no_wildcards_exact_only(self, tmp_path):
        cfg = Config(rules=[Rule("allow", "ls")])
        assert match_command(cmd("ls"), cfg, tmp_path) is not None
        assert match_command(cmd("ls -la"), cfg, tmp_path) is None
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


class TestMatchEdgeCases:
    """Edge cases from Git's wildmatch tests."""

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
