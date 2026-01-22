"""Tests for handler description quality.

When a command is blocked, the reason message should indicate WHY it's blocked,
not just the command name. These tests verify that handlers include the
triggering flag or action in their description.
"""

from __future__ import annotations

import pytest


def get_reason(result: dict) -> str:
    """Extract the reason message from a hook result."""
    output = result.get("hookSpecificOutput", {})
    reason = output.get("permissionDecisionReason", "")
    # Strip the duck emoji prefix
    return reason.lstrip("🐤 ").strip()


class TestCurlDescriptions:
    """Curl should indicate WHY it's blocked, not just 'curl'."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            # Data flags should be mentioned
            ("curl -d 'data' https://example.com", "-d"),
            ("curl --data 'data' https://example.com", "--data"),
            ("curl --json '{}'  https://example.com", "--json"),
            # Form flags
            ("curl -F 'file=@f.txt' https://example.com", "-F"),
            ("curl --form 'file=@f.txt' https://example.com", "--form"),
            # Upload
            ("curl -T file.txt ftp://example.com", "-T"),
            ("curl --upload-file file.txt ftp://example.com", "--upload-file"),
            # Unsafe methods
            ("curl -X POST https://example.com", "POST"),
            ("curl -X DELETE https://example.com", "DELETE"),
            ("curl --request PUT https://example.com", "PUT"),
            # Mail
            (
                "curl --mail-from sender@example.com smtp://mail.example.com",
                "--mail-from",
            ),
            (
                "curl --mail-rcpt rcpt@example.com smtp://mail.example.com",
                "--mail-rcpt",
            ),
            # Config file
            ("curl -K config.txt", "-K"),
            ("curl --config config.txt", "--config"),
            # FTP write commands
            (
                "curl --ftp-create-dirs ftp://example.com/dir/file.txt",
                "--ftp-create-dirs",
            ),
        ],
    )
    def test_curl_description_contains_trigger(
        self, check, command: str, should_contain: str
    ):
        """Curl's reason should mention the flag/method that triggered the block."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason, (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestTarDescriptions:
    """Tar should indicate the operation type, not just 'tar'."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            # Create
            ("tar -cf archive.tar file.txt", "create"),
            ("tar -cvf archive.tar file.txt", "create"),
            ("tar --create -f archive.tar file.txt", "create"),
            # Extract
            ("tar -xf archive.tar", "extract"),
            ("tar -xvf archive.tar", "extract"),
            ("tar --extract -f archive.tar", "extract"),
            # Append
            ("tar -rf archive.tar file.txt", "append"),
            ("tar --append -f archive.tar file.txt", "append"),
            # Update
            ("tar -uf archive.tar file.txt", "update"),
            ("tar --update -f archive.tar file.txt", "update"),
            # Delete
            ("tar --delete -f archive.tar file.txt", "delete"),
        ],
    )
    def test_tar_description_contains_operation(
        self, check, command: str, should_contain: str
    ):
        """Tar's reason should mention the operation (create/extract/etc)."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestAwkDescriptions:
    """Awk should indicate WHY it's blocked for non-file-flag cases."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            # system() calls
            ("awk '{system(\"ls\")}' file.txt", "system"),
            ("awk 'BEGIN {system(\"rm -rf /\")}'", "system"),
            # Output redirects
            ("awk '{print > \"output.txt\"}' file.txt", "redirect"),
            ("awk '{print >> \"output.txt\"}' file.txt", "redirect"),
            # Pipe output
            ("awk '{print | \"sort\"}' file.txt", "pipe"),
            ("awk '{print | \"mail user@example.com\"}' file.txt", "pipe"),
        ],
    )
    def test_awk_description_contains_trigger(
        self, check, command: str, should_contain: str
    ):
        """Awk's reason should mention system()/redirect/pipe when relevant."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestWgetDescriptions:
    """Wget should indicate it's downloading, not just 'wget'."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("wget https://example.com", "download"),
            ("wget -O file.zip https://example.com/file.zip", "download"),
            ("wget -r https://example.com", "download"),
        ],
    )
    def test_wget_description_contains_download(
        self, check, command: str, should_contain: str
    ):
        """Wget's reason should mention 'download'."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestSortDescriptions:
    """Sort -o should explain it writes to file."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("sort -o output.txt input.txt", "write"),
            ("sort --output output.txt input.txt", "write"),
            ("sort -ooutput.txt input.txt", "write"),
        ],
    )
    def test_sort_description_contains_write(
        self, check, command: str, should_contain: str
    ):
        """Sort's reason should mention writing to file."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestXxdDescriptions:
    """Xxd -r should explain it writes binary."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("xxd -r hex.txt binary.bin", "binary"),
            ("xxd -revert hex.txt binary.bin", "binary"),
        ],
    )
    def test_xxd_description_contains_binary(
        self, check, command: str, should_contain: str
    ):
        """Xxd's reason should mention writing binary."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestFindDescriptions:
    """Find -ok/-okdir should explain they execute with prompt."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("find . -ok rm {} \\;", "prompt"),
            ("find . -okdir rm {} \\;", "prompt"),
        ],
    )
    def test_find_ok_description_contains_prompt(
        self, check, command: str, should_contain: str
    ):
        """Find -ok/-okdir should mention prompting."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestIfconfigDescriptions:
    """Ifconfig with modification args should explain it modifies interface."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("ifconfig eth0 192.168.1.1", "modify"),
            ("ifconfig eth0 up", "modify"),
            ("ifconfig eth0 down", "modify"),
        ],
    )
    def test_ifconfig_description_contains_modify(
        self, check, command: str, should_contain: str
    ):
        """Ifconfig's reason should mention modifying interface."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestFdDescriptions:
    """Fd -x/-X should explain they execute commands (when no inner command)."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            # When there's no inner command, fd's description is used
            ("fd -x", "execute"),
            ("fd -X", "execute"),
            ("fd --exec", "execute"),
            ("fd --exec-batch", "execute"),
        ],
    )
    def test_fd_description_contains_execute(
        self, check, command: str, should_contain: str
    ):
        """Fd's reason should mention executing when no inner command."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestXargsDescriptions:
    """Xargs -p/-o should explain what they do."""

    @pytest.mark.parametrize(
        "command,should_contain",
        [
            ("xargs -p rm", "prompt"),
            ("xargs -o vim", "tty"),
        ],
    )
    def test_xargs_description_contains_context(
        self, check, command: str, should_contain: str
    ):
        """Xargs's reason should explain the flag."""
        result = check(command)
        reason = get_reason(result)
        assert should_contain in reason.lower(), (
            f"Expected '{should_contain}' in reason for: {command}\nGot: '{reason}'"
        )


