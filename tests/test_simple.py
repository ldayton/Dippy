"""
Tests for simple safe commands (ls, cat, head, etc.)
"""

import pytest


def is_approved(result: dict) -> bool:
    """Check if a hook result is an approval."""
    return result.get("decision") == "approve"


def needs_confirmation(result: dict) -> bool:
    """Check if a hook result requires user confirmation."""
    return "decision" not in result


class TestFileViewing:
    """Tests for file viewing commands."""
    
    @pytest.mark.parametrize("cmd", [
        "cat file.txt",
        "cat -n file.txt",
        "head file.txt",
        "head -20 file.txt",
        "tail file.txt",
        "tail -f log.txt",
        "less file.txt",
        "more file.txt",
        "bat file.txt",
    ])
    def test_file_viewing(self, check, cmd):
        """File viewing commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestDirectoryListing:
    """Tests for directory listing commands."""
    
    @pytest.mark.parametrize("cmd", [
        "ls",
        "ls -la",
        "ls -lah /tmp",
        "ll",
        "la",
        "tree",
        "tree -L 2",
        "exa",
        "eza --long",
    ])
    def test_directory_listing(self, check, cmd):
        """Directory listing commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestFileInfo:
    """Tests for file information commands."""
    
    @pytest.mark.parametrize("cmd", [
        "stat file.txt",
        "file document.pdf",
        "wc -l file.txt",
        "wc file.txt",
        "du -sh .",
        "df -h",
    ])
    def test_file_info(self, check, cmd):
        """File info commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestSearch:
    """Tests for search commands."""
    
    @pytest.mark.parametrize("cmd", [
        "grep pattern file.txt",
        "grep -r pattern .",
        "grep -E 'regex' file.txt",
        "rg pattern",
        "rg -i pattern .",
        "ag pattern",
        "ack pattern",
        "find . -name '*.py'",
        "find /tmp -type f",
        "fd pattern",
        "locate file.txt",
    ])
    def test_search_commands(self, check, cmd):
        """Search commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestTextProcessing:
    """Tests for text processing commands."""
    
    @pytest.mark.parametrize("cmd", [
        "sort file.txt",
        "uniq file.txt",
        "cut -d: -f1 file.txt",
        "awk '{print $1}' file.txt",
        "sed 's/foo/bar/' file.txt",
        "jq '.key' file.json",
        "yq '.key' file.yaml",
    ])
    def test_text_processing(self, check, cmd):
        """Text processing commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestSystemInfo:
    """Tests for system info commands."""
    
    @pytest.mark.parametrize("cmd", [
        "pwd",
        "whoami",
        "hostname",
        "uname -a",
        "date",
        "cal",
        "uptime",
        "free -h",
        "ps aux",
        "ps -ef",
        "pgrep python",
        "env",
        "printenv",
        "echo hello",
        "printf 'test'",
    ])
    def test_system_info(self, check, cmd):
        """System info commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestNetworkInfo:
    """Tests for network info commands."""
    
    @pytest.mark.parametrize("cmd", [
        "ping -c 3 google.com",
        "host google.com",
        "dig google.com",
        "nslookup google.com",
        "ifconfig",
        "ip addr",
        "ip route",
    ])
    def test_network_info(self, check, cmd):
        """Network info commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestDevelopmentTools:
    """Tests for development tool commands."""
    
    @pytest.mark.parametrize("cmd", [
        "which python",
        "whereis python",
        "type ls",
        "command -v python",
        "man ls",
        "help cd",
    ])
    def test_development_tools(self, check, cmd):
        """Development tool commands should be approved."""
        result = check(cmd)
        assert is_approved(result)


class TestUnsafeSimpleCommands:
    """Tests for commands that should NOT be auto-approved."""
    
    @pytest.mark.parametrize("cmd", [
        "rm file.txt",
        "rm -rf /",
        "mv file.txt other.txt",
        "chmod 755 script.sh",
        "chown user file.txt",
        "sudo anything",
        "dd if=/dev/zero of=/dev/sda",
    ])
    def test_unsafe_simple_commands(self, check, cmd):
        """Unsafe commands should require confirmation."""
        result = check(cmd)
        assert needs_confirmation(result)
