"""Test cases for hook output format and reasons."""

import pytest


@pytest.fixture
def check():
    from dippy.dippy import check_command
    return check_command


def get_reason(result: dict) -> str:
    """Extract reason without bird emoji."""
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    return reason.removeprefix("🐤 ")


class TestOutputFormat:
    """Verify hook output uses correct format."""

    def test_approve_format(self, check):
        result = check("ls")
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert result["hookSpecificOutput"]["permissionDecisionReason"].startswith("🐤")

    def test_ask_format(self, check):
        """Ask returns empty dict to let Claude's normal permission flow handle it."""
        result = check("rm foo")
        assert result == {}


class TestApproveReasons:
    """Verify approved commands list matched commands."""

    def test_ls(self, check):
        assert get_reason(check("ls")) == "ls"

    def test_ls_with_args(self, check):
        assert get_reason(check("ls -la /tmp")) == "ls"

    def test_cat(self, check):
        assert get_reason(check("cat foo.txt")) == "cat"

    def test_git_status(self, check):
        assert get_reason(check("git status")) == "git status"

    def test_git_log(self, check):
        assert get_reason(check("git log --oneline")) == "git log"

    def test_git_diff(self, check):
        assert get_reason(check("git diff HEAD")) == "git diff"

    def test_pipeline(self, check):
        assert get_reason(check("ls | grep foo")) == "ls, grep"

    def test_pipeline_three(self, check):
        assert get_reason(check("cat file | grep x | wc -l")) == "cat, grep, wc"

    def test_list_two(self, check):
        assert get_reason(check("ls && pwd")) == "ls, pwd"

    def test_list_three(self, check):
        assert get_reason(check("ls && pwd && whoami")) == "ls, pwd, whoami"

    def test_git_list(self, check):
        assert get_reason(check("git status && git log")) == "git status, git log"


class TestAskCommands:
    """Verify unsafe commands return empty dict (no Dippy decision)."""

    @pytest.mark.parametrize("cmd", [
        "rm foo",
        "rm -rf /tmp/foo",
        "mv foo bar",
        "chmod 755 file",
        "git push",
        "git commit -m 'msg'",
        "git add .",
        "kubectl delete pod foo",
        "aws s3 rm s3://bucket/key",
        "terraform apply",
        "echo foo > file.txt",
        "echo foo >> file.txt",
    ])
    def test_unsafe_returns_empty(self, check, cmd):
        """Unsafe commands return {} to let Claude handle permission."""
        assert check(cmd) == {}

    @pytest.mark.parametrize("cmd", [
        "git add . && git commit -m 'x'",
        "rm foo && mv bar baz",
        "chmod 755 f && chown root f",
        "rm x && git push && docker rm y",
        "ls && rm foo",
        "cat file | tee output",
    ])
    def test_mixed_returns_empty(self, check, cmd):
        """Commands with any unsafe part return {} to let Claude handle permission."""
        assert check(cmd) == {}
