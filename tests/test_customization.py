"""Tests for dippy-local.toml config loading - exercises all configurable sections."""

import pytest
from pathlib import Path

from dippy.dippy import (
    parse_commands,
    is_command_safe,
    _load_custom_configs,
    SAFE_SCRIPTS,
    CURL_WRAPPERS,
    SAFE_COMMANDS,
    PREFIX_COMMANDS,
    CLI_ALIASES,
    CLI_CONFIGS,
    WRAPPERS,
    CUSTOM_PATTERNS,
)

# Load configs before tests
_load_custom_configs()

HOME = str(Path.home())


class TestSafeScripts:
    def test_safe_script_approved(self):
        assert is_command_safe(["./safe-test-script.sh"])

    def test_safe_script_with_args(self):
        assert is_command_safe(["./safe-test-script.sh", "--verbose"])

    def test_safe_script_in_set(self):
        assert "safe-test-script.sh" in SAFE_SCRIPTS


class TestCurlWrappers:
    def test_curl_wrapper_get_approved(self):
        assert is_command_safe(["./curl-wrapper.sh", "https://example.com"])

    def test_curl_wrapper_post_rejected(self):
        assert not is_command_safe(
            ["./curl-wrapper.sh", "-X", "POST", "https://example.com"]
        )

    def test_curl_wrapper_in_set(self):
        assert "curl-wrapper.sh" in CURL_WRAPPERS


class TestSafePatterns:
    def test_pattern_matches(self):
        assert is_command_safe([f"{HOME}/test-tools/foo/bin/run.sh"])

    def test_pattern_matches_with_args(self):
        assert is_command_safe([f"{HOME}/test-tools/bar/bin/run.sh", "--test"])

    def test_pattern_no_match(self):
        assert not is_command_safe([f"{HOME}/test-tools/bin/run.sh"])  # missing subdir

    def test_patterns_loaded(self):
        assert len(CUSTOM_PATTERNS) > 0


class TestSafeCommands:
    def test_custom_command_approved(self):
        assert is_command_safe(["testcmd"])

    def test_custom_command_with_args(self):
        assert is_command_safe(["testcmd", "--flag", "value"])

    def test_command_in_set(self):
        assert "testcmd" in SAFE_COMMANDS


class TestPrefixCommands:
    def test_prefix_command_approved(self):
        assert is_command_safe(["testprefix", "status"])

    def test_prefix_command_with_args(self):
        assert is_command_safe(["testprefix", "status", "--verbose"])

    def test_prefix_command_different_action_rejected(self):
        assert not is_command_safe(["testprefix", "delete"])

    def test_prefix_in_set(self):
        assert "testprefix status" in PREFIX_COMMANDS


class TestCliAliases:
    def test_alias_uses_base_rules(self):
        # testalias -> git, so "testalias status" should be safe
        assert is_command_safe(["testalias", "status"])

    def test_alias_unsafe_action_rejected(self):
        # testalias -> git, so "testalias push" should be rejected
        assert not is_command_safe(["testalias", "push"])

    def test_alias_in_dict(self):
        assert CLI_ALIASES.get("testalias") == "git"


class TestCliSafeActions:
    def test_added_action_approved(self):
        # pre-commit run was added via config
        assert is_command_safe(["pre-commit", "run"])

    def test_added_action_with_flags(self):
        assert is_command_safe(["pre-commit", "run", "--all-files"])

    def test_ruff_format_approved(self):
        assert is_command_safe(["ruff", "format", "."])

    def test_uv_sync_approved(self):
        assert is_command_safe(["uv", "sync"])


class TestCliTools:
    def test_new_cli_exists(self):
        assert "testcli" in CLI_CONFIGS

    def test_new_cli_safe_action(self):
        assert is_command_safe(["testcli", "safecmd"])

    def test_new_cli_safe_prefix(self):
        assert is_command_safe(["testcli", "safe-something"])

    def test_new_cli_common_actions(self):
        # New CLIs get COMMON_SAFE_ACTIONS by default
        assert is_command_safe(["testcli", "list"])
        assert is_command_safe(["testcli", "show"])
        assert is_command_safe(["testcli", "status"])

    def test_new_cli_unsafe_action_rejected(self):
        assert not is_command_safe(["testcli", "delete"])

    def test_new_cli_flags_with_arg(self):
        # -c takes an arg, so "list" is still the action
        assert is_command_safe(["testcli", "-c", "config.yml", "list"])


class TestWrappers:
    def test_wrapper_exists(self):
        assert "testwrap" in WRAPPERS

    def test_wrapper_with_safe_inner(self):
        assert is_command_safe(["testwrap", "exec", "ls"])

    def test_wrapper_with_unsafe_inner(self):
        assert not is_command_safe(["testwrap", "exec", "rm", "file"])

    def test_wrapper_skips_flags(self):
        # --config takes an arg, should skip to inner command
        assert is_command_safe(["testwrap", "exec", "--config", "foo.yml", "ls"])

    def test_wrapper_config(self):
        prefix, skip, flags = WRAPPERS["testwrap"]
        assert prefix == ["testwrap", "exec"]
        assert skip is None  # "flags" -> None
        assert "--config" in flags
