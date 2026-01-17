"""Tests for analyzer bugs found in PR #29 review."""

from pathlib import Path

import pytest

from dippy.core.analyzer import analyze
from dippy.core.config import Config


class TestEnvVarPrefixHandling:
    """Handler should receive tokens without env var prefixes."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_git_status_with_env_var(self, config, cwd):
        """FOO=bar git status should be recognized as 'git status'."""
        result = analyze("FOO=bar git status", config, cwd)
        # Should recognize this as git status (safe read operation)
        assert result.action == "allow"
        assert result.reason == "git status"

    def test_git_log_with_multiple_env_vars(self, config, cwd):
        """Multiple env vars should all be skipped."""
        result = analyze("FOO=bar BAZ=qux git log", config, cwd)
        assert result.action == "allow"
        assert result.reason == "git log"

    def test_docker_ps_with_env_var(self, config, cwd):
        """DOCKER_HOST=x docker ps should work."""
        result = analyze("DOCKER_HOST=tcp://localhost:2375 docker ps", config, cwd)
        assert result.action == "allow"
        assert result.reason == "docker ps"

    def test_env_var_with_unsafe_command(self, config, cwd):
        """Env var prefix shouldn't hide unsafe commands."""
        result = analyze("FOO=bar git push", config, cwd)
        assert result.action == "ask"
        assert result.reason == "git push"


class TestCmdsubInjectionWarning:
    """Pure cmdsubs in handler CLIs should warn about injection risk."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_git_cmdsub_injection_reason(self, config, cwd):
        """git $(echo status) should mention injection risk."""
        result = analyze("git $(echo status)", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()

    def test_docker_cmdsub_injection_reason(self, config, cwd):
        """docker $(echo run) should mention injection risk."""
        result = analyze("docker $(echo run) alpine", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()

    def test_kubectl_cmdsub_injection_reason(self, config, cwd):
        """kubectl $(echo delete) should mention injection risk."""
        result = analyze("kubectl $(echo delete) pod foo", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()


class TestNegationAndArith:
    """Test negation (!) and arithmetic (( )) constructs."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("! grep foo", "allow"),
            ("! rm file", "ask"),
            ("(( i++ ))", "allow"),
            ("(( x = 5 ))", "allow"),
            ("(( x = $(echo 1) ))", "allow"),  # safe cmdsub
            ("(( arr[$(rm -rf /)] ))", "ask"),  # dangerous cmdsub in subscript
        ],
    )
    def test_negation_and_arith(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected


class TestCoproc:
    """Test coproc construct."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("coproc cat", "allow"),
            ("coproc { echo hi; }", "allow"),
            ("coproc NAME { echo hi; }", "allow"),
            ("coproc NAME { cat; }", "allow"),
            ("coproc rm -rf /", "ask"),
            ("coproc { rm -rf /; }", "ask"),
            ("coproc NAME { rm file; }", "ask"),
        ],
    )
    def test_coproc(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected
