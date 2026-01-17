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


class TestCondExpr:
    """Test [[ ]] conditional expression construct."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Simple conditions - allow
            ("[[ -f foo ]]", "allow"),
            ('[[ -z "$x" ]]', "allow"),
            ("[[ $a == $b ]]", "allow"),
            ("[[ -f x && -d y ]]", "allow"),
            ("[[ -f x || -d y ]]", "allow"),
            ("[[ ! -f foo ]]", "allow"),
            ("[[ ( -f x ) ]]", "allow"),
            # Safe cmdsubs - allow
            ("[[ -f $(echo foo) ]]", "allow"),
            ("[[ $(echo x) == y ]]", "allow"),
            ("[[ -f x && $(pwd) == y ]]", "allow"),
            # Dangerous cmdsubs - ask
            ("[[ -f $(rm -rf /) ]]", "ask"),
            ("[[ $(rm file) == x ]]", "ask"),
            ("[[ -f x && $(rm y) == z ]]", "ask"),
            ("[[ ! -f $(rm foo) ]]", "ask"),
            ("[[ ( $(rm x) == y ) ]]", "ask"),
        ],
    )
    def test_cond_expr(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected


class TestCmdsubSecurityGaps:
    """Tests for cmdsub analysis in various constructs.

    These tests verify that dangerous command substitutions are detected
    in all contexts, not just simple command arguments.
    """

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # for loop iteration words
            ("for i in $(rm foo); do echo $i; done", "ask"),
            ("for i in $(ls); do echo $i; done", "allow"),
            ("for i in a $(rm foo) b; do echo $i; done", "ask"),
        ],
    )
    def test_for_iteration_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in for loop iteration list should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # select word list
            ("select x in $(rm foo); do echo $x; done", "ask"),
            ("select x in $(ls); do echo $x; done", "allow"),
        ],
    )
    def test_select_words_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in select word list should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # case word
            ("case $(rm foo) in *) echo y;; esac", "ask"),
            ("case $(echo x) in *) echo y;; esac", "allow"),
        ],
    )
    def test_case_word_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in case word should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # subshell with redirect containing cmdsub
            ("(ls) > $(rm foo)", "ask"),
            ("(ls) > $(echo /tmp/out)", "ask"),  # still ask - output redirect
            # brace-group with redirect containing cmdsub
            ("{ ls; } > $(rm foo)", "ask"),
            ("{ ls; } > $(echo /tmp/out)", "ask"),  # still ask - output redirect
        ],
    )
    def test_compound_redirect_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in redirect targets of compound commands should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Redirect target with cmdsub - inner command should be analyzed
            ("ls > $(rm foo)", "ask"),
            # Even safe inner cmdsub should ask due to output redirect
            ("ls > $(echo /tmp/out)", "ask"),
        ],
    )
    def test_redirect_target_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in redirect targets should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestArithCmdRedirect:
    """Tests for arith-cmd redirect checking."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("(( 1 )) > $(rm foo)", "ask"),
            ("(( x++ )) > /tmp/out", "ask"),
        ],
    )
    def test_arith_cmd_redirect(self, cmd, expected, config, cwd):
        """Arith-cmd should check its redirects."""
        assert analyze(cmd, config, cwd).action == expected


class TestForArithCmdsub:
    """Tests for cmdsubs in for-arith init/cond/incr expressions."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("for (( i=$(rm foo); i<10; i++ )); do echo $i; done", "ask"),
            ("for (( i=0; i<$(rm foo); i++ )); do echo $i; done", "ask"),
            ("for (( i=0; i<10; i+=$(rm foo) )); do echo $i; done", "ask"),
        ],
    )
    def test_for_arith_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in for-arith init/cond/incr should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestParamExpansionCmdsub:
    """Tests for cmdsubs nested inside parameter expansions."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("echo ${x:-$(rm foo)}", "ask"),
            ("echo ${x:=$(rm foo)}", "ask"),
            ("echo ${x:+$(rm foo)}", "ask"),
            ("echo ${x:?$(rm foo)}", "ask"),
            ("[[ -f ${x:-$(rm foo)} ]]", "ask"),
            ("for i in ${x:-$(rm foo)}; do echo $i; done", "ask"),
        ],
    )
    def test_param_expansion_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs nested in parameter expansions should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestBacktickCmdsub:
    """Tests for backtick command substitutions in raw strings."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Backticks in for-arith expressions
            ("for (( i=`rm foo`; i<10; i++ )); do echo $i; done", "ask"),
            # Backticks in param expansion
            ("echo ${x:-`rm foo`}", "ask"),
        ],
    )
    def test_backtick_cmdsub(self, cmd, expected, config, cwd):
        """Backtick command substitutions should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestHeredocCmdsub:
    """Tests for command substitutions in heredocs."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Unquoted heredoc - cmdsubs ARE executed
            ("cat <<EOF\n$(rm foo)\nEOF", "ask"),
            # Multiple cmdsubs in heredoc
            ("cat <<EOF\n$(echo a)\n$(rm foo)\nEOF", "ask"),
        ],
    )
    def test_heredoc_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in unquoted heredocs should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestCdPathResolution:
    """Test that `cd <literal> && ...` resolves paths against the cd target."""

    def test_cd_resolves_relative_path_for_config_match(self, tmp_path):
        """cd /foo && ./bar should resolve ./bar against /foo."""
        from dippy.core.config import parse_config

        target_dir = tmp_path / "myproject"
        target_dir.mkdir()
        config = parse_config(f"allow {target_dir}/tool *")
        # cwd is tmp_path, but cd changes to target_dir
        result = analyze(f"cd {target_dir} && ./tool --flag", config, tmp_path)
        assert result.action == "allow"

    def test_cd_tilde_path(self):
        """cd ~ && ./script should resolve ./script against home."""
        from dippy.core.config import parse_config

        home = Path.home()
        config = parse_config(f"allow {home}/script *")
        result = analyze("cd ~ && ./script arg", config, Path("/somewhere/else"))
        assert result.action == "allow"
