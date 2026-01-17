"""
Tests for the core parser module.
"""

from dippy.core.parser import tokenize


class TestTokenize:
    """Tests for command tokenization."""

    def test_simple_command(self):
        """Simple command should tokenize correctly."""
        tokens = tokenize("ls -la")
        assert tokens == ["ls", "-la"]

    def test_quoted_string(self):
        """Quoted strings should be preserved."""
        tokens = tokenize("echo 'hello world'")
        assert tokens == ["echo", "hello world"]

    def test_double_quoted(self):
        """Double quoted strings should be preserved."""
        tokens = tokenize('grep "pattern with spaces" file.txt')
        assert tokens == ["grep", "pattern with spaces", "file.txt"]

    def test_empty_command(self):
        """Empty command should return empty list."""
        tokens = tokenize("")
        assert tokens == []

    def test_whitespace_only(self):
        """Whitespace-only command should return empty list."""
        tokens = tokenize("   ")
        assert tokens == []

    def test_complex_command(self):
        """Complex command with flags and args."""
        tokens = tokenize("git log --oneline -n 10")
        assert tokens == ["git", "log", "--oneline", "-n", "10"]
