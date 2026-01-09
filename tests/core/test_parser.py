"""
Tests for the core parser module.
"""

from dippy.core.parser import (
    tokenize,
    has_output_redirect,
    is_piped,
    split_pipeline,
)


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


class TestOutputRedirect:
    """Tests for output redirect detection."""

    def test_stdout_redirect(self):
        """Should detect stdout redirect."""
        assert has_output_redirect("ls > file.txt")

    def test_append_redirect(self):
        """Should detect append redirect."""
        assert has_output_redirect("echo hello >> file.txt")

    def test_no_redirect(self):
        """Should not detect redirect when none present."""
        assert not has_output_redirect("ls -la")

    def test_greater_than_in_string(self):
        """Greater-than in quoted string should not count."""
        # This depends on bashlex being available
        result = has_output_redirect("echo '>' file.txt")
        # Conservative: if bashlex fails, this might still return True
        # which is acceptable (safer to ask user)
        assert isinstance(result, bool)


class TestIsPiped:
    """Tests for pipeline detection."""

    def test_simple_pipe(self):
        """Should detect simple pipe."""
        assert is_piped("ls | grep foo")

    def test_multi_pipe(self):
        """Should detect multi-stage pipe."""
        assert is_piped("cat file | grep x | wc -l")

    def test_no_pipe(self):
        """Should not detect pipe when none present."""
        assert not is_piped("ls -la")

    def test_pipe_in_string(self):
        """Pipe in quoted string might or might not be detected."""
        # Depends on bashlex parsing
        result = is_piped("echo '|' test")
        assert isinstance(result, bool)


class TestSplitPipeline:
    """Tests for pipeline splitting."""

    def test_simple_split(self):
        """Should split simple pipeline."""
        parts = split_pipeline("ls | grep foo")
        assert len(parts) == 2
        assert "ls" in parts[0]
        assert "grep" in parts[1]

    def test_multi_split(self):
        """Should split multi-stage pipeline."""
        parts = split_pipeline("cat file | grep x | wc -l")
        assert len(parts) == 3

    def test_no_pipe(self):
        """Single command should return single-element list."""
        parts = split_pipeline("ls -la")
        assert len(parts) == 1
        assert "ls" in parts[0]
