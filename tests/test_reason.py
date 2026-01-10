"""Test cases for hook output format and reasons."""

from pathlib import Path

import pytest

from dippy.core.config import Config


@pytest.fixture
def check():
    from dippy.dippy import check_command

    def _check(command: str):
        return check_command(command, Config(), Path.cwd())

    return _check


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
        result = check("rm foo")
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert result["hookSpecificOutput"]["permissionDecisionReason"].startswith("🐤")


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


class TestAskReasons:
    """Verify unsafe commands list matched commands."""

    def test_rm(self, check):
        assert get_reason(check("rm foo")) == "rm"

    def test_rm_rf(self, check):
        assert get_reason(check("rm -rf /tmp/foo")) == "rm"

    def test_mv(self, check):
        assert get_reason(check("mv foo bar")) == "mv"

    def test_chmod(self, check):
        assert get_reason(check("chmod 755 file")) == "chmod"

    def test_git_push(self, check):
        assert get_reason(check("git push")) == "git push"

    def test_git_commit(self, check):
        assert get_reason(check("git commit -m 'msg'")) == "git commit"

    def test_git_add(self, check):
        assert get_reason(check("git add .")) == "git add"

    def test_git_add_commit(self, check):
        assert (
            get_reason(check("git add . && git commit -m 'x'")) == "git add, git commit"
        )

    def test_kubectl_delete(self, check):
        assert get_reason(check("kubectl delete pod foo")) == "kubectl delete"

    def test_aws_s3_rm(self, check):
        assert get_reason(check("aws s3 rm s3://bucket/key")) == "aws s3 rm"

    def test_terraform_apply(self, check):
        assert get_reason(check("terraform apply")) == "terraform apply"

    def test_redirect(self, check):
        assert get_reason(check("echo foo > file.txt")) == "output redirect"

    def test_append_redirect(self, check):
        assert get_reason(check("echo foo >> file.txt")) == "output redirect"

    def test_rm_mv(self, check):
        assert get_reason(check("rm foo && mv bar baz")) == "rm, mv"

    def test_chmod_chown(self, check):
        assert get_reason(check("chmod 755 f && chown root f")) == "chmod, chown"

    def test_rm_git_push_docker_rm(self, check):
        assert (
            get_reason(check("rm x && git push && docker rm y"))
            == "rm, git push, docker rm"
        )

    def test_mixed_safe_unsafe(self, check):
        # ls is safe, rm is not - only list unsafe
        assert get_reason(check("ls && rm foo")) == "rm"

    def test_mixed_pipeline(self, check):
        # cat is safe, tee writes
        assert get_reason(check("cat file | tee output")) == "tee"