class TestCargoAliasExpansion:
    """Cargo short aliases should be expanded (replaced, not appended)."""

    @pytest.mark.parametrize(
        "command,alias,expanded",
        [
            ("cargo r", "r", "run"),
            ("cargo b", "b", "build"),
            ("cargo t", "t", "test"),
        ],
    )
    def test_cargo_alias_replaced(self, check, command: str, alias: str, expanded: str):
        """Cargo aliases should be replaced with full command name."""
        result = check(command)
        reason = get_reason(result)
        # Alias should be replaced, not present alongside expanded form
        assert f"cargo {expanded}" in reason.lower(), (
            f"Expected 'cargo {expanded}' in reason for: {command}\nGot: '{reason}'"
        )
        # The single-letter alias should not appear as a standalone word
        words = reason.lower().split()
        assert alias not in words, (
            f"Alias '{alias}' should be expanded, not present in: {reason}"
        )


class TestNpmAliasExpansion:
    """Npm short aliases should be expanded (replaced, not appended)."""

    @pytest.mark.parametrize(
        "command,alias,expanded",
        [
            ("npm i express", "i", "install"),
            ("npm rm express", "rm", "remove"),
            ("npm un express", "un", "uninstall"),
            ("npm t", "t", "test"),
            ("npm x cowsay", "x", "exec"),
            ("npm c list", "c", "config"),
            ("npm ddp", "ddp", "dedupe"),
            ("npm rb", "rb", "rebuild"),
        ],
    )
    def test_npm_alias_replaced(self, check, command: str, alias: str, expanded: str):
        """Npm aliases should be replaced with full command name."""
        result = check(command)
        reason = get_reason(result)
        assert f"npm {expanded}" in reason.lower(), (
            f"Expected 'npm {expanded}' in reason for: {command}\nGot: '{reason}'"
        )
        words = reason.lower().split()
        assert alias not in words, (
            f"Alias '{alias}' should be expanded, not present in: {reason}"
        )


class TestHelmAliasExpansion:
    """Helm short aliases should be expanded (replaced, not appended)."""

    @pytest.mark.parametrize(
        "command,alias,expanded",
        [
            ("helm del myrelease", "del", "delete"),
            ("helm un myrelease", "un", "uninstall"),
            ("helm fetch mychart", "fetch", "pull"),
        ],
    )
    def test_helm_alias_replaced(self, check, command: str, alias: str, expanded: str):
        """Helm aliases should be replaced with full command name."""
        result = check(command)
        reason = get_reason(result)
        assert f"helm {expanded}" in reason.lower(), (
            f"Expected 'helm {expanded}' in reason for: {command}\nGot: '{reason}'"
        )
        words = reason.lower().split()
        assert alias not in words, (
            f"Alias '{alias}' should be expanded, not present in: {reason}"
        )


class TestGitContextDescriptions:
    """Git unclear commands should have parenthetical context."""

    @pytest.mark.parametrize(
        "command,expected_desc",
        [
            ("git gc", "git gc (garbage collect)"),
            ("git prune", "git prune (remove unreachable objects)"),
            ("git filter-branch --all", "git filter-branch (rewrite history)"),
        ],
    )
    def test_git_context_format(self, check, command: str, expected_desc: str):
        """Git unclear commands should have exact context format."""
        result = check(command)
        reason = get_reason(result)
        assert reason.lower() == expected_desc.lower(), (
            f"Expected '{expected_desc}' for: {command}\nGot: '{reason}'"
        )
