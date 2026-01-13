"""Tests for handler description quality.

When a command is blocked, the reason message should indicate WHY it's blocked,
not just the command name. These tests verify that handlers include the
triggering flag or action in their description.
"""

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
