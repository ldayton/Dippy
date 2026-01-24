"""Tests for bash quoting utilities."""

from dippy.core.bash import bash_join, bash_quote


class TestBashQuote:
    def test_empty_string(self):
        assert bash_quote("") == "''"

    def test_simple_word(self):
        assert bash_quote("hello") == "hello"

    def test_with_spaces(self):
        assert bash_quote("hello world") == "'hello world'"

    def test_with_single_quote(self):
        assert bash_quote("it's") == "'it'\"'\"'s'"

    def test_safe_chars(self):
        assert bash_quote("foo-bar_baz.txt") == "foo-bar_baz.txt"
        assert bash_quote("/path/to/file") == "/path/to/file"
        assert bash_quote("key=value") == "key=value"

    def test_special_chars(self):
        assert bash_quote("$HOME") == "'$HOME'"
        assert bash_quote("a*b") == "'a*b'"
        assert bash_quote("a;b") == "'a;b'"


class TestBashJoin:
    def test_simple(self):
        assert bash_join(["echo", "hello"]) == "echo hello"

    def test_with_spaces(self):
        assert bash_join(["echo", "hello world"]) == "echo 'hello world'"

    def test_empty_arg(self):
        assert bash_join(["echo", ""]) == "echo ''"

    def test_empty_list(self):
        assert bash_join([]) == ""
