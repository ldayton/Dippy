"""
Parable - A recursive descent parser for bash.

MIT License - https://github.com/ldayton/Parable

from parable import parse
ast = parse("ps aux | grep python | awk '{print $2}'")
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Union


class ParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, pos: int = 0, line: int = 0):
        self.message = message
        self.pos = pos  # 0 = not specified
        self.line = line  # 0 = not specified
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.line != 0 and self.pos != 0:
            return f"Parse error at line {self.line}, position {self.pos}: {self.message}"
        elif self.pos != 0:
            return f"Parse error at position {self.pos}: {self.message}"
        return f"Parse error: {self.message}"


class MatchedPairError(ParseError):
    """Raised when a matched pair (like parentheses or braces) is unclosed at EOF.

    This is distinct from returning None/"" which signals "try alternative parsing".
    MatchedPairError means "this IS the construct, but it's unclosed at EOF".
    """

    pass


def _is_hex_digit(c: str) -> bool:
    return (c >= "0" and c <= "9") or (c >= "a" and c <= "f") or (c >= "A" and c <= "F")


def _is_octal_digit(c: str) -> bool:
    return c >= "0" and c <= "7"


# ANSI-C escape sequence byte values
ANSI_C_ESCAPES = {
    "a": 0x07,  # bell
    "b": 0x08,  # backspace
    "e": 0x1B,  # escape
    "E": 0x1B,  # escape (alt)
    "f": 0x0C,  # form feed
    "n": 0x0A,  # newline
    "r": 0x0D,  # carriage return
    "t": 0x09,  # tab
    "v": 0x0B,  # vertical tab
    "\\": 0x5C,  # backslash
    '"': 0x22,  # double quote
    "?": 0x3F,  # question mark
}


def _get_ansi_escape(c: str) -> int:
    """Look up simple ANSI-C escape byte value. Returns -1 if not found."""
    return ANSI_C_ESCAPES.get(c, -1)


def _is_whitespace(c: str) -> bool:
    return c == " " or c == "\t" or c == "\n"


def _string_to_bytes(s: str) -> bytearray:
    """Convert a string to a list of UTF-8 bytes."""
    return list(s.encode("utf-8"))


def _is_whitespace_no_newline(c: str) -> bool:
    return c == " " or c == "\t"


def _substring(s: str, start: int, end: int) -> str:
    """Extract substring from start to end (exclusive)."""
    return s[start:end]


def _starts_with_at(s: str, pos: int, prefix: str) -> bool:
    """Check if s starts with prefix at position pos."""
    return s.startswith(prefix, pos)


def _count_consecutive_dollars_before(s: str, pos: int) -> int:
    """Count consecutive '$' characters immediately before pos.

    Stops counting when hitting a '$' that is preceded by an unescaped backslash,
    since escaped dollars don't participate in dollar sequences like $$.
    """
    count = 0
    k = pos - 1
    while k >= 0 and s[k] == "$":
        # Check if this dollar is escaped by counting preceding backslashes
        bs_count = 0
        j = k - 1
        while j >= 0 and s[j] == "\\":
            bs_count += 1
            j -= 1
        if bs_count % 2 == 1:
            # Odd number of backslashes means the dollar is escaped, stop counting
            break
        count += 1
        k -= 1
    return count


def _is_expansion_start(s: str, pos: int, delimiter: str) -> bool:
    """Check if s[pos:] starts a real expansion (not after $$).

    Returns True if s starts with delimiter at pos AND the preceding
    context indicates this is a real expansion (not $$ followed by
    the delimiter's second character).
    """
    if not _starts_with_at(s, pos, delimiter):
        return False
    # If preceded by odd number of $, this $ pairs with previous to form $$
    return _count_consecutive_dollars_before(s, pos) % 2 == 0


def _sublist(lst: list[Node], start: int, end: int) -> list[Node]:
    """Extract sublist from start to end (exclusive)."""
    return lst[start:end]


def _repeat_str(s: str, n: int) -> str:
    """Repeat string s n times."""
    result = []
    i = 0
    while i < n:
        result.append(s)
        i += 1
    return "".join(result)


class TokenType:
    """Token type constants for the lexer."""

    EOF = 0
    WORD = 1
    NEWLINE = 2

    # Single-char operators
    SEMI = 10
    PIPE = 11
    AMP = 12
    LPAREN = 13
    RPAREN = 14
    LBRACE = 15
    RBRACE = 16
    LESS = 17
    GREATER = 18

    # Multi-char operators
    AND_AND = 30
    OR_OR = 31
    SEMI_SEMI = 32
    SEMI_AMP = 33
    SEMI_SEMI_AMP = 34
    LESS_LESS = 35
    GREATER_GREATER = 36
    LESS_AMP = 37
    GREATER_AMP = 38
    LESS_GREATER = 39
    GREATER_PIPE = 40
    LESS_LESS_MINUS = 41
    LESS_LESS_LESS = 42
    AMP_GREATER = 43
    AMP_GREATER_GREATER = 44
    PIPE_AMP = 45

    # Reserved words
    IF = 50
    THEN = 51
    ELSE = 52
    ELIF = 53
    FI = 54
    CASE = 55
    ESAC = 56
    FOR = 57
    WHILE = 58
    UNTIL = 59
    DO = 60
    DONE = 61
    IN = 62
    FUNCTION = 63
    SELECT = 64
    COPROC = 65
    TIME = 66
    BANG = 67
    LBRACKET_LBRACKET = 68
    RBRACKET_RBRACKET = 69

    # Special
    ASSIGNMENT_WORD = 80
    NUMBER = 81


class Token:
    """A token produced by the lexer.

    For WORD tokens, `parts` contains expansion AST nodes (CommandSubstitution,
    ParameterExpansion, etc.) found within the word. The `word` field contains
    the fully parsed Word object.
    """

    def __init__(
        self,
        type_: int,
        value: str,
        pos: int,
        parts: list[Node] | None = None,
        word: Word | None = None,
    ):
        self.type = type_
        self.value = value
        self.pos = pos
        self.parts: list[Node] = parts if parts is not None else []
        self.word = word  # Parsed Word object for WORD tokens

    def __repr__(self) -> str:
        if self.word:
            return f"Token({self.type}, {self.value}, {self.pos}, word={self.word})"
        if self.parts:
            return f"Token({self.type}, {self.value}, {self.pos}, parts={len(self.parts)})"
        return f"Token({self.type}, {self.value}, {self.pos})"


class ParserStateFlags:
    """Parser state flags for context-sensitive parsing decisions."""

    NONE = 0
    PST_CASEPAT = 0x0001
    PST_CMDSUBST = 0x0002
    PST_CASESTMT = 0x0004
    PST_CONDEXPR = 0x0008
    PST_COMPASSIGN = 0x0010
    PST_ARITH = 0x0020
    PST_HEREDOC = 0x0040
    PST_REGEXP = 0x0080
    PST_EXTPAT = 0x0100
    PST_SUBSHELL = 0x0200
    PST_REDIRLIST = 0x0400
    PST_COMMENT = 0x0800
    PST_EOFTOKEN = 0x1000  # Check for EOF token at grammar level (like Bash)


class DolbraceState:
    """States for ${...} parameter expansion parsing.

    These states determine how single quotes are handled inside parameter expansions.
    Based on bash's DOLBRACE_* defines in parser.h.
    """

    NONE = 0
    PARAM = 0x01  # Reading parameter name: ${foo
    OP = 0x02  # Reading operator: ${foo%
    WORD = 0x04  # Reading word after operator: ${foo%bar
    QUOTE = 0x40  # Single quote is special (%, #, ^, ,)
    QUOTE2 = 0x80  # Single quote semi-special (/)


class MatchedPairFlags:
    """Flags for _parse_matched_pair() to control parsing behavior.

    Based on bash's P_* flags used in parse_matched_pair().
    These flags control how the function handles quotes, escapes, and nested constructs.
    """

    NONE = 0
    DQUOTE = 0x01  # Inside double quotes
    DOLBRACE = 0x02  # Inside ${...}
    COMMAND = 0x04  # Inside command substitution
    ARITH = 0x08  # Inside arithmetic expression
    ALLOWESC = 0x10  # Allow backslash escapes (for $'...')
    EXTGLOB = 0x20  # Inside extglob pattern - don't parse ${ $( as constructs
    FIRSTCLOSE = 0x40  # Bare open delimiter doesn't increment count (bash's P_FIRSTCLOSE)
    ARRAYSUB = 0x80  # Inside [...] array subscript (bash's P_ARRAYSUB)
    BACKQUOTE = 0x100  # Inside backtick substitution (bash's P_BACKQUOTE, reserved)


class SavedParserState:
    """Saved parser state for nested parsing (e.g., command substitutions).

    Based on bash's sh_parser_state_t and save_parser_state/restore_parser_state.
    Used when parsing nested constructs to save and restore parser context.
    """

    def __init__(
        self,
        parser_state: int,
        dolbrace_state: int,
        pending_heredocs: list[Node],
        ctx_stack: list[ParseContext],
        eof_token: str | None = None,
    ):
        self.parser_state = parser_state
        self.dolbrace_state = dolbrace_state
        self.pending_heredocs = pending_heredocs
        self.ctx_stack = ctx_stack
        self.eof_token = eof_token


class QuoteState:
    """Unified quote state tracker for parsing.

    Tracks single and double quote state, with stack support for nested contexts
    like command substitutions inside parameter expansions.
    """

    def __init__(self):
        self.single = False
        self.double = False
        self._stack: list[tuple[bool, bool]] = []

    def push(self) -> None:
        """Push current state onto stack and reset for nested context."""
        self._stack.append((self.single, self.double))
        self.single = False
        self.double = False

    def pop(self) -> None:
        """Restore quote state from stack."""
        if self._stack:
            self.single, self.double = self._stack.pop()

    def in_quotes(self) -> bool:
        """Return True if inside any quotes."""
        return self.single or self.double

    def copy(self) -> QuoteState:
        """Create a copy of this quote state."""
        qs = QuoteState()
        qs.single = self.single
        qs.double = self.double
        qs._stack = list(self._stack)
        return qs

    def outer_double(self) -> bool:
        """Return True if the outer (parent) context is in double quotes."""
        if len(self._stack) == 0:
            return False
        return self._stack[len(self._stack) - 1][1]


class ParseContext:
    """Context for parsing state within a specific scope.

    Tracks context type, nesting depths, and quote state for a single parsing scope.
    Used with ContextStack to manage nested contexts like command substitutions,
    arithmetic expressions, and case patterns.
    """

    # Context kind constants
    NORMAL = 0
    COMMAND_SUB = 1
    ARITHMETIC = 2
    CASE_PATTERN = 3
    BRACE_EXPANSION = 4

    def __init__(self, kind: int = 0):
        self.kind = kind
        self.paren_depth = 0
        self.brace_depth = 0
        self.bracket_depth = 0
        self.case_depth = 0  # Nested case statements
        self.arith_depth = 0  # Nested $((...)) expressions
        self.arith_paren_depth = 0  # Grouping parens inside arithmetic
        self.quote: QuoteState = QuoteState()

    def copy(self) -> ParseContext:
        """Create a deep copy of this context."""
        ctx = ParseContext(self.kind)
        ctx.paren_depth = self.paren_depth
        ctx.brace_depth = self.brace_depth
        ctx.bracket_depth = self.bracket_depth
        ctx.case_depth = self.case_depth
        ctx.arith_depth = self.arith_depth
        ctx.arith_paren_depth = self.arith_paren_depth
        ctx.quote = self.quote.copy()
        return ctx


class ContextStack:
    """Stack of parsing contexts for tracking nested scopes.

    Maintains a stack of ParseContext objects to handle nested structures like
    command substitutions inside arithmetic expressions inside case patterns.
    Always has at least one context (NORMAL) on the stack.
    """

    def __init__(self):
        self._stack: list[ParseContext] = [ParseContext()]

    def get_current(self) -> ParseContext:
        """Return the current (topmost) context."""
        return self._stack[len(self._stack) - 1]

    def push(self, kind: int) -> None:
        """Push a new context onto the stack."""
        self._stack.append(ParseContext(kind))

    def pop(self) -> ParseContext:
        """Pop and return the top context. Never pops the base context."""
        if len(self._stack) > 1:
            return self._stack.pop()
        return self._stack[0]

    def copy_stack(self) -> list[ParseContext]:
        """Return a deep copy of the context stack for state saving."""
        result = []
        for ctx in self._stack:
            result.append(ctx.copy())
        return result

    def restore_from(self, saved_stack: list[ParseContext]) -> None:
        """Restore the context stack from a saved copy."""
        result = []
        for ctx in saved_stack:
            result.append(ctx.copy())
        self._stack = result


class Lexer:
    """Lexer for tokenizing shell input."""

    def __init__(self, source: str, extglob: bool = False):
        self.source = source
        self.pos = 0
        self.length: int = len(source)
        self.quote: QuoteState = QuoteState()
        self._token_cache: Token | None = None
        # Parser state flags for context-sensitive tokenization
        self._parser_state: int = ParserStateFlags.NONE
        self._dolbrace_state: int = DolbraceState.NONE
        # Pending heredocs tracked during word parsing
        self._pending_heredocs: list[Node] = []
        # Extglob parsing enabled (bash shopt extglob)
        self._extglob = extglob
        # Reference to Parser for expansion parsing callbacks (set by Parser)
        self._parser: Parser | None = None
        # EOF token mechanism for command substitution parsing
        self._eof_token: str | None = None
        # Last token returned by next_token (for context-sensitive parsing)
        self._last_read_token: Token | None = None
        # Word parsing context (set by Parser before peeking)
        self._word_context: int = WORD_CTX_NORMAL
        self._at_command_start = False
        self._in_array_literal = False
        self._in_assign_builtin = False
        # Position after reading a token (may differ from token.pos due to heredocs)
        self._post_read_pos: int = 0
        # Context used when token was cached (for cache invalidation)
        self._cached_word_context: int = WORD_CTX_NORMAL
        self._cached_at_command_start: bool = False
        self._cached_in_array_literal: bool = False
        self._cached_in_assign_builtin: bool = False

    def peek(self) -> str | None:
        """Return current character without consuming."""
        if self.pos >= self.length:
            return None
        return self.source[self.pos]

    def advance(self) -> str | None:
        """Consume and return current character."""
        if self.pos >= self.length:
            return None
        c = self.source[self.pos]
        self.pos += 1
        return c

    def at_end(self) -> bool:
        """Return True if at end of input."""
        return self.pos >= self.length

    def lookahead(self, n: int) -> str:
        """Return next n characters without consuming."""
        return _substring(self.source, self.pos, self.pos + n)

    def is_metachar(self, c: str) -> bool:
        """Return True if c is a shell metacharacter."""
        return c in "|&;()<> \t\n"

    def _read_operator(self) -> Token | None:
        """Try to read an operator token. Returns None if not at operator."""
        start = self.pos
        c = self.peek()
        if c is None:
            return None
        two = self.lookahead(2)
        three = self.lookahead(3)
        # Three-char operators
        if three == ";;&":
            self.pos += 3
            return Token(TokenType.SEMI_SEMI_AMP, three, start)
        if three == "<<-":
            self.pos += 3
            return Token(TokenType.LESS_LESS_MINUS, three, start)
        if three == "<<<":
            self.pos += 3
            return Token(TokenType.LESS_LESS_LESS, three, start)
        if three == "&>>":
            self.pos += 3
            return Token(TokenType.AMP_GREATER_GREATER, three, start)
        # Two-char operators
        if two == "&&":
            self.pos += 2
            return Token(TokenType.AND_AND, two, start)
        if two == "||":
            self.pos += 2
            return Token(TokenType.OR_OR, two, start)
        if two == ";;":
            self.pos += 2
            return Token(TokenType.SEMI_SEMI, two, start)
        if two == ";&":
            self.pos += 2
            return Token(TokenType.SEMI_AMP, two, start)
        if two == "<<":
            self.pos += 2
            return Token(TokenType.LESS_LESS, two, start)
        if two == ">>":
            self.pos += 2
            return Token(TokenType.GREATER_GREATER, two, start)
        if two == "<&":
            self.pos += 2
            return Token(TokenType.LESS_AMP, two, start)
        if two == ">&":
            self.pos += 2
            return Token(TokenType.GREATER_AMP, two, start)
        if two == "<>":
            self.pos += 2
            return Token(TokenType.LESS_GREATER, two, start)
        if two == ">|":
            self.pos += 2
            return Token(TokenType.GREATER_PIPE, two, start)
        if two == "&>":
            self.pos += 2
            return Token(TokenType.AMP_GREATER, two, start)
        if two == "|&":
            self.pos += 2
            return Token(TokenType.PIPE_AMP, two, start)
        # Single-char operators
        if c == ";":
            self.pos += 1
            return Token(TokenType.SEMI, c, start)
        if c == "|":
            self.pos += 1
            return Token(TokenType.PIPE, c, start)
        if c == "&":
            self.pos += 1
            return Token(TokenType.AMP, c, start)
        if c == "(":
            # In REGEX context, ( is regex grouping, not operator
            if self._word_context == WORD_CTX_REGEX:
                return None
            self.pos += 1
            return Token(TokenType.LPAREN, c, start)
        if c == ")":
            # In REGEX context, ) is regex grouping, not operator
            if self._word_context == WORD_CTX_REGEX:
                return None
            self.pos += 1
            return Token(TokenType.RPAREN, c, start)
        if c == "<":
            # <( is process substitution, not operator
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                return None
            self.pos += 1
            return Token(TokenType.LESS, c, start)
        if c == ">":
            # >( is process substitution, not operator
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                return None
            self.pos += 1
            return Token(TokenType.GREATER, c, start)
        if c == "\n":
            self.pos += 1
            return Token(TokenType.NEWLINE, c, start)
        return None

    def skip_blanks(self) -> None:
        """Skip spaces and tabs (not newlines)."""
        while self.pos < self.length:
            c = self.source[self.pos]
            if c != " " and c != "\t":
                break
            self.pos += 1

    def _skip_comment(self) -> bool:
        """Skip comment if at # in comment-allowed context. Returns True if skipped."""
        if self.pos >= self.length:
            return False
        if self.source[self.pos] != "#":
            return False
        if self.quote.in_quotes():
            return False
        # Check if in comment-allowed position (start of line or after blank/meta)
        if self.pos > 0:
            prev = self.source[self.pos - 1]
            if prev not in " \t\n;|&(){}":
                return False
        # Skip to end of line
        while self.pos < self.length and self.source[self.pos] != "\n":
            self.pos += 1
        return True

    def _read_single_quote(self, start: int) -> tuple[str, bool]:
        """Read single-quoted string content for word parsing.

        Assumes opening quote already consumed.
        Returns (content_with_quotes, saw_newline).
        Raises ParseError if unterminated.
        """
        chars = ["'"]
        saw_newline = False
        while self.pos < self.length:
            c = self.source[self.pos]
            if c == "\n":
                saw_newline = True
            chars.append(c)
            self.pos += 1
            if c == "'":
                return "".join(chars), saw_newline
        raise ParseError("Unterminated single quote", pos=start)

    def _is_word_terminator(
        self, ctx: int, ch: str, bracket_depth: int = 0, paren_depth: int = 0
    ) -> bool:
        """Check if character terminates word in given context."""
        if ctx == WORD_CTX_REGEX:
            if ch == "]" and self.pos + 1 < self.length and self.source[self.pos + 1] == "]":
                return True
            if ch == "&" and self.pos + 1 < self.length and self.source[self.pos + 1] == "&":
                return True
            if ch == ")" and paren_depth == 0:
                return True
            return _is_whitespace(ch) and paren_depth == 0
        if ctx == WORD_CTX_COND:
            if ch == "]" and self.pos + 1 < self.length and self.source[self.pos + 1] == "]":
                return True
            # ) always terminates, but ( is handled in the loop for extglob
            if ch == ")":
                return True
            if ch == "&":
                return True
            if ch == "|":
                return True
            if ch == ";":
                return True
            # < and > terminate unless followed by ( (process sub)
            if _is_redirect_char(ch) and not (
                self.pos + 1 < self.length and self.source[self.pos + 1] == "("
            ):
                return True
            return _is_whitespace(ch)
        # WORD_CTX_NORMAL
        # PST_EOFTOKEN: EOF token character terminates word at depth 0
        if (
            (self._parser_state & ParserStateFlags.PST_EOFTOKEN)
            and self._eof_token is not None
            and ch == self._eof_token
            and bracket_depth == 0
        ):
            return True
        # < and > don't terminate if followed by ( (process substitution)
        if (
            _is_redirect_char(ch)
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        ):
            return False
        return _is_metachar(ch) and bracket_depth == 0

    def _read_bracket_expression(
        self, chars: list[str], parts: list[Node], for_regex: bool = False, paren_depth: int = 0
    ) -> bool:
        """Scan [...] bracket expression. Returns True if consumed, False if [ is literal.

        For regex mode, calls back to Parser._parse_dollar_expansion for $ expansions.
        """
        if for_regex:
            # Regex mode: lookahead to check if bracket will close before terminators
            scan = self.pos + 1
            if scan < self.length and self.source[scan] == "^":
                scan += 1
            if scan < self.length and self.source[scan] == "]":
                scan += 1
            bracket_will_close = False
            while scan < self.length:
                sc = self.source[scan]
                if sc == "]" and scan + 1 < self.length and self.source[scan + 1] == "]":
                    break
                if sc == ")" and paren_depth > 0:
                    break
                if sc == "&" and scan + 1 < self.length and self.source[scan + 1] == "&":
                    break
                if sc == "]":
                    bracket_will_close = True
                    break
                if sc == "[" and scan + 1 < self.length and self.source[scan + 1] == ":":
                    scan += 2
                    while scan < self.length and not (
                        self.source[scan] == ":"
                        and scan + 1 < self.length
                        and self.source[scan + 1] == "]"
                    ):
                        scan += 1
                    if scan < self.length:
                        scan += 2
                    continue
                scan += 1
            if not bracket_will_close:
                return False
        else:
            # Cond mode: check for [ followed by whitespace/operators
            if self.pos + 1 >= self.length:
                return False
            next_ch = self.source[self.pos + 1]
            if _is_whitespace_no_newline(next_ch) or next_ch == "&" or next_ch == "|":
                return False
        chars.append(self.advance())  # consume [
        # Handle negation [^
        if not self.at_end() and self.peek() == "^":
            chars.append(self.advance())
        # Handle ] as first char (literal ])
        if not self.at_end() and self.peek() == "]":
            chars.append(self.advance())
        # Consume until closing ]
        while not self.at_end():
            c = self.peek()
            if c == "]":
                chars.append(self.advance())
                break
            if c == "[" and self.pos + 1 < self.length and self.source[self.pos + 1] == ":":
                chars.append(self.advance())  # [
                chars.append(self.advance())  # :
                while not self.at_end() and not (
                    self.peek() == ":"
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "]"
                ):
                    chars.append(self.advance())
                if not self.at_end():
                    chars.append(self.advance())  # :
                    chars.append(self.advance())  # ]
            elif (
                not for_regex
                and c == "["
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "="
            ):
                chars.append(self.advance())  # [
                chars.append(self.advance())  # =
                while not self.at_end() and not (
                    self.peek() == "="
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "]"
                ):
                    chars.append(self.advance())
                if not self.at_end():
                    chars.append(self.advance())  # =
                    chars.append(self.advance())  # ]
            elif (
                not for_regex
                and c == "["
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "."
            ):
                chars.append(self.advance())  # [
                chars.append(self.advance())  # .
                while not self.at_end() and not (
                    self.peek() == "."
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "]"
                ):
                    chars.append(self.advance())
                if not self.at_end():
                    chars.append(self.advance())  # .
                    chars.append(self.advance())  # ]
            elif for_regex and c == "$":
                # Callback to Parser for dollar expansion
                self._sync_to_parser()
                if not self._parser._parse_dollar_expansion(chars, parts):
                    self._sync_from_parser()
                    chars.append(self.advance())
                else:
                    self._sync_from_parser()
            else:
                chars.append(self.advance())
        return True

    def _parse_matched_pair(
        self,
        open_char: str,
        close_char: str,
        flags: int = 0,
        initial_was_dollar: bool = False,
    ) -> str:
        """Parse a matched pair construct, handling quotes via recursion.

        This is the unified approach based on bash's parse_matched_pair().
        Quotes are handled by recursive calls where the quote is both open and close.

        Args:
            open_char: Opening delimiter (e.g., '(', '{', '[', '"', "'")
            close_char: Closing delimiter (e.g., ')', '}', ']', '"', "'")
            flags: MatchedPairFlags controlling behavior

        Returns:
            The content between delimiters (not including the delimiters themselves).

        Raises:
            MatchedPairError: If EOF is reached before finding the closing delimiter.
        """
        start = self.pos
        count = 1
        chars: list[str] = []
        pass_next = False
        was_dollar = initial_was_dollar  # Track if previous char was $ (bash's LEX_WASDOL)
        was_gtlt = False  # Track if previous char was < or > (bash's LEX_GTLT)

        while count > 0:
            if self.at_end():
                raise MatchedPairError(
                    f"unexpected EOF while looking for matching `{close_char}'",
                    pos=start,
                )

            ch = self.advance()

            # OP -> WORD transition in DOLBRACE mode
            if (flags & MatchedPairFlags.DOLBRACE) and self._dolbrace_state == DolbraceState.OP:
                if ch not in "#%^,~:-=?+/":
                    self._dolbrace_state = DolbraceState.WORD

            # Backslash escape handling - pass through next char
            if pass_next:
                pass_next = False
                chars.append(ch)
                was_dollar = ch == "$"
                was_gtlt = ch in "<>"
                continue

            # Inside single quotes, almost everything is literal
            if open_char == "'":
                if ch == close_char:
                    count -= 1
                    if count == 0:
                        break
                # In $'...' mode, backslash escapes are processed
                if ch == "\\" and (flags & MatchedPairFlags.ALLOWESC):
                    pass_next = True
                chars.append(ch)
                was_dollar = False
                was_gtlt = False
                continue

            # Backslash - set pass_next flag
            if ch == "\\":
                # Line continuation - skip \n
                if not self.at_end() and self.peek() == "\n":
                    self.advance()
                    was_dollar = False
                    was_gtlt = False
                    continue
                pass_next = True
                chars.append(ch)
                was_dollar = False
                was_gtlt = False
                continue

            # Closing delimiter
            if ch == close_char:
                count -= 1
                if count == 0:
                    break
                chars.append(ch)
                was_dollar = False
                was_gtlt = ch in "<>"
                continue

            # Opening delimiter (only when open != close)
            # In DOLBRACE mode, don't track bare '{' - only ${...} nesting matters
            # (handled by the $ block below via recursion)
            if ch == open_char and open_char != close_char:
                if not (flags & MatchedPairFlags.DOLBRACE and open_char == "{"):
                    count += 1
                chars.append(ch)
                was_dollar = False
                was_gtlt = ch in "<>"
                continue

            # Quote characters trigger recursion (when not already in quote mode)
            if ch in "'\"`" and open_char != close_char:
                if ch == "'":
                    # Single quote - recursively parse until matching '
                    # If previous char was $, this is ANSI-C $'...' quoting with escapes
                    chars.append(ch)
                    quote_flags = flags | MatchedPairFlags.ALLOWESC if was_dollar else flags
                    nested = self._parse_matched_pair("'", "'", quote_flags)
                    chars.append(nested)
                    chars.append("'")
                    was_dollar = False
                    was_gtlt = False
                    continue
                elif ch == '"':
                    # Double quote - recursively parse until matching "
                    chars.append(ch)
                    nested = self._parse_matched_pair('"', '"', flags | MatchedPairFlags.DQUOTE)
                    chars.append(nested)
                    chars.append('"')
                    was_dollar = False
                    was_gtlt = False
                    continue
                elif ch == "`":
                    # Backtick - recursively parse until matching `
                    chars.append(ch)
                    nested = self._parse_matched_pair("`", "`", flags)
                    chars.append(nested)
                    chars.append("`")
                    was_dollar = False
                    was_gtlt = False
                    continue

            # ${ $( $[ trigger nested parsing (unless in extglob where they're just pattern chars)
            if ch == "$" and not self.at_end() and not (flags & MatchedPairFlags.EXTGLOB):
                next_ch = self.peek()
                # If previous char was $, this is the second $ in $$ - treat as unit
                # Reset was_dollar so next char doesn't think it follows single $
                if was_dollar:
                    chars.append(ch)
                    was_dollar = False  # $$ is a unit, next char is NOT preceded by single $
                    was_gtlt = False
                    continue
                if next_ch == "{":
                    # In ARITH mode, only parse ${ if followed by funsub char (bash parse.y:4137-4145)
                    # Otherwise treat $ as literal
                    if flags & MatchedPairFlags.ARITH:
                        after_brace_pos = self.pos + 1
                        if after_brace_pos >= self.length or not _is_funsub_char(
                            self.source[after_brace_pos]
                        ):
                            # Not funsub - treat $ as literal
                            chars.append(ch)
                            was_dollar = True
                            was_gtlt = False
                            continue
                    # ${ ... } parameter expansion - use full parsing
                    self.pos -= 1  # back up to before $
                    self._sync_to_parser()
                    in_dquote = bool(flags & MatchedPairFlags.DQUOTE)
                    param_node, param_text = self._parser._parse_param_expansion(in_dquote)
                    self._sync_from_parser()
                    if param_node:
                        chars.append(param_text)
                        was_dollar = False  # Ended with }
                        was_gtlt = False
                    else:
                        # Parser failed - add $ as literal
                        chars.append(self.advance())  # $
                        was_dollar = True
                        was_gtlt = False
                    continue
                elif next_ch == "(":
                    # Back up to before $ for Parser callback
                    self.pos -= 1
                    self._sync_to_parser()
                    # Check if $(( arithmetic or $( command substitution
                    if self.pos + 2 < self.length and self.source[self.pos + 2] == "(":
                        # $(( ... )) arithmetic - use full parsing
                        arith_node, arith_text = self._parser._parse_arithmetic_expansion()
                        self._sync_from_parser()
                        if arith_node:
                            chars.append(arith_text)
                            was_dollar = False  # Ended with ))
                            was_gtlt = False
                        else:
                            # Arithmetic failed - try as command substitution fallback
                            self._sync_to_parser()
                            cmd_node, cmd_text = self._parser._parse_command_substitution()
                            self._sync_from_parser()
                            if cmd_node:
                                chars.append(cmd_text)
                                was_dollar = False  # Ended with )
                                was_gtlt = False
                            else:
                                # Both failed - add $( as literal
                                chars.append(self.advance())  # $
                                chars.append(self.advance())  # (
                                was_dollar = False  # Ended with (
                                was_gtlt = False
                    else:
                        # $( ... ) command substitution - use full parsing
                        cmd_node, cmd_text = self._parser._parse_command_substitution()
                        self._sync_from_parser()
                        if cmd_node:
                            chars.append(cmd_text)
                            was_dollar = False  # Ended with )
                            was_gtlt = False
                        else:
                            # Parser failed - add $( as literal
                            chars.append(self.advance())  # $
                            chars.append(self.advance())  # (
                            was_dollar = False  # Ended with (
                            was_gtlt = False
                    continue
                elif next_ch == "[":
                    # Deprecated $[ ... ] arithmetic - use full parsing
                    self.pos -= 1  # back up to before $
                    self._sync_to_parser()
                    arith_node, arith_text = self._parser._parse_deprecated_arithmetic()
                    self._sync_from_parser()
                    if arith_node:
                        chars.append(arith_text)
                        was_dollar = False  # Ended with ]
                        was_gtlt = False
                    else:
                        # Parser failed - add $ as literal
                        chars.append(self.advance())  # $
                        was_dollar = True
                        was_gtlt = False
                    continue

            # Process substitution <(...) or >(...) inside ${...} or array subscripts
            # (bash's LEX_GTLT check at parse.y:4151-4160)
            if (
                ch == "("
                and was_gtlt
                and (flags & (MatchedPairFlags.DOLBRACE | MatchedPairFlags.ARRAYSUB))
            ):
                # Back up: remove the < or > we already added to chars
                direction = chars.pop()
                self.pos -= 1  # Back up before (
                self._sync_to_parser()
                procsub_node, procsub_text = self._parser._parse_process_substitution()
                self._sync_from_parser()
                if procsub_node:
                    chars.append(procsub_text)
                    was_dollar = False
                    was_gtlt = False
                else:
                    # Failed - restore the < or > and (
                    chars.append(direction)
                    chars.append(self.advance())  # (
                    was_dollar = False
                    was_gtlt = False
                continue

            chars.append(ch)
            was_dollar = ch == "$"
            was_gtlt = ch in "<>"

        return "".join(chars)

    def _collect_param_argument(
        self, flags: int = MatchedPairFlags.NONE, was_dollar: bool = False
    ) -> str:
        """Collect argument portion of ${...} until closing brace.

        Wraps _parse_matched_pair() with DOLBRACE flag for parameter expansion arguments.
        was_dollar should be True if the param name ended with $ (for $$ handling).
        """
        return self._parse_matched_pair("{", "}", flags | MatchedPairFlags.DOLBRACE, was_dollar)

    def _read_word_internal(
        self,
        ctx: int,
        at_command_start: bool = False,
        in_array_literal: bool = False,
        in_assign_builtin: bool = False,
    ) -> Word | None:
        """Unified word parser with context-aware termination.

        Uses callbacks to Parser for methods that need parse_list or other parsing.
        """
        start = self.pos
        chars: list[str] = []
        parts: list[Node] = []
        bracket_depth = 0  # Track [...] for array subscripts (NORMAL only)
        bracket_start_pos: int = -1  # Position where bracket tracking started (-1 = not set)
        seen_equals = False  # Track if we've seen = (NORMAL only)
        paren_depth = 0  # Track regex grouping parens (REGEX only)
        while not self.at_end():
            ch = self.peek()
            # REGEX: Backslash-newline continuation (check first)
            if ctx == WORD_CTX_REGEX:
                if ch == "\\" and self.pos + 1 < self.length and self.source[self.pos + 1] == "\n":
                    self.advance()
                    self.advance()
                    continue
            # Check termination for COND and REGEX contexts (NORMAL checks at end)
            if ctx != WORD_CTX_NORMAL and self._is_word_terminator(
                ctx, ch, bracket_depth, paren_depth
            ):
                break
            # NORMAL: Array subscript tracking
            if ctx == WORD_CTX_NORMAL and ch == "[":
                if bracket_depth > 0:
                    bracket_depth += 1
                    chars.append(self.advance())
                    continue
                if (
                    chars
                    and at_command_start
                    and not seen_equals
                    and _is_array_assignment_prefix(chars)
                ):
                    prev_char = chars[len(chars) - 1]
                    if prev_char.isalnum() or prev_char == "_":
                        bracket_start_pos = self.pos
                        bracket_depth += 1
                        chars.append(self.advance())
                        continue
                if not chars and not seen_equals and in_array_literal:
                    bracket_start_pos = self.pos
                    bracket_depth += 1
                    chars.append(self.advance())
                    continue
            if ctx == WORD_CTX_NORMAL and ch == "]" and bracket_depth > 0:
                bracket_depth -= 1
                chars.append(self.advance())
                continue
            if ctx == WORD_CTX_NORMAL and ch == "=" and bracket_depth == 0:
                seen_equals = True
            # REGEX: Track paren depth
            if ctx == WORD_CTX_REGEX and ch == "(":
                paren_depth += 1
                chars.append(self.advance())
                continue
            if ctx == WORD_CTX_REGEX and ch == ")":
                if paren_depth > 0:
                    paren_depth -= 1
                    chars.append(self.advance())
                    continue
                break
            # COND/REGEX: Bracket expressions
            if ctx in (WORD_CTX_COND, WORD_CTX_REGEX) and ch == "[":
                for_regex = ctx == WORD_CTX_REGEX
                if self._read_bracket_expression(
                    chars, parts, for_regex=for_regex, paren_depth=paren_depth
                ):
                    continue
                chars.append(self.advance())
                continue
            # COND: Extglob patterns or ( terminates
            if ctx == WORD_CTX_COND and ch == "(":
                if self._extglob and chars and _is_extglob_prefix(chars[len(chars) - 1]):
                    chars.append(self.advance())  # (
                    content = self._parse_matched_pair("(", ")", MatchedPairFlags.EXTGLOB)
                    chars.append(content)
                    chars.append(")")
                    continue
                else:
                    # ( without extglob prefix terminates the word
                    break
            # REGEX: Space inside parens is part of pattern
            if ctx == WORD_CTX_REGEX and _is_whitespace(ch) and paren_depth > 0:
                chars.append(self.advance())
                continue
            # Single-quoted string
            if ch == "'":
                self.advance()
                track_newline = ctx == WORD_CTX_NORMAL
                content, saw_newline = self._read_single_quote(start)
                chars.append(content)
                if track_newline and saw_newline and self._parser is not None:
                    self._parser._saw_newline_in_single_quote = True
                continue
            # Double-quoted string
            if ch == '"':
                self.advance()
                if ctx == WORD_CTX_NORMAL:
                    # NORMAL has special in_single_in_dquote and backtick handling
                    chars.append('"')
                    in_single_in_dquote = False
                    while not self.at_end() and (in_single_in_dquote or self.peek() != '"'):
                        c = self.peek()
                        if in_single_in_dquote:
                            chars.append(self.advance())
                            if c == "'":
                                in_single_in_dquote = False
                            continue
                        if c == "\\" and self.pos + 1 < self.length:
                            next_c = self.source[self.pos + 1]
                            if next_c == "\n":
                                self.advance()
                                self.advance()
                            else:
                                chars.append(self.advance())
                                chars.append(self.advance())
                        elif c == "$":
                            # Callback to Parser for dollar expansion (inside dquote)
                            self._sync_to_parser()
                            if not self._parser._parse_dollar_expansion(
                                chars, parts, in_dquote=True
                            ):
                                self._sync_from_parser()
                                chars.append(self.advance())
                            else:
                                self._sync_from_parser()
                        elif c == "`":
                            # Callback to Parser for backtick substitution
                            self._sync_to_parser()
                            cmdsub_result = self._parser._parse_backtick_substitution()
                            self._sync_from_parser()
                            if cmdsub_result[0]:
                                parts.append(cmdsub_result[0])
                                chars.append(cmdsub_result[1])
                            else:
                                chars.append(self.advance())
                        else:
                            chars.append(self.advance())
                    if self.at_end():
                        raise ParseError("Unterminated double quote", pos=start)
                    chars.append(self.advance())
                else:
                    # COND/REGEX modes - callback to Parser's _scan_double_quote
                    handle_line_continuation = ctx == WORD_CTX_COND
                    self._sync_to_parser()
                    self._parser._scan_double_quote(chars, parts, start, handle_line_continuation)
                    self._sync_from_parser()
                continue
            # Escape
            if ch == "\\" and self.pos + 1 < self.length:
                next_ch = self.source[self.pos + 1]
                if ctx != WORD_CTX_REGEX and next_ch == "\n":
                    self.advance()
                    self.advance()
                else:
                    chars.append(self.advance())
                    chars.append(self.advance())
                continue
            # NORMAL/COND: ANSI-C quoting $'...'
            if (
                ctx != WORD_CTX_REGEX
                and ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "'"
            ):
                ansi_result = self._read_ansi_c_quote()
                if ansi_result[0]:
                    parts.append(ansi_result[0])
                    chars.append(ansi_result[1])
                else:
                    chars.append(self.advance())
                continue
            # NORMAL/COND: Locale translation $"..."
            if (
                ctx != WORD_CTX_REGEX
                and ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == '"'
            ):
                locale_result = self._read_locale_string()
                if locale_result[0]:
                    parts.append(locale_result[0])
                    parts.extend(locale_result[2])
                    chars.append(locale_result[1])
                else:
                    chars.append(self.advance())
                continue
            # Dollar expansions - callback to Parser
            if ch == "$":
                self._sync_to_parser()
                if not self._parser._parse_dollar_expansion(chars, parts):
                    self._sync_from_parser()
                    chars.append(self.advance())
                else:
                    self._sync_from_parser()
                    # Special params $? $* $@ can be followed by () as extglob pattern
                    if (
                        self._extglob
                        and ctx == WORD_CTX_NORMAL
                        and chars
                        and len(chars[len(chars) - 1]) == 2
                        and chars[len(chars) - 1][0] == "$"
                        and chars[len(chars) - 1][1] in "?*@"
                        and not self.at_end()
                        and self.peek() == "("
                    ):
                        chars.append(self.advance())  # (
                        content = self._parse_matched_pair("(", ")", MatchedPairFlags.EXTGLOB)
                        chars.append(content)
                        chars.append(")")
                continue
            # NORMAL/COND: Backtick command substitution - callback to Parser
            if ctx != WORD_CTX_REGEX and ch == "`":
                self._sync_to_parser()
                cmdsub_result = self._parser._parse_backtick_substitution()
                self._sync_from_parser()
                if cmdsub_result[0]:
                    parts.append(cmdsub_result[0])
                    chars.append(cmdsub_result[1])
                else:
                    chars.append(self.advance())
                continue
            # NORMAL/COND: Process substitution <(...) or >(...) - callback to Parser
            if (
                ctx != WORD_CTX_REGEX
                and _is_redirect_char(ch)
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                self._sync_to_parser()
                procsub_result = self._parser._parse_process_substitution()
                self._sync_from_parser()
                if procsub_result[0]:
                    parts.append(procsub_result[0])
                    chars.append(procsub_result[1])
                elif procsub_result[1]:
                    chars.append(procsub_result[1])
                else:
                    chars.append(self.advance())
                    if ctx == WORD_CTX_NORMAL:
                        chars.append(self.advance())
                continue
            # NORMAL: Array literal - callback to Parser
            # Only if there's a valid variable name before = or +=
            if ctx == WORD_CTX_NORMAL and ch == "(" and chars and bracket_depth == 0:
                is_array_assign = False
                # Check += first (before =) since += ends with =
                if (
                    len(chars) >= 3
                    and chars[len(chars) - 2] == "+"
                    and chars[len(chars) - 1] == "="
                ):
                    # Check chars before += form valid name
                    is_array_assign = _is_array_assignment_prefix(chars[:-2])
                elif chars[len(chars) - 1] == "=" and len(chars) >= 2:
                    # Check chars before = form valid name
                    is_array_assign = _is_array_assignment_prefix(chars[:-1])
                if is_array_assign and (at_command_start or in_assign_builtin):
                    self._sync_to_parser()
                    array_result = self._parser._parse_array_literal()
                    self._sync_from_parser()
                    if array_result[0]:
                        parts.append(array_result[0])
                        chars.append(array_result[1])
                    else:
                        break
                    continue
            # NORMAL: Extglob pattern @(), ?(), *(), +(), !()
            if (
                self._extglob
                and ctx == WORD_CTX_NORMAL
                and _is_extglob_prefix(ch)
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                chars.append(self.advance())  # @, ?, *, +, or !
                chars.append(self.advance())  # (
                content = self._parse_matched_pair("(", ")", MatchedPairFlags.EXTGLOB)
                chars.append(content)
                chars.append(")")
                continue
            # NORMAL: PST_EOFTOKEN - EOF token character terminates word at depth 0
            # But if we haven't read anything yet, read it as a single-char word
            if (
                ctx == WORD_CTX_NORMAL
                and (self._parser_state & ParserStateFlags.PST_EOFTOKEN)
                and self._eof_token is not None
                and ch == self._eof_token
                and bracket_depth == 0
            ):
                if not chars:
                    chars.append(self.advance())
                break
            # NORMAL: Metacharacter terminates word (unless inside brackets)
            if ctx == WORD_CTX_NORMAL and _is_metachar(ch) and bracket_depth == 0:
                break
            # Regular character
            chars.append(self.advance())
        # Check for unclosed bracket at EOF
        if bracket_depth > 0 and bracket_start_pos != -1 and self.at_end():
            raise MatchedPairError("unexpected EOF looking for `]'", pos=bracket_start_pos)
        if not chars:
            return None
        if parts:
            return Word("".join(chars), parts)
        return Word("".join(chars), None)

    def _read_word(self) -> Token | None:
        """Read a word token using _read_word_internal with current context."""
        start = self.pos
        if self.pos >= self.length:
            return None
        c = self.peek()
        if c is None:
            return None
        # Allow process substitution <( and >( even though < and > are metachars
        is_procsub = (
            (c == "<" or c == ">")
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        )
        # In REGEX context, ( and ) are regex grouping, not metachars
        is_regex_paren = self._word_context == WORD_CTX_REGEX and (c == "(" or c == ")")
        if self.is_metachar(c) and not is_procsub and not is_regex_paren:
            return None
        word = self._read_word_internal(
            self._word_context,
            self._at_command_start,
            self._in_array_literal,
            self._in_assign_builtin,
        )
        if word is None:
            return None
        return Token(TokenType.WORD, word.value, start, None, word)

    def next_token(self) -> Token:
        """Return the next token from the input."""
        if self._token_cache is not None:
            tok = self._token_cache
            self._token_cache = None
            self._last_read_token = tok
            return tok
        self.skip_blanks()
        if self.at_end():
            tok = Token(TokenType.EOF, "", self.pos)
            self._last_read_token = tok
            return tok
        # EOF token mechanism: return EOF when we hit the closing delimiter at depth 0
        # PST_EOFTOKEN: let normal tokenization proceed, grammar will handle it
        if (
            self._eof_token is not None
            and self.peek() == self._eof_token
            and not (self._parser_state & ParserStateFlags.PST_CASEPAT)
            and not (self._parser_state & ParserStateFlags.PST_EOFTOKEN)
        ):
            tok = Token(TokenType.EOF, "", self.pos)
            self._last_read_token = tok
            return tok
        while self._skip_comment():
            self.skip_blanks()
            if self.at_end():
                tok = Token(TokenType.EOF, "", self.pos)
                self._last_read_token = tok
                return tok
            # Check EOF token again after comment
            if (
                self._eof_token is not None
                and self.peek() == self._eof_token
                and not (self._parser_state & ParserStateFlags.PST_CASEPAT)
                and not (self._parser_state & ParserStateFlags.PST_EOFTOKEN)
            ):
                tok = Token(TokenType.EOF, "", self.pos)
                self._last_read_token = tok
                return tok
        tok = self._read_operator()
        if tok is not None:
            self._last_read_token = tok
            return tok
        tok = self._read_word()
        if tok is not None:
            self._last_read_token = tok
            return tok
        tok = Token(TokenType.EOF, "", self.pos)
        self._last_read_token = tok
        return tok

    def peek_token(self) -> Token:
        """Peek at next token without consuming."""
        if self._token_cache is None:
            saved_last = self._last_read_token
            self._token_cache = self.next_token()
            self._last_read_token = saved_last  # Peeking shouldn't advance history
        return self._token_cache

    def _read_ansi_c_quote(self) -> tuple[Node | None, str]:
        """Read ANSI-C quoting $'...'.

        Returns (node, text) where node is the AST node and text is the raw text.
        Returns (None, "") if not a valid ANSI-C quote.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != "'":
            return None, ""
        start = self.pos
        self.advance()  # consume $
        self.advance()  # consume opening '
        content_chars: list[str] = []
        found_close = False
        while not self.at_end():
            ch = self.peek()
            if ch == "'":
                self.advance()  # consume closing '
                found_close = True
                break
            elif ch == "\\":
                # Escape sequence - include both backslash and following char
                content_chars.append(self.advance())  # backslash
                if not self.at_end():
                    content_chars.append(self.advance())  # escaped char
            else:
                content_chars.append(self.advance())
        if not found_close:
            # Unterminated ANSI-C quote - this is an error, not a fallback
            raise MatchedPairError("unexpected EOF while looking for matching `''", pos=start)
        text = _substring(self.source, start, self.pos)
        content = "".join(content_chars)
        node = AnsiCQuote(content)
        return node, text

    def _sync_to_parser(self) -> None:
        """Sync Parser position to Lexer position before calling Parser methods."""
        if self._parser is not None:
            self._parser.pos = self.pos

    def _sync_from_parser(self) -> None:
        """Sync Lexer position from Parser position after calling Parser methods."""
        if self._parser is not None:
            self.pos = self._parser.pos

    def _read_locale_string(self) -> tuple[Node | None, str, list[Node]]:
        """Read locale translation $"...".

        Returns (node, text, inner_parts) where:
        - node is the LocaleString AST node
        - text is the raw text including $"..."
        - inner_parts is a list of expansion nodes found inside
        Returns (None, "", []) if not a valid locale string.
        """
        if self.at_end() or self.peek() != "$":
            return None, "", []
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != '"':
            return None, "", []
        start = self.pos
        self.advance()  # consume $
        self.advance()  # consume opening "
        content_chars: list[str] = []
        inner_parts: list[Node] = []
        found_close = False
        while not self.at_end():
            ch = self.peek()
            if ch == '"':
                self.advance()  # consume closing "
                found_close = True
                break
            elif ch == "\\" and self.pos + 1 < self.length:
                # Escape sequence (line continuation removes both)
                next_ch = self.source[self.pos + 1]
                if next_ch == "\n":
                    # Line continuation - skip both backslash and newline
                    self.advance()
                    self.advance()
                else:
                    content_chars.append(self.advance())  # backslash
                    content_chars.append(self.advance())  # escaped char
            # Handle arithmetic expansion $((...))
            elif (
                ch == "$"
                and self.pos + 2 < self.length
                and self.source[self.pos + 1] == "("
                and self.source[self.pos + 2] == "("
            ):
                # Delegate to Parser (sync positions for callback)
                self._sync_to_parser()
                arith_node, arith_text = self._parser._parse_arithmetic_expansion()
                self._sync_from_parser()
                if arith_node:
                    inner_parts.append(arith_node)
                    content_chars.append(arith_text)
                else:
                    # Not arithmetic - try command substitution
                    self._sync_to_parser()
                    cmdsub_node, cmdsub_text = self._parser._parse_command_substitution()
                    self._sync_from_parser()
                    if cmdsub_node:
                        inner_parts.append(cmdsub_node)
                        content_chars.append(cmdsub_text)
                    else:
                        content_chars.append(self.advance())
            # Handle command substitution $(...)
            elif _is_expansion_start(self.source, self.pos, "$("):
                self._sync_to_parser()
                cmdsub_node, cmdsub_text = self._parser._parse_command_substitution()
                self._sync_from_parser()
                if cmdsub_node:
                    inner_parts.append(cmdsub_node)
                    content_chars.append(cmdsub_text)
                else:
                    content_chars.append(self.advance())
            # Handle parameter expansion
            elif ch == "$":
                self._sync_to_parser()
                param_node, param_text = self._parser._parse_param_expansion()
                self._sync_from_parser()
                if param_node:
                    inner_parts.append(param_node)
                    content_chars.append(param_text)
                else:
                    content_chars.append(self.advance())
            # Handle backtick command substitution
            elif ch == "`":
                self._sync_to_parser()
                cmdsub_node, cmdsub_text = self._parser._parse_backtick_substitution()
                self._sync_from_parser()
                if cmdsub_node:
                    inner_parts.append(cmdsub_node)
                    content_chars.append(cmdsub_text)
                else:
                    content_chars.append(self.advance())
            else:
                content_chars.append(self.advance())
        if not found_close:
            # Unterminated - reset and return None
            self.pos = start
            return None, "", []
        content = "".join(content_chars)
        # Reconstruct text from parsed content (handles line continuation removal)
        text = '$"' + content + '"'
        return LocaleString(content), text, inner_parts

    def _update_dolbrace_for_op(self, op: str | None, has_param: bool) -> None:
        """Update dolbrace state based on operator seen."""
        if self._dolbrace_state == DolbraceState.NONE:
            return
        if op is None or len(op) == 0:
            return
        first_char = op[0]
        if self._dolbrace_state == DolbraceState.PARAM and has_param:
            if first_char in "%#^,":
                self._dolbrace_state = DolbraceState.QUOTE
                return
            if first_char == "/":
                self._dolbrace_state = DolbraceState.QUOTE2
                return
        if self._dolbrace_state == DolbraceState.PARAM:
            if first_char in "#%^,~:-=?+/":
                self._dolbrace_state = DolbraceState.OP

    def _consume_param_operator(self) -> str | None:
        """Consume a parameter expansion operator."""
        if self.at_end():
            return None
        ch = self.peek()
        # Operators with optional colon prefix: :- := :? :+
        if ch == ":":
            self.advance()
            if self.at_end():
                return ":"
            next_ch = self.peek()
            if _is_simple_param_op(next_ch):
                self.advance()
                return ":" + next_ch
            return ":"
        # Operators without colon: - = ? +
        if _is_simple_param_op(ch):
            self.advance()
            return ch
        # Pattern removal: # ## % %%
        if ch == "#":
            self.advance()
            if not self.at_end() and self.peek() == "#":
                self.advance()
                return "##"
            return "#"
        if ch == "%":
            self.advance()
            if not self.at_end() and self.peek() == "%":
                self.advance()
                return "%%"
            return "%"
        # Substitution: / // /# /%
        if ch == "/":
            self.advance()
            if not self.at_end():
                next_ch = self.peek()
                if next_ch == "/":
                    self.advance()
                    return "//"
                elif next_ch == "#":
                    self.advance()
                    return "/#"
                elif next_ch == "%":
                    self.advance()
                    return "/%"
            return "/"
        # Case modification: ^ ^^ , ,,
        if ch == "^":
            self.advance()
            if not self.at_end() and self.peek() == "^":
                self.advance()
                return "^^"
            return "^"
        if ch == ",":
            self.advance()
            if not self.at_end() and self.peek() == ",":
                self.advance()
                return ",,"
            return ","
        # Transformation: @
        if ch == "@":
            self.advance()
            return "@"
        return None

    def _param_subscript_has_close(self, start_pos: int) -> bool:
        """Check for a matching ] in a parameter subscript before closing }."""
        depth = 1
        i = start_pos + 1
        quote = QuoteState()
        while i < self.length:
            c = self.source[i]
            if quote.single:
                if c == "'":
                    quote.single = False
                i += 1
                continue
            if quote.double:
                if c == "\\" and i + 1 < self.length:
                    i += 2
                    continue
                if c == '"':
                    quote.double = False
                i += 1
                continue
            if c == "'":
                quote.single = True
                i += 1
                continue
            if c == '"':
                quote.double = True
                i += 1
                continue
            if c == "\\":
                i += 2
                continue
            if c == "}":
                return False
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return True
            i += 1
        return False

    def _consume_param_name(self) -> str | None:
        """Consume a parameter name (variable name, special char, or array subscript)."""
        if self.at_end():
            return None
        ch = self.peek()
        # Special parameters (but NOT $ followed by { ' or " - those are special expansions)
        if _is_special_param(ch):
            if ch == "$" and self.pos + 1 < self.length and self.source[self.pos + 1] in "{'\"":
                return None
            self.advance()
            return ch
        # Digits (positional params)
        if ch.isdigit():
            name_chars: list[str] = []
            while not self.at_end() and self.peek().isdigit():
                name_chars.append(self.advance())
            return "".join(name_chars)
        # Variable name
        if ch.isalpha() or ch == "_":
            name_chars = []
            while not self.at_end():
                c = self.peek()
                if c.isalnum() or c == "_":
                    name_chars.append(self.advance())
                elif c == "[":
                    if not self._param_subscript_has_close(self.pos):
                        break
                    # Array subscript - use _parse_matched_pair for bracket/quote handling
                    # ARRAYSUB enables ${} and <() detection inside subscripts
                    name_chars.append(self.advance())  # [
                    content = self._parse_matched_pair("[", "]", MatchedPairFlags.ARRAYSUB)
                    name_chars.append(content)
                    name_chars.append("]")
                    break
                else:
                    break
            if name_chars:
                return "".join(name_chars)
            else:
                return None
        return None

    def _read_param_expansion(self, in_dquote: bool = False) -> tuple[Node | None, str]:
        """Read a parameter expansion starting at $.

        Returns (node, text) where node is the AST node and text is the raw text.
        in_dquote is True if this expansion is inside double quotes.
        Returns (None, "") if not a valid parameter expansion.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""
        start = self.pos
        self.advance()  # consume $
        if self.at_end():
            self.pos = start
            return None, ""
        ch = self.peek()
        # Braced expansion ${...}
        if ch == "{":
            self.advance()  # consume {
            return self._read_braced_param(start, in_dquote)
        # Simple expansion $var or $special
        if _is_special_param_unbraced(ch) or _is_digit(ch) or ch == "#":
            self.advance()
            text = _substring(self.source, start, self.pos)
            return ParamExpansion(ch), text
        # Variable name [a-zA-Z_][a-zA-Z0-9_]*
        if ch.isalpha() or ch == "_":
            name_start = self.pos
            while not self.at_end():
                c = self.peek()
                if c.isalnum() or c == "_":
                    self.advance()
                else:
                    break
            name = _substring(self.source, name_start, self.pos)
            text = _substring(self.source, start, self.pos)
            return ParamExpansion(name), text
        # Not a valid expansion, restore position
        self.pos = start
        return None, ""

    def _read_braced_param(self, start: int, in_dquote: bool = False) -> tuple[Node | None, str]:
        """Read contents of ${...} after the opening brace.

        start is the position of the $.
        in_dquote is True if this expansion is inside double quotes.
        Returns (node, text).
        """
        if self.at_end():
            raise MatchedPairError("unexpected EOF looking for `}'", pos=start)
        # Save and initialize dolbrace state
        saved_dolbrace = self._dolbrace_state
        self._dolbrace_state = DolbraceState.PARAM
        ch = self.peek()
        # Brace command substitution ${ cmd; } or ${| cmd; }
        if _is_funsub_char(ch):
            self._dolbrace_state = saved_dolbrace
            return self._read_funsub(start)
        # ${#param} - length
        if ch == "#":
            self.advance()
            param = self._consume_param_name()
            if param and not self.at_end() and self.peek() == "}":
                self.advance()
                text = _substring(self.source, start, self.pos)
                self._dolbrace_state = saved_dolbrace
                return ParamLength(param), text
            # Not a simple length expansion - fall through to parse as regular expansion
            self.pos = start + 2  # reset to just after ${
        # ${!param} or ${!param<op><arg>} - indirect
        if ch == "!":
            self.advance()
            while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                self.advance()
            param = self._consume_param_name()
            if param:
                # Skip optional whitespace before closing brace
                while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                    self.advance()
                if not self.at_end() and self.peek() == "}":
                    self.advance()
                    text = _substring(self.source, start, self.pos)
                    self._dolbrace_state = saved_dolbrace
                    return ParamIndirect(param), text
                # ${!prefix@} and ${!prefix*} are prefix matching
                if not self.at_end() and _is_at_or_star(self.peek()):
                    suffix = self.advance()
                    trailing = self._parse_matched_pair("{", "}", MatchedPairFlags.DOLBRACE)
                    text = _substring(self.source, start, self.pos)
                    self._dolbrace_state = saved_dolbrace
                    return ParamIndirect(param + suffix + trailing), text
                # Check for operator (e.g., ${!##} = indirect of # with # op)
                op = self._consume_param_operator()
                if op is None and not self.at_end() and self.peek() not in "}\"'`":
                    op = self.advance()
                if op is not None and op not in "\"'`":
                    arg = self._parse_matched_pair("{", "}", MatchedPairFlags.DOLBRACE)
                    text = _substring(self.source, start, self.pos)
                    self._dolbrace_state = saved_dolbrace
                    return ParamIndirect(param, op, arg), text
                # Fell through - continue to general parsing
                if self.at_end():
                    self._dolbrace_state = saved_dolbrace
                    raise MatchedPairError("unexpected EOF looking for `}'", pos=start)
                self.pos = start + 2  # reset to just after ${
            else:
                # ${! followed by non-param char like | - fall through to regular parsing
                self.pos = start + 2  # reset to just after ${
        # ${param} or ${param<op><arg>}
        param = self._consume_param_name()
        if not param:
            # Allow empty parameter for simple operators like ${:-word}
            if not self.at_end() and (
                self.peek() in "-=+?"
                or (
                    self.peek() == ":"
                    and self.pos + 1 < self.length
                    and _is_simple_param_op(self.source[self.pos + 1])
                )
            ):
                param = ""
            else:
                # Unknown syntax - consume until matching }
                content = self._parse_matched_pair("{", "}", MatchedPairFlags.DOLBRACE)
                text = "${" + content + "}"
                self._dolbrace_state = saved_dolbrace
                return ParamExpansion(content), text
        if self.at_end():
            self._dolbrace_state = saved_dolbrace
            raise MatchedPairError("unexpected EOF looking for `}'", pos=start)
        # Check for closing brace (simple expansion)
        if self.peek() == "}":
            self.advance()
            text = _substring(self.source, start, self.pos)
            self._dolbrace_state = saved_dolbrace
            return ParamExpansion(param), text
        # Parse operator
        op = self._consume_param_operator()
        if op is None:
            # Check for $" or $' which should have $ stripped
            if (
                not self.at_end()
                and self.peek() == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] in ('"', "'")
            ):
                dollar_count = 1 + _count_consecutive_dollars_before(self.source, self.pos)
                if dollar_count % 2 == 1:
                    op = ""
                else:
                    op = self.advance()
            elif not self.at_end() and self.peek() == "`":
                backtick_pos = self.pos
                self.advance()
                while not self.at_end() and self.peek() != "`":
                    bc = self.peek()
                    if bc == "\\" and self.pos + 1 < self.length:
                        next_c = self.source[self.pos + 1]
                        if _is_escape_char_in_backtick(next_c):
                            self.advance()
                    self.advance()
                if self.at_end():
                    self._dolbrace_state = saved_dolbrace
                    raise ParseError("Unterminated backtick", pos=backtick_pos)
                self.advance()
                op = "`"
            elif (
                not self.at_end()
                and self.peek() == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "{"
            ):
                op = ""
            elif not self.at_end() and self.peek() in ("'", '"'):
                # Quotes start the argument, not the operator
                op = ""
            elif not self.at_end() and self.peek() == "\\":
                # Backslash escapes the following character
                op = self.advance()
                if not self.at_end():
                    op += self.advance()
            else:
                op = self.advance()
        # Update dolbrace state based on operator
        self._update_dolbrace_for_op(op, len(param) > 0)
        # Parse argument (everything until closing brace)
        # Pass was_dollar=True if param ends with $ (for $$ handling in nested expansions)
        try:
            flags = MatchedPairFlags.DQUOTE if in_dquote else MatchedPairFlags.NONE
            param_ends_with_dollar = param is not None and param.endswith("$")
            arg = self._collect_param_argument(flags, param_ends_with_dollar)
        except MatchedPairError as e:
            self._dolbrace_state = saved_dolbrace
            raise e
        # Format process substitution content within param expansion
        if op in ("<", ">") and arg.startswith("(") and arg.endswith(")"):
            inner = arg[1:-1]
            try:
                # Use Parser for formatting (calls back via _parser reference)
                sub_parser = Parser(inner, in_process_sub=True, extglob=self._parser._extglob)
                parsed = sub_parser.parse_list()
                if parsed and sub_parser.at_end():
                    formatted = _format_cmdsub_node(parsed, 0, True, False, True)
                    arg = "(" + formatted + ")"
            except Exception:
                pass
        text = "${" + param + op + arg + "}"
        self._dolbrace_state = saved_dolbrace
        return ParamExpansion(param, op, arg), text

    def _read_funsub(self, start: int) -> tuple[Node | None, str]:
        """Read brace command substitution ${ cmd; } or ${| cmd; }."""
        return self._parser._parse_funsub(start)

    # Reserved words mapping
    RESERVED_WORDS: dict[str, int] = {
        "if": TokenType.IF,
        "then": TokenType.THEN,
        "else": TokenType.ELSE,
        "elif": TokenType.ELIF,
        "fi": TokenType.FI,
        "case": TokenType.CASE,
        "esac": TokenType.ESAC,
        "for": TokenType.FOR,
        "while": TokenType.WHILE,
        "until": TokenType.UNTIL,
        "do": TokenType.DO,
        "done": TokenType.DONE,
        "in": TokenType.IN,
        "function": TokenType.FUNCTION,
        "select": TokenType.SELECT,
        "coproc": TokenType.COPROC,
        "time": TokenType.TIME,
        "!": TokenType.BANG,
        "[[": TokenType.LBRACKET_LBRACKET,
        "]]": TokenType.RBRACKET_RBRACKET,
        "{": TokenType.LBRACE,
        "}": TokenType.RBRACE,
    }


def _strip_line_continuations_comment_aware(text: str) -> str:
    """Strip backslash-newline line continuations, preserving newlines in comments.

    In comments, backslash-newline is replaced with just newline (to keep the comment
    terminator). Outside comments, backslash-newline is fully removed.
    """
    result = []
    i = 0
    in_comment = False
    quote = QuoteState()
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] == "\n":
            # Count preceding backslashes to determine if this backslash is escaped
            num_preceding_backslashes = 0
            j = i - 1
            while j >= 0 and text[j] == "\\":
                num_preceding_backslashes += 1
                j -= 1
            # If there's an even number of preceding backslashes (including 0),
            # this backslash escapes the newline (line continuation)
            # If odd, this backslash is itself escaped
            if num_preceding_backslashes % 2 == 0:
                # Line continuation
                if in_comment:
                    result.append("\n")
                i += 2
                in_comment = False
                continue
            # else: backslash is escaped, don't treat as line continuation, fall through
        if c == "\n":
            in_comment = False
            result.append(c)
            i += 1
            continue
        if c == "'" and not quote.double and not in_comment:
            quote.single = not quote.single
        elif c == '"' and not quote.single and not in_comment:
            quote.double = not quote.double
        elif c == "#" and not quote.single and not in_comment:
            in_comment = True
        result.append(c)
        i += 1
    return "".join(result)


def _append_redirects(base: str, redirects: list[Node] | None) -> str:
    """Append redirect sexp strings to a base sexp string."""
    if redirects:
        parts = []
        for r in redirects:
            parts.append(r.to_sexp())
        return base + " " + " ".join(parts)
    return base


class Node:
    """Base class for all AST nodes."""

    kind: str

    def to_sexp(self) -> str:
        """Convert node to S-expression string for testing."""
        raise NotImplementedError


class Word(Node):
    """A word token, possibly containing expansions."""

    value: str
    parts: list[Node]

    def __init__(self, value: str, parts: list[Node] | None = None):
        self.kind = "word"
        self.value = value
        if parts is None:
            parts = []
        self.parts = parts

    def to_sexp(self) -> str:
        value = self.value
        # Expand ALL $'...' ANSI-C quotes (handles escapes and strips $)
        value = self._expand_all_ansi_c_quotes(value)
        # Strip $ from locale strings $"..." (quote-aware)
        value = self._strip_locale_string_dollars(value)
        # Normalize whitespace in array assignments: name=(a  b\tc) -> name=(a b c)
        value = self._normalize_array_whitespace(value)
        # Format command substitutions with bash-oracle pretty-printing (before escaping)
        value = self._format_command_substitutions(value)
        # Convert newlines at param expansion boundaries to spaces (bash behavior)
        value = self._normalize_param_expansion_newlines(value)
        # Strip line continuations (backslash-newline) from arithmetic expressions
        value = self._strip_arith_line_continuations(value)
        # Double CTLESC (0x01) bytes - bash-oracle uses this for quoting control chars
        # Exception: don't double when preceded by odd number of backslashes (escaped)
        value = self._double_ctlesc_smart(value)
        # Prefix DEL (0x7f) with CTLESC - bash-oracle quotes this control char
        value = value.replace("\x7f", "\x01\x7f")
        # Escape backslashes for s-expression output
        value = value.replace("\\", "\\\\")
        # Double trailing escaped backslash (bash-oracle outputs \\\\ for trailing \)
        if value.endswith("\\\\") and not value.endswith("\\\\\\\\"):
            value = value + "\\\\"
        # Escape double quotes, newlines, and tabs
        escaped = value.replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return '(word "' + escaped + '")'

    def _append_with_ctlesc(self, result: bytearray, byte_val: int) -> None:
        """Append byte to result (CTLESC doubling happens later in to_sexp)."""
        result.append(byte_val)

    def _double_ctlesc_smart(self, value: str) -> str:
        """Double CTLESC bytes unless escaped by backslash inside double quotes."""
        result = []
        quote = QuoteState()
        for c in value:
            # Track quote state
            if c == "'" and not quote.double:
                quote.single = not quote.single
            elif c == '"' and not quote.single:
                quote.double = not quote.double
            result.append(c)
            if c == "\x01":
                # Only count backslashes in double-quoted context (where they escape)
                # In single quotes, backslashes are literal, so always double CTLESC
                if quote.double:
                    bs_count = 0
                    for j in range(len(result) - 2, -1, -1):
                        if result[j] == "\\":
                            bs_count += 1
                        else:
                            break
                    if bs_count % 2 == 0:
                        result.append("\x01")
                else:
                    # Outside double quotes (including single quotes): always double
                    result.append("\x01")
        return "".join(result)

    def _normalize_param_expansion_newlines(self, value: str) -> str:
        """Normalize newlines at param expansion boundaries.

        When there's a newline immediately after ${, bash converts it to a space
        and adds a trailing space before the closing }.
        """
        result = []
        i = 0
        quote = QuoteState()
        while i < len(value):
            c = value[i]
            # Track quote state
            if c == "'" and not quote.double:
                quote.single = not quote.single
                result.append(c)
                i += 1
            elif c == '"' and not quote.single:
                quote.double = not quote.double
                result.append(c)
                i += 1
            # Check for ${ param expansion
            elif _is_expansion_start(value, i, "${") and not quote.single:
                result.append("$")
                result.append("{")
                i += 2
                # Check for leading newline and convert to space
                had_leading_newline = i < len(value) and value[i] == "\n"
                if had_leading_newline:
                    result.append(" ")
                    i += 1
                # Find matching close brace and process content
                depth = 1
                while i < len(value) and depth > 0:
                    ch = value[i]
                    if ch == "\\" and i + 1 < len(value) and not quote.single:
                        if value[i + 1] == "\n":
                            i += 2
                            continue
                        result.append(ch)
                        result.append(value[i + 1])
                        i += 2
                        continue
                    if ch == "'" and not quote.double:
                        quote.single = not quote.single
                    elif ch == '"' and not quote.single:
                        quote.double = not quote.double
                    elif not quote.in_quotes():
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                # Add trailing space if we had leading newline
                                if had_leading_newline:
                                    result.append(" ")
                                result.append(ch)
                                i += 1
                                break
                    result.append(ch)
                    i += 1
            else:
                result.append(c)
                i += 1
        return "".join(result)

    def _sh_single_quote(self, s: str) -> str:
        """Shell-quote a string using single quotes (matches bash's sh_single_quote)."""
        if not s:
            return "''"
        if s == "'":
            return "\\'"
        result = ["'"]
        for c in s:
            if c == "'":
                result.append("'\\''")
            else:
                result.append(c)
        result.append("'")
        return "".join(result)

    def _ansi_c_to_bytes(self, inner: str) -> bytearray:
        """Expand ANSI-C escapes to literal bytes (matches bash's ansicstr)."""
        result = bytearray()
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                c = inner[i + 1]
                simple = _get_ansi_escape(c)
                if simple >= 0:
                    result.append(simple)
                    i += 2
                elif c == "'":
                    result.append(0x27)  # literal single quote
                    i += 2
                elif c == "x":
                    if i + 2 < len(inner) and inner[i + 2] == "{":
                        j = i + 3
                        while j < len(inner) and _is_hex_digit(inner[j]):
                            j += 1
                        hex_str = _substring(inner, i + 3, j)
                        if j < len(inner) and inner[j] == "}":
                            j += 1
                        if not hex_str:
                            return result  # NUL truncates
                        byte_val = int(hex_str, 16) & 0xFF
                        if byte_val == 0:
                            return result
                        self._append_with_ctlesc(result, byte_val)
                        i = j
                    else:
                        j = i + 2
                        while j < len(inner) and j < i + 4 and _is_hex_digit(inner[j]):
                            j += 1
                        if j > i + 2:
                            byte_val = int(_substring(inner, i + 2, j), 16)
                            if byte_val == 0:
                                return result
                            self._append_with_ctlesc(result, byte_val)
                            i = j
                        else:
                            result.append(ord(inner[i]))
                            i += 1
                elif c == "u":
                    j = i + 2
                    while j < len(inner) and j < i + 6 and _is_hex_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        codepoint = int(_substring(inner, i + 2, j), 16)
                        if codepoint == 0:
                            return result
                        result.extend(chr(codepoint).encode("utf-8"))
                        i = j
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "U":
                    j = i + 2
                    while j < len(inner) and j < i + 10 and _is_hex_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        codepoint = int(_substring(inner, i + 2, j), 16)
                        if codepoint == 0:
                            return result
                        result.extend(chr(codepoint).encode("utf-8"))
                        i = j
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "c":
                    if i + 3 <= len(inner):
                        ctrl_char = inner[i + 2]
                        skip_extra = 0
                        if ctrl_char == "\\" and i + 4 <= len(inner) and inner[i + 3] == "\\":
                            skip_extra = 1
                        ctrl_val = ord(ctrl_char) & 0x1F
                        if ctrl_val == 0:
                            return result
                        self._append_with_ctlesc(result, ctrl_val)
                        i += 3 + skip_extra
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "0":
                    j = i + 2
                    while j < len(inner) and j < i + 4 and _is_octal_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        byte_val = int(_substring(inner, i + 1, j), 8) & 0xFF
                        if byte_val == 0:
                            return result
                        self._append_with_ctlesc(result, byte_val)
                        i = j
                    else:
                        return result  # Just \0 - NUL truncates
                elif c >= "1" and c <= "7":
                    j = i + 1
                    while j < len(inner) and j < i + 4 and _is_octal_digit(inner[j]):
                        j += 1
                    byte_val = int(_substring(inner, i + 1, j), 8) & 0xFF
                    if byte_val == 0:
                        return result
                    self._append_with_ctlesc(result, byte_val)
                    i = j
                else:
                    result.append(0x5C)
                    result.append(ord(c))
                    i += 2
            else:
                result.extend(inner[i].encode("utf-8"))
                i += 1
        return result

    def _expand_ansi_c_escapes(self, value: str) -> str:
        """Expand ANSI-C escape sequences in $'...' strings.

        Two-phase approach matching bash's architecture:
        1. Expand escapes to literal bytes (ansicstr)
        2. Apply shell quoting to result (sh_single_quote)
        """
        if not (value.startswith("'") and value.endswith("'")):
            return value
        inner = _substring(value, 1, len(value) - 1)
        literal_bytes = self._ansi_c_to_bytes(inner)
        literal_str = literal_bytes.decode("utf-8", errors="replace")
        return self._sh_single_quote(literal_str)

    def _expand_all_ansi_c_quotes(self, value: str) -> str:
        """Find and expand ALL $'...' ANSI-C quoted strings in value."""
        result = []
        i = 0
        quote = QuoteState()
        in_backtick = False  # Track backtick substitutions - don't expand inside
        brace_depth = 0  # Track ${...} nesting - inside braces, $'...' is expanded
        while i < len(value):
            ch = value[i]
            # Track backtick context - don't expand $'...' inside backticks
            if ch == "`" and not quote.single:
                in_backtick = not in_backtick
                result.append(ch)
                i += 1
                continue
            # Inside backticks, just copy everything as-is
            if in_backtick:
                if ch == "\\" and i + 1 < len(value):
                    result.append(ch)
                    result.append(value[i + 1])
                    i += 2
                else:
                    result.append(ch)
                    i += 1
                continue
            # Track brace depth for parameter expansions
            if not quote.single:
                if _is_expansion_start(value, i, "${"):
                    brace_depth += 1
                    quote.push()
                    result.append("${")
                    i += 2
                    continue
                elif ch == "}" and brace_depth > 0 and not quote.double:
                    brace_depth -= 1
                    result.append(ch)
                    quote.pop()
                    i += 1
                    continue
            # Double quotes inside ${...} still protect $'...' from expansion
            effective_in_dquote = quote.double
            # Track quote state to avoid matching $' inside regular quotes
            if ch == "'" and not effective_in_dquote:
                # Toggle quote state unless this is $' that will be expanded as ANSI-C
                is_ansi_c = (
                    not quote.single
                    and i > 0
                    and value[i - 1] == "$"
                    and _count_consecutive_dollars_before(value, i - 1) % 2 == 0
                )
                if not is_ansi_c:
                    quote.single = not quote.single
                result.append(ch)
                i += 1
            elif ch == '"' and not quote.single:
                quote.double = not quote.double
                result.append(ch)
                i += 1
            elif ch == "\\" and i + 1 < len(value) and not quote.single:
                # Backslash escape - skip both chars to avoid misinterpreting \" or \'
                result.append(ch)
                result.append(value[i + 1])
                i += 2
            elif (
                _starts_with_at(value, i, "$'")
                and not quote.single
                and not effective_in_dquote
                and _count_consecutive_dollars_before(value, i) % 2 == 0
            ):
                # ANSI-C quoted string - find matching closing quote
                j = i + 2
                while j < len(value):
                    if value[j] == "\\" and j + 1 < len(value):
                        j += 2  # Skip escaped char
                    elif value[j] == "'":
                        j += 1  # Include closing quote
                        break
                    else:
                        j += 1
                # Extract and expand the $'...' sequence
                ansi_str = _substring(value, i, j)  # e.g. $'hello\nworld'
                # Strip the $ and expand escapes
                expanded = self._expand_ansi_c_escapes(
                    _substring(ansi_str, 1, len(ansi_str))
                )  # Pass 'hello\nworld'
                # Inside ${...} that's itself in double quotes, check if quotes should be stripped
                outer_in_dquote = quote.outer_double()
                if (
                    brace_depth > 0
                    and outer_in_dquote
                    and expanded.startswith("'")
                    and expanded.endswith("'")
                ):
                    inner = _substring(expanded, 1, len(expanded) - 1)
                    # Only strip if no CTLESC (empty inner is OK for $'')
                    if inner.find("\x01") == -1:
                        # Check if we're in a pattern context (%, %%, #, ##, /, //)
                        # For pattern operators, keep quotes; for others (like ~), strip them
                        result_str = "".join(result)
                        in_pattern = False
                        # Find the last ${
                        last_brace_idx = result_str.rfind("${")
                        if last_brace_idx >= 0:
                            # Get the content after ${
                            after_brace = result_str[last_brace_idx + 2 :]
                            # Parse variable name to find where operator starts
                            var_name_len = 0
                            if after_brace:
                                # Special parameters like $, @, *, etc.
                                if after_brace[0] in "@*#?-$!0123456789_":
                                    var_name_len = 1
                                # Regular variable names
                                elif after_brace[0].isalpha() or after_brace[0] == "_":
                                    while var_name_len < len(after_brace):
                                        c = after_brace[var_name_len]
                                        if not (c.isalnum() or c == "_"):
                                            break
                                        var_name_len += 1
                            # Check if operator immediately after variable name is a pattern operator
                            if (
                                var_name_len > 0
                                and var_name_len < len(after_brace)
                                and after_brace[0] not in "#?-"
                            ):
                                op_start = after_brace[var_name_len:]
                                # Skip @ prefix if present (handles @%, @#, @/ etc.)
                                if op_start.startswith("@") and len(op_start) > 1:
                                    op_start = op_start[1:]
                                # Check if it starts with a pattern operator
                                for op in ["//", "%%", "##", "/", "%", "#", "^", "^^", ",", ",,"]:
                                    if op_start.startswith(op):
                                        in_pattern = True
                                        break
                                # If no operator at start and the first char is NOT a known
                                # bash operator character, also check if any operator exists
                                # later (handles cases like ${x{%...} where { precedes the operator)
                                # Known operator start chars: % # / ^ , ~ : + - = ?
                                if not in_pattern and op_start and op_start[0] not in "%#/^,~:+-=?":
                                    for op in [
                                        "//",
                                        "%%",
                                        "##",
                                        "/",
                                        "%",
                                        "#",
                                        "^",
                                        "^^",
                                        ",",
                                        ",,",
                                    ]:
                                        if op in op_start:
                                            in_pattern = True
                                            break
                            # Handle invalid variable names (var_name_len = 0) where first char is not a pattern operator
                            # but there's a pattern operator later (e.g., ${>%$'b'})
                            elif var_name_len == 0 and len(after_brace) > 1:
                                first_char = after_brace[0]
                                # If first char is not itself a pattern operator, check for pattern ops after it
                                if first_char not in "%#/^,":
                                    rest = after_brace[1:]
                                    for op in [
                                        "//",
                                        "%%",
                                        "##",
                                        "/",
                                        "%",
                                        "#",
                                        "^",
                                        "^^",
                                        ",",
                                        ",,",
                                    ]:
                                        if op in rest:
                                            in_pattern = True
                                            break
                        if not in_pattern:
                            expanded = inner
                result.append(expanded)
                i = j
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _strip_locale_string_dollars(self, value: str) -> str:
        """Strip $ from locale strings $"..." while tracking quote context."""
        result = []
        i = 0
        brace_depth = 0
        bracket_depth = 0
        quote = QuoteState()  # Top-level quote state
        brace_quote = QuoteState()  # Quote state inside ${...}
        bracket_in_double_quote = False  # Quote state inside [...] (only double tracked)
        while i < len(value):
            ch = value[i]
            if ch == "\\" and i + 1 < len(value) and not quote.single and not brace_quote.single:
                # Escape - copy both chars (but NOT inside single quotes where \ is literal)
                result.append(ch)
                result.append(value[i + 1])
                i += 2
            elif (
                _starts_with_at(value, i, "${")
                and not quote.single
                and not brace_quote.single
                # Don't treat ${ as brace expansion if preceded by $ (it's $$ + literal {)
                and (i == 0 or value[i - 1] != "$")
            ):
                brace_depth += 1
                brace_quote.double = False
                brace_quote.single = False
                result.append("$")
                result.append("{")
                i += 2
            elif (
                ch == "}"
                and brace_depth > 0
                and not quote.single
                and not brace_quote.double
                and not brace_quote.single
            ):
                brace_depth -= 1
                result.append(ch)
                i += 1
            elif ch == "[" and brace_depth > 0 and not quote.single and not brace_quote.double:
                # Start of subscript inside brace expansion
                bracket_depth += 1
                bracket_in_double_quote = False
                result.append(ch)
                i += 1
            elif (
                ch == "]" and bracket_depth > 0 and not quote.single and not bracket_in_double_quote
            ):
                # End of subscript
                bracket_depth -= 1
                result.append(ch)
                i += 1
            elif ch == "'" and not quote.double and brace_depth == 0:
                quote.single = not quote.single
                result.append(ch)
                i += 1
            elif ch == '"' and not quote.single and brace_depth == 0:
                quote.double = not quote.double
                result.append(ch)
                i += 1
            elif ch == '"' and not quote.single and bracket_depth > 0:
                # Toggle quote state inside bracket (subscript)
                bracket_in_double_quote = not bracket_in_double_quote
                result.append(ch)
                i += 1
            elif ch == '"' and not quote.single and not brace_quote.single and brace_depth > 0:
                # Toggle quote state inside brace expansion
                brace_quote.double = not brace_quote.double
                result.append(ch)
                i += 1
            elif ch == "'" and not quote.double and not brace_quote.double and brace_depth > 0:
                # Toggle single quote state inside brace expansion
                brace_quote.single = not brace_quote.single
                result.append(ch)
                i += 1
            elif (
                _starts_with_at(value, i, '$"')
                and not quote.single
                and not brace_quote.single
                and (brace_depth > 0 or bracket_depth > 0 or not quote.double)
                and not brace_quote.double
                and not bracket_in_double_quote
            ):
                # Count consecutive $ chars ending at i to check for $$ (PID param)
                dollar_count = 1 + _count_consecutive_dollars_before(value, i)
                if dollar_count % 2 == 1:
                    # Odd count: locale string $"..." - strip the $ and enter double quote
                    result.append('"')
                    if bracket_depth > 0:
                        bracket_in_double_quote = True
                    elif brace_depth > 0:
                        brace_quote.double = True
                    else:
                        quote.double = True
                    i += 2
                else:
                    # Even count: this $ is part of $$ (PID), just append it
                    result.append(ch)
                    i += 1
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _normalize_array_whitespace(self, value: str) -> str:
        """Normalize whitespace inside array assignments: arr=(a  b\tc) -> arr=(a b c)."""
        # Match array assignment pattern: name=( or name+=( or name[sub]=( or name[sub]+=(
        # Parse identifier: starts with letter/underscore, then alnum/underscore
        i = 0
        if not (i < len(value) and (value[i].isalpha() or value[i] == "_")):
            return value
        i += 1
        while i < len(value) and (value[i].isalnum() or value[i] == "_"):
            i += 1
        # Optional subscript(s): [...]
        while i < len(value) and value[i] == "[":
            depth = 1
            i += 1
            while i < len(value) and depth > 0:
                if value[i] == "[":
                    depth += 1
                elif value[i] == "]":
                    depth -= 1
                i += 1
            if depth != 0:
                return value
        # Optional + for +=
        if i < len(value) and value[i] == "+":
            i += 1
        # Must have =(
        if not (i + 1 < len(value) and value[i] == "=" and value[i + 1] == "("):
            return value
        prefix = _substring(value, 0, i + 1)  # e.g., "arr=" or "arr+="
        open_paren_pos = i + 1
        # Find matching closing paren
        if value.endswith(")"):
            close_paren_pos = len(value) - 1
        else:
            close_paren_pos = self._find_matching_paren(value, open_paren_pos)
            if close_paren_pos < 0:
                return value
        # Extract content inside parentheses
        inner = _substring(value, open_paren_pos + 1, close_paren_pos)
        suffix = _substring(value, close_paren_pos + 1, len(value))
        result = self._normalize_array_inner(inner)
        return prefix + "(" + result + ")" + suffix

    def _find_matching_paren(self, value: str, open_pos: int) -> int:
        """Find position of matching ) for ( at open_pos, handling quotes and comments."""
        if open_pos >= len(value) or value[open_pos] != "(":
            return -1
        i = open_pos + 1
        depth = 1
        quote = QuoteState()
        while i < len(value) and depth > 0:
            ch = value[i]
            # Handle escapes (only meaningful outside single quotes)
            if ch == "\\" and i + 1 < len(value) and not quote.single:
                i += 2
                continue
            # Track quote state
            if ch == "'" and not quote.double:
                quote.single = not quote.single
                i += 1
                continue
            if ch == '"' and not quote.single:
                quote.double = not quote.double
                i += 1
                continue
            # Skip content inside quotes
            if quote.single or quote.double:
                i += 1
                continue
            # Handle comments (only outside quotes)
            if ch == "#":
                while i < len(value) and value[i] != "\n":
                    i += 1
                continue
            # Track paren depth
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def _normalize_array_inner(self, inner: str) -> str:
        """Normalize whitespace inside array content, handling nested constructs."""
        normalized = []
        i = 0
        in_whitespace = True  # Start true to skip leading whitespace
        brace_depth = 0  # Track ${...} nesting
        bracket_depth = 0  # Track [...] subscript nesting
        while i < len(inner):
            ch = inner[i]
            if _is_whitespace(ch):
                if not in_whitespace and normalized and brace_depth == 0 and bracket_depth == 0:
                    normalized.append(" ")
                    in_whitespace = True
                if brace_depth > 0 or bracket_depth > 0:
                    normalized.append(ch)
                i += 1
            elif ch == "'":
                # Single-quoted string - preserve as-is
                in_whitespace = False
                j = i + 1
                while j < len(inner) and inner[j] != "'":
                    j += 1
                normalized.append(_substring(inner, i, j + 1))
                i = j + 1
            elif ch == '"':
                # Double-quoted string - strip line continuations
                # Track ${...} nesting since quotes inside expansions don't end the string
                in_whitespace = False
                j = i + 1
                dq_content = ['"']
                dq_brace_depth = 0
                while j < len(inner):
                    if inner[j] == "\\" and j + 1 < len(inner):
                        if inner[j + 1] == "\n":
                            # Skip line continuation
                            j += 2
                        else:
                            dq_content.append(inner[j])
                            dq_content.append(inner[j + 1])
                            j += 2
                    elif _is_expansion_start(inner, j, "${"):
                        # Start of ${...} expansion
                        dq_content.append("${")
                        dq_brace_depth += 1
                        j += 2
                    elif inner[j] == "}" and dq_brace_depth > 0:
                        # End of ${...} expansion
                        dq_content.append("}")
                        dq_brace_depth -= 1
                        j += 1
                    elif inner[j] == '"' and dq_brace_depth == 0:
                        dq_content.append('"')
                        j += 1
                        break
                    else:
                        dq_content.append(inner[j])
                        j += 1
                normalized.append("".join(dq_content))
                i = j
            elif ch == "\\" and i + 1 < len(inner):
                if inner[i + 1] == "\n":
                    # Line continuation - skip both backslash and newline
                    i += 2
                else:
                    # Escape sequence - preserve
                    in_whitespace = False
                    normalized.append(_substring(inner, i, i + 2))
                    i += 2
            elif _is_expansion_start(inner, i, "$(("):
                # Arithmetic expansion $(( - find matching )) and preserve as-is
                in_whitespace = False
                j = i + 3
                depth = 1
                while j < len(inner) and depth > 0:
                    if j + 1 < len(inner) and inner[j] == "(" and inner[j + 1] == "(":
                        depth += 1
                        j += 2
                    elif j + 1 < len(inner) and inner[j] == ")" and inner[j + 1] == ")":
                        depth -= 1
                        j += 2
                    else:
                        j += 1
                normalized.append(_substring(inner, i, j))
                i = j
            elif _is_expansion_start(inner, i, "$("):
                # Command substitution - find matching ) and preserve as-is
                # (formatting is handled later by _format_command_substitutions)
                in_whitespace = False
                j = i + 2
                depth = 1
                while j < len(inner) and depth > 0:
                    if inner[j] == "(" and j > 0 and inner[j - 1] == "$":
                        depth += 1
                    elif inner[j] == ")":
                        depth -= 1
                    elif inner[j] == "'":
                        j += 1
                        while j < len(inner) and inner[j] != "'":
                            j += 1
                    elif inner[j] == '"':
                        j += 1
                        while j < len(inner):
                            if inner[j] == "\\" and j + 1 < len(inner):
                                j += 2
                                continue
                            if inner[j] == '"':
                                break
                            j += 1
                    j += 1
                # Preserve command substitution as-is
                normalized.append(_substring(inner, i, j))
                i = j
            elif (ch == "<" or ch == ">") and i + 1 < len(inner) and inner[i + 1] == "(":
                # Process substitution <(...) or >(...) - find matching ) and preserve as-is
                # (formatting is handled later by _format_command_substitutions)
                in_whitespace = False
                j = i + 2
                depth = 1
                while j < len(inner) and depth > 0:
                    if inner[j] == "(":
                        depth += 1
                    elif inner[j] == ")":
                        depth -= 1
                    elif inner[j] == "'":
                        j += 1
                        while j < len(inner) and inner[j] != "'":
                            j += 1
                    elif inner[j] == '"':
                        j += 1
                        while j < len(inner):
                            if inner[j] == "\\" and j + 1 < len(inner):
                                j += 2
                                continue
                            if inner[j] == '"':
                                break
                            j += 1
                    j += 1
                # Preserve process substitution as-is
                normalized.append(_substring(inner, i, j))
                i = j
            elif _is_expansion_start(inner, i, "${"):
                # Start of ${...} expansion
                in_whitespace = False
                normalized.append("${")
                brace_depth += 1
                i += 2
            elif ch == "{" and brace_depth > 0:
                # Nested brace inside expansion
                normalized.append(ch)
                brace_depth += 1
                i += 1
            elif ch == "}" and brace_depth > 0:
                # End of expansion
                normalized.append(ch)
                brace_depth -= 1
                i += 1
            elif ch == "#" and brace_depth == 0 and in_whitespace:
                # Comment - skip to end of line (only at top level, start of word)
                while i < len(inner) and inner[i] != "\n":
                    i += 1
            elif ch == "[":
                # Only start subscript tracking if at word start (for [key]=val patterns)
                # Mid-word [ like a[ is literal, not a subscript
                # But if already inside brackets, track nested brackets
                if in_whitespace or bracket_depth > 0:
                    bracket_depth += 1
                in_whitespace = False
                normalized.append(ch)
                i += 1
            elif ch == "]" and bracket_depth > 0:
                # End of subscript
                normalized.append(ch)
                bracket_depth -= 1
                i += 1
            else:
                in_whitespace = False
                normalized.append(ch)
                i += 1
        # Strip trailing whitespace
        return "".join(normalized).rstrip()

    def _strip_arith_line_continuations(self, value: str) -> str:
        """Strip backslash-newline (line continuation) from inside $((...))."""
        result = []
        i = 0
        while i < len(value):
            # Check for $(( arithmetic expression
            if _is_expansion_start(value, i, "$(("):
                start = i
                i += 3
                depth = 2  # Track single parens: $(( starts at depth 2
                arith_content = []
                # Track position of first ) that brings depth 2→1 (-1 = not set)
                first_close_idx: int = -1
                while i < len(value) and depth > 0:
                    if value[i] == "(":
                        arith_content.append("(")
                        depth += 1
                        i += 1
                        if depth > 1:
                            first_close_idx = -1  # Content after first close
                    elif value[i] == ")":
                        if depth == 2:
                            first_close_idx = len(arith_content)
                        depth -= 1
                        if depth > 0:
                            arith_content.append(")")
                        i += 1
                    elif value[i] == "\\" and i + 1 < len(value) and value[i + 1] == "\n":
                        # Count preceding backslashes in arith_content
                        num_backslashes = 0
                        j = len(arith_content) - 1
                        # Skip trailing newlines before counting backslashes
                        while j >= 0 and arith_content[j] == "\n":
                            j -= 1
                        while j >= 0 and arith_content[j] == "\\":
                            num_backslashes += 1
                            j -= 1
                        # If odd number of preceding backslashes, this backslash is escaped
                        if num_backslashes % 2 == 1:
                            arith_content.append("\\")
                            arith_content.append("\n")
                            i += 2
                        else:
                            # Skip backslash-newline (line continuation)
                            i += 2
                        if depth == 1:
                            first_close_idx = -1  # Content after first close
                    else:
                        arith_content.append(value[i])
                        i += 1
                        if depth == 1:
                            first_close_idx = -1  # Content after first close
                if depth == 0 or (depth == 1 and first_close_idx != -1):
                    content = "".join(arith_content)
                    if first_close_idx != -1:
                        # Standard close: trim content, add ))
                        content = content[:first_close_idx]
                        # If depth==1, we only found one closing paren, add )
                        # If depth==0, we found both closing parens, add ))
                        closing = "))" if depth == 0 else ")"
                        result.append("$((" + content + closing)
                    else:
                        # Content after first close: content has intermediate ), add single )
                        result.append("$((" + content + ")")
                else:
                    # Didn't close properly - pass through original
                    result.append(_substring(value, start, i))
            else:
                result.append(value[i])
                i += 1
        return "".join(result)

    def _collect_cmdsubs(self, node: Node) -> list[Node]:
        """Recursively collect CommandSubstitution nodes from an AST node."""
        result: list[Node] = []
        if isinstance(node, CommandSubstitution):
            result.append(node)
        elif isinstance(node, Array):
            for elem in node.elements:
                for p in elem.parts:
                    if isinstance(p, CommandSubstitution):
                        result.append(p)
                    else:
                        result.extend(self._collect_cmdsubs(p))
        elif isinstance(node, ArithmeticExpansion):
            if node.expression is not None:
                result.extend(self._collect_cmdsubs(node.expression))
        elif isinstance(node, ArithBinaryOp) or isinstance(node, ArithComma):
            result.extend(self._collect_cmdsubs(node.left))
            result.extend(self._collect_cmdsubs(node.right))
        elif (
            isinstance(node, ArithUnaryOp)
            or isinstance(node, ArithPreIncr)
            or isinstance(node, ArithPostIncr)
            or isinstance(node, ArithPreDecr)
            or isinstance(node, ArithPostDecr)
        ):
            result.extend(self._collect_cmdsubs(node.operand))
        elif isinstance(node, ArithTernary):
            result.extend(self._collect_cmdsubs(node.condition))
            result.extend(self._collect_cmdsubs(node.if_true))
            result.extend(self._collect_cmdsubs(node.if_false))
        elif isinstance(node, ArithAssign):
            result.extend(self._collect_cmdsubs(node.target))
            result.extend(self._collect_cmdsubs(node.value))
        return result

    def _collect_procsubs(self, node: Node) -> list[Node]:
        """Recursively collect ProcessSubstitution nodes from an AST node."""
        result: list[Node] = []
        if isinstance(node, ProcessSubstitution):
            result.append(node)
        elif isinstance(node, Array):
            for elem in node.elements:
                for p in elem.parts:
                    if isinstance(p, ProcessSubstitution):
                        result.append(p)
                    else:
                        result.extend(self._collect_procsubs(p))
        return result

    def _format_command_substitutions(self, value: str, in_arith: bool = False) -> str:
        """Replace $(...) and >(...) / <(...) with bash-oracle-formatted AST output."""
        # Collect command substitutions from all parts, including nested ones
        cmdsub_parts = []
        procsub_parts = []
        has_arith = False  # Track if we have any arithmetic expansion nodes
        for p in self.parts:
            if p.kind == "cmdsub":
                cmdsub_parts.append(p)
            elif p.kind == "procsub":
                procsub_parts.append(p)
            elif p.kind == "arith":
                has_arith = True
            else:
                cmdsub_parts.extend(self._collect_cmdsubs(p))
                procsub_parts.extend(self._collect_procsubs(p))
        # Check if we have ${ or ${| brace command substitutions to format
        has_brace_cmdsub = (
            value.find("${ ") != -1
            or value.find("${\t") != -1
            or value.find("${\n") != -1
            or value.find("${|") != -1
        )
        # Check if there's an untracked $( that isn't $((, skipping over quotes only
        has_untracked_cmdsub = False
        has_untracked_procsub = False
        idx = 0
        scan_quote = QuoteState()
        while idx < len(value):
            if value[idx] == '"':
                scan_quote.double = not scan_quote.double
                idx += 1
            elif value[idx] == "'" and not scan_quote.double:
                # Skip over single-quoted string (contents are literal)
                # But only when not inside double quotes
                idx += 1
                while idx < len(value) and value[idx] != "'":
                    idx += 1
                if idx < len(value):
                    idx += 1  # skip closing quote
            elif (
                _starts_with_at(value, idx, "$(")
                and not _starts_with_at(value, idx, "$((")
                and not _is_backslash_escaped(value, idx)
                and not _is_dollar_dollar_paren(value, idx)
            ):
                has_untracked_cmdsub = True
                break
            elif (
                _starts_with_at(value, idx, "<(") or _starts_with_at(value, idx, ">(")
            ) and not scan_quote.double:
                # Only treat as process substitution if not preceded by alphanumeric or quote
                # (e.g., "i<(3)" is arithmetic comparison, not process substitution)
                # Also don't treat as process substitution inside double quotes or after quotes
                if idx == 0 or (not value[idx - 1].isalnum() and value[idx - 1] not in "\"'"):
                    has_untracked_procsub = True
                    break
                idx += 1
            else:
                idx += 1
        # Check if ${...} contains <( or >( patterns that need normalization
        has_param_with_procsub_pattern = "${" in value and ("<(" in value or ">(" in value)
        if (
            not cmdsub_parts
            and not procsub_parts
            and not has_brace_cmdsub
            and not has_untracked_cmdsub
            and not has_untracked_procsub
            and not has_param_with_procsub_pattern
        ):
            return value
        result = []
        i = 0
        cmdsub_idx = 0
        procsub_idx = 0
        main_quote = QuoteState()
        extglob_depth = 0
        deprecated_arith_depth = 0  # Track $[...] depth
        arith_depth = 0  # Track $((...)) depth
        arith_paren_depth = 0  # Track paren depth inside arithmetic
        while i < len(value):
            # Check for extglob start: @( ?( *( +( !(
            if (
                i > 0
                and _is_extglob_prefix(value[i - 1])
                and value[i] == "("
                and not _is_backslash_escaped(value, i - 1)
            ):
                extglob_depth += 1
                result.append(value[i])
                i += 1
                continue
            # Track ) that closes extglob (but not inside cmdsub/procsub)
            if value[i] == ")" and extglob_depth > 0:
                extglob_depth -= 1
                result.append(value[i])
                i += 1
                continue
            # Track deprecated arithmetic $[...] - inside it, >( and <( are not procsub
            if _starts_with_at(value, i, "$[") and not _is_backslash_escaped(value, i):
                deprecated_arith_depth += 1
                result.append(value[i])
                i += 1
                continue
            if value[i] == "]" and deprecated_arith_depth > 0:
                deprecated_arith_depth -= 1
                result.append(value[i])
                i += 1
                continue
            # Track $((...)) arithmetic - inside it, >( and <( are not process subs
            # But skip if this is actually $( ( (command substitution with subshell)
            if (
                _is_expansion_start(value, i, "$((")
                and not _is_backslash_escaped(value, i)
                and has_arith
            ):
                arith_depth += 1
                arith_paren_depth += 2  # For the two opening parens
                result.append("$((")
                i += 3
                continue
            # Track )) that closes arithmetic (only when no inner parens open)
            if arith_depth > 0 and arith_paren_depth == 2 and _starts_with_at(value, i, "))"):
                arith_depth -= 1
                arith_paren_depth -= 2
                result.append("))")
                i += 2
                continue
            # Track ( and ) inside arithmetic
            if arith_depth > 0:
                if value[i] == "(":
                    arith_paren_depth += 1
                    result.append(value[i])
                    i += 1
                    continue
                elif value[i] == ")":
                    arith_paren_depth -= 1
                    result.append(value[i])
                    i += 1
                    continue
            # Check for $( command substitution (but not $(( arithmetic or escaped \$()
            # Special case: $(( without arithmetic nodes - preserve as-is
            if _is_expansion_start(value, i, "$((") and not has_arith:
                # This looks like $(( but wasn't parsed as arithmetic
                # It's actually $( ( ... ) ) - preserve original text
                j = _find_cmdsub_end(value, i + 2)
                result.append(_substring(value, i, j))
                if cmdsub_idx < len(cmdsub_parts):
                    cmdsub_idx += 1
                i = j
                continue
            # Regular command substitution
            if (
                _starts_with_at(value, i, "$(")
                and not _starts_with_at(value, i, "$((")
                and not _is_backslash_escaped(value, i)
                and not _is_dollar_dollar_paren(value, i)
            ):
                # Find matching close paren using bash-aware matching
                j = _find_cmdsub_end(value, i + 2)
                # Inside extglob: don't format, just copy raw content
                if extglob_depth > 0:
                    result.append(_substring(value, i, j))
                    if cmdsub_idx < len(cmdsub_parts):
                        cmdsub_idx += 1
                    i = j
                    continue
                # Format this command substitution
                inner = _substring(value, i + 2, j - 1)
                if cmdsub_idx < len(cmdsub_parts):
                    # Have parsed AST node - use it (} is preserved in AST)
                    node = cmdsub_parts[cmdsub_idx]
                    formatted = _format_cmdsub_node(node.command)
                    cmdsub_idx += 1
                else:
                    # No AST node (e.g., inside arithmetic) - parse content on the fly
                    try:
                        parser = Parser(inner)
                        parsed = parser.parse_list()
                        formatted = _format_cmdsub_node(parsed) if parsed else ""
                    except Exception:
                        formatted = inner
                # Add space after $( if content starts with ( to avoid $((
                if formatted.startswith("("):
                    result.append("$( " + formatted + ")")
                else:
                    result.append("$(" + formatted + ")")
                i = j
            # Check for backtick command substitution
            elif value[i] == "`" and cmdsub_idx < len(cmdsub_parts):
                # Find matching backtick
                j = i + 1
                while j < len(value):
                    if value[j] == "\\" and j + 1 < len(value):
                        j += 2
                        continue
                    if value[j] == "`":
                        j += 1
                        break
                    j += 1
                # Keep backtick substitutions as-is (bash-oracle doesn't reformat them)
                result.append(_substring(value, i, j))
                cmdsub_idx += 1
                i = j
            # Check for ${ brace command substitution (funsub)
            elif (
                _is_expansion_start(value, i, "${")
                and i + 2 < len(value)
                and _is_funsub_char(value[i + 2])
                and not _is_backslash_escaped(value, i)
            ):
                # Find matching close brace
                j = _find_funsub_end(value, i + 2)
                # Check if we have a parsed node with brace=True
                cmdsub_node = cmdsub_parts[cmdsub_idx] if cmdsub_idx < len(cmdsub_parts) else None
                if isinstance(cmdsub_node, CommandSubstitution) and cmdsub_node.brace:
                    node = cmdsub_node
                    formatted = _format_cmdsub_node(node.command)
                    # Determine prefix: ${ or ${|
                    has_pipe = value[i + 2] == "|"
                    prefix = "${|" if has_pipe else "${ "
                    # Check if original content ends with newline
                    orig_inner = _substring(value, i + 2, j - 1)
                    ends_with_newline = orig_inner.endswith("\n")
                    # Add terminator before closing brace
                    if not formatted or formatted.isspace():
                        # Empty funsub: ${ }
                        suffix = "}"
                    elif formatted.endswith("&") or formatted.endswith("& "):
                        # Background: ${ cmd & }
                        suffix = " }" if formatted.endswith("&") else "}"
                    elif ends_with_newline:
                        # Preserve trailing newline: ${ cmd\n }
                        suffix = "\n }"
                    else:
                        # Normal: ${ cmd; }
                        suffix = "; }"
                    result.append(prefix + formatted + suffix)
                    cmdsub_idx += 1
                else:
                    # No parsed node, keep as-is
                    result.append(_substring(value, i, j))
                i = j
            # Check for >( or <( process substitution (not inside double quotes, $[...], or $((...)))
            elif (
                (_starts_with_at(value, i, ">(") or _starts_with_at(value, i, "<("))
                and not main_quote.double
                and deprecated_arith_depth == 0
                and arith_depth == 0
            ):
                # Check if this is actually a process substitution or just comparison + parens
                # Process substitution: not preceded by alphanumeric or quote
                is_procsub = i == 0 or (not value[i - 1].isalnum() and value[i - 1] not in "\"'")
                # Inside extglob: don't format, just copy raw content
                if extglob_depth > 0:
                    j = _find_cmdsub_end(value, i + 2)
                    result.append(_substring(value, i, j))
                    if procsub_idx < len(procsub_parts):
                        procsub_idx += 1
                    i = j
                    continue
                if procsub_idx < len(procsub_parts):
                    # Have parsed AST node - use it
                    direction = value[i]
                    j = _find_cmdsub_end(value, i + 2)
                    node = procsub_parts[procsub_idx]
                    compact = _starts_with_subshell(node.command)
                    formatted = _format_cmdsub_node(node.command, 0, True, compact, True)
                    raw_content = _substring(value, i + 2, j - 1)
                    if node.command.kind == "subshell":
                        # Extract leading whitespace
                        leading_ws_end = 0
                        while (
                            leading_ws_end < len(raw_content)
                            and raw_content[leading_ws_end] in " \t\n"
                        ):
                            leading_ws_end += 1
                        leading_ws = raw_content[:leading_ws_end]
                        stripped = raw_content[leading_ws_end:]
                        if stripped.startswith("("):
                            if leading_ws:
                                # Leading whitespace before subshell: normalize ws + format subshell with spaces
                                normalized_ws = leading_ws.replace("\n", " ").replace("\t", " ")
                                spaced = _format_cmdsub_node(node.command, in_procsub=False)
                                result.append(direction + "(" + normalized_ws + spaced + ")")
                            else:
                                # No leading whitespace - preserve original raw content
                                raw_content = raw_content.replace("\\\n", "")
                                result.append(direction + "(" + raw_content + ")")
                            procsub_idx += 1
                            i = j
                            continue
                    # Extract raw content for further checks
                    raw_content = _substring(value, i + 2, j - 1)
                    raw_stripped = raw_content.replace("\\\n", "")
                    # Check for pattern: subshell followed by operator with no space (e.g., "(0)&+")
                    # In this case, preserve original to match bash-oracle behavior
                    if _starts_with_subshell(node.command) and formatted != raw_stripped:
                        # Starts with subshell and formatting would change it - preserve original
                        result.append(direction + "(" + raw_stripped + ")")
                    else:
                        final_output = direction + "(" + formatted + ")"
                        result.append(final_output)
                    procsub_idx += 1
                    i = j
                elif is_procsub and len(self.parts):
                    # No AST node but valid procsub context - parse content on the fly
                    direction = value[i]
                    j = _find_cmdsub_end(value, i + 2)
                    # Check if we found a valid closing ) - if not, treat as literal characters
                    if j > len(value) or (j > 0 and j <= len(value) and value[j - 1] != ")"):
                        result.append(value[i])
                        i += 1
                        continue
                    inner = _substring(value, i + 2, j - 1)
                    try:
                        parser = Parser(inner)
                        parsed = parser.parse_list()
                        # Only use parsed result if parser consumed all input and no newlines in content
                        # (newlines would be lost during formatting)
                        if parsed and parser.pos == len(inner) and "\n" not in inner:
                            compact = _starts_with_subshell(parsed)
                            formatted = _format_cmdsub_node(parsed, 0, True, compact, True)
                        else:
                            formatted = inner
                    except Exception:
                        formatted = inner
                    result.append(direction + "(" + formatted + ")")
                    i = j
                elif is_procsub:
                    # Process substitution but no parts (failed to parse or in arithmetic context)
                    direction = value[i]
                    j = _find_cmdsub_end(value, i + 2)
                    if j > len(value) or (j > 0 and j <= len(value) and value[j - 1] != ")"):
                        # Couldn't find closing paren, treat as literal
                        result.append(value[i])
                        i += 1
                        continue
                    inner = _substring(value, i + 2, j - 1)
                    # In arithmetic context, preserve whitespace; otherwise strip leading whitespace
                    if in_arith:
                        result.append(direction + "(" + inner + ")")
                    elif inner.strip():
                        stripped = inner.lstrip(" \t")
                        result.append(direction + "(" + stripped + ")")
                    else:
                        result.append(direction + "(" + inner + ")")
                    i = j
                else:
                    # Not a process substitution (e.g., arithmetic comparison)
                    result.append(value[i])
                    i += 1
            # Check for ${ (space/tab/newline) or ${| brace command substitution
            # But not if the $ is escaped by a backslash
            elif (
                _is_expansion_start(value, i, "${ ")
                or _is_expansion_start(value, i, "${\t")
                or _is_expansion_start(value, i, "${\n")
                or _is_expansion_start(value, i, "${|")
            ) and not _is_backslash_escaped(value, i):
                prefix = _substring(value, i, i + 3).replace("\t", " ").replace("\n", " ")
                # Find matching close brace
                j = i + 3
                depth = 1
                while j < len(value) and depth > 0:
                    if value[j] == "{":
                        depth += 1
                    elif value[j] == "}":
                        depth -= 1
                    j += 1
                # Parse and format the inner content
                inner = _substring(value, i + 2, j - 1)  # Content between ${ and }
                # Check if content is all whitespace - normalize to single space
                if inner.strip() == "":
                    result.append("${ }")
                else:
                    try:
                        parser = Parser(inner.lstrip(" \t\n|"))
                        parsed = parser.parse_list()
                        if parsed:
                            formatted = _format_cmdsub_node(parsed)
                            formatted = formatted.rstrip(";")
                            # Preserve trailing newline from original if present
                            if inner.rstrip(" \t").endswith("\n"):
                                terminator = "\n }"
                            elif formatted.endswith(" &"):
                                terminator = " }"
                            else:
                                terminator = "; }"
                            result.append(prefix + formatted + terminator)
                        else:
                            result.append("${ }")
                    except Exception:
                        result.append(_substring(value, i, j))
                i = j
            # Process regular ${...} parameter expansions (recursively format cmdsubs inside)
            # But not if the $ is escaped by a backslash
            elif _is_expansion_start(value, i, "${") and not _is_backslash_escaped(value, i):
                # Find matching close brace, respecting nesting, quotes, and cmdsubs
                j = i + 2
                depth = 1
                brace_quote = QuoteState()
                while j < len(value) and depth > 0:
                    c = value[j]
                    if c == "\\" and j + 1 < len(value) and not brace_quote.single:
                        j += 2
                        continue
                    if c == "'" and not brace_quote.double:
                        brace_quote.single = not brace_quote.single
                    elif c == '"' and not brace_quote.single:
                        brace_quote.double = not brace_quote.double
                    elif not brace_quote.in_quotes():
                        # Skip over $(...) command substitutions
                        if _is_expansion_start(value, j, "$(") and not _starts_with_at(
                            value, j, "$(("
                        ):
                            j = _find_cmdsub_end(value, j + 2)
                            continue
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                    j += 1
                # Recursively format any cmdsubs inside the param expansion
                # When depth > 0 (unclosed ${), include all remaining chars
                if depth > 0:
                    inner = _substring(value, i + 2, j)
                else:
                    inner = _substring(value, i + 2, j - 1)
                formatted_inner = self._format_command_substitutions(inner)
                # Normalize <( and >( patterns in param expansion (for pipe alternation)
                formatted_inner = self._normalize_extglob_whitespace(formatted_inner)
                # Only append closing } if we found one in the input
                if depth == 0:
                    result.append("${" + formatted_inner + "}")
                else:
                    # Unclosed ${...} - output without closing brace
                    result.append("${" + formatted_inner)
                i = j
            # Track double-quote state (single quotes inside double quotes are literal)
            elif value[i] == '"':
                main_quote.double = not main_quote.double
                result.append(value[i])
                i += 1
            # Skip single-quoted strings (contents are literal, don't look for cmdsubs)
            # But only when NOT inside double quotes (where single quotes are literal)
            elif value[i] == "'" and not main_quote.double:
                j = i + 1
                while j < len(value) and value[j] != "'":
                    j += 1
                if j < len(value):
                    j += 1  # include closing quote
                result.append(_substring(value, i, j))
                i = j
            else:
                result.append(value[i])
                i += 1
        return "".join(result)

    def _normalize_extglob_whitespace(self, value: str) -> str:
        """Normalize whitespace around | in >() and <() patterns for regex contexts."""
        result = []
        i = 0
        extglob_quote = QuoteState()
        deprecated_arith_depth = 0  # Track $[...] depth
        while i < len(value):
            # Track double-quote state
            if value[i] == '"':
                extglob_quote.double = not extglob_quote.double
                result.append(value[i])
                i += 1
                continue
            # Track deprecated arithmetic $[...] - inside it, >( and <( are not procsub
            if _starts_with_at(value, i, "$[") and not _is_backslash_escaped(value, i):
                deprecated_arith_depth += 1
                result.append(value[i])
                i += 1
                continue
            if value[i] == "]" and deprecated_arith_depth > 0:
                deprecated_arith_depth -= 1
                result.append(value[i])
                i += 1
                continue
            # Check for >( or <( pattern (process substitution-like in regex)
            # Only process these patterns when NOT inside double quotes or $[...]
            if i + 1 < len(value) and value[i + 1] == "(":
                prefix_char = value[i]
                if prefix_char in "><" and not extglob_quote.double and deprecated_arith_depth == 0:
                    # Found pattern start
                    result.append(prefix_char)
                    result.append("(")
                    i += 2
                    # Process content until matching )
                    depth = 1
                    pattern_parts = []
                    current_part = []
                    has_pipe = False
                    while i < len(value) and depth > 0:
                        if value[i] == "\\" and i + 1 < len(value):
                            # Escaped character, keep as-is
                            current_part.append(value[i : i + 2])
                            i += 2
                            continue
                        elif value[i] == "(":
                            depth += 1
                            current_part.append(value[i])
                            i += 1
                        elif value[i] == ")":
                            depth -= 1
                            if depth == 0:
                                # End of pattern
                                part_content = "".join(current_part)
                                # Only strip if this is an alternation pattern (has |) or contains heredoc
                                if "<<" in part_content:
                                    pattern_parts.append(part_content)
                                elif has_pipe:
                                    pattern_parts.append(part_content.strip())
                                else:
                                    pattern_parts.append(part_content)
                                break
                            current_part.append(value[i])
                            i += 1
                        elif value[i] == "|" and depth == 1:
                            # Check for || (OR operator) - keep as single token
                            if i + 1 < len(value) and value[i + 1] == "|":
                                current_part.append("||")
                                i += 2
                            else:
                                # Top-level pipe separator
                                has_pipe = True
                                part_content = "".join(current_part)
                                # Don't strip if this looks like a process substitution with heredoc
                                if "<<" in part_content:
                                    pattern_parts.append(part_content)
                                else:
                                    pattern_parts.append(part_content.strip())
                                current_part = []
                                i += 1
                        else:
                            current_part.append(value[i])
                            i += 1
                    # Join parts with " | "
                    result.append(" | ".join(pattern_parts))
                    # Only append closing ) if we found one (depth == 0)
                    if depth == 0:
                        result.append(")")
                        i += 1
                    continue
            result.append(value[i])
            i += 1
        return "".join(result)

    def get_cond_formatted_value(self) -> str:
        """Return value with command substitutions formatted for cond-term output."""
        # Expand ANSI-C quotes
        value = self._expand_all_ansi_c_quotes(self.value)
        # Strip $ from locale strings $"..."
        value = self._strip_locale_string_dollars(value)
        # Format command substitutions
        value = self._format_command_substitutions(value)
        # Normalize whitespace in extglob-like patterns
        value = self._normalize_extglob_whitespace(value)
        # Bash doubles CTLESC (\x01) characters in output
        value = value.replace("\x01", "\x01\x01")
        return value.rstrip("\n")


class Command(Node):
    """A simple command (words + redirections)."""

    words: list[Word]
    redirects: list[Node]

    def __init__(self, words: list[Word], redirects: list[Node] | None = None):
        self.kind = "command"
        self.words = words
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        parts = []
        for w in self.words:
            parts.append(w.to_sexp())
        for r in self.redirects:
            parts.append(r.to_sexp())
        inner = " ".join(parts)
        if not inner:
            return "(command)"
        return "(command " + inner + ")"


class Pipeline(Node):
    """A pipeline of commands."""

    commands: list[Node]

    def __init__(self, commands: list[Node]):
        self.kind = "pipeline"
        self.commands = commands

    def to_sexp(self) -> str:
        if len(self.commands) == 1:
            return self.commands[0].to_sexp()
        # Build list of (cmd, needs_pipe_both_redirect) filtering out PipeBoth markers
        cmds = []
        i = 0
        while i < len(self.commands):
            cmd = self.commands[i]
            if cmd.kind == "pipe-both":
                i += 1
                continue
            # Check if next element is PipeBoth
            needs_redirect = i + 1 < len(self.commands) and self.commands[i + 1].kind == "pipe-both"
            cmds.append((cmd, needs_redirect))
            i += 1
        if len(cmds) == 1:
            pair = cmds[0]
            cmd = pair[0]
            needs = pair[1]
            return self._cmd_sexp(cmd, needs)
        # Nest right-associatively: (pipe a (pipe b c))
        last_pair = cmds[len(cmds) - 1]
        last_cmd = last_pair[0]
        last_needs = last_pair[1]
        result = self._cmd_sexp(last_cmd, last_needs)
        j = len(cmds) - 2
        while j >= 0:
            pair = cmds[j]
            cmd = pair[0]
            needs = pair[1]
            if needs and cmd.kind != "command":
                # Compound command: redirect as sibling in pipe
                result = "(pipe " + cmd.to_sexp() + ' (redirect ">&" 1) ' + result + ")"
            else:
                result = "(pipe " + self._cmd_sexp(cmd, needs) + " " + result + ")"
            j -= 1
        return result

    def _cmd_sexp(self, cmd: Node, needs_redirect: bool) -> str:
        """Get s-expression for a command, optionally injecting pipe-both redirect."""
        if not needs_redirect:
            return cmd.to_sexp()
        if cmd.kind == "command":
            # Inject redirect inside command
            parts = []
            for w in cmd.words:
                parts.append(w.to_sexp())
            for r in cmd.redirects:
                parts.append(r.to_sexp())
            parts.append('(redirect ">&" 1)')
            return "(command " + " ".join(parts) + ")"
        # Compound command handled by caller
        return cmd.to_sexp()


class List(Node):
    """A list of pipelines with operators."""

    parts: list[Node]  # alternating: pipeline, operator, pipeline, ...

    def __init__(self, parts: list[Node]):
        self.kind = "list"
        self.parts = parts

    def to_sexp(self) -> str:
        # parts = [cmd, op, cmd, op, cmd, ...]
        # Bash precedence: && and || bind tighter than ; and &
        parts = list(self.parts)
        op_names = {"&&": "and", "||": "or", ";": "semi", "\n": "semi", "&": "background"}
        # Strip trailing ; or \n (bash ignores it)
        while (
            len(parts) > 1
            and parts[len(parts) - 1].kind == "operator"
            and (parts[len(parts) - 1].op == ";" or parts[len(parts) - 1].op == "\n")
        ):
            parts = _sublist(parts, 0, len(parts) - 1)
        if len(parts) == 1:
            return parts[0].to_sexp()
        # Handle trailing & as unary background operator
        # & only applies to the immediately preceding pipeline, not the whole list
        if parts[len(parts) - 1].kind == "operator" and parts[len(parts) - 1].op == "&":
            # Find rightmost ; or \n to split there
            for i in range(len(parts) - 3, 0, -2):
                if parts[i].kind == "operator" and (parts[i].op == ";" or parts[i].op == "\n"):
                    left = _sublist(parts, 0, i)
                    right = _sublist(parts, i + 1, len(parts) - 1)  # exclude trailing &
                    if len(left) > 1:
                        left_sexp = List(left).to_sexp()
                    else:
                        left_sexp = left[0].to_sexp()
                    if len(right) > 1:
                        right_sexp = List(right).to_sexp()
                    else:
                        right_sexp = right[0].to_sexp()
                    return "(semi " + left_sexp + " (background " + right_sexp + "))"
            # No ; or \n found, background the whole list (minus trailing &)
            inner_parts = _sublist(parts, 0, len(parts) - 1)
            if len(inner_parts) == 1:
                return "(background " + inner_parts[0].to_sexp() + ")"
            inner_list = List(inner_parts)
            return "(background " + inner_list.to_sexp() + ")"
        # Process by precedence: first split on ; and &, then on && and ||
        return self._to_sexp_with_precedence(parts, op_names)

    def _to_sexp_with_precedence(self, parts: list[Node], op_names: dict[str, str]) -> str:
        # Process operators by precedence: ; (lowest), then &, then && and ||
        # Use iterative approach to avoid stack overflow on large lists
        # Find all ; or \n positions (may not be at regular intervals due to consecutive ops)
        semi_positions = []
        for i in range(len(parts)):
            if parts[i].kind == "operator" and (parts[i].op == ";" or parts[i].op == "\n"):
                semi_positions.append(i)
        if semi_positions:
            # Split into segments at ; and \n positions, filtering empty/operator-only segments
            segments = []
            start = 0
            for pos in semi_positions:
                seg = _sublist(parts, start, pos)
                if seg and seg[0].kind != "operator":
                    segments.append(seg)
                start = pos + 1
            # Final segment
            seg = _sublist(parts, start, len(parts))
            if seg and seg[0].kind != "operator":
                segments.append(seg)
            if not segments:
                return "()"
            # Build left-associative result iteratively
            result = self._to_sexp_amp_and_higher(segments[0], op_names)
            for i in range(1, len(segments)):
                result = (
                    "(semi "
                    + result
                    + " "
                    + self._to_sexp_amp_and_higher(segments[i], op_names)
                    + ")"
                )
            return result
        # No ; or \n, handle & and higher
        return self._to_sexp_amp_and_higher(parts, op_names)

    def _to_sexp_amp_and_higher(self, parts: list[Node], op_names: dict[str, str]) -> str:
        # Handle & operator iteratively
        if len(parts) == 1:
            return parts[0].to_sexp()
        amp_positions = []
        for i in range(1, len(parts) - 1, 2):
            if parts[i].kind == "operator" and parts[i].op == "&":
                amp_positions.append(i)
        if amp_positions:
            # Split into segments at & positions
            segments = []
            start = 0
            for pos in amp_positions:
                segments.append(_sublist(parts, start, pos))
                start = pos + 1
            segments.append(_sublist(parts, start, len(parts)))
            # Build left-associative result iteratively
            result = self._to_sexp_and_or(segments[0], op_names)
            for i in range(1, len(segments)):
                result = (
                    "(background "
                    + result
                    + " "
                    + self._to_sexp_and_or(segments[i], op_names)
                    + ")"
                )
            return result
        # No &, handle && and ||
        return self._to_sexp_and_or(parts, op_names)

    def _to_sexp_and_or(self, parts: list[Node], op_names: dict[str, str]) -> str:
        # Process && and || left-associatively (already iterative)
        if len(parts) == 1:
            return parts[0].to_sexp()
        result = parts[0].to_sexp()
        for i in range(1, len(parts) - 1, 2):
            op = parts[i]
            cmd = parts[i + 1]
            op_name = op_names.get(op.op, op.op)
            result = "(" + op_name + " " + result + " " + cmd.to_sexp() + ")"
        return result


class Operator(Node):
    """An operator token (&&, ||, ;, &, |)."""

    op: str

    def __init__(self, op: str):
        self.kind = "operator"
        self.op = op

    def to_sexp(self) -> str:
        names = {
            "&&": "and",
            "||": "or",
            ";": "semi",
            "&": "bg",
            "|": "pipe",
        }
        return "(" + names.get(self.op, self.op) + ")"


class PipeBoth(Node):
    """Marker for |& pipe (stdout + stderr)."""

    def __init__(self):
        self.kind = "pipe-both"

    def to_sexp(self) -> str:
        return "(pipe-both)"


class Empty(Node):
    """Empty input."""

    def __init__(self):
        self.kind = "empty"

    def to_sexp(self) -> str:
        return ""


class Comment(Node):
    """A comment (# to end of line)."""

    text: str

    def __init__(self, text: str):
        self.kind = "comment"
        self.text = text

    def to_sexp(self) -> str:
        # bash-oracle doesn't output comments
        return ""


class Redirect(Node):
    """A redirection."""

    op: str
    target: Word
    fd: int = -1  # -1 = no fd specified

    def __init__(self, op: str, target: Word, fd: int = -1):
        self.kind = "redirect"
        self.op = op
        self.target = target
        self.fd = fd  # -1 = no fd specified

    def to_sexp(self) -> str:
        # Strip fd prefix from operator (e.g., "2>" -> ">", "{fd}>" -> ">")
        op = self.op.lstrip("0123456789")
        # Strip {varname} or {varname[subscript]} prefix if present
        if op.startswith("{"):
            j = 1
            if j < len(op) and (op[j].isalpha() or op[j] == "_"):
                j += 1
                while j < len(op) and (op[j].isalnum() or op[j] == "_"):
                    j += 1
                # Handle optional [subscript] part
                if j < len(op) and op[j] == "[":
                    j += 1
                    while j < len(op) and op[j] != "]":
                        j += 1
                    if j < len(op) and op[j] == "]":
                        j += 1
                if j < len(op) and op[j] == "}":
                    op = _substring(op, j + 1, len(op))
        target_val = self.target.value
        # Expand ANSI-C $'...' quotes (converts escapes like \n to actual newline)
        target_val = self.target._expand_all_ansi_c_quotes(target_val)
        # Strip $ from locale strings $"..."
        target_val = self.target._strip_locale_string_dollars(target_val)
        # Format command/process substitutions (uses self.target for parts access)
        target_val = self.target._format_command_substitutions(target_val)
        # Strip line continuations (backslash-newline) from arithmetic expressions
        target_val = self.target._strip_arith_line_continuations(target_val)
        # Escape trailing backslash (would escape the closing quote otherwise)
        if target_val.endswith("\\") and not target_val.endswith("\\\\"):
            target_val = target_val + "\\"
        # For fd duplication, target starts with & (e.g., "&1", "&2", "&-")
        if target_val.startswith("&"):
            # Determine the real operator
            if op == ">":
                op = ">&"
            elif op == "<":
                op = "<&"
            raw = _substring(target_val, 1, len(target_val))  # "&0--" -> "0--"
            # Pure digits: dup fd N (must be <= INT_MAX to be a valid fd)
            if raw.isdigit() and int(raw) <= 2147483647:
                return '(redirect "' + op + '" ' + str(int(raw)) + ")"
            # Exact move syntax: N- (digits + exactly one dash, N <= INT_MAX)
            if raw.endswith("-") and raw[:-1].isdigit() and int(raw[:-1]) <= 2147483647:
                return '(redirect "' + op + '" ' + str(int(raw[:-1])) + ")"
            if target_val == "&-":
                return '(redirect ">&-" 0)'
            # Variable/word target: strip exactly one trailing dash if present
            fd_target = raw[:-1] if raw.endswith("-") else raw
            return '(redirect "' + op + '" "' + fd_target + '")'
        # Handle case where op is already >& or <&
        if op == ">&" or op == "<&":
            # Valid fd number must be digits and <= INT_MAX (2147483647)
            if target_val.isdigit() and int(target_val) <= 2147483647:
                return '(redirect "' + op + '" ' + str(int(target_val)) + ")"
            # Handle close: <& - or >& - (with space before -)
            if target_val == "-":
                return '(redirect ">&-" 0)'
            # Exact move syntax: N- (digits + exactly one dash, N <= INT_MAX)
            if (
                target_val.endswith("-")
                and target_val[:-1].isdigit()
                and int(target_val[:-1]) <= 2147483647
            ):
                return '(redirect "' + op + '" ' + str(int(target_val[:-1])) + ")"
            # Variable/word target: strip exactly one trailing dash if present
            out_val = target_val[:-1] if target_val.endswith("-") else target_val
            return '(redirect "' + op + '" "' + out_val + '")'
        return '(redirect "' + op + '" "' + target_val + '")'


class HereDoc(Node):
    """A here document <<DELIM ... DELIM."""

    delimiter: str
    content: str
    strip_tabs: bool = False
    quoted: bool = False
    fd: int = -1  # -1 = no fd specified
    complete: bool = True
    _start_pos: int = -1  # Parser position where heredoc redirect started (for dedup)

    def __init__(
        self,
        delimiter: str,
        content: str,
        strip_tabs: bool = False,
        quoted: bool = False,
        fd: int = -1,
        complete: bool = True,
    ):
        self.kind = "heredoc"
        self.delimiter = delimiter
        self.content = content
        self.strip_tabs = strip_tabs
        self.quoted = quoted
        self.fd = fd  # -1 = no fd specified
        self.complete = complete
        self._start_pos = -1

    def to_sexp(self) -> str:
        op = "<<-" if self.strip_tabs else "<<"
        content = self.content
        # Escape trailing backslash (would escape the closing quote otherwise)
        if content.endswith("\\") and not content.endswith("\\\\"):
            content = content + "\\"
        return f'(redirect "{op}" "{content}")'


class Subshell(Node):
    """A subshell ( list )."""

    body: Node
    redirects: list[Redirect | HereDoc] | None = None

    def __init__(self, body: Node, redirects: list[Redirect | HereDoc] | None = None):
        self.kind = "subshell"
        self.body = body
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(subshell " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class BraceGroup(Node):
    """A brace group { list; }."""

    body: Node
    redirects: list[Redirect | HereDoc] | None = None

    def __init__(self, body: Node, redirects: list[Redirect | HereDoc] | None = None):
        self.kind = "brace-group"
        self.body = body
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(brace-group " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class If(Node):
    """An if statement."""

    condition: Node
    then_body: Node
    else_body: Node | None = None
    redirects: list[Node]

    def __init__(
        self,
        condition: Node,
        then_body: Node,
        else_body: Node | None = None,
        redirects: list[Node] | None = None,
    ):
        self.kind = "if"
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        result = "(if " + self.condition.to_sexp() + " " + self.then_body.to_sexp()
        if self.else_body:
            result = result + " " + self.else_body.to_sexp()
        result = result + ")"
        for r in self.redirects:
            result = result + " " + r.to_sexp()
        return result


class While(Node):
    """A while loop."""

    condition: Node
    body: Node
    redirects: list[Node]

    def __init__(self, condition: Node, body: Node, redirects: list[Node] | None = None):
        self.kind = "while"
        self.condition = condition
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(while " + self.condition.to_sexp() + " " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class Until(Node):
    """An until loop."""

    condition: Node
    body: Node
    redirects: list[Node]

    def __init__(self, condition: Node, body: Node, redirects: list[Node] | None = None):
        self.kind = "until"
        self.condition = condition
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(until " + self.condition.to_sexp() + " " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class For(Node):
    """A for loop."""

    var: str
    words: list[Word] | None
    body: Node
    redirects: list[Node]

    def __init__(
        self, var: str, words: list[Word] | None, body: Node, redirects: list[Node] | None = None
    ):
        self.kind = "for"
        self.var = var
        self.words = words
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (for (word "var") (in (word "a") ...) body)
        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        # Format command substitutions in var (e.g., for $(echo i) normalizes whitespace)
        temp_word = Word(self.var, [])
        var_formatted = temp_word._format_command_substitutions(self.var)
        var_escaped = var_formatted.replace("\\", "\\\\").replace('"', '\\"')
        if self.words is None:
            # No 'in' clause - bash-oracle implies (in (word "\"$@\""))
            return (
                '(for (word "'
                + var_escaped
                + '") (in (word "\\"$@\\"")) '
                + self.body.to_sexp()
                + ")"
                + suffix
            )
        elif len(self.words) == 0:
            # Empty 'in' clause - bash-oracle outputs (in)
            return '(for (word "' + var_escaped + '") (in) ' + self.body.to_sexp() + ")" + suffix
        else:
            word_parts = []
            for w in self.words:
                word_parts.append(w.to_sexp())
            word_strs = " ".join(word_parts)
            return (
                '(for (word "'
                + var_escaped
                + '") (in '
                + word_strs
                + ") "
                + self.body.to_sexp()
                + ")"
                + suffix
            )


def _format_arith_val(s: str) -> str:
    """Format arithmetic value for sexp output."""
    w = Word(s, [])
    val = w._expand_all_ansi_c_quotes(s)
    val = w._strip_locale_string_dollars(val)
    val = w._format_command_substitutions(val)
    val = val.replace("\\", "\\\\").replace('"', '\\"')
    val = val.replace("\n", "\\n").replace("\t", "\\t")
    return val


class ForArith(Node):
    """A C-style for loop: for ((init; cond; incr)); do ... done."""

    init: str
    cond: str
    incr: str
    body: Node
    redirects: list[Node]

    def __init__(
        self, init: str, cond: str, incr: str, body: Node, redirects: list[Node] | None = None
    ):
        self.kind = "for-arith"
        self.init = init
        self.cond = cond
        self.incr = incr
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (arith-for (init (word "x")) (test (word "y")) (step (word "z")) body)
        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        init_val = self.init if self.init else "1"
        cond_val = self.cond if self.cond else "1"
        incr_val = self.incr if self.incr else "1"
        init_str = _format_arith_val(init_val)
        cond_str = _format_arith_val(cond_val)
        incr_str = _format_arith_val(incr_val)
        body_str = self.body.to_sexp()
        return f'(arith-for (init (word "{init_str}")) (test (word "{cond_str}")) (step (word "{incr_str}")) {body_str}){suffix}'


class Select(Node):
    """A select statement."""

    var: str
    words: list[Word] | None
    body: Node
    redirects: list[Node]

    def __init__(
        self, var: str, words: list[Word] | None, body: Node, redirects: list[Node] | None = None
    ):
        self.kind = "select"
        self.var = var
        self.words = words
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (select (word "var") (in (word "a") ...) body)
        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        var_escaped = self.var.replace("\\", "\\\\").replace('"', '\\"')
        if self.words is not None:
            word_parts = []
            for w in self.words:
                word_parts.append(w.to_sexp())
            word_strs = " ".join(word_parts)
            if self.words:
                in_clause = "(in " + word_strs + ")"
            else:
                in_clause = "(in)"
        else:
            # No 'in' clause means implicit "$@"
            in_clause = '(in (word "\\"$@\\""))'
        return (
            '(select (word "'
            + var_escaped
            + '") '
            + in_clause
            + " "
            + self.body.to_sexp()
            + ")"
            + suffix
        )


class Case(Node):
    """A case statement."""

    word: Word
    patterns: list[CasePattern]
    redirects: list[Node]

    def __init__(
        self, word: Word, patterns: list[CasePattern], redirects: list[Node] | None = None
    ):
        self.kind = "case"
        self.word = word
        self.patterns = patterns
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        parts = []
        parts.append("(case " + self.word.to_sexp())
        for p in self.patterns:
            parts.append(p.to_sexp())
        base = " ".join(parts) + ")"
        return _append_redirects(base, self.redirects)


def _consume_single_quote(s: str, start: int) -> tuple[int, list[str]]:
    """Consume '...' from start. Returns (end_index, chars_list)."""
    chars = ["'"]
    i = start + 1
    while i < len(s) and s[i] != "'":
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars)


def _consume_double_quote(s: str, start: int) -> tuple[int, list[str]]:
    """Consume "..." from start, handling escapes. Returns (end_index, chars_list)."""
    chars = ['"']
    i = start + 1
    while i < len(s) and s[i] != '"':
        if s[i] == "\\" and i + 1 < len(s):
            chars.append(s[i])
            i += 1
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars)


def _has_bracket_close(s: str, start: int, depth: int) -> bool:
    """Check if there's a ] before | or ) at depth 0."""
    i = start
    while i < len(s):
        if s[i] == "]":
            return True
        if (s[i] == "|" or s[i] == ")") and depth == 0:
            return False
        i += 1
    return False


def _consume_bracket_class(s: str, start: int, depth: int) -> tuple[int, list[str], bool]:
    """Consume [...] bracket expression. Returns (end_index, chars_list, was_bracket)."""
    # First scan to see if this is a valid bracket expression
    scan_pos = start + 1
    # Skip [! or [^ at start
    if scan_pos < len(s) and (s[scan_pos] == "!" or s[scan_pos] == "^"):
        scan_pos += 1
    # Handle ] as first char
    if scan_pos < len(s) and s[scan_pos] == "]":
        if _has_bracket_close(s, scan_pos + 1, depth):
            scan_pos += 1
    # Scan for closing ]
    is_bracket = False
    while scan_pos < len(s):
        if s[scan_pos] == "]":
            is_bracket = True
            break
        if s[scan_pos] == ")" and depth == 0:
            break
        if s[scan_pos] == "|" and depth == 0:
            break
        scan_pos += 1
    if not is_bracket:
        return (start + 1, ["["], False)
    # Valid bracket - consume it
    chars = ["["]
    i = start + 1
    # Handle [! or [^
    if i < len(s) and (s[i] == "!" or s[i] == "^"):
        chars.append(s[i])
        i += 1
    # Handle ] as first char
    if i < len(s) and s[i] == "]":
        if _has_bracket_close(s, i + 1, depth):
            chars.append(s[i])
            i += 1
    # Consume until ]
    while i < len(s) and s[i] != "]":
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars, True)


class CasePattern(Node):
    """A pattern clause in a case statement."""

    pattern: str
    body: Node | None
    terminator: str = ";;"  # ";;", ";&", or ";;&"

    def __init__(self, pattern: str, body: Node | None, terminator: str = ";;"):
        self.kind = "pattern"
        self.pattern = pattern
        self.body = body
        self.terminator = terminator

    def to_sexp(self) -> str:
        # bash-oracle format: (pattern ((word "a") (word "b")) body)
        # Split pattern by | respecting escapes, extglobs, quotes, and brackets
        alternatives = []
        current = []
        i = 0
        depth = 0  # Track extglob/paren depth
        while i < len(self.pattern):
            ch = self.pattern[i]
            if ch == "\\" and i + 1 < len(self.pattern):
                current.append(_substring(self.pattern, i, i + 2))
                i += 2
            elif (
                (ch == "@" or ch == "?" or ch == "*" or ch == "+" or ch == "!")
                and i + 1 < len(self.pattern)
                and self.pattern[i + 1] == "("
            ):
                # Start of extglob: @(, ?(, *(, +(, !(
                current.append(ch)
                current.append("(")
                depth += 1
                i += 2
            elif _is_expansion_start(self.pattern, i, "$("):
                # $( command sub or $(( arithmetic - track depth
                current.append(ch)
                current.append("(")
                depth += 1
                i += 2
            elif ch == "(" and depth > 0:
                current.append(ch)
                depth += 1
                i += 1
            elif ch == ")" and depth > 0:
                current.append(ch)
                depth -= 1
                i += 1
            elif ch == "[":
                result = _consume_bracket_class(self.pattern, i, depth)
                i = result[0]
                current.extend(result[1])
            elif ch == "'" and depth == 0:
                result = _consume_single_quote(self.pattern, i)
                i = result[0]
                current.extend(result[1])
            elif ch == '"' and depth == 0:
                result = _consume_double_quote(self.pattern, i)
                i = result[0]
                current.extend(result[1])
            elif ch == "|" and depth == 0:
                alternatives.append("".join(current))
                current = []
                i += 1
            else:
                current.append(ch)
                i += 1
        alternatives.append("".join(current))
        word_list = []
        for alt in alternatives:
            # Use Word.to_sexp() to properly expand ANSI-C quotes and escape
            word_list.append(Word(alt).to_sexp())
        pattern_str = " ".join(word_list)
        parts = ["(pattern (" + pattern_str + ")"]
        if self.body:
            parts.append(" " + self.body.to_sexp())
        else:
            parts.append(" ()")
        # bash-oracle doesn't output fallthrough/falltest markers
        parts.append(")")
        return "".join(parts)


class Function(Node):
    """A function definition."""

    name: str
    body: Node

    def __init__(self, name: str, body: Node):
        self.kind = "function"
        self.name = name
        self.body = body

    def to_sexp(self) -> str:
        return '(function "' + self.name + '" ' + self.body.to_sexp() + ")"


class ParamExpansion(Node):
    """A parameter expansion ${var} or ${var:-default}."""

    param: str
    op: str | None = None
    arg: str | None = None

    def __init__(self, param: str, op: str | None = None, arg: str | None = None):
        self.kind = "param"
        self.param = param
        self.op = op
        self.arg = arg

    def to_sexp(self) -> str:
        escaped_param = self.param.replace("\\", "\\\\").replace('"', '\\"')
        if self.op is not None:
            escaped_op = self.op.replace("\\", "\\\\").replace('"', '\\"')
            if self.arg is not None:
                arg_val = self.arg
            else:
                arg_val = ""
            escaped_arg = arg_val.replace("\\", "\\\\").replace('"', '\\"')
            return '(param "' + escaped_param + '" "' + escaped_op + '" "' + escaped_arg + '")'
        return '(param "' + escaped_param + '")'


class ParamLength(Node):
    """A parameter length expansion ${#var}."""

    param: str

    def __init__(self, param: str):
        self.kind = "param-len"
        self.param = param

    def to_sexp(self) -> str:
        escaped = self.param.replace("\\", "\\\\").replace('"', '\\"')
        return '(param-len "' + escaped + '")'


class ParamIndirect(Node):
    """An indirect parameter expansion ${!var} or ${!var<op><arg>}."""

    param: str
    op: str | None
    arg: str | None

    def __init__(self, param: str, op: str | None = None, arg: str | None = None):
        self.kind = "param-indirect"
        self.param = param
        self.op = op
        self.arg = arg

    def to_sexp(self) -> str:
        escaped = self.param.replace("\\", "\\\\").replace('"', '\\"')
        if self.op is not None:
            escaped_op = self.op.replace("\\", "\\\\").replace('"', '\\"')
            if self.arg is not None:
                arg_val = self.arg
            else:
                arg_val = ""
            escaped_arg = arg_val.replace("\\", "\\\\").replace('"', '\\"')
            return '(param-indirect "' + escaped + '" "' + escaped_op + '" "' + escaped_arg + '")'
        return '(param-indirect "' + escaped + '")'


class CommandSubstitution(Node):
    """A command substitution $(...), `...`, or ${ cmd; }."""

    command: Node
    brace: bool

    def __init__(self, command: Node, brace: bool = False):
        self.kind = "cmdsub"
        self.command = command
        self.brace = brace

    def to_sexp(self) -> str:
        if self.brace:
            return "(funsub " + self.command.to_sexp() + ")"
        return "(cmdsub " + self.command.to_sexp() + ")"


class ArithmeticExpansion(Node):
    """An arithmetic expansion $((...)) with parsed internals."""

    expression: ArithNode | None  # Parsed arithmetic expression, or None for empty

    def __init__(self, expression: ArithNode | None):
        self.kind = "arith"
        self.expression = expression

    def to_sexp(self) -> str:
        if self.expression is None:
            return "(arith)"
        return "(arith " + self.expression.to_sexp() + ")"


class ArithmeticCommand(Node):
    """An arithmetic command ((...)) with parsed internals."""

    expression: ArithNode | None  # Parsed arithmetic expression, or None for empty
    redirects: list[Redirect | HereDoc]
    raw_content: str  # Raw expression text for bash-oracle-compatible output

    def __init__(
        self,
        expression: ArithNode | None,
        redirects: list[Redirect | HereDoc] | None = None,
        raw_content: str = "",
    ):
        self.kind = "arith-cmd"
        self.expression = expression
        if redirects is None:
            redirects = []
        self.redirects = redirects
        self.raw_content = raw_content

    def to_sexp(self) -> str:
        # bash-oracle format: (arith (word "content"))
        # Redirects are siblings: (arith (word "...")) (redirect ...)
        # Format command substitutions using Word's method
        formatted = Word(self.raw_content)._format_command_substitutions(
            self.raw_content, in_arith=True
        )
        escaped = (
            formatted.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        result = '(arith (word "' + escaped + '"))'
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            redirect_sexps = " ".join(redirect_parts)
            return result + " " + redirect_sexps
        return result


# Arithmetic expression nodes


class ArithNumber(Node):
    """A numeric literal in arithmetic context."""

    value: str  # Raw string (may be hex, octal, base#n)

    def __init__(self, value: str):
        self.kind = "number"
        self.value = value

    def to_sexp(self) -> str:
        return '(number "' + self.value + '")'


class ArithEmpty(Node):
    """A missing operand in arithmetic context (e.g., in $((|)) or $((1|)))."""

    def __init__(self):
        self.kind = "empty"

    def to_sexp(self) -> str:
        return "(empty)"


class ArithVar(Node):
    """A variable reference in arithmetic context (without $)."""

    name: str

    def __init__(self, name: str):
        self.kind = "var"
        self.name = name

    def to_sexp(self) -> str:
        return '(var "' + self.name + '")'


class ArithBinaryOp(Node):
    """A binary operation in arithmetic."""

    op: str
    left: ArithNode
    right: ArithNode

    def __init__(self, op: str, left: ArithNode, right: ArithNode):
        self.kind = "binary-op"
        self.op = op
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return (
            '(binary-op "' + self.op + '" ' + self.left.to_sexp() + " " + self.right.to_sexp() + ")"
        )


class ArithUnaryOp(Node):
    """A unary operation in arithmetic."""

    op: str
    operand: ArithNode

    def __init__(self, op: str, operand: ArithNode):
        self.kind = "unary-op"
        self.op = op
        self.operand = operand

    def to_sexp(self) -> str:
        return '(unary-op "' + self.op + '" ' + self.operand.to_sexp() + ")"


class ArithPreIncr(Node):
    """Pre-increment ++var."""

    operand: ArithNode

    def __init__(self, operand: ArithNode):
        self.kind = "pre-incr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(pre-incr " + self.operand.to_sexp() + ")"


class ArithPostIncr(Node):
    """Post-increment var++."""

    operand: ArithNode

    def __init__(self, operand: ArithNode):
        self.kind = "post-incr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(post-incr " + self.operand.to_sexp() + ")"


class ArithPreDecr(Node):
    """Pre-decrement --var."""

    operand: ArithNode

    def __init__(self, operand: ArithNode):
        self.kind = "pre-decr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(pre-decr " + self.operand.to_sexp() + ")"


class ArithPostDecr(Node):
    """Post-decrement var--."""

    operand: ArithNode

    def __init__(self, operand: ArithNode):
        self.kind = "post-decr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(post-decr " + self.operand.to_sexp() + ")"


class ArithAssign(Node):
    """Assignment operation (=, +=, -=, etc.)."""

    op: str
    target: ArithNode
    value: ArithNode

    def __init__(self, op: str, target: ArithNode, value: ArithNode):
        self.kind = "assign"
        self.op = op
        self.target = target
        self.value = value

    def to_sexp(self) -> str:
        return (
            '(assign "' + self.op + '" ' + self.target.to_sexp() + " " + self.value.to_sexp() + ")"
        )


class ArithTernary(Node):
    """Ternary conditional expr ? expr : expr."""

    condition: ArithNode
    if_true: ArithNode
    if_false: ArithNode

    def __init__(self, condition: ArithNode, if_true: ArithNode, if_false: ArithNode):
        self.kind = "ternary"
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false

    def to_sexp(self) -> str:
        return (
            "(ternary "
            + self.condition.to_sexp()
            + " "
            + self.if_true.to_sexp()
            + " "
            + self.if_false.to_sexp()
            + ")"
        )


class ArithComma(Node):
    """Comma operator expr, expr."""

    left: ArithNode
    right: ArithNode

    def __init__(self, left: ArithNode, right: ArithNode):
        self.kind = "comma"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(comma " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class ArithSubscript(Node):
    """Array subscript arr[expr]."""

    array: str
    index: ArithNode

    def __init__(self, array: str, index: ArithNode):
        self.kind = "subscript"
        self.array = array
        self.index = index

    def to_sexp(self) -> str:
        return '(subscript "' + self.array + '" ' + self.index.to_sexp() + ")"


class ArithEscape(Node):
    """An escaped character in arithmetic expression."""

    char: str

    def __init__(self, char: str):
        self.kind = "escape"
        self.char = char

    def to_sexp(self) -> str:
        return '(escape "' + self.char + '")'


class ArithDeprecated(Node):
    """A deprecated arithmetic expansion $[expr]."""

    expression: str

    def __init__(self, expression: str):
        self.kind = "arith-deprecated"
        self.expression = expression

    def to_sexp(self) -> str:
        escaped = self.expression.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '(arith-deprecated "' + escaped + '")'


class ArithConcat(Node):
    """A concatenation of prefix + expansion in arithmetic (e.g., 0x$var)."""

    parts: list[ArithNode]

    def __init__(self, parts: list[ArithNode]):
        self.kind = "arith-concat"
        self.parts = parts

    def to_sexp(self) -> str:
        sexps = []
        for p in self.parts:
            sexps.append(p.to_sexp())
        return "(arith-concat " + " ".join(sexps) + ")"


class AnsiCQuote(Node):
    """An ANSI-C quoted string $'...'."""

    content: str

    def __init__(self, content: str):
        self.kind = "ansi-c"
        self.content = content

    def to_sexp(self) -> str:
        escaped = self.content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '(ansi-c "' + escaped + '")'


class LocaleString(Node):
    """A locale-translated string $"..."."""

    content: str

    def __init__(self, content: str):
        self.kind = "locale"
        self.content = content

    def to_sexp(self) -> str:
        escaped = self.content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '(locale "' + escaped + '")'


class ProcessSubstitution(Node):
    """A process substitution <(...) or >(...)."""

    direction: str  # "<" for input, ">" for output
    command: Node

    def __init__(self, direction: str, command: Node):
        self.kind = "procsub"
        self.direction = direction
        self.command = command

    def to_sexp(self) -> str:
        return '(procsub "' + self.direction + '" ' + self.command.to_sexp() + ")"


class Negation(Node):
    """Pipeline negation with !."""

    pipeline: Node

    def __init__(self, pipeline: Node):
        self.kind = "negation"
        self.pipeline = pipeline

    def to_sexp(self) -> str:
        if self.pipeline is None:
            # Bare "!" with no command - bash-oracle shows empty command
            return "(negation (command))"
        return "(negation " + self.pipeline.to_sexp() + ")"


class Time(Node):
    """Time measurement with time keyword."""

    pipeline: Node
    posix: bool = False  # -p flag

    def __init__(self, pipeline: Node, posix: bool = False):
        self.kind = "time"
        self.pipeline = pipeline
        self.posix = posix

    def to_sexp(self) -> str:
        if self.pipeline is None:
            # Bare "time" with no command - bash-oracle shows empty command
            if self.posix:
                return "(time -p (command))"
            else:
                return "(time (command))"
        if self.posix:
            return "(time -p " + self.pipeline.to_sexp() + ")"
        return "(time " + self.pipeline.to_sexp() + ")"


class ConditionalExpr(Node):
    """A conditional expression [[ expression ]]."""

    body: CondNode | str  # Parsed node or raw string for backwards compat
    redirects: list[Redirect | HereDoc]

    def __init__(self, body: CondNode | str, redirects: list[Redirect | HereDoc] | None = None):
        self.kind = "cond-expr"
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (cond ...) not (cond-expr ...)
        # Redirects are siblings, not children: (cond ...) (redirect ...)
        body = self.body
        if isinstance(body, str):
            escaped = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            result = '(cond "' + escaped + '")'
        else:
            result = "(cond " + body.to_sexp() + ")"
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            redirect_sexps = " ".join(redirect_parts)
            return result + " " + redirect_sexps
        return result


class UnaryTest(Node):
    """A unary test in [[ ]], e.g., -f file, -z string."""

    op: str
    operand: Word

    def __init__(self, op: str, operand: Word):
        self.kind = "unary-test"
        self.op = op
        self.operand = operand

    def to_sexp(self) -> str:
        # bash-oracle format: (cond-unary "-f" (cond-term "file"))
        # cond-term preserves content as-is (no backslash escaping)
        operand_val = self.operand.get_cond_formatted_value()
        return '(cond-unary "' + self.op + '" (cond-term "' + operand_val + '"))'


class BinaryTest(Node):
    """A binary test in [[ ]], e.g., $a == $b, file1 -nt file2."""

    op: str
    left: Word
    right: Word

    def __init__(self, op: str, left: Word, right: Word):
        self.kind = "binary-test"
        self.op = op
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        # bash-oracle format: (cond-binary "==" (cond-term "x") (cond-term "y"))
        # cond-term preserves content as-is (no backslash escaping)
        left_val = self.left.get_cond_formatted_value()
        right_val = self.right.get_cond_formatted_value()
        return (
            '(cond-binary "'
            + self.op
            + '" (cond-term "'
            + left_val
            + '") (cond-term "'
            + right_val
            + '"))'
        )


class CondAnd(Node):
    """Logical AND in [[ ]], e.g., expr1 && expr2."""

    left: CondNode
    right: CondNode

    def __init__(self, left: CondNode, right: CondNode):
        self.kind = "cond-and"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(cond-and " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class CondOr(Node):
    """Logical OR in [[ ]], e.g., expr1 || expr2."""

    left: CondNode
    right: CondNode

    def __init__(self, left: CondNode, right: CondNode):
        self.kind = "cond-or"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(cond-or " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class CondNot(Node):
    """Logical NOT in [[ ]], e.g., ! expr."""

    operand: CondNode

    def __init__(self, operand: CondNode):
        self.kind = "cond-not"
        self.operand = operand

    def to_sexp(self) -> str:
        # bash-oracle ignores negation - just output the operand
        return self.operand.to_sexp()


class CondParen(Node):
    """Parenthesized group in [[ ]], e.g., ( expr )."""

    inner: CondNode

    def __init__(self, inner: CondNode):
        self.kind = "cond-paren"
        self.inner = inner

    def to_sexp(self) -> str:
        return "(cond-expr " + self.inner.to_sexp() + ")"


# Type aliases for AST node unions (Union required for Python 3.8/3.9 runtime)
ArithNode = Union[  # noqa: UP007
    ArithNumber,
    ArithEmpty,
    ArithVar,
    ArithBinaryOp,
    ArithUnaryOp,
    ArithPreIncr,
    ArithPostIncr,
    ArithPreDecr,
    ArithPostDecr,
    ArithAssign,
    ArithTernary,
    ArithComma,
    ArithSubscript,
    ArithEscape,
    ArithDeprecated,
    ArithConcat,
]

CondNode = Union[UnaryTest, BinaryTest, CondAnd, CondOr, CondNot, CondParen]  # noqa: UP007


class Array(Node):
    """An array literal (word1 word2 ...)."""

    elements: list[Word]

    def __init__(self, elements: list[Word]):
        self.kind = "array"
        self.elements = elements

    def to_sexp(self) -> str:
        if not self.elements:
            return "(array)"
        parts = []
        for e in self.elements:
            parts.append(e.to_sexp())
        inner = " ".join(parts)
        return "(array " + inner + ")"


class Coproc(Node):
    """A coprocess coproc [NAME] command."""

    command: Node
    name: str | None = None

    def __init__(self, command: Node, name: str | None = None):
        self.kind = "coproc"
        self.command = command
        self.name = name

    def to_sexp(self) -> str:
        # Use provided name for compound commands, "COPROC" for simple commands
        if self.name:
            name = self.name
        else:
            name = "COPROC"
        return '(coproc "' + name + '" ' + self.command.to_sexp() + ")"


def _format_cond_body(node: Node) -> str:
    """Format the body of a [[ ]] conditional expression."""
    kind = node.kind
    if kind == "unary-test":
        operand_val = node.operand.get_cond_formatted_value()
        return node.op + " " + operand_val
    if kind == "binary-test":
        left_val = node.left.get_cond_formatted_value()
        right_val = node.right.get_cond_formatted_value()
        return left_val + " " + node.op + " " + right_val
    if kind == "cond-and":
        return _format_cond_body(node.left) + " && " + _format_cond_body(node.right)
    if kind == "cond-or":
        return _format_cond_body(node.left) + " || " + _format_cond_body(node.right)
    if kind == "cond-not":
        return "! " + _format_cond_body(node.operand)
    if kind == "cond-paren":
        return "( " + _format_cond_body(node.inner) + " )"
    return ""


def _starts_with_subshell(node: Node) -> bool:
    """Check if a node starts with a subshell (for compact redirect formatting in procsub)."""
    if node.kind == "subshell":
        return True
    if node.kind == "list":
        for p in node.parts:
            if p.kind != "operator":
                return _starts_with_subshell(p)
        return False
    if node.kind == "pipeline":
        if node.commands:
            return _starts_with_subshell(node.commands[0])
        return False
    return False


def _format_cmdsub_node(
    node: Node,
    indent: int = 0,
    in_procsub: bool = False,
    compact_redirects: bool = False,
    procsub_first: bool = False,
) -> str:
    """Format an AST node for command substitution output (bash-oracle pretty-print format)."""
    if node is None:
        return ""
    sp = _repeat_str(" ", indent)
    inner_sp = _repeat_str(" ", indent + 4)
    if node.kind == "empty":
        return ""
    if node.kind == "command":
        parts = []
        for w in node.words:
            val = w._expand_all_ansi_c_quotes(w.value)
            # Strip $ from locale strings $"..." (quote-aware)
            val = w._strip_locale_string_dollars(val)
            # Normalize whitespace in array assignments
            val = w._normalize_array_whitespace(val)
            val = w._format_command_substitutions(val)
            parts.append(val)
        # Check for heredocs - their bodies need to come at the end
        heredocs: list[HereDoc] = []
        for r in node.redirects:
            if r.kind == "heredoc":
                heredocs.append(r)
        for r in node.redirects:
            # For heredocs, output just the operator part; body comes at end
            parts.append(_format_redirect(r, compact=compact_redirects, heredoc_op_only=True))
        # In compact mode with words, don't add space before redirects
        if compact_redirects and node.words and node.redirects:
            word_parts = parts[: len(node.words)]
            redirect_parts = parts[len(node.words) :]
            result = " ".join(word_parts) + "".join(redirect_parts)
        else:
            result = " ".join(parts)
        # Append heredoc bodies at the end
        for h in heredocs:
            result = result + _format_heredoc_body(h)
        return result
    if node.kind == "pipeline":
        # Build list of (cmd, needs_pipe_both_redirect) filtering out PipeBoth markers
        cmds: list[tuple[Node, bool]] = []
        i = 0
        while i < len(node.commands):
            cmd = node.commands[i]
            if cmd.kind == "pipe-both":
                i += 1
                continue
            # Check if next element is PipeBoth
            needs_redirect = i + 1 < len(node.commands) and node.commands[i + 1].kind == "pipe-both"
            cmds.append((cmd, needs_redirect))
            i += 1
        # Format pipeline, handling heredocs specially
        result_parts = []
        idx = 0
        while idx < len(cmds):
            cmd, needs_redirect = cmds[idx]
            # Only first command in pipeline inherits procsub_first
            formatted = _format_cmdsub_node(
                cmd, indent, in_procsub, False, procsub_first and idx == 0
            )
            is_last = idx == len(cmds) - 1
            # Check if command has actual heredoc redirects
            has_heredoc = False
            if cmd.kind == "command" and cmd.redirects:
                for r in cmd.redirects:
                    if r.kind == "heredoc":
                        has_heredoc = True
                        break
            # Add 2>&1 for |& pipes - before heredoc body if present
            if needs_redirect:
                if has_heredoc:
                    first_nl = formatted.find("\n")
                    if first_nl != -1:
                        formatted = formatted[:first_nl] + " 2>&1" + formatted[first_nl:]
                    else:
                        formatted = formatted + " 2>&1"
                else:
                    formatted = formatted + " 2>&1"
            if not is_last and has_heredoc:
                # Heredoc present - insert pipe after heredoc delimiter, before content
                # Pattern: "... <<DELIM\ncontent\nDELIM\n" -> "... <<DELIM |\ncontent\nDELIM\n"
                first_nl = formatted.find("\n")
                if first_nl != -1:
                    formatted = formatted[:first_nl] + " |" + formatted[first_nl:]
                result_parts.append(formatted)
            else:
                result_parts.append(formatted)
            idx += 1
        # Join with " | " for commands without heredocs, or just join if heredocs handled
        # In procsub, if first command is subshell, use compact "|" separator
        compact_pipe = in_procsub and cmds and cmds[0][0].kind == "subshell"
        result = ""
        idx = 0
        while idx < len(result_parts):
            part = result_parts[idx]
            if idx > 0:
                # If previous part ends with heredoc (newline), add indented command
                if result.endswith("\n"):
                    result = result + "  " + part
                elif compact_pipe:
                    result = result + "|" + part
                else:
                    result = result + " | " + part
            else:
                result = part
            idx += 1
        return result
    if node.kind == "list":
        # Check if any command in the list has a heredoc redirect
        has_heredoc = False
        for p in node.parts:
            if p.kind == "command" and p.redirects:
                for r in p.redirects:
                    if r.kind == "heredoc":
                        has_heredoc = True
                        break
            elif p.kind == "pipeline":
                # Check commands within the pipeline
                for cmd in p.commands:
                    if cmd.kind == "command" and cmd.redirects:
                        for r in cmd.redirects:
                            if r.kind == "heredoc":
                                has_heredoc = True
                                break
                    if has_heredoc:
                        break
        # Join commands with operators
        result = []
        skipped_semi = False
        cmd_count = 0  # Track number of non-operator commands seen
        for p in node.parts:
            if p.kind == "operator":
                if p.op == ";":
                    # Skip semicolon if previous command ends with heredoc (newline)
                    if result and result[len(result) - 1].endswith("\n"):
                        skipped_semi = True
                        continue
                    # Skip semicolon after pattern: heredoc, newline, command
                    if (
                        len(result) >= 3
                        and result[len(result) - 2] == "\n"
                        and result[len(result) - 3].endswith("\n")
                    ):
                        skipped_semi = True
                        continue
                    result.append(";")
                    skipped_semi = False
                elif p.op == "\n":
                    # Skip newline if it follows a semicolon (redundant separator)
                    if result and result[len(result) - 1] == ";":
                        skipped_semi = False
                        continue
                    # If previous ends with heredoc newline
                    if result and result[len(result) - 1].endswith("\n"):
                        # Add space if semicolon was skipped, else newline
                        result.append(" " if skipped_semi else "\n")
                        skipped_semi = False
                        continue
                    result.append("\n")
                    skipped_semi = False
                elif p.op == "&":
                    # If previous command has heredoc, insert & before heredoc content
                    # But if it's a pipeline (contains |), append at end instead
                    if (
                        result
                        and "<<" in result[len(result) - 1]
                        and "\n" in result[len(result) - 1]
                    ):
                        last = result[len(result) - 1]
                        # If this is a pipeline (has |), append & at the end
                        if " |" in last or last.startswith("|"):
                            result[len(result) - 1] = last + " &"
                        else:
                            first_nl = last.find("\n")
                            result[len(result) - 1] = last[:first_nl] + " &" + last[first_nl:]
                    else:
                        result.append(" &")
                else:
                    # For || and &&, insert before heredoc content like we do for &
                    if (
                        result
                        and "<<" in result[len(result) - 1]
                        and "\n" in result[len(result) - 1]
                    ):
                        last = result[len(result) - 1]
                        first_nl = last.find("\n")
                        result[len(result) - 1] = (
                            last[:first_nl] + " " + p.op + " " + last[first_nl:]
                        )
                    else:
                        result.append(" " + p.op)
            else:
                if result and not result[len(result) - 1].endswith((" ", "\n")):
                    result.append(" ")
                # Only first command in list inherits procsub_first
                formatted_cmd = _format_cmdsub_node(
                    p, indent, in_procsub, compact_redirects, procsub_first and cmd_count == 0
                )
                # After heredoc with || or && inserted, add leading space to next command
                if len(result) > 0:
                    last = result[len(result) - 1]
                    if " || \n" in last or " && \n" in last:
                        formatted_cmd = " " + formatted_cmd
                # When semicolon was skipped due to heredoc, add leading space
                if skipped_semi:
                    formatted_cmd = " " + formatted_cmd
                    skipped_semi = False
                result.append(formatted_cmd)
                cmd_count += 1
        # Strip trailing ; or newline (but preserve heredoc's trailing newline)
        s = "".join(result)
        # If we have & with heredoc (& before newline content), preserve trailing newline and add space
        if " &\n" in s and s.endswith("\n"):
            return s + " "
        while s.endswith(";"):
            s = _substring(s, 0, len(s) - 1)
        if not has_heredoc:
            while s.endswith("\n"):
                s = _substring(s, 0, len(s) - 1)
        return s
    if node.kind == "if":
        cond = _format_cmdsub_node(node.condition, indent)
        then_body = _format_cmdsub_node(node.then_body, indent + 4)
        result = "if " + cond + "; then\n" + inner_sp + then_body + ";"
        if node.else_body:
            else_body = _format_cmdsub_node(node.else_body, indent + 4)
            result = result + "\n" + sp + "else\n" + inner_sp + else_body + ";"
        result = result + "\n" + sp + "fi"
        return result
    if node.kind == "while":
        cond = _format_cmdsub_node(node.condition, indent)
        body = _format_cmdsub_node(node.body, indent + 4)
        result = "while " + cond + "; do\n" + inner_sp + body + ";\n" + sp + "done"
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "until":
        cond = _format_cmdsub_node(node.condition, indent)
        body = _format_cmdsub_node(node.body, indent + 4)
        result = "until " + cond + "; do\n" + inner_sp + body + ";\n" + sp + "done"
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "for":
        var = node.var
        body = _format_cmdsub_node(node.body, indent + 4)
        if node.words is not None:
            word_vals: list[str] = []
            for w in node.words:
                word_vals.append(w.value)
            words = " ".join(word_vals)
            if words:
                result = (
                    "for "
                    + var
                    + " in "
                    + words
                    + ";\n"
                    + sp
                    + "do\n"
                    + inner_sp
                    + body
                    + ";\n"
                    + sp
                    + "done"
                )
            else:
                # Empty 'in' clause: for var in ;
                result = (
                    "for " + var + " in ;\n" + sp + "do\n" + inner_sp + body + ";\n" + sp + "done"
                )
        else:
            # No 'in' clause - bash implies 'in "$@"'
            result = (
                "for " + var + ' in "$@";\n' + sp + "do\n" + inner_sp + body + ";\n" + sp + "done"
            )
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "for-arith":
        body = _format_cmdsub_node(node.body, indent + 4)
        result = (
            "for (("
            + node.init
            + "; "
            + node.cond
            + "; "
            + node.incr
            + "))\ndo\n"
            + inner_sp
            + body
            + ";\n"
            + sp
            + "done"
        )
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "case":
        word = node.word.value
        patterns: list[str] = []
        i = 0
        while i < len(node.patterns):
            p = node.patterns[i]
            pat = p.pattern.replace("|", " | ")
            if p.body:
                body = _format_cmdsub_node(p.body, indent + 8)
            else:
                body = ""
            term = p.terminator  # ;;, ;&, or ;;&
            pat_indent = _repeat_str(" ", indent + 8)
            term_indent = _repeat_str(" ", indent + 4)
            body_part = pat_indent + body + "\n" if body else "\n"
            if i == 0:
                # First pattern on same line as 'in'
                patterns.append(" " + pat + ")\n" + body_part + term_indent + term)
            else:
                patterns.append(pat + ")\n" + body_part + term_indent + term)
            i += 1
        pattern_str = ("\n" + _repeat_str(" ", indent + 4)).join(patterns)
        redirects = ""
        if node.redirects:
            redirect_parts: list[str] = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " " + " ".join(redirect_parts)
        return "case " + word + " in" + pattern_str + "\n" + sp + "esac" + redirects
    if node.kind == "function":
        name = node.name
        # Get the body content - if it's a BraceGroup, unwrap it
        inner_body = node.body.body if node.body.kind == "brace-group" else node.body
        body = _format_cmdsub_node(inner_body, indent + 4).rstrip(";")
        return f"function {name} () \n{{ \n{inner_sp}{body}\n}}"
    if node.kind == "subshell":
        body = _format_cmdsub_node(node.body, indent, in_procsub, compact_redirects)
        redirects = ""
        if node.redirects:
            redirect_parts: list[str] = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " ".join(redirect_parts)
        # Use compact format only when subshell is at the start of a procsub
        if procsub_first:
            if redirects:
                return "(" + body + ") " + redirects
            return "(" + body + ")"
        if redirects:
            return "( " + body + " ) " + redirects
        return "( " + body + " )"
    if node.kind == "brace-group":
        body = _format_cmdsub_node(node.body, indent)
        body = body.rstrip(";")  # Strip trailing semicolons before adding our own
        # Don't add semicolon after background operator
        terminator = " }" if body.endswith(" &") else "; }"
        redirects = ""
        if node.redirects:
            redirect_parts: list[str] = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " ".join(redirect_parts)
        if redirects:
            return "{ " + body + terminator + " " + redirects
        return "{ " + body + terminator
    if node.kind == "arith-cmd":
        return "((" + node.raw_content + "))"
    if node.kind == "cond-expr":
        body = _format_cond_body(node.body)
        return "[[ " + body + " ]]"
    if node.kind == "negation":
        if node.pipeline:
            return "! " + _format_cmdsub_node(node.pipeline, indent)
        return "! "
    if node.kind == "time":
        prefix = "time -p " if node.posix else "time "
        if node.pipeline:
            return prefix + _format_cmdsub_node(node.pipeline, indent)
        return prefix
    # Fallback: return empty for unknown types
    return ""


def _format_redirect(
    r: Redirect | HereDoc, compact: bool = False, heredoc_op_only: bool = False
) -> str:
    """Format a redirect for command substitution output."""
    if r.kind == "heredoc":
        if r.strip_tabs:
            op = "<<-"
        else:
            op = "<<"
        # fd > 0: explicitly specified and non-default (0 is default for heredoc input)
        # fd == -1 means "not specified" (sentinel value)
        if r.fd > 0:
            op = str(r.fd) + op
        if r.quoted:
            delim = "'" + r.delimiter + "'"
        else:
            delim = r.delimiter
        if heredoc_op_only:
            # Just the operator part (<<DELIM), body comes separately
            return op + delim
        # Include heredoc content: <<DELIM\ncontent\nDELIM\n
        return op + delim + "\n" + r.content + r.delimiter + "\n"
    op = r.op
    # Normalize default fd: 1> -> >, 0< -> <
    if op == "1>":
        op = ">"
    elif op == "0<":
        op = "<"
    target = r.target.value
    # Expand ANSI-C $'...' quotes
    target = r.target._expand_all_ansi_c_quotes(target)
    # Strip $ from locale strings $"..."
    target = r.target._strip_locale_string_dollars(target)
    # Format command/process substitutions
    target = r.target._format_command_substitutions(target)
    # For fd duplication (target starts with &), handle normalization
    if target.startswith("&"):
        # Normalize N<&- to N>&- (close always uses >)
        was_input_close = False
        if target == "&-" and op.endswith("<"):
            was_input_close = True
            op = _substring(op, 0, len(op) - 1) + ">"
        # Check if target is a literal fd (digit or -)
        after_amp = _substring(target, 1, len(target))
        is_literal_fd = after_amp == "-" or (len(after_amp) > 0 and after_amp[0].isdigit())
        if is_literal_fd:
            # Add default fd for bare >&N or <&N
            if op == ">" or op == ">&":
                # If we normalized from <&-, use fd 0 (stdin), otherwise fd 1 (stdout)
                op = "0>" if was_input_close else "1>"
            elif op == "<" or op == "<&":
                op = "0<"
        else:
            # Variable target: use bare >& or <&
            if op == "1>":
                op = ">"
            elif op == "0<":
                op = "<"
        return op + target
    # For >& and <& (fd dup operators), no space before target
    if op.endswith("&"):
        return op + target
    if compact:
        return op + target
    return op + " " + target


def _format_heredoc_body(r: HereDoc) -> str:
    """Format just the heredoc body part (content + closing delimiter)."""
    return "\n" + r.content + r.delimiter + "\n"


def _lookahead_for_esac(value: str, start: int, case_depth: int) -> bool:
    """Look ahead from start to find if esac closes all cases before a closing ).

    Returns True if we find esac that brings case_depth to 0.
    Returns False if we hit a ) that would close the command substitution.
    """
    i = start
    depth = case_depth
    quote = QuoteState()
    while i < len(value):
        c = value[i]
        # Handle escapes (only in double quotes)
        if c == "\\" and i + 1 < len(value) and quote.double:
            i += 2
            continue
        # Track quote state
        if c == "'" and not quote.double:
            quote.single = not quote.single
            i += 1
            continue
        if c == '"' and not quote.single:
            quote.double = not quote.double
            i += 1
            continue
        # Skip content inside quotes
        if quote.single or quote.double:
            i += 1
            continue
        # Check for case/esac keywords
        if _starts_with_at(value, i, "case") and _is_word_boundary(value, i, 4):
            depth += 1
            i += 4
        elif _starts_with_at(value, i, "esac") and _is_word_boundary(value, i, 4):
            depth -= 1
            if depth == 0:
                return True
            i += 4
        elif c == "(":
            i += 1
        elif c == ")":
            if depth > 0:
                i += 1
            else:
                break
        else:
            i += 1
    return False


def _skip_backtick(value: str, start: int) -> int:
    """Skip past a backtick command substitution. Returns position after closing `."""
    i = start + 1  # Skip opening `
    while i < len(value) and value[i] != "`":
        if value[i] == "\\" and i + 1 < len(value):
            i += 2
        else:
            i += 1
    if i < len(value):
        i += 1  # Skip closing `
    return i


def _skip_single_quoted(s: str, start: int) -> int:
    """Skip from after opening ' to after closing '. Mirrors bash skip_single_quoted()."""
    i = start
    while i < len(s) and s[i] != "'":
        i += 1
    return i + 1 if i < len(s) else i


def _skip_double_quoted(s: str, start: int) -> int:
    """Skip from after opening " to after closing ". Handles $(), ${}, backticks."""
    i, n = start, len(s)
    pass_next = backq = False
    while i < n:
        c = s[i]
        if pass_next:
            pass_next = False
            i += 1
            continue
        if c == "\\":
            pass_next = True
            i += 1
            continue
        if backq:
            if c == "`":
                backq = False
            i += 1
            continue
        if c == "`":
            backq = True
            i += 1
            continue
        if c == "$" and i + 1 < n:
            if s[i + 1] == "(":
                i = _find_cmdsub_end(s, i + 2)
                continue
            if s[i + 1] == "{":
                i = _find_braced_param_end(s, i + 2)
                continue
        if c == '"':
            return i + 1
        i += 1
    return i


def _is_valid_arithmetic_start(value: str, start: int) -> bool:
    """Check if $(( at position starts a valid arithmetic expression.

    Scans forward looking for )) at the top paren level (excluding nested $()).
    Returns True if valid arithmetic, False if this is actually $( ( ... ) )
    (command substitution containing a subshell).
    """
    scan_paren = 0
    scan_i = start + 3  # Skip past $((
    while scan_i < len(value):
        scan_c = value[scan_i]
        # Skip over $( command subs - their parens shouldn't count
        if _is_expansion_start(value, scan_i, "$("):
            scan_i = _find_cmdsub_end(value, scan_i + 2)
            continue
        if scan_c == "(":
            scan_paren += 1
        elif scan_c == ")":
            if scan_paren > 0:
                scan_paren -= 1
            elif scan_i + 1 < len(value) and value[scan_i + 1] == ")":
                return True  # Found )) at top level, valid arithmetic
            else:
                # Single ) at top level without following ) - not valid arithmetic
                return False
        scan_i += 1
    return False  # Never found ))


def _find_funsub_end(value: str, start: int) -> int:
    """Find the end of a ${ cmd; } brace command substitution.

    Starts after the opening ${. Returns position after the closing }.
    Handles nested braces, quotes, and command substitutions.
    """
    depth = 1
    i = start
    quote = QuoteState()
    while i < len(value) and depth > 0:
        c = value[i]
        if c == "\\" and i + 1 < len(value) and not quote.single:
            i += 2
            continue
        if c == "'" and not quote.double:
            quote.single = not quote.single
            i += 1
            continue
        if c == '"' and not quote.single:
            quote.double = not quote.double
            i += 1
            continue
        if quote.single or quote.double:
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(value)


def _find_cmdsub_end(value: str, start: int) -> int:
    """Find the end of a $(...) command substitution, handling case statements.

    Starts after the opening $(. Returns position after the closing ).
    """
    depth = 1
    i = start
    case_depth = 0  # Track nested case statements
    in_case_patterns = False  # After 'in' but before first ;; or esac
    arith_depth = 0  # Track nested arithmetic expressions
    arith_paren_depth = 0  # Track grouping parens inside arithmetic
    while i < len(value) and depth > 0:
        c = value[i]
        # Handle escapes (work everywhere except inside single quotes, which we delegate)
        if c == "\\" and i + 1 < len(value):
            i += 2
            continue
        # Handle quotes via delegation
        if c == "'":
            i = _skip_single_quoted(value, i + 1)
            continue
        if c == '"':
            i = _skip_double_quoted(value, i + 1)
            continue
        # Handle comments - skip from # to end of line
        # Only treat # as comment if preceded by whitespace or at start
        # Don't treat # as comment inside arithmetic expressions (arith_depth > 0)
        if (
            c == "#"
            and arith_depth == 0
            and (
                i == start
                or value[i - 1] == " "
                or value[i - 1] == "\t"
                or value[i - 1] == "\n"
                or value[i - 1] == ";"
                or value[i - 1] == "|"
                or value[i - 1] == "&"
                or value[i - 1] == "("
                or value[i - 1] == ")"
            )
        ):
            while i < len(value) and value[i] != "\n":
                i += 1
            continue
        # Handle here-strings (<<< word) - must check before heredocs
        if _starts_with_at(value, i, "<<<"):
            i += 3  # Skip <<<
            # Skip whitespace
            while i < len(value) and (value[i] == " " or value[i] == "\t"):
                i += 1
            # Skip the word (may be quoted)
            if i < len(value) and value[i] == '"':
                i += 1
                while i < len(value) and value[i] != '"':
                    if value[i] == "\\" and i + 1 < len(value):
                        i += 2
                    else:
                        i += 1
                if i < len(value):
                    i += 1  # Skip closing quote
            elif i < len(value) and value[i] == "'":
                i += 1
                while i < len(value) and value[i] != "'":
                    i += 1
                if i < len(value):
                    i += 1  # Skip closing quote
            else:
                # Unquoted word - skip until whitespace or special char
                while i < len(value) and value[i] not in " \t\n;|&<>()":
                    i += 1
            continue
        # Handle arithmetic expressions $((
        if _is_expansion_start(value, i, "$(("):
            if _is_valid_arithmetic_start(value, i):
                arith_depth += 1
                i += 3
                continue
            # Not valid arithmetic, treat $( as nested cmdsub and ( as paren
            j = _find_cmdsub_end(value, i + 2)
            i = j
            continue
        # Handle arithmetic close )) - only when no inner grouping parens are open
        if arith_depth > 0 and arith_paren_depth == 0 and _starts_with_at(value, i, "))"):
            arith_depth -= 1
            i += 2
            continue
        # Handle backtick command substitution - skip to closing backtick
        # Must handle this before heredoc check to avoid treating << inside backticks as heredoc
        if c == "`":
            i = _skip_backtick(value, i)
            continue
        # Handle heredocs (but not << inside arithmetic, which is shift operator)
        if arith_depth == 0 and _starts_with_at(value, i, "<<"):
            i = _skip_heredoc(value, i)
            continue
        # Check for 'case' keyword
        if _starts_with_at(value, i, "case") and _is_word_boundary(value, i, 4):
            case_depth += 1
            in_case_patterns = False
            i += 4
            continue
        # Check for 'in' keyword (after case)
        if case_depth > 0 and _starts_with_at(value, i, "in") and _is_word_boundary(value, i, 2):
            in_case_patterns = True
            i += 2
            continue
        # Check for 'esac' keyword
        if _starts_with_at(value, i, "esac") and _is_word_boundary(value, i, 4):
            if case_depth > 0:
                case_depth -= 1
                in_case_patterns = False
            i += 4
            continue
        # Check for ';;' (end of case pattern, next pattern or esac follows)
        if _starts_with_at(value, i, ";;"):
            i += 2
            continue
        # Handle parens
        if c == "(":
            # In case patterns, ( before pattern name is optional and not a grouping paren
            if not (in_case_patterns and case_depth > 0):
                if arith_depth > 0:
                    arith_paren_depth += 1
                else:
                    depth += 1
        elif c == ")":
            # In case patterns, ) after pattern name is not a grouping paren
            if in_case_patterns and case_depth > 0:
                if not _lookahead_for_esac(value, i + 1, case_depth):
                    depth -= 1
            elif arith_depth > 0:
                if arith_paren_depth > 0:
                    arith_paren_depth -= 1
                # else: single ) in arithmetic without matching ( - skip it
            else:
                depth -= 1
        i += 1
    return i


def _find_braced_param_end(value: str, start: int) -> int:
    """Find end of ${...}. Starts after ${. Returns position after }."""
    depth = 1
    i = start
    in_double = False
    dolbrace_state = DolbraceState.PARAM
    while i < len(value) and depth > 0:
        c = value[i]
        # Escapes work everywhere except inside single quotes (which we delegate)
        if c == "\\" and i + 1 < len(value):
            i += 2
            continue
        # Single quotes: only delegate in QUOTE state (after %#^,)
        if c == "'" and dolbrace_state == DolbraceState.QUOTE and not in_double:
            i = _skip_single_quoted(value, i + 1)
            continue
        if c == '"':
            in_double = not in_double
            i += 1
            continue
        if in_double:
            i += 1
            continue
        # State transitions: operators move from PARAM to WORD or QUOTE
        if dolbrace_state == DolbraceState.PARAM and c in "%#^,":
            dolbrace_state = DolbraceState.QUOTE
        elif dolbrace_state == DolbraceState.PARAM and c in ":-=?+/":
            dolbrace_state = DolbraceState.WORD
        # Handle array subscripts (only in PARAM state, not pattern words)
        if c == "[" and dolbrace_state == DolbraceState.PARAM and not in_double:
            end = _skip_subscript(value, i, 0)
            if end != -1:
                i = end
                continue
        # Handle process substitution <(...) and >(...)
        if (c == "<" or c == ">") and i + 1 < len(value) and value[i + 1] == "(":
            i = _find_cmdsub_end(value, i + 2)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        if _is_expansion_start(value, i, "$("):
            i = _find_cmdsub_end(value, i + 2)
            continue
        if _is_expansion_start(value, i, "${"):
            i = _find_braced_param_end(value, i + 2)
            continue
        i += 1
    return i


def _skip_heredoc(value: str, start: int) -> int:
    """Skip past a heredoc starting at <<. Returns position after heredoc content."""
    i = start + 2  # Skip <<
    # Handle <<- (strip tabs)
    if i < len(value) and value[i] == "-":
        i += 1
    # Skip whitespace before delimiter
    while i < len(value) and _is_whitespace_no_newline(value[i]):
        i += 1
    # Extract delimiter - may be quoted
    delim_start = i
    quote_char = None
    if i < len(value) and (value[i] == '"' or value[i] == "'"):
        quote_char = value[i]
        i += 1
        delim_start = i
        while i < len(value) and value[i] != quote_char:
            i += 1
        delimiter = _substring(value, delim_start, i)
        if i < len(value):
            i += 1  # Skip closing quote
    elif i < len(value) and value[i] == "\\":
        # Backslash-quoted delimiter like <<\EOF
        i += 1
        delim_start = i
        if i < len(value):
            i += 1
        while i < len(value) and not _is_metachar(value[i]):
            i += 1
        delimiter = _substring(value, delim_start, i)
    else:
        # Unquoted delimiter - stop at metacharacters like )
        while i < len(value) and not _is_metachar(value[i]):
            i += 1
        delimiter = _substring(value, delim_start, i)
    # Skip to end of line (heredoc content starts on next line)
    # But track paren depth - if we hit a ) at depth 0, it closes the cmdsub
    # Must handle quotes and backticks since newlines in them don't end the line
    paren_depth = 0
    quote = QuoteState()
    in_backtick = False
    while i < len(value) and value[i] != "\n":
        c = value[i]
        # Handle escapes (in double quotes or backticks)
        if c == "\\" and i + 1 < len(value) and (quote.double or in_backtick):
            i += 2
            continue
        # Track quote state
        if c == "'" and not quote.double and not in_backtick:
            quote.single = not quote.single
            i += 1
            continue
        if c == '"' and not quote.single and not in_backtick:
            quote.double = not quote.double
            i += 1
            continue
        if c == "`" and not quote.single:
            in_backtick = not in_backtick
            i += 1
            continue
        # Skip content inside quotes/backticks
        if quote.single or quote.double or in_backtick:
            i += 1
            continue
        # Track paren depth
        if c == "(":
            paren_depth += 1
        elif c == ")":
            if paren_depth == 0:
                # This ) closes the enclosing command substitution, stop here
                break
            paren_depth -= 1
        i += 1
    # If we stopped at ) (closing cmdsub), return here - no heredoc content
    if i < len(value) and value[i] == ")":
        return i
    if i < len(value) and value[i] == "\n":
        i += 1  # Skip newline
    # Find the end delimiter on its own line
    while i < len(value):
        line_start = i
        # Find end of this line - heredoc content can contain )
        line_end = i
        while line_end < len(value) and value[line_end] != "\n":
            line_end += 1
        line = _substring(value, line_start, line_end)
        # Handle backslash-newline continuation (join continued lines)
        while line_end < len(value):
            trailing_bs = 0
            for j in range(len(line) - 1, -1, -1):
                if line[j] == "\\":
                    trailing_bs += 1
                else:
                    break
            if trailing_bs % 2 == 0:
                break  # Even backslashes (including 0) - no continuation
            # Odd backslashes - line continuation
            line = line[:-1]  # Remove trailing backslash
            line_end += 1  # Skip newline
            next_line_start = line_end
            while line_end < len(value) and value[line_end] != "\n":
                line_end += 1
            line = line + _substring(value, next_line_start, line_end)
        # Check if this line is the delimiter (possibly with leading tabs for <<-)
        if start + 2 < len(value) and value[start + 2] == "-":
            stripped = line.lstrip("\t")
        else:
            stripped = line
        if stripped == delimiter:
            # Found end - return position after delimiter line
            if line_end < len(value):
                return line_end + 1
            else:
                return line_end
        # Check if line starts with delimiter followed by other content
        # This handles cases like "Xb)" where X is delimiter and b) continues the cmdsub
        if stripped.startswith(delimiter) and len(stripped) > len(delimiter):
            # Return position right after the delimiter
            tabs_stripped = len(line) - len(stripped)
            return line_start + tabs_stripped + len(delimiter)
        if line_end < len(value):
            i = line_end + 1
        else:
            i = line_end
    return i


def _find_heredoc_content_end(
    source: str, start: int, delimiters: list[tuple[str, bool]]
) -> tuple[int, int]:
    """Find heredoc content in source starting at start.
    Returns (content_start, content_end) where content_start is position after newline
    and content_end is position after all heredoc content.
    delimiters is list of (delimiter, strip_tabs) tuples.
    """
    if not delimiters:
        return start, start
    pos = start
    # Skip to end of current line (including non-whitespace)
    while pos < len(source) and source[pos] != "\n":
        pos += 1
    if pos >= len(source):
        return start, start
    content_start = pos  # Include the newline in heredoc content
    pos += 1  # skip the newline for scanning
    for delimiter, strip_tabs in delimiters:
        while pos < len(source):
            line_start = pos
            line_end = pos
            while line_end < len(source) and source[line_end] != "\n":
                line_end += 1
            line = _substring(source, line_start, line_end)
            # Handle backslash-newline continuation (join continued lines)
            while line_end < len(source):
                trailing_bs = 0
                for j in range(len(line) - 1, -1, -1):
                    if line[j] == "\\":
                        trailing_bs += 1
                    else:
                        break
                if trailing_bs % 2 == 0:
                    break  # Even backslashes (including 0) - no continuation
                # Odd backslashes - line continuation
                line = line[:-1]  # Remove trailing backslash
                line_end += 1  # Skip newline
                next_line_start = line_end
                while line_end < len(source) and source[line_end] != "\n":
                    line_end += 1
                line = line + _substring(source, next_line_start, line_end)
            if strip_tabs:
                line_stripped = line.lstrip("\t")
            else:
                line_stripped = line
            if line_stripped == delimiter:
                pos = line_end + 1 if line_end < len(source) else line_end
                break
            # Check if line starts with delimiter followed by other content
            # This handles cases like "a?&)" where "a" is delimiter and "?&)" continues the process sub
            if line_stripped.startswith(delimiter) and len(line_stripped) > len(delimiter):
                # Return position right after the delimiter
                tabs_stripped = len(line) - len(line_stripped)
                pos = line_start + tabs_stripped + len(delimiter)
                break
            pos = line_end + 1 if line_end < len(source) else line_end
    return content_start, pos


def _is_word_boundary(s: str, pos: int, word_len: int) -> bool:
    """Check if the word at pos is a standalone word (not part of larger word).

    For reserved words to be recognized, they must be preceded by whitespace,
    command separators, or be at the start of the string. Characters like }
    can be part of command names (e.g., }case is a valid command).
    """
    # Check character before - must be whitespace, separator, or start
    if pos > 0:
        prev = s[pos - 1]
        # Alphanumeric or _ means the keyword is part of a larger word
        if prev.isalnum() or prev == "_":
            return False
        # These characters can prefix a word and make it not a keyword
        # e.g., }case, {case, !case are command names, not keyword
        if prev in "{}!":
            return False
    # Check character after
    end = pos + word_len
    if end < len(s) and (s[end].isalnum() or s[end] == "_"):
        return False
    return True


# Reserved words that cannot be command names
RESERVED_WORDS = {
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "while",
    "until",
    "for",
    "select",
    "do",
    "done",
    "case",
    "esac",
    "in",
    "function",
    "coproc",
}

COND_UNARY_OPS = {
    "-a",
    "-b",
    "-c",
    "-d",
    "-e",
    "-f",
    "-g",
    "-h",
    "-k",
    "-p",
    "-r",
    "-s",
    "-t",
    "-u",
    "-w",
    "-x",
    "-G",
    "-L",
    "-N",
    "-O",
    "-S",
    "-z",
    "-n",
    "-o",
    "-v",
    "-R",
}

COND_BINARY_OPS = {
    "==",
    "!=",
    "=~",
    "=",
    "<",
    ">",
    "-eq",
    "-ne",
    "-lt",
    "-le",
    "-gt",
    "-ge",
    "-nt",
    "-ot",
    "-ef",
}

COMPOUND_KEYWORDS = {"while", "until", "for", "if", "case", "select"}

# Builtins that allow array assignments in argument position (bash's ASSIGNMENT_BUILTIN flag)
ASSIGNMENT_BUILTINS = {"alias", "declare", "typeset", "local", "export", "readonly", "eval", "let"}


def _is_quote(c: str) -> bool:
    return c == "'" or c == '"'


def _collapse_whitespace(s: str) -> str:
    """Collapse consecutive tabs/spaces to single space and strip."""
    result = []
    prev_was_ws = False
    for c in s:
        if c == " " or c == "\t":
            if not prev_was_ws:
                result.append(" ")
            prev_was_ws = True
        else:
            result.append(c)
            prev_was_ws = False
    joined = "".join(result)
    return joined.strip(" \t")


def _count_trailing_backslashes(s: str) -> int:
    """Count trailing backslashes in a string."""
    count = 0
    for i in range(len(s) - 1, -1, -1):
        if s[i] == "\\":
            count += 1
        else:
            break
    return count


def _normalize_heredoc_delimiter(delimiter: str) -> str:
    """Normalize heredoc delimiter for matching."""
    result = []
    i = 0
    while i < len(delimiter):
        # Handle command substitution $(...)
        if i + 1 < len(delimiter) and delimiter[i : i + 2] == "$(":
            result.append("$(")
            i += 2
            depth = 1
            inner = []
            while i < len(delimiter) and depth > 0:
                if delimiter[i] == "(":
                    depth += 1
                    inner.append(delimiter[i])
                elif delimiter[i] == ")":
                    depth -= 1
                    if depth == 0:
                        inner_str = "".join(inner)
                        inner_str = _collapse_whitespace(inner_str)
                        result.append(inner_str)
                        result.append(")")
                    else:
                        inner.append(delimiter[i])
                else:
                    inner.append(delimiter[i])
                i += 1
        # Handle parameter expansion ${...}
        elif i + 1 < len(delimiter) and delimiter[i : i + 2] == "${":
            result.append("${")
            i += 2
            depth = 1
            inner = []
            while i < len(delimiter) and depth > 0:
                if delimiter[i] == "{":
                    depth += 1
                    inner.append(delimiter[i])
                elif delimiter[i] == "}":
                    depth -= 1
                    if depth == 0:
                        inner_str = "".join(inner)
                        inner_str = _collapse_whitespace(inner_str)
                        result.append(inner_str)
                        result.append("}")
                    else:
                        inner.append(delimiter[i])
                else:
                    inner.append(delimiter[i])
                i += 1
        # Handle process substitution <(...) and >(...)
        elif i + 1 < len(delimiter) and delimiter[i] in "<>" and delimiter[i + 1] == "(":
            result.append(delimiter[i])
            result.append("(")
            i += 2
            depth = 1
            inner = []
            while i < len(delimiter) and depth > 0:
                if delimiter[i] == "(":
                    depth += 1
                    inner.append(delimiter[i])
                elif delimiter[i] == ")":
                    depth -= 1
                    if depth == 0:
                        inner_str = "".join(inner)
                        inner_str = _collapse_whitespace(inner_str)
                        result.append(inner_str)
                        result.append(")")
                    else:
                        inner.append(delimiter[i])
                else:
                    inner.append(delimiter[i])
                i += 1
        else:
            result.append(delimiter[i])
            i += 1
    return "".join(result)


def _is_metachar(c: str) -> bool:
    return (
        c == " "
        or c == "\t"
        or c == "\n"
        or c == "|"
        or c == "&"
        or c == ";"
        or c == "("
        or c == ")"
        or c == "<"
        or c == ">"
    )


def _is_funsub_char(c: str) -> bool:
    """Check if character triggers brace command substitution (funsub)."""
    return c == " " or c == "\t" or c == "\n" or c == "|"


def _is_extglob_prefix(c: str) -> bool:
    return c == "@" or c == "?" or c == "*" or c == "+" or c == "!"


def _is_redirect_char(c: str) -> bool:
    return c == "<" or c == ">"


def _is_special_param(c: str) -> bool:
    return (
        c == "?" or c == "$" or c == "!" or c == "#" or c == "@" or c == "*" or c == "-" or c == "&"
    )


def _is_special_param_unbraced(c: str) -> bool:
    """Special params valid after bare $ (excludes & which is a shell metachar)."""
    return c == "?" or c == "$" or c == "!" or c == "#" or c == "@" or c == "*" or c == "-"


def _is_digit(c: str) -> bool:
    return c >= "0" and c <= "9"


def _is_semicolon_or_newline(c: str) -> bool:
    return c == ";" or c == "\n"


def _is_word_end_context(c: str) -> bool:
    """Check if char ends a word context (whitespace or metachar)."""
    return (
        c == " "
        or c == "\t"
        or c == "\n"
        or c == ";"
        or c == "|"
        or c == "&"
        or c == "<"
        or c == ">"
        or c == "("
        or c == ")"
    )


# Flags for _skip_matched_pair (mirrors bash subst.c)
_SMP_LITERAL = 1  # No quote/escape processing
_SMP_PAST_OPEN = 2  # start points past open bracket


def _skip_matched_pair(s: str, start: int, open: str, close: str, flags: int = 0) -> int:
    """Skip a matched pair of brackets, handling quotes and escapes.

    Mirrors bash's skip_matched_pair() in subst.c:2086.
    Returns index after closing bracket, or -1 if unmatched.

    Flags:
        _SMP_LITERAL (1): No quote/escape processing
        _SMP_PAST_OPEN (2): start already points past open bracket
    """
    n = len(s)
    if flags & _SMP_PAST_OPEN:
        i = start
    else:
        if start >= n or s[start] != open:
            return -1
        i = start + 1
    depth = 1
    pass_next = False
    backq = False
    while i < n and depth > 0:
        c = s[i]
        if pass_next:
            pass_next = False
            i += 1
            continue
        literal = flags & _SMP_LITERAL
        if not literal and c == "\\":
            pass_next = True
            i += 1
            continue
        if backq:
            if c == "`":
                backq = False
            i += 1
            continue
        if not literal and c == "`":
            backq = True
            i += 1
            continue
        if not literal and c == "'":
            i = _skip_single_quoted(s, i + 1)
            continue
        if not literal and c == '"':
            i = _skip_double_quoted(s, i + 1)
            continue
        if not literal and _is_expansion_start(s, i, "$("):
            i = _find_cmdsub_end(s, i + 2)
            continue
        if not literal and _is_expansion_start(s, i, "${"):
            i = _find_braced_param_end(s, i + 2)
            continue
        if not literal and c == open:
            depth += 1
        elif c == close:
            depth -= 1
        i += 1
    return i if depth == 0 else -1


def _skip_subscript(s: str, start: int, flags: int = 0) -> int:
    """Skip a bracketed subscript starting at s[start]='['.

    Mirrors bash's skipsubscript() in subst.c:2186.
    Flags are passed through to _skip_matched_pair().
    """
    return _skip_matched_pair(s, start, "[", "]", flags)


def _assignment(s: str, flags: int = 0) -> int:
    """Return index of '=' if s is an assignment word, else -1.

    Handles: NAME=, NAME+=, NAME[sub]=, NAME[sub]+=
    Matches bash's assignment() function in general.c.

    Flags:
        & 2: Use literal subscript matching (for compound assignments)
    """
    if not s:
        return -1
    if not (s[0].isalpha() or s[0] == "_"):
        return -1
    i = 1
    while i < len(s):
        c = s[i]
        if c == "=":
            return i
        if c == "[":
            sub_flags = _SMP_LITERAL if (flags & 2) else 0
            end = _skip_subscript(s, i, sub_flags)
            if end == -1:
                return -1
            i = end
            if i < len(s) and s[i] == "+":
                i += 1
            if i < len(s) and s[i] == "=":
                return i
            return -1
        if c == "+":
            if i + 1 < len(s) and s[i + 1] == "=":
                return i + 1
            return -1
        if not (c.isalnum() or c == "_"):
            return -1
        i += 1
    return -1


def _is_array_assignment_prefix(chars: list[str]) -> bool:
    """Check if chars form name or name[subscript]... for array assignments."""
    if not chars:
        return False
    if not (chars[0].isalpha() or chars[0] == "_"):
        return False
    s = "".join(chars)
    i = 1
    while i < len(s) and (s[i].isalnum() or s[i] == "_"):
        i += 1
    while i < len(s):
        if s[i] != "[":
            return False
        end = _skip_subscript(s, i, _SMP_LITERAL)
        if end == -1:
            return False
        i = end
    return True


def _is_special_param_or_digit(c: str) -> bool:
    return _is_special_param(c) or _is_digit(c)


def _is_param_expansion_op(c: str) -> bool:
    return (
        c == ":"
        or c == "-"
        or c == "="
        or c == "+"
        or c == "?"
        or c == "#"
        or c == "%"
        or c == "/"
        or c == "^"
        or c == ","
        or c == "@"
        or c == "*"
        or c == "["
    )


def _is_simple_param_op(c: str) -> bool:
    return c == "-" or c == "=" or c == "?" or c == "+"


def _is_escape_char_in_backtick(c: str) -> bool:
    return c == "$" or c == "`" or c == "\\"


def _is_negation_boundary(c: str) -> bool:
    return _is_whitespace(c) or c == ";" or c == "|" or c == ")" or c == "&" or c == ">" or c == "<"


def _is_backslash_escaped(value: str, idx: int) -> bool:
    """Return True if value[idx] is escaped by an odd number of backslashes."""
    bs_count = 0
    j = idx - 1
    while j >= 0 and value[j] == "\\":
        bs_count += 1
        j -= 1
    return bs_count % 2 == 1


def _is_dollar_dollar_paren(value: str, idx: int) -> bool:
    """Return True if $( at idx is actually $$( where $$ is PID, not command sub.

    Count consecutive $ before idx. If odd, the $( is consumed by $$ (PID param).
    E.g., $$(  -> $$ + ( literal (1 $ before, odd)
          $$$( -> $$ + $( cmdsub (2 $ before, even)
    """
    dollar_count = 0
    j = idx - 1
    while j >= 0 and value[j] == "$":
        dollar_count += 1
        j -= 1
    return dollar_count % 2 == 1


def _is_paren(c: str) -> bool:
    return c == "(" or c == ")"


def _is_caret_or_bang(c: str) -> bool:
    return c == "!" or c == "^"


def _is_at_or_star(c: str) -> bool:
    return c == "@" or c == "*"


def _is_digit_or_dash(c: str) -> bool:
    return _is_digit(c) or c == "-"


def _is_newline_or_right_paren(c: str) -> bool:
    return c == "\n" or c == ")"


def _is_semicolon_newline_brace(c: str) -> bool:
    return c == ";" or c == "\n" or c == "{"


def _looks_like_assignment(s: str) -> bool:
    """Check if s looks like an assignment word."""
    return _assignment(s) != -1


def _is_valid_identifier(name: str) -> bool:
    """Check if name is a valid bash identifier (variable/function name)."""
    if not name:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    for c in name[1:]:
        if not (c.isalnum() or c == "_"):
            return False
    return True


# Word parsing context constants
WORD_CTX_NORMAL = 0  # Regular command context
WORD_CTX_COND = 1  # Inside [[ ]]
WORD_CTX_REGEX = 2  # RHS of =~ in [[ ]]


class Parser:
    """Recursive descent parser for bash."""

    def __init__(self, source: str, in_process_sub: bool = False, extglob: bool = False):
        self.source = source
        self.pos = 0
        self.length: int = len(source)
        self._pending_heredocs: list[HereDoc] = []
        # Track heredoc content that was consumed into command/process substitutions
        # and needs to be skipped when we reach a newline
        self._cmdsub_heredoc_end: int = -1  # -1 = not set
        self._saw_newline_in_single_quote = False
        self._in_process_sub = in_process_sub
        # Extglob parsing enabled (bash shopt extglob)
        self._extglob = extglob
        # Context stack for tracking nested parsing scopes
        self._ctx: ContextStack = ContextStack()
        # Lexer for tokenization
        self._lexer: Lexer = Lexer(source, extglob=extglob)
        self._lexer._parser = self  # Back-reference for expansion parsing
        # Token history for context-sensitive parsing (last 4 tokens like bash)
        self._token_history: list[Token | None] = [None, None, None, None]
        # Parser state flags for context-sensitive decisions
        self._parser_state: int = ParserStateFlags.NONE
        # Dolbrace state for ${...} parameter expansion parsing
        self._dolbrace_state: int = DolbraceState.NONE
        # EOF token mechanism for inline command substitution parsing
        self._eof_token: str | None = None
        # Word parsing context for Lexer sync
        self._word_context: int = WORD_CTX_NORMAL
        self._at_command_start = False
        self._in_array_literal = False
        self._in_assign_builtin = False
        # Arithmetic expression parsing context (for nested parsing)
        self._arith_src: str = ""
        self._arith_pos: int = 0
        self._arith_len: int = 0

    def _set_state(self, flag: int) -> None:
        """Set a parser state flag."""
        self._parser_state = self._parser_state | flag

    def _clear_state(self, flag: int) -> None:
        """Clear a parser state flag."""
        self._parser_state = self._parser_state & ~flag

    def _in_state(self, flag: int) -> bool:
        """Check if a parser state flag is set."""
        return (self._parser_state & flag) != 0

    def _save_parser_state(self) -> SavedParserState:
        """Save current parser state for nested parsing.

        Based on bash's save_parser_state(). Used when entering nested
        constructs like command substitutions to preserve context.
        """
        return SavedParserState(
            parser_state=self._parser_state,
            dolbrace_state=self._dolbrace_state,
            pending_heredocs=list(self._pending_heredocs),
            ctx_stack=self._ctx.copy_stack(),
            eof_token=self._eof_token,
        )

    def _restore_parser_state(self, saved: SavedParserState) -> None:
        """Restore parser state after nested parsing.

        Based on bash's restore_parser_state(). Note: position is NOT restored
        since we've advanced through the nested content. Heredocs are also not
        restored since they were consumed during nested parsing.
        """
        self._parser_state = saved.parser_state
        self._dolbrace_state = saved.dolbrace_state
        self._eof_token = saved.eof_token
        # Restore complete context stack
        self._ctx.restore_from(saved.ctx_stack)

    def _record_token(self, tok: Token) -> None:
        """Record token in history, shifting older tokens."""
        self._token_history = [
            tok,
            self._token_history[0],
            self._token_history[1],
            self._token_history[2],
        ]

    def _update_dolbrace_for_op(self, op: str | None, has_param: bool) -> None:
        """Update dolbrace state based on operator seen.

        Based on bash's parse.y lines 4010-4027.
        """
        if self._dolbrace_state == DolbraceState.NONE:
            return
        if op is None or len(op) == 0:
            return
        first_char = op[0]
        # If we have a param name and see certain operators, go to QUOTE/QUOTE2
        if self._dolbrace_state == DolbraceState.PARAM and has_param:
            if first_char in "%#^,":
                self._dolbrace_state = DolbraceState.QUOTE
                return
            if first_char == "/":
                self._dolbrace_state = DolbraceState.QUOTE2
                return
        # Any operator char transitions PARAM -> OP
        if self._dolbrace_state == DolbraceState.PARAM:
            if first_char in "#%^,~:-=?+/":
                self._dolbrace_state = DolbraceState.OP

    def _sync_lexer(self) -> None:
        """Sync Lexer position and state to Parser."""
        # Invalidate cache if it doesn't match our current position or context
        if self._lexer._token_cache is not None:
            if (
                self._lexer._token_cache.pos != self.pos
                or self._lexer._cached_word_context != self._word_context
                or self._lexer._cached_at_command_start != self._at_command_start
                or self._lexer._cached_in_array_literal != self._in_array_literal
                or self._lexer._cached_in_assign_builtin != self._in_assign_builtin
            ):
                self._lexer._token_cache = None
        # Sync lexer position
        if self._lexer.pos != self.pos:
            self._lexer.pos = self.pos
        self._lexer._eof_token = self._eof_token
        self._lexer._parser_state = self._parser_state
        # Sync last read token from parser's token history
        self._lexer._last_read_token = self._token_history[0]
        # Sync word context
        self._lexer._word_context = self._word_context
        self._lexer._at_command_start = self._at_command_start
        self._lexer._in_array_literal = self._in_array_literal
        self._lexer._in_assign_builtin = self._in_assign_builtin

    def _sync_parser(self) -> None:
        """Sync Parser position to Lexer position."""
        self.pos = self._lexer.pos

    def _lex_peek_token(self) -> Token:
        """Peek at next token via Lexer."""
        # Check if cached token is valid: same position AND same word context
        # (word context affects how array subscripts and other constructs are parsed)
        if (
            self._lexer._token_cache is not None
            and self._lexer._token_cache.pos == self.pos
            and self._lexer._cached_word_context == self._word_context
            and self._lexer._cached_at_command_start == self._at_command_start
            and self._lexer._cached_in_array_literal == self._in_array_literal
            and self._lexer._cached_in_assign_builtin == self._in_assign_builtin
        ):
            return self._lexer._token_cache
        # Need to read a new token - sync lexer to our position first
        saved_pos = self.pos
        self._sync_lexer()
        result = self._lexer.peek_token()
        # Save the context used for this cached token
        self._lexer._cached_word_context = self._word_context
        self._lexer._cached_at_command_start = self._at_command_start
        self._lexer._cached_in_array_literal = self._in_array_literal
        self._lexer._cached_in_assign_builtin = self._in_assign_builtin
        # Save the post-read position (may have advanced for heredocs)
        self._lexer._post_read_pos = self._lexer.pos
        # Restore parser position for peek semantics
        self.pos = saved_pos
        return result

    def _lex_next_token(self) -> Token:
        """Get next token via Lexer and sync position."""
        # Check if cached token is valid: same position AND same word context
        if (
            self._lexer._token_cache is not None
            and self._lexer._token_cache.pos == self.pos
            and self._lexer._cached_word_context == self._word_context
            and self._lexer._cached_at_command_start == self._at_command_start
            and self._lexer._cached_in_array_literal == self._in_array_literal
            and self._lexer._cached_in_assign_builtin == self._in_assign_builtin
        ):
            # Consume cached token - use saved post-read position
            tok = self._lexer.next_token()
            self.pos = self._lexer._post_read_pos
            self._lexer.pos = self._lexer._post_read_pos
        else:
            # No valid cache - sync and read fresh
            self._sync_lexer()
            tok = self._lexer.next_token()
            # Save context for this token
            self._lexer._cached_word_context = self._word_context
            self._lexer._cached_at_command_start = self._at_command_start
            self._lexer._cached_in_array_literal = self._in_array_literal
            self._lexer._cached_in_assign_builtin = self._in_assign_builtin
            self._sync_parser()
        self._record_token(tok)
        return tok

    def _lex_skip_blanks(self) -> None:
        """Skip blanks via Lexer."""
        self._sync_lexer()
        self._lexer.skip_blanks()
        self._sync_parser()

    def _lex_skip_comment(self) -> bool:
        """Skip comment via Lexer. Returns True if comment was skipped."""
        self._sync_lexer()
        result = self._lexer._skip_comment()
        self._sync_parser()
        return result

    def _lex_is_command_terminator(self) -> bool:
        """Check if next token is a simple command terminator.

        Returns True for tokens that terminate a simple command:
        - EOF (including via _eof_token mechanism)
        - NEWLINE
        - PIPE (but not PIPE_AMP)
        - SEMI (but not SEMI_SEMI, SEMI_AMP, SEMI_SEMI_AMP)
        - LPAREN, RPAREN
        - AMP (but not AMP_GREATER, AMP_GREATER_GREATER, AND_AND)
        - RBRACE (at command position)
        """
        tok = self._lex_peek_token()
        t = tok.type
        return t in (
            TokenType.EOF,
            TokenType.NEWLINE,
            TokenType.PIPE,
            TokenType.SEMI,
            TokenType.LPAREN,
            TokenType.RPAREN,
            TokenType.AMP,
        )

    def _lex_peek_operator(self) -> tuple[int, str]:
        """Peek operator token. Returns (token_type, value) or (0, "") if not an operator."""
        tok = self._lex_peek_token()
        t = tok.type
        # Single-char operators: SEMI(10) through GREATER(18)
        # Multi-char operators: AND_AND(30) through PIPE_AMP(45)
        if (t >= TokenType.SEMI and t <= TokenType.GREATER) or (
            t >= TokenType.AND_AND and t <= TokenType.PIPE_AMP
        ):
            return (t, tok.value)
        return (0, "")

    def _lex_peek_reserved_word(self) -> str | None:
        """Peek reserved word. Returns word value if reserved, None otherwise."""
        tok = self._lex_peek_token()
        if tok.type != TokenType.WORD:
            return None
        # Strip trailing backslash-newline (line continuation) for classification
        # The lexer includes \<newline> in words, but reserved word check ignores it
        word = tok.value
        if word.endswith("\\\n"):
            word = word[:-2]
        # Check against module-level RESERVED_WORDS set plus additional reserved tokens
        # (Using module-level constant for transpiler compatibility)
        if word in RESERVED_WORDS or word in ("{", "}", "[[", "]]", "!", "time"):
            return word
        return None

    def _lex_is_at_reserved_word(self, word: str) -> bool:
        """Check if next token is a specific reserved word."""
        reserved = self._lex_peek_reserved_word()
        return reserved == word

    def _lex_consume_word(self, expected: str) -> bool:
        """Try to consume a word token matching expected. Returns True if successful."""
        tok = self._lex_peek_token()
        if tok.type != TokenType.WORD:
            return False
        # Strip trailing backslash-newline (line continuation) for comparison
        word = tok.value
        if word.endswith("\\\n"):
            word = word[:-2]
        if word == expected:
            self._lex_next_token()
            return True
        return False

    def _lex_peek_case_terminator(self) -> str | None:
        """Peek case terminator (;;, ;&, ;;&). Returns value or None."""
        tok = self._lex_peek_token()
        t = tok.type
        if t == TokenType.SEMI_SEMI:
            return ";;"
        if t == TokenType.SEMI_AMP:
            return ";&"
        if t == TokenType.SEMI_SEMI_AMP:
            return ";;&"
        return None

    def at_end(self) -> bool:
        """Check if we've reached the end of input."""
        return self.pos >= self.length

    def peek(self) -> str | None:
        """Return current character without consuming."""
        if self.at_end():
            return None
        return self.source[self.pos]

    def advance(self) -> str | None:
        """Consume and return current character."""
        if self.at_end():
            return None
        ch = self.source[self.pos]
        self.pos += 1
        return ch

    def peek_at(self, offset: int) -> str:
        """Peek at character at offset from current position.

        Returns empty string if position is out of bounds.
        """
        pos = self.pos + offset
        if pos < 0 or pos >= self.length:
            return ""
        return self.source[pos]

    def lookahead(self, n: int) -> str:
        """Return next n characters without consuming."""
        return _substring(self.source, self.pos, self.pos + n)

    def _is_bang_followed_by_procsub(self) -> bool:
        """Check if ! at current position is followed by >( or <( process substitution."""
        if self.pos + 2 >= self.length:
            return False
        next_char = self.source[self.pos + 1]
        if next_char != ">" and next_char != "<":
            return False
        return self.source[self.pos + 2] == "("

    def skip_whitespace(self) -> None:
        """Skip spaces, tabs, comments, and backslash-newline continuations."""
        while not self.at_end():
            # Use Lexer for spaces/tabs
            self._lex_skip_blanks()
            if self.at_end():
                break
            ch = self.peek()
            if ch == "#":
                # Use Lexer to skip comment
                self._lex_skip_comment()
            elif ch == "\\" and self.peek_at(1) == "\n":
                # Backslash-newline is line continuation - skip both
                self.advance()
                self.advance()
            else:
                break

    def skip_whitespace_and_newlines(self) -> None:
        """Skip spaces, tabs, newlines, comments, and backslash-newline continuations."""
        while not self.at_end():
            ch = self.peek()
            if _is_whitespace(ch):
                self.advance()
                # After advancing past a newline, gather pending heredoc content
                if ch == "\n":
                    self._gather_heredoc_bodies()
                    # Skip heredoc content consumed by command/process substitutions
                    if self._cmdsub_heredoc_end != -1 and self._cmdsub_heredoc_end > self.pos:
                        self.pos = self._cmdsub_heredoc_end
                        self._cmdsub_heredoc_end = -1
            elif ch == "#":
                # Skip comment to end of line
                while not self.at_end() and self.peek() != "\n":
                    self.advance()
            elif ch == "\\" and self.peek_at(1) == "\n":
                # Backslash-newline is line continuation - skip both
                self.advance()
                self.advance()
            else:
                break

    def _at_list_terminating_bracket(self) -> bool:
        """Check if we're at a bracket that terminates a list (closing subshell or brace group).

        Returns True for ')' always (since it's a metachar).
        Returns True for '}' only if it's standalone (followed by word-end context or EOF).
        This handles cases like 'a&}}' where '}}' is a word, not a brace-group closer.
        Also returns True if we're at the EOF token (for funsub parsing).
        """
        if self.at_end():
            return False
        ch = self.peek()
        # Check if we're at the EOF token (e.g., } in funsub or ) in comsub)
        if self._eof_token is not None and ch == self._eof_token:
            return True
        if ch == ")":
            return True
        if ch == "}":
            # } is only a list terminator if standalone (not part of a word like }})
            next_pos = self.pos + 1
            if next_pos >= self.length:
                return True  # } at EOF is standalone
            return _is_word_end_context(self.source[next_pos])
        return False

    def _at_eof_token(self) -> bool:
        """Check if next token is the EOF token (grammar-level check)."""
        if self._eof_token is None:
            return False
        tok = self._lex_peek_token()
        if self._eof_token == ")":
            return tok.type == TokenType.RPAREN
        if self._eof_token == "}":
            return tok.type == TokenType.WORD and tok.value == "}"
        return False

    def _collect_redirects(self) -> list[Node] | None:
        """Collect trailing redirects after a compound command."""
        redirects = []
        while True:
            self.skip_whitespace()
            redirect = self.parse_redirect()
            if redirect is None:
                break
            redirects.append(redirect)
        return redirects if redirects else None

    def _parse_loop_body(self, context: str) -> Node:
        """Parse a loop body that can be either do/done or brace group."""
        if self.peek() == "{":
            brace = self.parse_brace_group()
            if brace is None:
                raise ParseError(
                    f"Expected brace group body in {context}", pos=self._lex_peek_token().pos
                )
            return brace.body
        if self._lex_consume_word("do"):
            body = self.parse_list_until({"done"})
            if body is None:
                raise ParseError("Expected commands after 'do'", pos=self._lex_peek_token().pos)
            self.skip_whitespace_and_newlines()
            if not self._lex_consume_word("done"):
                raise ParseError(
                    f"Expected 'done' to close {context}", pos=self._lex_peek_token().pos
                )
            return body
        raise ParseError(f"Expected 'do' or '{{' in {context}", pos=self._lex_peek_token().pos)

    def peek_word(self) -> str | None:
        """Peek at the next word without consuming it."""
        saved_pos = self.pos
        self.skip_whitespace()

        if self.at_end() or _is_metachar(self.peek()):
            self.pos = saved_pos
            return None

        chars = []
        while not self.at_end() and not _is_metachar(self.peek()):
            ch = self.peek()
            # Stop at quotes - don't include in peek
            if _is_quote(ch):
                break
            # Stop at backslash-newline (line continuation)
            if ch == "\\" and self.pos + 1 < self.length and self.source[self.pos + 1] == "\n":
                break
            # Handle backslash escaping next character (even metacharacters)
            if ch == "\\" and self.pos + 1 < self.length:
                chars.append(self.advance())  # backslash
                chars.append(self.advance())  # escaped char
                continue
            chars.append(self.advance())

        if chars:
            word = "".join(chars)
        else:
            word = None
        self.pos = saved_pos
        return word

    def consume_word(self, expected: str) -> bool:
        """Try to consume a specific word. Returns True if successful.

        Note: This is kept for edge cases (process sub leading }, variable names).
        Most reserved word consumption has been migrated to _lex_consume_word().
        """
        saved_pos = self.pos
        self.skip_whitespace()

        word = self.peek_word()
        # In command substitutions, strip leading } for keyword matching
        # Don't strip { because it's used for brace groups
        keyword_word = word
        has_leading_brace = False
        if word is not None and self._in_process_sub and len(word) > 1 and word[0] == "}":
            keyword_word = word[1:]
            has_leading_brace = True

        if keyword_word != expected:
            self.pos = saved_pos
            return False

        # Actually consume the word
        self.skip_whitespace()
        # If there's a leading } or {, skip it first
        if has_leading_brace:
            self.advance()
        for _ in expected:
            self.advance()
        # Skip trailing backslash-newline (line continuation)
        while (
            self.peek() == "\\" and self.pos + 1 < self.length and self.source[self.pos + 1] == "\n"
        ):
            self.advance()  # skip backslash
            self.advance()  # skip newline
        return True

    def _is_word_terminator(
        self, ctx: int, ch: str, bracket_depth: int = 0, paren_depth: int = 0
    ) -> bool:
        """Check if character terminates word in given context."""
        self._sync_lexer()
        return self._lexer._is_word_terminator(ctx, ch, bracket_depth, paren_depth)

    def _scan_double_quote(
        self, chars: list[str], parts: list[Node], start: int, handle_line_continuation: bool = True
    ) -> None:
        """Scan double-quoted string with expansions. Assumes opening quote consumed."""
        chars.append('"')
        while not self.at_end() and self.peek() != '"':
            c = self.peek()
            if c == "\\" and self.pos + 1 < self.length:
                next_c = self.source[self.pos + 1]
                if handle_line_continuation and next_c == "\n":
                    self.advance()
                    self.advance()
                else:
                    chars.append(self.advance())
                    chars.append(self.advance())
            elif c == "$":
                if not self._parse_dollar_expansion(chars, parts, in_dquote=True):
                    chars.append(self.advance())
            else:
                chars.append(self.advance())
        if self.at_end():
            raise ParseError("Unterminated double quote", pos=start)
        chars.append(self.advance())

    def _parse_dollar_expansion(
        self, chars: list[str], parts: list[Node], in_dquote: bool = False
    ) -> bool:
        """Handle $ expansions. Returns True if expansion parsed, False if bare $."""
        # Check $(( -> arithmetic expansion
        if (
            self.pos + 2 < self.length
            and self.source[self.pos + 1] == "("
            and self.source[self.pos + 2] == "("
        ):
            result = self._parse_arithmetic_expansion()
            if result[0]:
                parts.append(result[0])
                chars.append(result[1])
                return True
            # Not arithmetic (e.g., '$( ( ... ) )' is command sub + subshell)
            result = self._parse_command_substitution()
            if result[0]:
                parts.append(result[0])
                chars.append(result[1])
                return True
            return False
        # Check $[ -> deprecated arithmetic
        if self.pos + 1 < self.length and self.source[self.pos + 1] == "[":
            result = self._parse_deprecated_arithmetic()
            if result[0]:
                parts.append(result[0])
                chars.append(result[1])
                return True
            return False
        # Check $( -> command substitution
        if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
            result = self._parse_command_substitution()
            if result[0]:
                parts.append(result[0])
                chars.append(result[1])
                return True
            return False
        # Otherwise -> parameter expansion
        result = self._parse_param_expansion(in_dquote)
        if result[0]:
            parts.append(result[0])
            chars.append(result[1])
            return True
        return False

    def _parse_word_internal(
        self, ctx: int, at_command_start: bool = False, in_array_literal: bool = False
    ) -> Word | None:
        """Unified word parser with context-aware termination. Sets context and delegates."""
        self._word_context = ctx
        return self.parse_word(at_command_start, in_array_literal)

    def parse_word(
        self,
        at_command_start: bool = False,
        in_array_literal: bool = False,
        in_assign_builtin: bool = False,
    ) -> Word | None:
        """Parse a word token by consuming WORD token with pre-parsed Word object."""
        self.skip_whitespace()
        if self.at_end():
            return None
        # Set context for Lexer before peeking
        self._at_command_start = at_command_start
        self._in_array_literal = in_array_literal
        self._in_assign_builtin = in_assign_builtin
        tok = self._lex_peek_token()
        if tok.type != TokenType.WORD:
            # Reset context when not a word to avoid affecting subsequent calls
            self._at_command_start = False
            self._in_array_literal = False
            self._in_assign_builtin = False
            return None
        self._lex_next_token()
        # Reset context after consuming to avoid affecting subsequent calls
        self._at_command_start = False
        self._in_array_literal = False
        self._in_assign_builtin = False
        return tok.word

    def _parse_command_substitution(self) -> tuple[Node | None, str]:
        """Parse a $(...) command substitution using EOF token mechanism.

        Returns (node, text) where node is CommandSubstitution and text is raw text.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos
        self.advance()  # consume $

        if self.at_end() or self.peek() != "(":
            self.pos = start
            return None, ""

        self.advance()  # consume (

        # Save state and set up for inline parsing with EOF token
        saved = self._save_parser_state()
        self._set_state(ParserStateFlags.PST_CMDSUBST | ParserStateFlags.PST_EOFTOKEN)
        self._eof_token = ")"

        # Parse the command list inline - grammar will stop at matching )
        cmd = self.parse_list()
        if cmd is None:
            cmd = Empty()

        # After parse_list, we should be at the closing )
        self.skip_whitespace_and_newlines()
        if self.at_end() or self.peek() != ")":
            self._restore_parser_state(saved)
            self.pos = start
            return None, ""

        self.advance()  # consume final )
        text_end = self.pos
        text = _substring(self.source, start, text_end)

        self._restore_parser_state(saved)
        return CommandSubstitution(cmd), text

    def _parse_funsub(self, start: int) -> tuple[Node | None, str]:
        """Parse brace command substitution ${ cmd; } or ${| cmd; }.

        Called from Lexer when ${ followed by funsub char is detected.
        start is position of $, and we're at the char after {.
        """
        self._sync_parser()
        # Skip leading | if present (${| ... } variant)
        if not self.at_end() and self.peek() == "|":
            self.advance()
        # Save state and set up for inline parsing with EOF token
        saved = self._save_parser_state()
        self._set_state(ParserStateFlags.PST_CMDSUBST | ParserStateFlags.PST_EOFTOKEN)
        self._eof_token = "}"
        # Parse the command list inline - grammar will stop at matching }
        cmd = self.parse_list()
        if cmd is None:
            cmd = Empty()
        # After parse_list, we should be at the closing }
        self.skip_whitespace_and_newlines()
        if self.at_end() or self.peek() != "}":
            self._restore_parser_state(saved)
            raise MatchedPairError("unexpected EOF looking for `}'", pos=start)
        self.advance()  # consume final }
        text = _substring(self.source, start, self.pos)
        self._restore_parser_state(saved)
        self._sync_lexer()
        return CommandSubstitution(cmd, brace=True), text

    def _is_assignment_word(self, word: Word) -> bool:
        """Check if a word is an assignment (name=value)."""
        return _assignment(word.value) != -1

    def _parse_backtick_substitution(self) -> tuple[Node | None, str]:
        """Parse a `...` command substitution.

        Returns (node, text) where node is CommandSubstitution and text is raw text.
        """
        if self.at_end() or self.peek() != "`":
            return None, ""

        start = self.pos
        self.advance()  # consume opening `

        # Find closing backtick, processing escape sequences as we go.
        # In backticks, backslash is special only before $, `, \, or newline.
        # \$ -> $, \` -> `, \\ -> \, \<newline> -> removed (line continuation)
        # other \X -> \X (backslash is literal)
        # content_chars: what gets parsed as the inner command
        # text_chars: what appears in the word representation (with line continuations removed)
        content_chars: list[str] = []
        text_chars = ["`"]  # opening backtick
        # Heredoc state tracking
        pending_heredocs: list[tuple[str, bool]] = []
        in_heredoc_body = False
        current_heredoc_delim = ""
        current_heredoc_strip = False

        while not self.at_end() and (in_heredoc_body or self.peek() != "`"):
            # When in heredoc body, scan for delimiter line by line (no escape processing)
            if in_heredoc_body:
                line_start = self.pos
                line_end = line_start
                while line_end < self.length and self.source[line_end] != "\n":
                    line_end += 1
                line = _substring(self.source, line_start, line_end)
                check_line = line.lstrip("\t") if current_heredoc_strip else line
                if check_line == current_heredoc_delim:
                    # Found delimiter - add line to content and exit body mode
                    for ch in line:
                        content_chars.append(ch)
                        text_chars.append(ch)
                    self.pos = line_end
                    if self.pos < self.length and self.source[self.pos] == "\n":
                        content_chars.append("\n")
                        text_chars.append("\n")
                        self.advance()
                    in_heredoc_body = False
                    if len(pending_heredocs) > 0:
                        current_heredoc_delim, current_heredoc_strip = pending_heredocs.pop(0)
                        in_heredoc_body = True
                elif check_line.startswith(current_heredoc_delim) and len(check_line) > len(
                    current_heredoc_delim
                ):
                    # Delimiter with trailing content
                    tabs_stripped = len(line) - len(check_line)
                    end_pos = tabs_stripped + len(current_heredoc_delim)
                    for i in range(end_pos):
                        content_chars.append(line[i])
                        text_chars.append(line[i])
                    self.pos = line_start + end_pos
                    in_heredoc_body = False
                    if len(pending_heredocs) > 0:
                        current_heredoc_delim, current_heredoc_strip = pending_heredocs.pop(0)
                        in_heredoc_body = True
                else:
                    # Not delimiter - add line and newline to content
                    for ch in line:
                        content_chars.append(ch)
                        text_chars.append(ch)
                    self.pos = line_end
                    if self.pos < self.length and self.source[self.pos] == "\n":
                        content_chars.append("\n")
                        text_chars.append("\n")
                        self.advance()
                continue

            c = self.peek()

            # Escape handling
            if c == "\\" and self.pos + 1 < self.length:
                next_c = self.source[self.pos + 1]
                if next_c == "\n":
                    # Line continuation: skip both backslash and newline
                    self.advance()  # skip \
                    self.advance()  # skip newline
                    # Don't add to content_chars or text_chars
                elif _is_escape_char_in_backtick(next_c):
                    # Escape sequence: skip backslash in content, keep both in text
                    self.advance()  # skip \
                    escaped = self.advance()
                    content_chars.append(escaped)
                    text_chars.append("\\")
                    text_chars.append(escaped)
                else:
                    # Backslash is literal before other characters
                    ch = self.advance()
                    content_chars.append(ch)
                    text_chars.append(ch)
                continue

            # Heredoc declaration
            if c == "<" and self.pos + 1 < self.length and self.source[self.pos + 1] == "<":
                # Check for here-string <<<
                if self.pos + 2 < self.length and self.source[self.pos + 2] == "<":
                    content_chars.append(self.advance())  # <
                    text_chars.append("<")
                    content_chars.append(self.advance())  # <
                    text_chars.append("<")
                    content_chars.append(self.advance())  # <
                    text_chars.append("<")
                    # Skip whitespace and here-string word
                    while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                        ch = self.advance()
                        content_chars.append(ch)
                        text_chars.append(ch)
                    while (
                        not self.at_end()
                        and not _is_whitespace(self.peek())
                        and self.peek() not in "()"
                    ):
                        if self.peek() == "\\" and self.pos + 1 < self.length:
                            ch = self.advance()
                            content_chars.append(ch)
                            text_chars.append(ch)
                            ch = self.advance()
                            content_chars.append(ch)
                            text_chars.append(ch)
                        elif self.peek() in "\"'":
                            quote = self.peek()
                            ch = self.advance()
                            content_chars.append(ch)
                            text_chars.append(ch)
                            while not self.at_end() and self.peek() != quote:
                                if quote == '"' and self.peek() == "\\":
                                    ch = self.advance()
                                    content_chars.append(ch)
                                    text_chars.append(ch)
                                ch = self.advance()
                                content_chars.append(ch)
                                text_chars.append(ch)
                            if not self.at_end():
                                ch = self.advance()
                                content_chars.append(ch)
                                text_chars.append(ch)
                        else:
                            ch = self.advance()
                            content_chars.append(ch)
                            text_chars.append(ch)
                    continue
                # Heredoc <<
                content_chars.append(self.advance())  # <
                text_chars.append("<")
                content_chars.append(self.advance())  # <
                text_chars.append("<")
                strip_tabs = False
                if not self.at_end() and self.peek() == "-":
                    strip_tabs = True
                    content_chars.append(self.advance())
                    text_chars.append("-")
                # Skip whitespace
                while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                    ch = self.advance()
                    content_chars.append(ch)
                    text_chars.append(ch)
                # Parse delimiter
                delimiter_chars: list[str] = []
                if not self.at_end():
                    ch = self.peek()
                    if _is_quote(ch):
                        quote = self.advance()
                        content_chars.append(quote)
                        text_chars.append(quote)
                        while not self.at_end() and self.peek() != quote:
                            dch = self.advance()
                            content_chars.append(dch)
                            text_chars.append(dch)
                            delimiter_chars.append(dch)
                        if not self.at_end():
                            closing = self.advance()
                            content_chars.append(closing)
                            text_chars.append(closing)
                    elif ch == "\\":
                        esc = self.advance()
                        content_chars.append(esc)
                        text_chars.append(esc)
                        if not self.at_end():
                            dch = self.advance()
                            content_chars.append(dch)
                            text_chars.append(dch)
                            delimiter_chars.append(dch)
                        while not self.at_end() and not _is_metachar(self.peek()):
                            dch = self.advance()
                            content_chars.append(dch)
                            text_chars.append(dch)
                            delimiter_chars.append(dch)
                    else:
                        # Stop at backtick (closes substitution) or metachar
                        while (
                            not self.at_end()
                            and not _is_metachar(self.peek())
                            and self.peek() != "`"
                        ):
                            ch = self.peek()
                            if _is_quote(ch):
                                quote = self.advance()
                                content_chars.append(quote)
                                text_chars.append(quote)
                                while not self.at_end() and self.peek() != quote:
                                    dch = self.advance()
                                    content_chars.append(dch)
                                    text_chars.append(dch)
                                    delimiter_chars.append(dch)
                                if not self.at_end():
                                    closing = self.advance()
                                    content_chars.append(closing)
                                    text_chars.append(closing)
                            elif ch == "\\":
                                esc = self.advance()
                                content_chars.append(esc)
                                text_chars.append(esc)
                                if not self.at_end():
                                    dch = self.advance()
                                    content_chars.append(dch)
                                    text_chars.append(dch)
                                    delimiter_chars.append(dch)
                            else:
                                dch = self.advance()
                                content_chars.append(dch)
                                text_chars.append(dch)
                                delimiter_chars.append(dch)
                delimiter = "".join(delimiter_chars)
                if delimiter:
                    pending_heredocs.append((delimiter, strip_tabs))
                continue

            # Newline - check for heredoc body mode
            if c == "\n":
                ch = self.advance()
                content_chars.append(ch)
                text_chars.append(ch)
                if len(pending_heredocs) > 0:
                    current_heredoc_delim, current_heredoc_strip = pending_heredocs.pop(0)
                    in_heredoc_body = True
                continue

            # Regular character
            ch = self.advance()
            content_chars.append(ch)
            text_chars.append(ch)

        if self.at_end():
            raise ParseError("Unterminated backtick", pos=start)

        self.advance()  # consume closing `
        text_chars.append("`")  # closing backtick
        text = "".join(text_chars)
        content = "".join(content_chars)

        # Check for heredocs whose bodies follow the closing backtick
        if len(pending_heredocs) > 0:
            heredoc_start, heredoc_end = _find_heredoc_content_end(
                self.source, self.pos, pending_heredocs
            )
            if heredoc_end > heredoc_start:
                content = content + _substring(self.source, heredoc_start, heredoc_end)
                if self._cmdsub_heredoc_end == -1:
                    self._cmdsub_heredoc_end = heredoc_end
                else:
                    self._cmdsub_heredoc_end = max(self._cmdsub_heredoc_end, heredoc_end)

        # Parse the content as a command list
        sub_parser = Parser(content, extglob=self._extglob)
        cmd = sub_parser.parse_list()
        if cmd is None:
            cmd = Empty()

        return CommandSubstitution(cmd), text

    def _parse_process_substitution(self) -> tuple[Node | None, str]:
        """Parse a <(...) or >(...) process substitution using EOF token mechanism.

        Returns (node, text) where node is ProcessSubstitution and text is raw text.
        If the content can't be parsed as a valid command, returns (None, text) so
        the caller can treat it as literal characters.
        """
        if self.at_end() or not _is_redirect_char(self.peek()):
            return None, ""

        start = self.pos
        direction = self.advance()  # consume < or >

        if self.at_end() or self.peek() != "(":
            self.pos = start
            return None, ""

        self.advance()  # consume (

        # Save state and set up for inline parsing with EOF token
        saved = self._save_parser_state()
        old_in_process_sub = self._in_process_sub
        self._in_process_sub = True
        self._set_state(ParserStateFlags.PST_EOFTOKEN)
        self._eof_token = ")"

        # Try to parse the command list inline - grammar will stop at matching )
        try:
            cmd = self.parse_list()
            if cmd is None:
                cmd = Empty()

            # After parse_list, we should be at the closing )
            self.skip_whitespace_and_newlines()
            if self.at_end() or self.peek() != ")":
                # Parsing didn't reach the closing ) - not a valid process sub
                raise ParseError("Invalid process substitution", pos=start)

            self.advance()  # consume final )
            text_end = self.pos
            text = _substring(self.source, start, text_end)
            # Strip line continuations (backslash-newline) from text
            text = _strip_line_continuations_comment_aware(text)

            self._restore_parser_state(saved)
            self._in_process_sub = old_in_process_sub
            return ProcessSubstitution(direction, cmd), text

        except ParseError as e:
            # Parsing failed - check if we should error or fall back to literal
            self._restore_parser_state(saved)
            self._in_process_sub = old_in_process_sub

            # Check what's after the opening <( or >(
            content_start_char = self.source[start + 2] if start + 2 < self.length else ""

            # If content starts with ( (like <((...)), bash treats as literal, not procsub
            # If content starts with space/tab/newline, bash commits to procsub and errors
            if content_start_char in " \t\n":
                # Committed to procsub - re-raise the error (bash behavior)
                raise e

            # Otherwise, fall back to scanning for closing ) and return as literal
            self.pos = start + 2  # after <( or >(
            self._lexer.pos = self.pos  # sync lexer to parser
            self._lexer._parse_matched_pair("(", ")")
            self.pos = self._lexer.pos  # sync parser from lexer
            text = _substring(self.source, start, self.pos)
            text = _strip_line_continuations_comment_aware(text)
            return None, text

    def _parse_array_literal(self) -> tuple[Node | None, str]:
        """Parse an array literal (word1 word2 ...).

        Returns (node, text) where node is Array and text is raw text.
        Called when positioned at the opening '(' after '=' or '+='.
        """
        if self.at_end() or self.peek() != "(":
            return None, ""

        start = self.pos
        self.advance()  # consume (
        self._set_state(ParserStateFlags.PST_COMPASSIGN)

        elements = []

        while True:
            # Skip whitespace, newlines, and comments between elements
            self.skip_whitespace_and_newlines()

            if self.at_end():
                self._clear_state(ParserStateFlags.PST_COMPASSIGN)
                raise ParseError("Unterminated array literal", pos=start)

            if self.peek() == ")":
                break

            # Parse an element word
            word = self.parse_word(False, True)  # at_command_start=False, in_array_literal=True
            if word is None:
                # Might be a closing paren or error
                if self.peek() == ")":
                    break
                self._clear_state(ParserStateFlags.PST_COMPASSIGN)
                raise ParseError("Expected word in array literal", pos=self.pos)

            elements.append(word)

        if self.at_end() or self.peek() != ")":
            self._clear_state(ParserStateFlags.PST_COMPASSIGN)
            raise ParseError("Expected ) to close array literal", pos=self.pos)
        self.advance()  # consume )

        text = _substring(self.source, start, self.pos)
        self._clear_state(ParserStateFlags.PST_COMPASSIGN)
        return Array(elements), text

    def _parse_arithmetic_expansion(self) -> tuple[Node | None, str]:
        """Parse a $((...)) arithmetic expansion with parsed internals.

        Returns (node, text) where node is ArithmeticExpansion and text is raw text.
        Returns (None, "") if this is not arithmetic expansion.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""
        start = self.pos
        # Check for $((
        if (
            self.pos + 2 >= self.length
            or self.source[self.pos + 1] != "("
            or self.source[self.pos + 2] != "("
        ):
            return None, ""
        self.advance()  # consume $
        self.advance()  # consume first (
        self.advance()  # consume second (
        # Find matching )) by tracking paren depth
        content_start = self.pos
        depth = 2
        first_close_pos: int = -1  # -1 = not set
        while not self.at_end() and depth > 0:
            c = self.peek()
            # Skip single-quoted strings (parens inside don't count)
            if c == "'":
                self.advance()
                while not self.at_end() and self.peek() != "'":
                    self.advance()
                if not self.at_end():
                    self.advance()
            # Skip double-quoted strings (parens inside don't count)
            elif c == '"':
                self.advance()
                while not self.at_end():
                    if self.peek() == "\\" and self.pos + 1 < self.length:
                        self.advance()
                        self.advance()
                    elif self.peek() == '"':
                        self.advance()
                        break
                    else:
                        self.advance()
            # Handle backslash escapes outside quotes
            elif c == "\\" and self.pos + 1 < self.length:
                self.advance()
                self.advance()
            elif c == "(":
                depth += 1
                self.advance()
            elif c == ")":
                if depth == 2:
                    first_close_pos = self.pos
                depth -= 1
                if depth == 0:
                    break
                self.advance()
            else:
                if depth == 1:
                    first_close_pos = -1
                self.advance()
        if depth != 0:
            if self.at_end():
                raise MatchedPairError("unexpected EOF looking for `))'", pos=start)
            self.pos = start
            return None, ""
        # Content ends at first_close_pos if set, else at final )
        if first_close_pos != -1:
            content = _substring(self.source, content_start, first_close_pos)
        else:
            content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume final )
        text = _substring(self.source, start, self.pos)
        # Parse the arithmetic expression
        try:
            expr = self._parse_arith_expr(content)
        except ParseError:
            self.pos = start
            return None, ""
        return ArithmeticExpansion(expr), text

    # ========== Arithmetic expression parser ==========
    # Operator precedence (lowest to highest):
    # 1. comma (,)
    # 2. assignment (= += -= *= /= %= <<= >>= &= ^= |=)
    # 3. ternary (? :)
    # 4. logical or (||)
    # 5. logical and (&&)
    # 6. bitwise or (|)
    # 7. bitwise xor (^)
    # 8. bitwise and (&)
    # 9. equality (== !=)
    # 10. comparison (< > <= >=)
    # 11. shift (<< >>)
    # 12. addition (+ -)
    # 13. multiplication (* / %)
    # 14. exponentiation (**)
    # 15. unary (! ~ + - ++ --)
    # 16. postfix (++ -- [])

    def _parse_arith_expr(self, content: str) -> Node | None:
        """Parse an arithmetic expression string into AST nodes."""
        # Save any existing arith context (for nested parsing)
        saved_arith_src = self._arith_src
        saved_arith_pos = self._arith_pos
        saved_arith_len = self._arith_len
        saved_parser_state = self._parser_state

        self._set_state(ParserStateFlags.PST_ARITH)
        self._arith_src: str = content
        self._arith_pos: int = 0
        self._arith_len: int = len(content)
        self._arith_skip_ws()
        if self._arith_at_end():
            result = None
        else:
            result = self._arith_parse_comma()

        # Restore previous arith context and parser state
        self._parser_state = saved_parser_state
        if saved_arith_src is not None:
            self._arith_src = saved_arith_src
            self._arith_pos = saved_arith_pos
            self._arith_len = saved_arith_len

        return result

    def _arith_at_end(self) -> bool:
        return self._arith_pos >= self._arith_len

    def _arith_peek(self, offset: int = 0) -> str:
        pos = self._arith_pos + offset
        if pos >= self._arith_len:
            return ""
        return self._arith_src[pos]

    def _arith_advance(self) -> str:
        if self._arith_at_end():
            return ""
        c = self._arith_src[self._arith_pos]
        self._arith_pos += 1
        return c

    def _arith_skip_ws(self) -> None:
        while not self._arith_at_end():
            c = self._arith_src[self._arith_pos]
            if _is_whitespace(c):
                self._arith_pos += 1
            elif (
                c == "\\"
                and self._arith_pos + 1 < self._arith_len
                and self._arith_src[self._arith_pos + 1] == "\n"
            ):
                # Backslash-newline continuation
                self._arith_pos += 2
            else:
                break

    def _arith_match(self, s: str) -> bool:
        """Check if the next characters match s (without consuming)."""
        return _starts_with_at(self._arith_src, self._arith_pos, s)

    def _arith_consume(self, s: str) -> bool:
        """If next chars match s, consume them and return True."""
        if self._arith_match(s):
            self._arith_pos += len(s)
            return True
        return False

    def _arith_parse_comma(self) -> Node:
        """Parse comma expressions (lowest precedence)."""
        left = self._arith_parse_assign()
        while True:
            self._arith_skip_ws()
            if self._arith_consume(","):
                self._arith_skip_ws()
                right = self._arith_parse_assign()
                left = ArithComma(left, right)
            else:
                break
        return left

    def _arith_parse_assign(self) -> Node:
        """Parse assignment expressions (right associative)."""
        left = self._arith_parse_ternary()
        self._arith_skip_ws()
        # Check for assignment operators
        assign_ops = ["<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "^=", "|=", "="]
        for op in assign_ops:
            if self._arith_match(op):
                # Make sure it's not == or !=
                if op == "=" and self._arith_peek(1) == "=":
                    break
                self._arith_consume(op)
                self._arith_skip_ws()
                right = self._arith_parse_assign()  # right associative
                return ArithAssign(op, left, right)
        return left

    def _arith_parse_ternary(self) -> Node:
        """Parse ternary conditional (right associative)."""
        cond = self._arith_parse_logical_or()
        self._arith_skip_ws()
        if self._arith_consume("?"):
            self._arith_skip_ws()
            # True branch can be empty (e.g., 4 ? : $A - invalid at runtime, valid syntax)
            if self._arith_match(":"):
                if_true = None
            else:
                if_true = self._arith_parse_assign()
            self._arith_skip_ws()
            # Check for : (may be missing in malformed expressions like 1 ? 20)
            if self._arith_consume(":"):
                self._arith_skip_ws()
                # False branch can be empty (e.g., 4 ? 20 : - invalid at runtime)
                if self._arith_at_end() or self._arith_peek() == ")":
                    if_false = None
                else:
                    if_false = self._arith_parse_ternary()
            else:
                if_false = None
            return ArithTernary(cond, if_true, if_false)
        return cond

    def _arith_parse_left_assoc(self, ops: list[str], parsefn: Callable[[], Node]) -> Node:
        """Parse left-associative binary operators using match/consume."""
        left = parsefn()
        while True:
            self._arith_skip_ws()
            matched = False
            for op in ops:
                if self._arith_match(op):
                    self._arith_consume(op)
                    self._arith_skip_ws()
                    left = ArithBinaryOp(op, left, parsefn())
                    matched = True
                    break
            if not matched:
                break
        return left

    def _arith_parse_logical_or(self) -> Node:
        """Parse logical or (||)."""
        return self._arith_parse_left_assoc(["||"], self._arith_parse_logical_and)

    def _arith_parse_logical_and(self) -> Node:
        """Parse logical and (&&)."""
        return self._arith_parse_left_assoc(["&&"], self._arith_parse_bitwise_or)

    def _arith_parse_bitwise_or(self) -> Node:
        """Parse bitwise or (|)."""
        left = self._arith_parse_bitwise_xor()
        while True:
            self._arith_skip_ws()
            # Make sure it's not || or |=
            if self._arith_peek() == "|" and (
                self._arith_peek(1) != "|" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_bitwise_xor()
                left = ArithBinaryOp("|", left, right)
            else:
                break
        return left

    def _arith_parse_bitwise_xor(self) -> Node:
        """Parse bitwise xor (^)."""
        left = self._arith_parse_bitwise_and()
        while True:
            self._arith_skip_ws()
            # Make sure it's not ^=
            if self._arith_peek() == "^" and self._arith_peek(1) != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_bitwise_and()
                left = ArithBinaryOp("^", left, right)
            else:
                break
        return left

    def _arith_parse_bitwise_and(self) -> Node:
        """Parse bitwise and (&)."""
        left = self._arith_parse_equality()
        while True:
            self._arith_skip_ws()
            # Make sure it's not && or &=
            if self._arith_peek() == "&" and (
                self._arith_peek(1) != "&" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_equality()
                left = ArithBinaryOp("&", left, right)
            else:
                break
        return left

    def _arith_parse_equality(self) -> Node:
        """Parse equality (== !=)."""
        return self._arith_parse_left_assoc(["==", "!="], self._arith_parse_comparison)

    def _arith_parse_comparison(self) -> Node:
        """Parse comparison (< > <= >=)."""
        left = self._arith_parse_shift()
        while True:
            self._arith_skip_ws()
            if self._arith_match("<="):
                self._arith_consume("<=")
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp("<=", left, right)
            elif self._arith_match(">="):
                self._arith_consume(">=")
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp(">=", left, right)
            elif self._arith_peek() == "<" and (
                self._arith_peek(1) != "<" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp("<", left, right)
            elif self._arith_peek() == ">" and (
                self._arith_peek(1) != ">" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp(">", left, right)
            else:
                break
        return left

    def _arith_parse_shift(self) -> Node:
        """Parse shift (<< >>)."""
        left = self._arith_parse_additive()
        while True:
            self._arith_skip_ws()
            if self._arith_match("<<="):
                break  # assignment, not shift
            if self._arith_match(">>="):
                break  # assignment, not shift
            if self._arith_match("<<"):
                self._arith_consume("<<")
                self._arith_skip_ws()
                right = self._arith_parse_additive()
                left = ArithBinaryOp("<<", left, right)
            elif self._arith_match(">>"):
                self._arith_consume(">>")
                self._arith_skip_ws()
                right = self._arith_parse_additive()
                left = ArithBinaryOp(">>", left, right)
            else:
                break
        return left

    def _arith_parse_additive(self) -> Node:
        """Parse addition and subtraction (+ -)."""
        left = self._arith_parse_multiplicative()
        while True:
            self._arith_skip_ws()
            c = self._arith_peek()
            c2 = self._arith_peek(1)
            if c == "+" and (c2 != "+" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_multiplicative()
                left = ArithBinaryOp("+", left, right)
            elif c == "-" and (c2 != "-" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_multiplicative()
                left = ArithBinaryOp("-", left, right)
            else:
                break
        return left

    def _arith_parse_multiplicative(self) -> Node:
        """Parse multiplication, division, modulo (* / %)."""
        left = self._arith_parse_exponentiation()
        while True:
            self._arith_skip_ws()
            c = self._arith_peek()
            c2 = self._arith_peek(1)
            if c == "*" and (c2 != "*" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("*", left, right)
            elif c == "/" and c2 != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("/", left, right)
            elif c == "%" and c2 != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("%", left, right)
            else:
                break
        return left

    def _arith_parse_exponentiation(self) -> Node:
        """Parse exponentiation (**) - right associative."""
        left = self._arith_parse_unary()
        self._arith_skip_ws()
        if self._arith_match("**"):
            self._arith_consume("**")
            self._arith_skip_ws()
            right = self._arith_parse_exponentiation()  # right associative
            return ArithBinaryOp("**", left, right)
        return left

    def _arith_parse_unary(self) -> Node:
        """Parse unary operators (! ~ + - ++ --)."""
        self._arith_skip_ws()
        # Pre-increment/decrement
        if self._arith_match("++"):
            self._arith_consume("++")
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithPreIncr(operand)
        if self._arith_match("--"):
            self._arith_consume("--")
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithPreDecr(operand)
        # Unary operators
        c = self._arith_peek()
        if c == "!":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("!", operand)
        if c == "~":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("~", operand)
        if c == "+" and self._arith_peek(1) != "+":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("+", operand)
        if c == "-" and self._arith_peek(1) != "-":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("-", operand)
        return self._arith_parse_postfix()

    def _arith_parse_postfix(self) -> Node:
        """Parse postfix operators (++ -- [])."""
        left = self._arith_parse_primary()
        while True:
            self._arith_skip_ws()
            if self._arith_match("++"):
                self._arith_consume("++")
                left = ArithPostIncr(left)
            elif self._arith_match("--"):
                self._arith_consume("--")
                left = ArithPostDecr(left)
            elif self._arith_peek() == "[":
                # Array subscript - but only for variables
                if left.kind == "var":
                    self._arith_advance()  # consume [
                    self._arith_skip_ws()
                    index = self._arith_parse_comma()
                    self._arith_skip_ws()
                    if not self._arith_consume("]"):
                        raise ParseError("Expected ']' in array subscript", pos=self._arith_pos)
                    left = ArithSubscript(left.name, index)
                else:
                    break
            else:
                break
        return left

    def _arith_parse_primary(self) -> Node:
        """Parse primary expressions (numbers, variables, parens, expansions)."""
        self._arith_skip_ws()
        c = self._arith_peek()

        # Parenthesized expression
        if c == "(":
            self._arith_advance()
            self._arith_skip_ws()
            expr = self._arith_parse_comma()
            self._arith_skip_ws()
            if not self._arith_consume(")"):
                raise ParseError("Expected ')' in arithmetic expression", pos=self._arith_pos)
            return expr

        # Parameter length #$var or #${...}
        if c == "#" and self._arith_peek(1) == "$":
            self._arith_advance()  # consume #
            return self._arith_parse_expansion()

        # Parameter expansion ${...} or $var or $(...)
        if c == "$":
            return self._arith_parse_expansion()

        # Single-quoted string - content becomes the number
        if c == "'":
            return self._arith_parse_single_quote()

        # Double-quoted string - may contain expansions
        if c == '"':
            return self._arith_parse_double_quote()

        # Backtick command substitution
        if c == "`":
            return self._arith_parse_backtick()

        # Escape sequence \X (not line continuation, which is handled in _arith_skip_ws)
        # Escape covers only the single character after backslash
        if c == "\\":
            self._arith_advance()  # consume backslash
            if self._arith_at_end():
                raise ParseError(
                    "Unexpected end after backslash in arithmetic", pos=self._arith_pos
                )
            escaped_char = self._arith_advance()  # consume escaped character
            return ArithEscape(escaped_char)

        # Check for end of expression or operators - bash allows missing operands
        # (defers validation to runtime), so we return an empty node
        # Include #{} and ; which bash accepts syntactically but fails at runtime
        if self._arith_at_end() or c in ")]:,;?|&<>=!+-*/%^~#{}":
            return ArithEmpty()

        # Number or variable
        return self._arith_parse_number_or_var()

    def _arith_parse_expansion(self) -> Node:
        """Parse $var, ${...}, or $(...)."""
        if not self._arith_consume("$"):
            raise ParseError("Expected '$'", pos=self._arith_pos)

        c = self._arith_peek()

        # Command substitution $(...)
        if c == "(":
            return self._arith_parse_cmdsub()

        # Braced parameter ${...}
        if c == "{":
            return self._arith_parse_braced_param()

        # Simple $var
        name_chars = []
        while not self._arith_at_end():
            ch = self._arith_peek()
            if ch.isalnum() or ch == "_":
                name_chars.append(self._arith_advance())
            elif (_is_special_param_or_digit(ch) or ch == "#") and not name_chars:
                # Special parameters
                name_chars.append(self._arith_advance())
                break
            else:
                break
        if not name_chars:
            raise ParseError("Expected variable name after $", pos=self._arith_pos)
        return ParamExpansion("".join(name_chars))

    def _arith_parse_cmdsub(self) -> Node:
        """Parse $(...) command substitution inside arithmetic."""
        # We're positioned after $, at (
        self._arith_advance()  # consume (

        # Check for $(( which is nested arithmetic
        if self._arith_peek() == "(":
            self._arith_advance()  # consume second (
            depth = 1
            content_start = self._arith_pos
            while not self._arith_at_end() and depth > 0:
                ch = self._arith_peek()
                if ch == "(":
                    depth += 1
                    self._arith_advance()
                elif ch == ")":
                    if depth == 1 and self._arith_peek(1) == ")":
                        break
                    depth -= 1
                    self._arith_advance()
                else:
                    self._arith_advance()
            content = _substring(self._arith_src, content_start, self._arith_pos)
            self._arith_advance()  # consume first )
            self._arith_advance()  # consume second )
            inner_expr = self._parse_arith_expr(content)
            return ArithmeticExpansion(inner_expr)

        # Regular command substitution
        depth = 1
        content_start = self._arith_pos
        while not self._arith_at_end() and depth > 0:
            ch = self._arith_peek()
            if ch == "(":
                depth += 1
                self._arith_advance()
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
                self._arith_advance()
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        self._arith_advance()  # consume )

        # Parse the command inside
        sub_parser = Parser(content, extglob=self._extglob)
        cmd = sub_parser.parse_list()

        return CommandSubstitution(cmd)

    def _arith_parse_braced_param(self) -> Node:
        """Parse ${...} parameter expansion inside arithmetic."""
        self._arith_advance()  # consume {

        # Handle indirect ${!var}
        if self._arith_peek() == "!":
            self._arith_advance()
            name_chars = []
            while not self._arith_at_end() and self._arith_peek() != "}":
                name_chars.append(self._arith_advance())
            self._arith_consume("}")
            return ParamIndirect("".join(name_chars))

        # Handle length ${#var}
        if self._arith_peek() == "#":
            self._arith_advance()
            name_chars = []
            while not self._arith_at_end() and self._arith_peek() != "}":
                name_chars.append(self._arith_advance())
            self._arith_consume("}")
            return ParamLength("".join(name_chars))

        # Regular ${var} or ${var...}
        name_chars = []
        while not self._arith_at_end():
            ch = self._arith_peek()
            if ch == "}":
                self._arith_advance()
                return ParamExpansion("".join(name_chars))
            if _is_param_expansion_op(ch):
                # Operator follows
                break
            name_chars.append(self._arith_advance())

        name = "".join(name_chars)

        # Check for operator
        op_chars = []
        depth = 1
        while not self._arith_at_end() and depth > 0:
            ch = self._arith_peek()
            if ch == "{":
                depth += 1
                op_chars.append(self._arith_advance())
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
                op_chars.append(self._arith_advance())
            else:
                op_chars.append(self._arith_advance())
        self._arith_consume("}")
        op_str = "".join(op_chars)

        # Parse the operator
        if op_str.startswith(":-"):
            return ParamExpansion(name, ":-", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":="):
            return ParamExpansion(name, ":=", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":+"):
            return ParamExpansion(name, ":+", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":?"):
            return ParamExpansion(name, ":?", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":"):
            return ParamExpansion(name, ":", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("##"):
            return ParamExpansion(name, "##", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("#"):
            return ParamExpansion(name, "#", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("%%"):
            return ParamExpansion(name, "%%", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("%"):
            return ParamExpansion(name, "%", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("//"):
            return ParamExpansion(name, "//", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("/"):
            return ParamExpansion(name, "/", _substring(op_str, 1, len(op_str)))
        return ParamExpansion(name, "", op_str)

    def _arith_parse_single_quote(self) -> Node:
        """Parse '...' inside arithmetic - returns content as a number/string."""
        self._arith_advance()  # consume opening '
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != "'":
            self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume("'"):
            raise ParseError("Unterminated single quote in arithmetic", pos=self._arith_pos)
        return ArithNumber(content)

    def _arith_parse_double_quote(self) -> Node:
        """Parse "..." inside arithmetic - may contain expansions."""
        self._arith_advance()  # consume opening "
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != '"':
            c = self._arith_peek()
            if c == "\\" and not self._arith_at_end():
                self._arith_advance()  # skip backslash
                self._arith_advance()  # skip escaped char
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume('"'):
            raise ParseError("Unterminated double quote in arithmetic", pos=self._arith_pos)
        return ArithNumber(content)

    def _arith_parse_backtick(self) -> Node:
        """Parse `...` command substitution inside arithmetic."""
        self._arith_advance()  # consume opening `
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != "`":
            c = self._arith_peek()
            if c == "\\" and not self._arith_at_end():
                self._arith_advance()  # skip backslash
                self._arith_advance()  # skip escaped char
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume("`"):
            raise ParseError("Unterminated backtick in arithmetic", pos=self._arith_pos)
        # Parse the command inside
        sub_parser = Parser(content, extglob=self._extglob)
        cmd = sub_parser.parse_list()
        return CommandSubstitution(cmd)

    def _arith_parse_number_or_var(self) -> Node:
        """Parse a number or variable name."""
        self._arith_skip_ws()
        chars = []
        c = self._arith_peek()

        # Check for number (starts with digit or base#)
        if c.isdigit():
            # Could be decimal, hex (0x), octal (0), or base#n
            while not self._arith_at_end():
                ch = self._arith_peek()
                if ch.isalnum() or (ch == "#" or ch == "_"):
                    chars.append(self._arith_advance())
                else:
                    break
            prefix = "".join(chars)
            # Check if followed by $ expansion (e.g., 0x$var)
            if not self._arith_at_end() and self._arith_peek() == "$":
                expansion = self._arith_parse_expansion()
                return ArithConcat([ArithNumber(prefix), expansion])
            return ArithNumber(prefix)

        # Variable name (starts with letter or _)
        if c.isalpha() or c == "_":
            while not self._arith_at_end():
                ch = self._arith_peek()
                if ch.isalnum() or ch == "_":
                    chars.append(self._arith_advance())
                else:
                    break
            return ArithVar("".join(chars))

        raise ParseError(
            "Unexpected character '" + c + "' in arithmetic expression", pos=self._arith_pos
        )

    def _parse_deprecated_arithmetic(self) -> tuple[Node | None, str]:
        """Parse a deprecated $[expr] arithmetic expansion.

        Returns (node, text) where node is ArithDeprecated and text is raw text.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos

        # Check for $[
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != "[":
            return None, ""

        self.advance()  # consume $
        self.advance()  # consume [

        # Find matching ] using unified matched pair parsing
        self._lexer.pos = self.pos  # sync lexer to parser
        content = self._lexer._parse_matched_pair("[", "]", MatchedPairFlags.ARITH)
        self.pos = self._lexer.pos  # sync parser from lexer

        text = _substring(self.source, start, self.pos)
        return ArithDeprecated(content), text

    def _parse_param_expansion(self, in_dquote: bool = False) -> tuple[Node | None, str]:
        """Parse a parameter expansion starting at $. Delegates to Lexer."""
        self._sync_lexer()
        result = self._lexer._read_param_expansion(in_dquote)
        self._sync_parser()
        return result

    def parse_redirect(self) -> Redirect | HereDoc | None:
        """Parse a redirection operator and target."""
        self.skip_whitespace()
        if self.at_end():
            return None

        start = self.pos
        fd: int = -1  # -1 = no fd specified
        varfd = ""  # Variable fd like {fd}, "" = none

        # Check for variable fd {varname} or {varname[subscript]} before redirect
        if self.peek() == "{":
            saved = self.pos
            self.advance()  # consume {
            varname_chars = []
            in_bracket = False
            while not self.at_end() and not _is_redirect_char(self.peek()):
                ch = self.peek()
                if ch == "}" and not in_bracket:
                    break
                elif ch == "[":
                    in_bracket = True
                    varname_chars.append(self.advance())
                elif ch == "]":
                    in_bracket = False
                    varname_chars.append(self.advance())
                elif ch.isalnum() or ch == "_":
                    varname_chars.append(self.advance())
                elif in_bracket and not _is_metachar(ch):
                    varname_chars.append(self.advance())
                else:
                    break
            varname = "".join(varname_chars)
            is_valid_varfd = False
            if varname:
                if varname[0].isalpha() or varname[0] == "_":
                    if "[" in varname or "]" in varname:
                        left = varname.find("[")
                        right = varname.rfind("]")
                        if left != -1 and right == len(varname) - 1 and right > left + 1:
                            base = varname[:left]
                            if base and (base[0].isalpha() or base[0] == "_"):
                                is_valid_varfd = True
                                for c in base[1:]:
                                    if not (c.isalnum() or c == "_"):
                                        is_valid_varfd = False
                                        break
                    else:
                        is_valid_varfd = True
                        for c in varname[1:]:
                            if not (c.isalnum() or c == "_"):
                                is_valid_varfd = False
                                break
            if not self.at_end() and self.peek() == "}" and is_valid_varfd:
                self.advance()  # consume }
                varfd = varname
            else:
                # Not a valid variable fd, restore
                self.pos = saved

        # Check for optional fd number before redirect (if no varfd)
        if varfd == "" and self.peek() and self.peek().isdigit():
            fd_chars = []
            while not self.at_end() and self.peek().isdigit():
                fd_chars.append(self.advance())
            fd = int("".join(fd_chars))

        ch = self.peek()

        # Handle &> and &>> (redirect both stdout and stderr)
        # Note: &> does NOT take a preceding fd number. If we consumed digits,
        # they should be a separate word, not an fd. E.g., "2&>1" is command "2"
        # with redirect "&> 1", not fd 2 redirected.
        if ch == "&" and self.pos + 1 < self.length and self.source[self.pos + 1] == ">":
            if fd != -1 or varfd != "":
                # We consumed digits/varfd that should be a word, not an fd
                # Restore position and let parse_word handle them
                self.pos = start
                return None
            self.advance()  # consume &
            self.advance()  # consume >
            if not self.at_end() and self.peek() == ">":
                self.advance()  # consume second > for &>>
                op = "&>>"
            else:
                op = "&>"
            self.skip_whitespace()
            target = self.parse_word()
            if target is None:
                raise ParseError("Expected target for redirect " + op, pos=self.pos)
            return Redirect(op, target)

        if ch is None or not _is_redirect_char(ch):
            # Not a redirect, restore position
            self.pos = start
            return None

        # Check for process substitution <(...) or >(...) - not a redirect
        # Only treat as redirect if there's a space before ( or an fd number
        if fd == -1 and self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
            # This is a process substitution, not a redirect
            self.pos = start
            return None

        # Parse the redirect operator
        op = self.advance()

        # Check for multi-char operators
        strip_tabs = False
        if not self.at_end():
            next_ch = self.peek()
            if op == ">" and next_ch == ">":
                self.advance()
                op = ">>"
            elif op == "<" and next_ch == "<":
                self.advance()
                if not self.at_end() and self.peek() == "<":
                    self.advance()
                    op = "<<<"
                elif not self.at_end() and self.peek() == "-":
                    self.advance()
                    op = "<<"
                    strip_tabs = True
                else:
                    op = "<<"
            # Handle <> (read-write)
            elif op == "<" and next_ch == ">":
                self.advance()
                op = "<>"
            # Handle >| (noclobber override)
            elif op == ">" and next_ch == "|":
                self.advance()
                op = ">|"
            # Only consume >& or <& as operators if NOT followed by a digit or -
            # (>&2 should be > with target &2, not >& with target 2)
            # (>&- should be > with target &-, not >& with target -)
            elif fd == -1 and varfd == "" and op == ">" and next_ch == "&":
                # Peek ahead to see if there's a digit or - after &
                if self.pos + 1 >= self.length or not _is_digit_or_dash(self.source[self.pos + 1]):
                    self.advance()
                    op = ">&"
            elif fd == -1 and varfd == "" and op == "<" and next_ch == "&":
                if self.pos + 1 >= self.length or not _is_digit_or_dash(self.source[self.pos + 1]):
                    self.advance()
                    op = "<&"

        # Handle here document
        if op == "<<":
            return self._parse_heredoc(fd, strip_tabs)

        # Combine fd or varfd with operator if present
        if varfd != "":
            op = "{" + varfd + "}" + op
        elif fd != -1:
            op = str(fd) + op

        # Handle fd duplication targets like &1, &2, &-, &10-, &$var
        # NOTE: No whitespace allowed between operator and & (e.g., <&- is valid, < &- is not)
        if not self.at_end() and self.peek() == "&":
            self.advance()  # consume &
            # Skip whitespace after & to check what follows
            self.skip_whitespace()
            # Check for "& -" followed by non-metachar (e.g., "3>& -5" -> 3>&- + word "5")
            if not self.at_end() and self.peek() == "-":
                if self.pos + 1 < self.length and not _is_metachar(self.source[self.pos + 1]):
                    # Consume just the - as close target, leave rest for next word
                    self.advance()
                    target = Word("&-")
                else:
                    # Set target to None to fall through to normal parsing
                    target = None
            else:
                target = None
            # If we didn't handle close syntax above, continue with normal parsing
            if target is None:
                if not self.at_end() and (self.peek().isdigit() or self.peek() == "-"):
                    word_start = self.pos
                    fd_chars = []
                    while not self.at_end() and self.peek().isdigit():
                        fd_chars.append(self.advance())
                    if fd_chars:
                        fd_target = "".join(fd_chars)
                    else:
                        fd_target = ""
                    # Handle just - for close, or N- for move syntax
                    if not self.at_end() and self.peek() == "-":
                        fd_target += self.advance()  # consume the trailing -
                    # If more word characters follow, treat the whole target as a word (e.g., <&0=)
                    # BUT: bare "-" (close syntax) is always complete - trailing chars are separate words
                    if fd_target != "-" and not self.at_end() and not _is_metachar(self.peek()):
                        self.pos = word_start
                        inner_word = self.parse_word()
                        if inner_word is not None:
                            target = Word("&" + inner_word.value)
                            target.parts = inner_word.parts
                        else:
                            raise ParseError("Expected target for redirect " + op, pos=self.pos)
                    else:
                        target = Word("&" + fd_target)
                else:
                    # Could be &$var or &word - parse word and prepend &
                    inner_word = self.parse_word()
                    if inner_word is not None:
                        target = Word("&" + inner_word.value)
                        target.parts = inner_word.parts
                    else:
                        raise ParseError("Expected target for redirect " + op, pos=self.pos)
        else:
            self.skip_whitespace()
            # Handle >& - or <& - where space precedes the close syntax
            # If op is >& or <& and next char is -, check for trailing word chars
            # that should become a separate word (e.g., ">& -b" -> >&- + word "b")
            if op in (">&", "<&") and not self.at_end() and self.peek() == "-":
                if self.pos + 1 < self.length and not _is_metachar(self.source[self.pos + 1]):
                    # Consume just the - as close target, leave rest for next word
                    self.advance()
                    target = Word("&-")
                else:
                    target = self.parse_word()
            else:
                target = self.parse_word()

        if target is None:
            raise ParseError("Expected target for redirect " + op, pos=self.pos)

        return Redirect(op, target)

    def _parse_heredoc_delimiter(self) -> tuple[str, bool]:
        """Parse heredoc delimiter, handling quoting (can be mixed like 'EOF'"2").

        Returns (delimiter, quoted) where delimiter is the raw delimiter string
        and quoted is True if any part was quoted (suppresses expansion).
        """
        self.skip_whitespace()
        quoted = False
        delimiter_chars: list[str] = []

        while True:
            while not self.at_end() and not _is_metachar(self.peek()):
                ch = self.peek()
                if ch == '"':
                    quoted = True
                    self.advance()
                    while not self.at_end() and self.peek() != '"':
                        delimiter_chars.append(self.advance())
                    if not self.at_end():
                        self.advance()
                elif ch == "'":
                    quoted = True
                    self.advance()
                    while not self.at_end() and self.peek() != "'":
                        c = self.advance()
                        if c == "\n":
                            self._saw_newline_in_single_quote = True
                        delimiter_chars.append(c)
                    if not self.at_end():
                        self.advance()
                elif ch == "\\":
                    self.advance()
                    if not self.at_end():
                        next_ch = self.peek()
                        if next_ch == "\n":
                            # Backslash-newline: continue delimiter on next line
                            self.advance()  # skip the newline
                        else:
                            # Regular escape - quotes the next char
                            quoted = True
                            delimiter_chars.append(self.advance())
                elif ch == "$" and self.pos + 1 < self.length and self.source[self.pos + 1] == "'":
                    # ANSI-C quoting $'...' - skip $ and quotes, expand escapes
                    quoted = True
                    self.advance()  # skip $
                    self.advance()  # skip opening '
                    while not self.at_end() and self.peek() != "'":
                        c = self.peek()
                        if c == "\\" and self.pos + 1 < self.length:
                            self.advance()  # skip backslash
                            esc = self.peek()
                            # Handle ANSI-C escapes using the lookup table
                            esc_val = _get_ansi_escape(esc)
                            if esc_val >= 0:
                                delimiter_chars.append(chr(esc_val))
                                self.advance()
                            elif esc == "'":
                                delimiter_chars.append(self.advance())
                            else:
                                # Other escapes - just use the escaped char
                                delimiter_chars.append(self.advance())
                        else:
                            delimiter_chars.append(self.advance())
                    if not self.at_end():
                        self.advance()  # skip closing '
                elif _is_expansion_start(self.source, self.pos, "$("):
                    # Command substitution embedded in delimiter
                    delimiter_chars.append(self.advance())  # $
                    delimiter_chars.append(self.advance())  # (
                    depth = 1
                    while not self.at_end() and depth > 0:
                        c = self.peek()
                        if c == "(":
                            depth += 1
                        elif c == ")":
                            depth -= 1
                        delimiter_chars.append(self.advance())
                elif ch == "$" and self.pos + 1 < self.length and self.source[self.pos + 1] == "{":
                    # Check if this is $${ where $$ is PID and { ends delimiter
                    dollar_count = 0
                    j = self.pos - 1
                    while j >= 0 and self.source[j] == "$":
                        dollar_count += 1
                        j -= 1
                    # If preceded by backslash, first dollar was escaped
                    if j >= 0 and self.source[j] == "\\":
                        dollar_count -= 1
                    if dollar_count % 2 == 1:
                        # Odd number of $ before: this $ pairs with previous to form $$
                        # Don't consume the {, let it end the delimiter
                        delimiter_chars.append(self.advance())  # $
                    else:
                        # Parameter expansion embedded in delimiter
                        delimiter_chars.append(self.advance())  # $
                        delimiter_chars.append(self.advance())  # {
                        depth = 0
                        while not self.at_end():
                            c = self.peek()
                            if c == "{":
                                depth += 1
                            elif c == "}":
                                # Consume the closing brace
                                delimiter_chars.append(self.advance())
                                if depth == 0:
                                    # Outer expansion closed
                                    break
                                depth -= 1
                                # After closing inner brace, check if next is metachar
                                # If so, the expansion ends here (bash behavior)
                                if depth == 0 and not self.at_end() and _is_metachar(self.peek()):
                                    break
                                continue
                            delimiter_chars.append(self.advance())
                elif ch == "$" and self.pos + 1 < self.length and self.source[self.pos + 1] == "[":
                    # Check if this is $$[ where $$ is PID and [ ends delimiter
                    dollar_count = 0
                    j = self.pos - 1
                    while j >= 0 and self.source[j] == "$":
                        dollar_count += 1
                        j -= 1
                    # If preceded by backslash, first dollar was escaped
                    if j >= 0 and self.source[j] == "\\":
                        dollar_count -= 1
                    if dollar_count % 2 == 1:
                        # Odd number of $ before: this $ pairs with previous to form $$
                        # Don't consume the [, let it end the delimiter
                        delimiter_chars.append(self.advance())  # $
                    else:
                        # Arithmetic expansion $[...] embedded in delimiter
                        delimiter_chars.append(self.advance())  # $
                        delimiter_chars.append(self.advance())  # [
                        depth = 1
                        while not self.at_end() and depth > 0:
                            c = self.peek()
                            if c == "[":
                                depth += 1
                            elif c == "]":
                                depth -= 1
                            delimiter_chars.append(self.advance())
                elif ch == "`":
                    # Backtick command substitution embedded in delimiter
                    # Note: In bash, backtick closes command sub even with unclosed quotes inside
                    delimiter_chars.append(self.advance())  # `
                    while not self.at_end() and self.peek() != "`":
                        c = self.peek()
                        if c == "'":
                            # Single-quoted string inside backtick - skip to closing quote or `
                            delimiter_chars.append(self.advance())  # '
                            while not self.at_end() and self.peek() != "'" and self.peek() != "`":
                                delimiter_chars.append(self.advance())
                            if not self.at_end() and self.peek() == "'":
                                delimiter_chars.append(self.advance())  # closing '
                        elif c == '"':
                            # Double-quoted string inside backtick - skip to closing quote or `
                            delimiter_chars.append(self.advance())  # "
                            while not self.at_end() and self.peek() != '"' and self.peek() != "`":
                                if self.peek() == "\\" and self.pos + 1 < self.length:
                                    delimiter_chars.append(self.advance())  # backslash
                                delimiter_chars.append(self.advance())
                            if not self.at_end() and self.peek() == '"':
                                delimiter_chars.append(self.advance())  # closing "
                        elif c == "\\" and self.pos + 1 < self.length:
                            delimiter_chars.append(self.advance())  # backslash
                            delimiter_chars.append(self.advance())  # escaped char
                        else:
                            delimiter_chars.append(self.advance())
                    if not self.at_end():
                        delimiter_chars.append(self.advance())  # closing `
                else:
                    delimiter_chars.append(self.advance())

            # Check for process substitution syntax <( or >( which is part of delimiter
            if (
                not self.at_end()
                and self.peek() in "<>"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                # Process substitution embedded in delimiter
                delimiter_chars.append(self.advance())  # < or >
                delimiter_chars.append(self.advance())  # (
                depth = 1
                while not self.at_end() and depth > 0:
                    c = self.peek()
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                    delimiter_chars.append(self.advance())
                continue  # Try to collect more delimiter characters
            break

        return "".join(delimiter_chars), quoted

    def _read_heredoc_line(self, quoted: bool) -> tuple[str, int]:
        """Read a heredoc line, handling backslash-newline continuation for unquoted heredocs.

        Returns (line_content, line_end_pos) where line_content is the logical line
        (with continuations joined) and line_end_pos is the position after the final newline.
        """
        line_start = self.pos
        line_end = self.pos
        while line_end < self.length and self.source[line_end] != "\n":
            line_end += 1
        line = _substring(self.source, line_start, line_end)
        if not quoted:
            while line_end < self.length:
                trailing_bs = _count_trailing_backslashes(line)
                if trailing_bs % 2 == 0:
                    break  # Even backslashes - no continuation
                line = _substring(line, 0, len(line) - 1)  # Remove escaping backslash
                line_end += 1  # Skip newline
                next_line_start = line_end
                while line_end < self.length and self.source[line_end] != "\n":
                    line_end += 1
                line = line + _substring(self.source, next_line_start, line_end)
        return line, line_end

    def _line_matches_delimiter(
        self, line: str, delimiter: str, strip_tabs: bool
    ) -> tuple[bool, str]:
        """Check if line matches the heredoc delimiter.

        Returns (matches, check_line) where check_line is the line after tab stripping.
        """
        check_line = line.lstrip("\t") if strip_tabs else line
        normalized_check = _normalize_heredoc_delimiter(check_line)
        normalized_delim = _normalize_heredoc_delimiter(delimiter)
        return normalized_check == normalized_delim, check_line

    def _gather_heredoc_bodies(self) -> None:
        """Gather content for all pending heredocs after command line ends.

        Called after a newline is consumed. Reads content for each pending heredoc
        in order, advancing self.pos past all heredoc content.
        """
        for heredoc in self._pending_heredocs:
            content_lines: list[str] = []
            line_start = self.pos
            while self.pos < self.length:
                line_start = self.pos
                line, line_end = self._read_heredoc_line(heredoc.quoted)
                matches, check_line = self._line_matches_delimiter(
                    line, heredoc.delimiter, heredoc.strip_tabs
                )
                if matches:
                    self.pos = line_end + 1 if line_end < self.length else line_end
                    break
                # Check for delimiter followed by cmdsub/procsub closer
                normalized_check = _normalize_heredoc_delimiter(check_line)
                normalized_delim = _normalize_heredoc_delimiter(heredoc.delimiter)
                # In command substitution: line starts with delimiter - heredoc ends there
                # Remaining content (e.g., ")x" or "b)") is part of the command sub
                if self._eof_token == ")" and normalized_check.startswith(normalized_delim):
                    tabs_stripped = len(line) - len(check_line)
                    self.pos = line_start + tabs_stripped + len(heredoc.delimiter)
                    break
                # At EOF with line starting with delimiter - heredoc terminates (process sub case)
                if (
                    line_end >= self.length
                    and normalized_check.startswith(normalized_delim)
                    and self._in_process_sub
                ):
                    tabs_stripped = len(line) - len(check_line)
                    self.pos = line_start + tabs_stripped + len(heredoc.delimiter)
                    break
                # Add line to content
                if heredoc.strip_tabs:
                    line = line.lstrip("\t")
                if line_end < self.length:
                    content_lines.append(line + "\n")
                    self.pos = line_end + 1
                else:
                    # EOF - bash keeps trailing newline unless escaped by odd backslash
                    add_newline = True
                    if not heredoc.quoted and _count_trailing_backslashes(line) % 2 == 1:
                        add_newline = False
                    content_lines.append(line + ("\n" if add_newline else ""))
                    self.pos = self.length
            heredoc.content = "".join(content_lines)
        self._pending_heredocs = []

    def _parse_heredoc(self, fd: int, strip_tabs: bool) -> HereDoc:
        """Parse a here document <<DELIM ... DELIM.

        Parses the delimiter only. Content is gathered later by _gather_heredoc_bodies
        after the command line is complete.
        """
        start_pos = self.pos
        self._set_state(ParserStateFlags.PST_HEREDOC)
        delimiter, quoted = self._parse_heredoc_delimiter()
        # Check if we've already registered this heredoc (can happen due to re-tokenization)
        for existing in self._pending_heredocs:
            if existing._start_pos == start_pos and existing.delimiter == delimiter:
                self._clear_state(ParserStateFlags.PST_HEREDOC)
                return existing
        # Create stub HereDoc with empty content - will be filled in later
        heredoc = HereDoc(delimiter, "", strip_tabs, quoted, fd, False)
        heredoc._start_pos = start_pos  # Track position for dedup
        self._pending_heredocs.append(heredoc)
        self._clear_state(ParserStateFlags.PST_HEREDOC)
        return heredoc

    def parse_command(self) -> Command | None:
        """Parse a simple command (sequence of words and redirections)."""
        words = []
        redirects = []

        while True:
            self.skip_whitespace()
            # Use token-based terminator detection
            # This enables the EOF token mechanism to work at the command level
            if self._lex_is_command_terminator():
                break
            # } and ]] are only terminators at command position (closing brace group
            # or conditional). In argument position, they're regular words.
            # Check as reserved words since lexer returns them as WORD tokens.
            # Use len() == 0 instead of 'not words' for JS transpiler compatibility
            if len(words) == 0:
                reserved = self._lex_peek_reserved_word()
                if reserved == "}" or reserved == "]]":
                    break

            # Try to parse a redirect first
            redirect = self.parse_redirect()
            if redirect is not None:
                redirects.append(redirect)
                continue

            # Otherwise parse a word
            # Allow array assignments like a[1 + 2]= in prefix position (before first non-assignment)
            # Check if all previous words were assignments (contain = not inside quotes)
            # and no redirects have been seen (redirects break assignment context)
            all_assignments = True
            for w in words:
                if not self._is_assignment_word(w):
                    all_assignments = False
                    break
            # Check if first word is an assignment builtin (bash's PST_ASSIGNOK)
            # This allows array literal assignments after builtins like declare, local, export
            # but does NOT enable bracket tracking (which is only for true command start)
            in_assign_builtin = len(words) > 0 and words[0].value in ASSIGNMENT_BUILTINS
            word = self.parse_word(
                at_command_start=not words or (all_assignments and len(redirects) == 0),
                in_array_literal=False,
                in_assign_builtin=in_assign_builtin,
            )
            if word is None:
                break
            words.append(word)

        if not words and not redirects:
            return None

        return Command(words, redirects)

    def parse_subshell(self) -> Subshell | None:
        """Parse a subshell ( list )."""
        self.skip_whitespace()
        if self.at_end() or self.peek() != "(":
            return None

        self.advance()  # consume (
        self._set_state(ParserStateFlags.PST_SUBSHELL)

        body = self.parse_list()
        if body is None:
            self._clear_state(ParserStateFlags.PST_SUBSHELL)
            raise ParseError("Expected command in subshell", pos=self.pos)

        self.skip_whitespace()
        if self.at_end() or self.peek() != ")":
            self._clear_state(ParserStateFlags.PST_SUBSHELL)
            raise ParseError("Expected ) to close subshell", pos=self.pos)
        self.advance()  # consume )
        self._clear_state(ParserStateFlags.PST_SUBSHELL)
        return Subshell(body, self._collect_redirects())

    def parse_arithmetic_command(self) -> ArithmeticCommand | None:
        """Parse an arithmetic command (( expression )) with parsed internals.

        Returns None if this is not an arithmetic command (e.g., nested subshells
        like '( ( x ) )' that close with ') )' instead of '))').
        """
        self.skip_whitespace()

        # Check for ((
        if (
            self.at_end()
            or self.peek() != "("
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "("
        ):
            return None

        saved_pos = self.pos
        self.advance()  # consume first (
        self.advance()  # consume second (

        # Find matching )) - track nested parens
        # Must be )) with no space between - ') )' is nested subshells
        content_start = self.pos
        depth = 1

        while not self.at_end() and depth > 0:
            c = self.peek()
            # Skip single-quoted strings (parens inside don't count)
            if c == "'":
                self.advance()
                while not self.at_end() and self.peek() != "'":
                    self.advance()
                if not self.at_end():
                    self.advance()  # consume closing '
            # Skip double-quoted strings (parens inside don't count)
            elif c == '"':
                self.advance()
                while not self.at_end():
                    if self.peek() == "\\" and self.pos + 1 < self.length:
                        self.advance()
                        self.advance()
                    elif self.peek() == '"':
                        self.advance()
                        break
                    else:
                        self.advance()
            # Handle backslash escapes outside quotes
            elif c == "\\" and self.pos + 1 < self.length:
                self.advance()
                self.advance()
            elif c == "(":
                depth += 1
                self.advance()
            elif c == ")":
                # Check for )) (must be consecutive, no space)
                if depth == 1 and self.pos + 1 < self.length and self.source[self.pos + 1] == ")":
                    # Found the closing ))
                    break
                depth -= 1
                if depth == 0:
                    # Closed with ) but next isn't ) - this is nested subshells, not arithmetic
                    self.pos = saved_pos
                    return None
                self.advance()
            else:
                self.advance()

        if self.at_end():
            # Hit EOF without finding )) - unclosed arithmetic command
            raise MatchedPairError("unexpected EOF looking for `))'", pos=saved_pos)
        if depth != 1:
            # Didn't find )) - might be nested subshells, not arithmetic command
            self.pos = saved_pos
            return None

        content = _substring(self.source, content_start, self.pos)
        # Strip backslash-newline line continuations
        content = content.replace("\\\n", "")
        self.advance()  # consume first )
        self.advance()  # consume second )

        # Parse the arithmetic expression
        expr = self._parse_arith_expr(content)
        return ArithmeticCommand(expr, self._collect_redirects(), raw_content=content)

    # Unary operators for [[ ]] conditionals
    COND_UNARY_OPS = {
        "-a",
        "-b",
        "-c",
        "-d",
        "-e",
        "-f",
        "-g",
        "-h",
        "-k",
        "-p",
        "-r",
        "-s",
        "-t",
        "-u",
        "-w",
        "-x",
        "-G",
        "-L",
        "-N",
        "-O",
        "-S",
        "-z",
        "-n",
        "-o",
        "-v",
        "-R",
    }
    # Binary operators for [[ ]] conditionals
    COND_BINARY_OPS = {
        "==",
        "!=",
        "=~",
        "=",
        "<",
        ">",
        "-eq",
        "-ne",
        "-lt",
        "-le",
        "-gt",
        "-ge",
        "-nt",
        "-ot",
        "-ef",
    }

    def parse_conditional_expr(self) -> ConditionalExpr | None:
        """Parse a conditional expression [[ expression ]]."""
        self.skip_whitespace()

        # Check for [[
        if (
            self.at_end()
            or self.peek() != "["
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "["
        ):
            return None
        next_pos = self.pos + 2
        if next_pos < self.length and not (
            _is_whitespace(self.source[next_pos])
            or (
                self.source[next_pos] == "\\"
                and next_pos + 1 < self.length
                and self.source[next_pos + 1] == "\n"
            )
        ):
            return None

        self.advance()  # consume first [
        self.advance()  # consume second [
        self._set_state(ParserStateFlags.PST_CONDEXPR)
        self._word_context = WORD_CTX_COND

        # Parse the conditional expression body
        body = self._parse_cond_or()

        # Skip whitespace before ]]
        while not self.at_end() and _is_whitespace_no_newline(self.peek()):
            self.advance()

        # Expect ]]
        if (
            self.at_end()
            or self.peek() != "]"
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "]"
        ):
            self._clear_state(ParserStateFlags.PST_CONDEXPR)
            self._word_context = WORD_CTX_NORMAL
            raise ParseError("Expected ]] to close conditional expression", pos=self.pos)

        self.advance()  # consume first ]
        self.advance()  # consume second ]
        self._clear_state(ParserStateFlags.PST_CONDEXPR)
        self._word_context = WORD_CTX_NORMAL
        return ConditionalExpr(body, self._collect_redirects())

    def _cond_skip_whitespace(self) -> None:
        """Skip whitespace inside [[ ]], including backslash-newline continuation."""
        while not self.at_end():
            if _is_whitespace_no_newline(self.peek()):
                self.advance()
            elif (
                self.peek() == "\\"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "\n"
            ):
                self.advance()  # consume backslash
                self.advance()  # consume newline
            elif self.peek() == "\n":
                # Bare newline is also allowed inside [[ ]]
                self.advance()
            else:
                break

    def _cond_at_end(self) -> bool:
        """Check if we're at ]] (end of conditional)."""
        return self.at_end() or (
            self.peek() == "]" and self.pos + 1 < self.length and self.source[self.pos + 1] == "]"
        )

    def _parse_cond_or(self) -> Node:
        """Parse: or_expr = and_expr (|| or_expr)?  (right-associative)"""
        self._cond_skip_whitespace()
        left = self._parse_cond_and()
        self._cond_skip_whitespace()
        if (
            not self._cond_at_end()
            and self.peek() == "|"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "|"
        ):
            self.advance()  # consume first |
            self.advance()  # consume second |
            right = self._parse_cond_or()  # recursive for right-associativity
            return CondOr(left, right)
        return left

    def _parse_cond_and(self) -> Node:
        """Parse: and_expr = term (&& and_expr)?  (right-associative)"""
        self._cond_skip_whitespace()
        left = self._parse_cond_term()
        self._cond_skip_whitespace()
        if (
            not self._cond_at_end()
            and self.peek() == "&"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "&"
        ):
            self.advance()  # consume first &
            self.advance()  # consume second &
            right = self._parse_cond_and()  # recursive for right-associativity
            return CondAnd(left, right)
        return left

    def _parse_cond_term(self) -> Node:
        """Parse: term = '!' term | '(' or_expr ')' | unary_test | binary_test | bare_word"""
        self._cond_skip_whitespace()

        if self._cond_at_end():
            raise ParseError("Unexpected end of conditional expression", pos=self.pos)

        # Negation: ! term
        if self.peek() == "!":
            # Check it's not != operator (need whitespace after !)
            if self.pos + 1 < self.length and not _is_whitespace_no_newline(
                self.source[self.pos + 1]
            ):
                pass  # not negation, fall through to word parsing
            else:
                self.advance()  # consume !
                operand = self._parse_cond_term()
                return CondNot(operand)

        # Parenthesized group: ( or_expr )
        if self.peek() == "(":
            self.advance()  # consume (
            inner = self._parse_cond_or()
            self._cond_skip_whitespace()
            if self.at_end() or self.peek() != ")":
                raise ParseError("Expected ) in conditional expression", pos=self.pos)
            self.advance()  # consume )
            return CondParen(inner)

        # Parse first word
        word1 = self._parse_cond_word()
        if word1 is None:
            raise ParseError("Expected word in conditional expression", pos=self.pos)

        self._cond_skip_whitespace()

        # Check if word1 is a unary operator
        if word1.value in COND_UNARY_OPS:
            # Unary test: -f file
            unary_operand = self._parse_cond_word()
            if unary_operand is None:
                raise ParseError("Expected operand after " + word1.value, pos=self.pos)
            return UnaryTest(word1.value, unary_operand)

        # Check if next token is a binary operator
        if not self._cond_at_end() and (
            self.peek() != "&" and self.peek() != "|" and self.peek() != ")"
        ):
            # Handle < and > as binary operators (they terminate words)
            # But not <( or >( which are process substitution
            if _is_redirect_char(self.peek()) and not (
                self.pos + 1 < self.length and self.source[self.pos + 1] == "("
            ):
                op = self.advance()
                self._cond_skip_whitespace()
                word2 = self._parse_cond_word()
                if word2 is None:
                    raise ParseError("Expected operand after " + op, pos=self.pos)
                return BinaryTest(op, word1, word2)
            # Peek at next word to see if it's a binary operator
            saved_pos = self.pos
            op_word = self._parse_cond_word()
            if op_word and op_word.value in COND_BINARY_OPS:
                # Binary test: word1 op word2
                self._cond_skip_whitespace()
                # For =~ operator, the RHS is a regex where ( ) are grouping, not conditional grouping
                if op_word.value == "=~":
                    word2 = self._parse_cond_regex_word()
                else:
                    word2 = self._parse_cond_word()
                if word2 is None:
                    raise ParseError("Expected operand after " + op_word.value, pos=self.pos)
                return BinaryTest(op_word.value, word1, word2)
            else:
                # Not a binary op, restore position
                self.pos = saved_pos

        # Bare word: implicit -n test
        return UnaryTest("-n", word1)

    def _parse_cond_word(self) -> Word | None:
        """Parse a word inside [[ ]], handling expansions but stopping at conditional operators."""
        self._cond_skip_whitespace()
        if self._cond_at_end():
            return None
        # Check for special tokens that aren't words
        c = self.peek()
        if _is_paren(c):
            return None
        if c == "&" and self.pos + 1 < self.length and self.source[self.pos + 1] == "&":
            return None
        if c == "|" and self.pos + 1 < self.length and self.source[self.pos + 1] == "|":
            return None
        return self._parse_word_internal(WORD_CTX_COND)

    def _parse_cond_regex_word(self) -> Word | None:
        """Parse a regex pattern word in [[ ]], where ( ) are regex grouping, not conditional grouping."""
        self._cond_skip_whitespace()
        if self._cond_at_end():
            return None
        self._set_state(ParserStateFlags.PST_REGEXP)
        result = self._parse_word_internal(WORD_CTX_REGEX)
        self._clear_state(ParserStateFlags.PST_REGEXP)
        # Restore word context to COND after parsing regex
        self._word_context = WORD_CTX_COND
        return result

    def parse_brace_group(self) -> BraceGroup | None:
        """Parse a brace group { list }."""
        self.skip_whitespace()
        # Lexer handles { vs {abc distinction: only returns reserved word for standalone {
        if not self._lex_consume_word("{"):
            return None
        self.skip_whitespace_and_newlines()

        body = self.parse_list()
        if body is None:
            raise ParseError("Expected command in brace group", pos=self._lex_peek_token().pos)

        self.skip_whitespace()
        if not self._lex_consume_word("}"):
            raise ParseError("Expected } to close brace group", pos=self._lex_peek_token().pos)
        return BraceGroup(body, self._collect_redirects())

    def parse_if(self) -> If | None:
        """Parse an if statement: if list; then list [elif list; then list]* [else list] fi."""
        self.skip_whitespace()
        if not self._lex_consume_word("if"):
            return None

        # Parse condition (a list that ends at 'then')
        condition = self.parse_list_until({"then"})
        if condition is None:
            raise ParseError("Expected condition after 'if'", pos=self._lex_peek_token().pos)

        # Expect 'then'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("then"):
            raise ParseError("Expected 'then' after if condition", pos=self._lex_peek_token().pos)

        # Parse then body (ends at elif, else, or fi)
        then_body = self.parse_list_until({"elif", "else", "fi"})
        if then_body is None:
            raise ParseError("Expected commands after 'then'", pos=self._lex_peek_token().pos)

        # Check what comes next: elif, else, or fi
        self.skip_whitespace_and_newlines()

        else_body = None
        if self._lex_is_at_reserved_word("elif"):
            # elif is syntactic sugar for else if ... fi
            self._lex_consume_word("elif")
            # Parse the rest as a nested if (but we've already consumed 'elif')
            # We need to parse: condition; then body [elif|else|fi]
            elif_condition = self.parse_list_until({"then"})
            if elif_condition is None:
                raise ParseError("Expected condition after 'elif'", pos=self._lex_peek_token().pos)

            self.skip_whitespace_and_newlines()
            if not self._lex_consume_word("then"):
                raise ParseError(
                    "Expected 'then' after elif condition", pos=self._lex_peek_token().pos
                )

            elif_then_body = self.parse_list_until({"elif", "else", "fi"})
            if elif_then_body is None:
                raise ParseError("Expected commands after 'then'", pos=self._lex_peek_token().pos)

            # Recursively handle more elif/else/fi
            self.skip_whitespace_and_newlines()

            inner_else = None
            if self._lex_is_at_reserved_word("elif"):
                # More elif - recurse by creating a fake "if" and parsing
                # Actually, let's just recursively call a helper
                inner_else = self._parse_elif_chain()
            elif self._lex_is_at_reserved_word("else"):
                self._lex_consume_word("else")
                inner_else = self.parse_list_until({"fi"})
                if inner_else is None:
                    raise ParseError(
                        "Expected commands after 'else'", pos=self._lex_peek_token().pos
                    )

            else_body = If(elif_condition, elif_then_body, inner_else)

        elif self._lex_is_at_reserved_word("else"):
            self._lex_consume_word("else")
            else_body = self.parse_list_until({"fi"})
            if else_body is None:
                raise ParseError("Expected commands after 'else'", pos=self._lex_peek_token().pos)

        # Expect 'fi'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("fi"):
            raise ParseError("Expected 'fi' to close if statement", pos=self._lex_peek_token().pos)
        return If(condition, then_body, else_body, self._collect_redirects())

    def _parse_elif_chain(self) -> If:
        """Parse elif chain (after seeing 'elif' keyword)."""
        self._lex_consume_word("elif")

        condition = self.parse_list_until({"then"})
        if condition is None:
            raise ParseError("Expected condition after 'elif'", pos=self._lex_peek_token().pos)

        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("then"):
            raise ParseError("Expected 'then' after elif condition", pos=self._lex_peek_token().pos)

        then_body = self.parse_list_until({"elif", "else", "fi"})
        if then_body is None:
            raise ParseError("Expected commands after 'then'", pos=self._lex_peek_token().pos)

        self.skip_whitespace_and_newlines()

        else_body = None
        if self._lex_is_at_reserved_word("elif"):
            else_body = self._parse_elif_chain()
        elif self._lex_is_at_reserved_word("else"):
            self._lex_consume_word("else")
            else_body = self.parse_list_until({"fi"})
            if else_body is None:
                raise ParseError("Expected commands after 'else'", pos=self._lex_peek_token().pos)

        return If(condition, then_body, else_body)

    def parse_while(self) -> While | None:
        """Parse a while loop: while list; do list; done."""
        self.skip_whitespace()
        if not self._lex_consume_word("while"):
            return None

        # Parse condition (ends at 'do')
        condition = self.parse_list_until({"do"})
        if condition is None:
            raise ParseError("Expected condition after 'while'", pos=self._lex_peek_token().pos)

        # Expect 'do'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("do"):
            raise ParseError("Expected 'do' after while condition", pos=self._lex_peek_token().pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self._lex_peek_token().pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("done"):
            raise ParseError("Expected 'done' to close while loop", pos=self._lex_peek_token().pos)
        return While(condition, body, self._collect_redirects())

    def parse_until(self) -> Until | None:
        """Parse an until loop: until list; do list; done."""
        self.skip_whitespace()
        if not self._lex_consume_word("until"):
            return None

        # Parse condition (ends at 'do')
        condition = self.parse_list_until({"do"})
        if condition is None:
            raise ParseError("Expected condition after 'until'", pos=self._lex_peek_token().pos)

        # Expect 'do'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("do"):
            raise ParseError("Expected 'do' after until condition", pos=self._lex_peek_token().pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self._lex_peek_token().pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("done"):
            raise ParseError("Expected 'done' to close until loop", pos=self._lex_peek_token().pos)
        return Until(condition, body, self._collect_redirects())

    def parse_for(self) -> For | ForArith | None:
        """Parse a for loop: for name [in words]; do list; done or C-style for ((;;))."""
        self.skip_whitespace()
        if not self._lex_consume_word("for"):
            return None
        self.skip_whitespace()

        # Check for C-style for loop: for ((init; cond; incr))
        if self.peek() == "(" and self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
            return self._parse_for_arith()

        # Parse variable name (bash allows reserved words and command substitutions as variable names)
        if self.peek() == "$":
            # Command substitution as variable name: for $(echo i) in ...
            var_word = self.parse_word()
            if var_word is None:
                raise ParseError(
                    "Expected variable name after 'for'", pos=self._lex_peek_token().pos
                )
            var_name = var_word.value
        else:
            var_name = self.peek_word()
            if var_name is None:
                raise ParseError(
                    "Expected variable name after 'for'", pos=self._lex_peek_token().pos
                )
            self.consume_word(var_name)

        self.skip_whitespace()

        # Handle optional semicolon or newline before 'in' or 'do'
        if self.peek() == ";":
            self.advance()
        self.skip_whitespace_and_newlines()

        # Check for optional 'in' clause
        words = None
        if self._lex_is_at_reserved_word("in"):
            self._lex_consume_word("in")
            self.skip_whitespace()  # Only skip whitespace, not newlines

            # Check for immediate delimiter (;, newline) after 'in'
            saw_delimiter = _is_semicolon_or_newline(self.peek())
            if self.peek() == ";":
                self.advance()
            self.skip_whitespace_and_newlines()

            # Parse words until semicolon or newline (not 'do' directly)
            words = []
            while True:
                self.skip_whitespace()
                # Check for end of word list
                if self.at_end():
                    break
                if _is_semicolon_or_newline(self.peek()):
                    saw_delimiter = True
                    if self.peek() == ";":
                        self.advance()  # consume semicolon
                    break
                # 'do' only terminates if preceded by delimiter
                if self._lex_is_at_reserved_word("do"):
                    if saw_delimiter:
                        break
                    # 'for x in do' or 'for x in a b c do' is invalid
                    raise ParseError(
                        "Expected ';' or newline before 'do'", pos=self._lex_peek_token().pos
                    )

                word = self.parse_word()
                if word is None:
                    break
                words.append(word)

        # Skip to 'do' or '{'
        self.skip_whitespace_and_newlines()

        # Check for brace group body as alternative to do/done
        if self.peek() == "{":
            # Bash allows: for x in a b; { cmd; }
            brace_group = self.parse_brace_group()
            if brace_group is None:
                raise ParseError("Expected brace group in for loop", pos=self._lex_peek_token().pos)
            return For(var_name, words, brace_group.body, self._collect_redirects())

        # Expect 'do'
        if not self._lex_consume_word("do"):
            raise ParseError("Expected 'do' in for loop", pos=self._lex_peek_token().pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self._lex_peek_token().pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("done"):
            raise ParseError("Expected 'done' to close for loop", pos=self._lex_peek_token().pos)
        return For(var_name, words, body, self._collect_redirects())

    def _parse_for_arith(self) -> ForArith:
        """Parse C-style for loop: for ((init; cond; incr)); do list; done."""
        # We've already consumed 'for' and positioned at '(('
        self.advance()  # consume first (
        self.advance()  # consume second (

        # Parse the three expressions separated by semicolons
        # Each can be empty
        parts = []
        current = []
        paren_depth = 0

        while not self.at_end():
            ch = self.peek()
            if ch == "(":
                paren_depth += 1
                current.append(self.advance())
            elif ch == ")":
                if paren_depth > 0:
                    paren_depth -= 1
                    current.append(self.advance())
                else:
                    # Check for closing ))
                    if self.pos + 1 < self.length and self.source[self.pos + 1] == ")":
                        # End of ((...)) - preserve trailing whitespace
                        parts.append("".join(current).lstrip(" \t"))
                        self.advance()  # consume first )
                        self.advance()  # consume second )
                        break
                    else:
                        current.append(self.advance())
            elif ch == ";" and paren_depth == 0:
                # Preserve trailing whitespace in expressions
                parts.append("".join(current).lstrip(" \t"))
                current = []
                self.advance()  # consume ;
            else:
                current.append(self.advance())

        if len(parts) != 3:
            raise ParseError("Expected three expressions in for ((;;))", pos=self.pos)

        init = parts[0]
        cond = parts[1]
        incr = parts[2]

        self.skip_whitespace()

        # Handle optional semicolon
        if not self.at_end() and self.peek() == ";":
            self.advance()

        self.skip_whitespace_and_newlines()
        body = self._parse_loop_body("for loop")
        return ForArith(init, cond, incr, body, self._collect_redirects())

    def parse_select(self) -> Select | None:
        """Parse a select statement: select name [in words]; do list; done."""
        self.skip_whitespace()
        if not self._lex_consume_word("select"):
            return None
        self.skip_whitespace()

        # Parse variable name
        var_name = self.peek_word()
        if var_name is None:
            raise ParseError(
                "Expected variable name after 'select'", pos=self._lex_peek_token().pos
            )
        self.consume_word(var_name)

        self.skip_whitespace()

        # Handle optional semicolon before 'in', 'do', or '{'
        if self.peek() == ";":
            self.advance()
        self.skip_whitespace_and_newlines()

        # Check for optional 'in' clause
        words = None
        if self._lex_is_at_reserved_word("in"):
            self._lex_consume_word("in")
            self.skip_whitespace_and_newlines()  # Allow newlines after 'in'

            # Parse words until semicolon, newline, 'do', or '{'
            words = []
            while True:
                self.skip_whitespace()
                # Check for end of word list
                if self.at_end():
                    break
                if _is_semicolon_newline_brace(self.peek()):
                    if self.peek() == ";":
                        self.advance()  # consume semicolon
                    break
                if self._lex_is_at_reserved_word("do"):
                    break

                word = self.parse_word()
                if word is None:
                    break
                words.append(word)

            # Empty word list is allowed for select (unlike for)

        # Skip whitespace before body
        self.skip_whitespace_and_newlines()
        body = self._parse_loop_body("select")
        return Select(var_name, words, body, self._collect_redirects())

    def _consume_case_terminator(self) -> str:
        """Consume and return case pattern terminator (;;, ;&, or ;;&)."""
        term = self._lex_peek_case_terminator()
        if term is not None:
            self._lex_next_token()
            return term
        return ";;"  # default

    def parse_case(self) -> Case | None:
        """Parse a case statement: case word in pattern) commands;; ... esac."""
        # Use consume_word for initial keyword to handle leading } in process subs
        if not self.consume_word("case"):
            return None
        self._set_state(ParserStateFlags.PST_CASESTMT)
        self.skip_whitespace()

        # Parse the word to match
        word = self.parse_word()
        if word is None:
            raise ParseError("Expected word after 'case'", pos=self._lex_peek_token().pos)

        self.skip_whitespace_and_newlines()

        # Expect 'in'
        if not self._lex_consume_word("in"):
            raise ParseError("Expected 'in' after case word", pos=self._lex_peek_token().pos)

        self.skip_whitespace_and_newlines()

        # Parse pattern clauses until 'esac'
        patterns: list[CasePattern] = []
        self._set_state(ParserStateFlags.PST_CASEPAT)
        while True:
            self.skip_whitespace_and_newlines()

            # Check if we're at 'esac' (but not 'esac)' which is esac as a pattern)
            if self._lex_is_at_reserved_word("esac"):
                # Look ahead to see if esac is a pattern (esac followed by ) then body/;;)
                # or the closing keyword (esac followed by ) that closes containing construct)
                saved = self.pos
                self.skip_whitespace()
                # Consume "esac"
                while (
                    not self.at_end()
                    and not _is_metachar(self.peek())
                    and not _is_quote(self.peek())
                ):
                    self.advance()
                self.skip_whitespace()
                # Check for ) and what follows
                is_pattern = False
                if not self.at_end() and self.peek() == ")":
                    # If we're at the EOF token delimiter (command sub closer), esac is keyword
                    if self._eof_token == ")":
                        is_pattern = False
                    else:
                        self.advance()  # consume )
                        self.skip_whitespace()
                        # esac is a pattern if there's body content or ;; after )
                        # Not a pattern if ) is followed by end, newline, or another )
                        if not self.at_end():
                            next_ch = self.peek()
                            # If followed by ;; or actual command content, it's a pattern
                            if next_ch == ";":
                                is_pattern = True
                            elif not _is_newline_or_right_paren(next_ch):
                                is_pattern = True
                self.pos = saved
                if not is_pattern:
                    break

            # Skip optional leading ( before pattern (POSIX allows this)
            self.skip_whitespace_and_newlines()
            if not self.at_end() and self.peek() == "(":
                self.advance()
                self.skip_whitespace_and_newlines()

            # Parse pattern (everything until ')' at depth 0)
            # Pattern can contain | for alternation, quotes, globs, extglobs, etc.
            # Extglob patterns @(), ?(), *(), +(), !() contain nested parens
            pattern_chars = []
            extglob_depth = 0
            while not self.at_end():
                ch = self.peek()
                if ch == ")":
                    if extglob_depth > 0:
                        # Inside extglob, consume the ) and decrement depth
                        pattern_chars.append(self.advance())
                        extglob_depth -= 1
                    else:
                        # End of pattern
                        self.advance()
                        break
                elif ch == "\\":
                    # Line continuation or backslash escape
                    if self.pos + 1 < self.length and self.source[self.pos + 1] == "\n":
                        # Line continuation - skip both backslash and newline
                        self.advance()
                        self.advance()
                    else:
                        # Normal escape - consume both chars
                        pattern_chars.append(self.advance())
                        if not self.at_end():
                            pattern_chars.append(self.advance())
                elif _is_expansion_start(self.source, self.pos, "$("):
                    # $( or $(( - command sub or arithmetic
                    pattern_chars.append(self.advance())  # $
                    pattern_chars.append(self.advance())  # (
                    if not self.at_end() and self.peek() == "(":
                        # $(( arithmetic - need to find matching ))
                        pattern_chars.append(self.advance())  # second (
                        paren_depth = 2
                        while not self.at_end() and paren_depth > 0:
                            c = self.peek()
                            if c == "(":
                                paren_depth += 1
                            elif c == ")":
                                paren_depth -= 1
                            pattern_chars.append(self.advance())
                    else:
                        # $() command sub - track single paren
                        extglob_depth += 1
                elif ch == "(" and extglob_depth > 0:
                    # Grouping paren inside extglob
                    pattern_chars.append(self.advance())
                    extglob_depth += 1
                elif (
                    self._extglob
                    and _is_extglob_prefix(ch)
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "("
                ):
                    # Extglob opener: @(, ?(, *(, +(, !(
                    pattern_chars.append(self.advance())  # @, ?, *, +, or !
                    pattern_chars.append(self.advance())  # (
                    extglob_depth += 1
                elif ch == "[":
                    # Character class - but only if there's a matching ]
                    # ] must come before ) at same depth (either extglob or pattern)
                    is_char_class = False
                    scan_pos = self.pos + 1
                    scan_depth = 0
                    has_first_bracket_literal = False
                    # Skip [! or [^ at start
                    if scan_pos < self.length and _is_caret_or_bang(self.source[scan_pos]):
                        scan_pos += 1
                    # Skip ] as first char (literal in char class) only if there's another ]
                    if scan_pos < self.length and self.source[scan_pos] == "]":
                        # Check if there's another ] later
                        if self.source.find("]", scan_pos + 1) != -1:
                            scan_pos += 1
                            has_first_bracket_literal = True
                    while scan_pos < self.length:
                        sc = self.source[scan_pos]
                        if sc == "]" and scan_depth == 0:
                            is_char_class = True
                            break
                        elif sc == "[":
                            scan_depth += 1
                        elif sc == ")" and scan_depth == 0:
                            # Hit pattern/extglob closer before finding ]
                            break
                        elif sc == "|" and scan_depth == 0:
                            # Hit pattern separator (| in case pattern or extglob alternation)
                            break
                        scan_pos += 1
                    if is_char_class:
                        pattern_chars.append(self.advance())
                        # Handle [! or [^ at start
                        if not self.at_end() and _is_caret_or_bang(self.peek()):
                            pattern_chars.append(self.advance())
                        # Handle ] as first char (literal) only if we detected it in scan
                        if has_first_bracket_literal and not self.at_end() and self.peek() == "]":
                            pattern_chars.append(self.advance())
                        # Consume until closing ]
                        while not self.at_end() and self.peek() != "]":
                            pattern_chars.append(self.advance())
                        if not self.at_end():
                            pattern_chars.append(self.advance())  # ]
                    else:
                        # Not a valid char class, treat [ as literal
                        pattern_chars.append(self.advance())
                elif ch == "'":
                    # Single-quoted string in pattern
                    pattern_chars.append(self.advance())
                    while not self.at_end() and self.peek() != "'":
                        pattern_chars.append(self.advance())
                    if not self.at_end():
                        pattern_chars.append(self.advance())
                elif ch == '"':
                    # Double-quoted string in pattern
                    pattern_chars.append(self.advance())
                    while not self.at_end() and self.peek() != '"':
                        if self.peek() == "\\" and self.pos + 1 < self.length:
                            pattern_chars.append(self.advance())
                        pattern_chars.append(self.advance())
                    if not self.at_end():
                        pattern_chars.append(self.advance())
                elif _is_whitespace(ch):
                    # Skip whitespace at top level, but preserve inside $() or extglob
                    if extglob_depth > 0:
                        pattern_chars.append(self.advance())
                    else:
                        self.advance()
                else:
                    pattern_chars.append(self.advance())

            pattern = "".join(pattern_chars)
            if not pattern:
                raise ParseError(
                    "Expected pattern in case statement", pos=self._lex_peek_token().pos
                )

            # Parse commands until ;;, ;&, ;;&, or esac
            # Commands are optional (can have empty body)
            self.skip_whitespace()

            body = None
            # Check for empty body: terminator right after pattern
            is_empty_body = self._lex_peek_case_terminator() is not None

            if not is_empty_body:
                # Skip newlines and check if there's content before terminator or esac
                self.skip_whitespace_and_newlines()
                if not self.at_end() and not self._lex_is_at_reserved_word("esac"):
                    # Check again for terminator after whitespace/newlines
                    is_at_terminator = self._lex_peek_case_terminator() is not None
                    if not is_at_terminator:
                        body = self.parse_list_until({"esac"})
                        self.skip_whitespace()

            # Handle terminator: ;;, ;&, or ;;&
            terminator = self._consume_case_terminator()

            self.skip_whitespace_and_newlines()

            patterns.append(CasePattern(pattern, body, terminator))

        self._clear_state(ParserStateFlags.PST_CASEPAT)
        # Expect 'esac'
        self.skip_whitespace_and_newlines()
        if not self._lex_consume_word("esac"):
            self._clear_state(ParserStateFlags.PST_CASESTMT)
            raise ParseError(
                "Expected 'esac' to close case statement", pos=self._lex_peek_token().pos
            )
        self._clear_state(ParserStateFlags.PST_CASESTMT)
        return Case(word, patterns, self._collect_redirects())

    def parse_coproc(self) -> Coproc | None:
        """Parse a coproc statement.

        bash-oracle behavior:
        - For compound commands (brace group, if, while, etc.), extract NAME if present
        - For simple commands, don't extract NAME (treat everything as the command)
        """
        self.skip_whitespace()
        if not self._lex_consume_word("coproc"):
            return None
        self.skip_whitespace()

        name = None

        # Check for compound command directly (no NAME)
        ch = None
        if not self.at_end():
            ch = self.peek()
        if ch == "{":
            body = self.parse_brace_group()
            if body is not None:
                return Coproc(body, name)
        if ch == "(":
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                body = self.parse_arithmetic_command()
                if body is not None:
                    return Coproc(body, name)
            body = self.parse_subshell()
            if body is not None:
                return Coproc(body, name)

        # Check for reserved word compounds directly
        next_word = self._lex_peek_reserved_word()
        if next_word is not None and next_word in COMPOUND_KEYWORDS:
            body = self.parse_compound_command()
            if body is not None:
                return Coproc(body, name)

        # Check if first word is NAME followed by compound command
        word_start = self.pos
        potential_name = self.peek_word()
        if potential_name:
            # Skip past the potential name
            while (
                not self.at_end() and not _is_metachar(self.peek()) and not _is_quote(self.peek())
            ):
                self.advance()
            self.skip_whitespace()

            # Check what follows
            ch = None
            if not self.at_end():
                ch = self.peek()
            next_word = self._lex_peek_reserved_word()

            if _is_valid_identifier(potential_name):
                # Valid identifier followed by compound command - extract name
                if ch == "{":
                    name = potential_name
                    body = self.parse_brace_group()
                    if body is not None:
                        return Coproc(body, name)
                elif ch == "(":
                    name = potential_name
                    if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                        body = self.parse_arithmetic_command()
                    else:
                        body = self.parse_subshell()
                    if body is not None:
                        return Coproc(body, name)
                elif next_word is not None and next_word in COMPOUND_KEYWORDS:
                    name = potential_name
                    body = self.parse_compound_command()
                    if body is not None:
                        return Coproc(body, name)

            # Not followed by compound - restore position and parse as simple command
            self.pos = word_start

        # Parse as simple command (includes any "NAME" as part of the command)
        body = self.parse_command()
        if body is not None:
            return Coproc(body, name)

        raise ParseError("Expected command after coproc", pos=self.pos)

    def parse_function(self) -> Function | None:
        """Parse a function definition.

        Forms:
            name() compound_command           # POSIX form
            function name compound_command    # bash form without parens
            function name() compound_command  # bash form with parens
        """
        self.skip_whitespace()
        if self.at_end():
            return None

        saved_pos = self.pos

        # Check for 'function' keyword form
        if self._lex_is_at_reserved_word("function"):
            self._lex_consume_word("function")
            self.skip_whitespace()

            # Get function name
            name = self.peek_word()
            if name is None:
                self.pos = saved_pos
                return None
            self.consume_word(name)
            self.skip_whitespace()

            # Optional () after name - but only if it's actually ()
            # and not the start of a subshell body
            if not self.at_end() and self.peek() == "(":
                # Check if this is () or start of subshell
                if self.pos + 1 < self.length and self.source[self.pos + 1] == ")":
                    self.advance()  # consume (
                    self.advance()  # consume )
                # else: the ( is start of subshell body, don't consume

            self.skip_whitespace_and_newlines()

            # Parse body (any compound command)
            body = self._parse_compound_command()
            if body is None:
                raise ParseError("Expected function body", pos=self.pos)

            return Function(name, body)

        # Check for POSIX form: name()
        # We need to peek ahead to see if there's a () after the word
        name = self.peek_word()
        if name is None or name in RESERVED_WORDS:
            return None

        # Assignment words (NAME=...) are not function definitions
        if _looks_like_assignment(name):
            return None

        # Save position after the name
        self.skip_whitespace()
        name_start = self.pos

        # Consume the name
        while (
            not self.at_end()
            and not _is_metachar(self.peek())
            and not _is_quote(self.peek())
            and not _is_paren(self.peek())
        ):
            self.advance()

        name = _substring(self.source, name_start, self.pos)
        if not name:
            self.pos = saved_pos
            return None

        # Check if name contains unclosed parameter expansion ${...}
        # If so, () is inside the expansion, not function definition syntax
        brace_depth = 0
        i = 0
        while i < len(name):
            if _is_expansion_start(name, i, "${"):
                brace_depth += 1
                i += 2
                continue
            if name[i] == "}":
                brace_depth -= 1
            i += 1
        if brace_depth > 0:
            self.pos = saved_pos
            return None

        # Check for () - whitespace IS allowed between name and (
        # But if name ends with extglob prefix (*?@+!) and () is adjacent,
        # it's an extglob pattern, not a function definition
        # Similarly, if name ends with $ and () is adjacent, it's a command
        # substitution, not a function definition
        pos_after_name = self.pos
        self.skip_whitespace()
        has_whitespace = self.pos > pos_after_name
        if not has_whitespace and name and name[len(name) - 1] in "*?@+!$":
            self.pos = saved_pos
            return None

        if self.at_end() or self.peek() != "(":
            self.pos = saved_pos
            return None

        self.advance()  # consume (
        self.skip_whitespace()
        if self.at_end() or self.peek() != ")":
            self.pos = saved_pos
            return None
        self.advance()  # consume )

        self.skip_whitespace_and_newlines()

        # Parse body (any compound command)
        body = self._parse_compound_command()
        if body is None:
            raise ParseError("Expected function body", pos=self.pos)

        return Function(name, body)

    def _parse_compound_command(self) -> Node | None:
        """Parse any compound command (for function bodies, etc.)."""
        # Try each compound command type
        result = self.parse_brace_group()
        if result:
            return result

        # Arithmetic command ((...)) - check before subshell
        if (
            not self.at_end()
            and self.peek() == "("
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        ):
            result = self.parse_arithmetic_command()
            if result is not None:
                return result

        result = self.parse_subshell()
        if result:
            return result

        result = self.parse_conditional_expr()
        if result:
            return result

        result = self.parse_if()
        if result:
            return result

        result = self.parse_while()
        if result:
            return result

        result = self.parse_until()
        if result:
            return result

        result = self.parse_for()
        if result:
            return result

        result = self.parse_case()
        if result:
            return result

        result = self.parse_select()
        if result:
            return result

        return None

    def _at_list_until_terminator(self, stop_words: set[str]) -> bool:
        """Check if we're at a terminator for parse_list_until context."""
        if self.at_end():
            return True
        if self.peek() == ")":
            return True
        # Check for standalone } (closing brace), not } as part of a word
        if self.peek() == "}":
            next_pos = self.pos + 1
            if next_pos >= self.length or _is_word_end_context(self.source[next_pos]):
                return True
        reserved = self._lex_peek_reserved_word()
        if reserved is not None and reserved in stop_words:
            return True
        if self._lex_peek_case_terminator() is not None:
            return True
        return False

    def parse_list_until(self, stop_words: set[str]) -> Node | None:
        """Parse a list that stops before certain reserved words."""
        # Check if we're already at a stop word
        self.skip_whitespace_and_newlines()
        reserved = self._lex_peek_reserved_word()
        if reserved is not None and reserved in stop_words:
            return None

        pipeline = self.parse_pipeline()
        if pipeline is None:
            return None

        parts = [pipeline]

        while True:
            # Check for explicit operator FIRST (without consuming newlines)
            self.skip_whitespace()
            op = self.parse_list_operator()

            if op is None:
                # No explicit operator - check for newline as implicit separator
                if not self.at_end() and self.peek() == "\n":
                    # compound_list context: newline acts as separator
                    self.advance()  # consume \n
                    self._gather_heredoc_bodies()
                    if self._cmdsub_heredoc_end != -1 and self._cmdsub_heredoc_end > self.pos:
                        self.pos = self._cmdsub_heredoc_end
                        self._cmdsub_heredoc_end = -1
                    self.skip_whitespace_and_newlines()
                    if self._at_list_until_terminator(stop_words):
                        break
                    # Validate next thing is a command start, not bare operator
                    next_op = self._peek_list_operator()
                    if next_op in ("&", ";"):
                        # Bare & or ; after newline - newline terminated the list
                        break
                    op = "\n"
                else:
                    break  # no operator, no newline - done

            if op is None:
                break

            # For ; - check if it's a terminator (don't include trailing semicolons)
            if op == ";":
                self.skip_whitespace_and_newlines()
                if self._at_list_until_terminator(stop_words):
                    # Don't include trailing semicolon - it's just a terminator
                    break
                parts.append(Operator(op))
            elif op == "&":
                parts.append(Operator(op))
                self.skip_whitespace_and_newlines()
                if self._at_list_until_terminator(stop_words):
                    break
            elif op in ("&&", "||"):
                parts.append(Operator(op))
                self.skip_whitespace_and_newlines()
            else:
                # op == "\n" - already handled above
                parts.append(Operator(op))

            # Check for stop words before parsing next pipeline
            if self._at_list_until_terminator(stop_words):
                break

            pipeline = self.parse_pipeline()
            if pipeline is None:
                raise ParseError("Expected command after " + op, pos=self.pos)
            parts.append(pipeline)

        if len(parts) == 1:
            return parts[0]
        return List(parts)

    def parse_compound_command(self) -> Node | None:
        """Parse a compound command (subshell, brace group, if, loops, or simple command)."""
        self.skip_whitespace()
        if self.at_end():
            return None

        ch = self.peek()

        # Arithmetic command ((...)) - check before subshell
        if ch == "(" and self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
            result = self.parse_arithmetic_command()
            if result is not None:
                return result
            # Not arithmetic (e.g., '(( x ) )' is nested subshells) - fall through

        # Subshell
        if ch == "(":
            return self.parse_subshell()

        # Brace group
        if ch == "{":
            result = self.parse_brace_group()
            if result is not None:
                return result
            # Fall through to simple command if not a brace group

        # Conditional expression [[ ]] - check before reserved words
        if ch == "[" and self.pos + 1 < self.length and self.source[self.pos + 1] == "[":
            result = self.parse_conditional_expr()
            if result is not None:
                return result
            # Fall through to simple command if [[ is not a conditional keyword

        # Check for reserved words using Lexer
        reserved = self._lex_peek_reserved_word()

        # In command substitutions, handle leading } for keyword matching
        # (fallback for edge cases like "$(}case x in x)esac)")
        if reserved is None and self._in_process_sub:
            word = self.peek_word()
            if word is not None and len(word) > 1 and word[0] == "}":
                keyword_word = word[1:]
                if keyword_word in RESERVED_WORDS or keyword_word in (
                    "{",
                    "}",
                    "[[",
                    "]]",
                    "!",
                    "time",
                ):
                    reserved = keyword_word

        # Reserved words that cannot start a statement (only valid in specific contexts)
        if reserved in ("fi", "then", "elif", "else", "done", "esac", "do", "in"):
            raise ParseError(
                f"Unexpected reserved word '{reserved}'", pos=self._lex_peek_token().pos
            )

        # If statement
        if reserved == "if":
            return self.parse_if()

        # While loop
        if reserved == "while":
            return self.parse_while()

        # Until loop
        if reserved == "until":
            return self.parse_until()

        # For loop
        if reserved == "for":
            return self.parse_for()

        # Select statement
        if reserved == "select":
            return self.parse_select()

        # Case statement
        if reserved == "case":
            return self.parse_case()

        # Function definition (function keyword form)
        if reserved == "function":
            return self.parse_function()

        # Coproc
        if reserved == "coproc":
            return self.parse_coproc()

        # Try POSIX function definition (name() form) before simple command
        func = self.parse_function()
        if func is not None:
            return func

        # Simple command
        return self.parse_command()

    def parse_pipeline(self) -> Node | None:
        """Parse a pipeline (commands separated by |), with optional time/negation prefix."""
        self.skip_whitespace()

        # Track order of prefixes: "time", "negation", or "time_negation" or "negation_time"
        prefix_order = None
        time_posix = False

        # Check for 'time' prefix first
        if self._lex_is_at_reserved_word("time"):
            self._lex_consume_word("time")
            prefix_order = "time"
            self.skip_whitespace()
            # Check for -p flag
            if not self.at_end() and self.peek() == "-":
                saved = self.pos
                self.advance()
                if not self.at_end() and self.peek() == "p":
                    self.advance()
                    if self.at_end() or _is_metachar(self.peek()):
                        time_posix = True
                    else:
                        self.pos = saved
                else:
                    self.pos = saved
            self.skip_whitespace()
            # Check for -- (end of options) - implies -p per bash-oracle
            if not self.at_end() and _starts_with_at(self.source, self.pos, "--"):
                if self.pos + 2 >= self.length or _is_whitespace(self.source[self.pos + 2]):
                    self.advance()
                    self.advance()
                    time_posix = True
                    self.skip_whitespace()
            # Skip nested time keywords (time time X collapses to time X)
            while self._lex_is_at_reserved_word("time"):
                self._lex_consume_word("time")
                self.skip_whitespace()
                # Check for -p after nested time
                if not self.at_end() and self.peek() == "-":
                    saved = self.pos
                    self.advance()
                    if not self.at_end() and self.peek() == "p":
                        self.advance()
                        if self.at_end() or _is_metachar(self.peek()):
                            time_posix = True
                        else:
                            self.pos = saved
                    else:
                        self.pos = saved
            self.skip_whitespace()
            # Check for ! after time
            if not self.at_end() and self.peek() == "!":
                if (
                    self.pos + 1 >= self.length or _is_negation_boundary(self.source[self.pos + 1])
                ) and not self._is_bang_followed_by_procsub():
                    self.advance()
                    prefix_order = "time_negation"
                    self.skip_whitespace()

        # Check for '!' negation prefix (if no time yet)
        elif not self.at_end() and self.peek() == "!":
            if (
                self.pos + 1 >= self.length or _is_negation_boundary(self.source[self.pos + 1])
            ) and not self._is_bang_followed_by_procsub():
                self.advance()
                self.skip_whitespace()
                # Recursively parse pipeline to handle ! ! cmd, ! time cmd, etc.
                # Bare ! (no following command) is valid POSIX - equivalent to false
                inner = self.parse_pipeline()
                # Double negation cancels out (! ! cmd -> cmd, ! ! -> empty command)
                if inner is not None and inner.kind == "negation":
                    if inner.pipeline is not None:
                        return inner.pipeline
                    else:
                        return Command([])
                return Negation(inner)

        # Parse the actual pipeline
        result = self._parse_simple_pipeline()

        # Wrap based on prefix order
        # Note: bare time and time ! are valid (null command timing)
        if prefix_order == "time":
            result = Time(result, time_posix)
        elif prefix_order == "negation":
            result = Negation(result)
        elif prefix_order == "time_negation":
            # time ! cmd -> Negation(Time(cmd)) per bash-oracle
            result = Time(result, time_posix)
            result = Negation(result)
        elif prefix_order == "negation_time":
            # ! time cmd -> Negation(Time(cmd))
            result = Time(result, time_posix)
            result = Negation(result)
        elif result is None:
            # No prefix and no pipeline
            return None

        return result

    def _parse_simple_pipeline(self) -> Node | None:
        """Parse a simple pipeline (commands separated by | or |&) without time/negation."""
        cmd = self.parse_compound_command()
        if cmd is None:
            return None

        commands = [cmd]

        while True:
            self.skip_whitespace()
            token_type, value = self._lex_peek_operator()
            if token_type == 0:
                break
            if token_type != TokenType.PIPE and token_type != TokenType.PIPE_AMP:
                break

            self._lex_next_token()  # consume pipe operator
            is_pipe_both = token_type == TokenType.PIPE_AMP

            self.skip_whitespace_and_newlines()  # Allow command on next line after pipe

            # Add pipe-both marker if this is a |& pipe
            if is_pipe_both:
                commands.append(PipeBoth())

            cmd = self.parse_compound_command()
            if cmd is None:
                raise ParseError("Expected command after |", pos=self.pos)
            commands.append(cmd)

        if len(commands) == 1:
            return commands[0]
        return Pipeline(commands)

    def parse_list_operator(self) -> str | None:
        """Parse a list operator (&&, ||, ;, &)."""
        self.skip_whitespace()
        token_type, _ = self._lex_peek_operator()
        if token_type == 0:
            return None
        if token_type == TokenType.AND_AND:
            self._lex_next_token()
            return "&&"
        if token_type == TokenType.OR_OR:
            self._lex_next_token()
            return "||"
        if token_type == TokenType.SEMI:
            self._lex_next_token()
            return ";"
        if token_type == TokenType.AMP:
            self._lex_next_token()
            return "&"
        return None

    def _peek_list_operator(self) -> str | None:
        """Peek at next list operator without consuming."""
        saved_pos = self.pos
        op = self.parse_list_operator()
        self.pos = saved_pos
        return op

    def parse_list(self, newline_as_separator: bool = True) -> Node | None:
        """Parse a command list (pipelines separated by &&, ||, ;, &).

        Args:
            newline_as_separator: If True, treat newlines as implicit semicolons.
                If False, stop at newlines (for top-level parsing).
        """
        if newline_as_separator:
            self.skip_whitespace_and_newlines()
        else:
            self.skip_whitespace()
        pipeline = self.parse_pipeline()
        if pipeline is None:
            return None

        parts = [pipeline]

        # Grammar-level EOF token check (like Bash's simple_list rule)
        if self._in_state(ParserStateFlags.PST_EOFTOKEN) and self._at_eof_token():
            return parts[0] if len(parts) == 1 else List(parts)

        while True:
            # Check for explicit operator FIRST (without consuming newlines)
            self.skip_whitespace()
            op = self.parse_list_operator()

            if op is None:
                # No explicit operator - check for newline as implicit separator
                if not self.at_end() and self.peek() == "\n":
                    if not newline_as_separator:
                        break  # top-level: newline ends this parse
                    # compound_list: newline acts as separator
                    self.advance()  # consume \n
                    self._gather_heredoc_bodies()
                    if self._cmdsub_heredoc_end != -1 and self._cmdsub_heredoc_end > self.pos:
                        self.pos = self._cmdsub_heredoc_end
                        self._cmdsub_heredoc_end = -1
                    self.skip_whitespace_and_newlines()
                    if self.at_end() or self._at_list_terminating_bracket():
                        break
                    # Validate next thing is a command start, not bare operator
                    next_op = self._peek_list_operator()
                    if next_op in ("&", ";"):
                        # Bare & or ; after newline - newline terminated the list
                        break
                    op = "\n"
                else:
                    break  # no operator, no newline - done

            if op is None:
                break

            parts.append(Operator(op))

            # Handle trailing newlines AFTER the operator
            if op in ("&&", "||"):
                self.skip_whitespace_and_newlines()  # always allowed
            elif op == "&":
                self.skip_whitespace()
                if self.at_end() or self._at_list_terminating_bracket():
                    break  # & at end - backgrounds last command
                if self.peek() == "\n":
                    if newline_as_separator:
                        self.skip_whitespace_and_newlines()
                        if self.at_end() or self._at_list_terminating_bracket():
                            break
                    else:
                        break  # simple_list: newline ends
            elif op == ";":
                self.skip_whitespace()
                if self.at_end() or self._at_list_terminating_bracket():
                    break
                if self.peek() == "\n":
                    if newline_as_separator:
                        self.skip_whitespace_and_newlines()
                        if self.at_end() or self._at_list_terminating_bracket():
                            break
                    else:
                        break  # simple_list: newline ends
            # op == "\n" already handled above (newlines consumed in the no-op branch)

            pipeline = self.parse_pipeline()
            if pipeline is None:
                raise ParseError("Expected command after " + op, pos=self.pos)
            parts.append(pipeline)

            # Grammar-level EOF token check after each command
            if self._in_state(ParserStateFlags.PST_EOFTOKEN) and self._at_eof_token():
                break

        if len(parts) == 1:
            return parts[0]
        return List(parts)

    def parse_comment(self) -> Node | None:
        """Parse a comment (# to end of line)."""
        if self.at_end() or self.peek() != "#":
            return None
        start = self.pos
        while not self.at_end() and self.peek() != "\n":
            self.advance()
        text = _substring(self.source, start, self.pos)
        return Comment(text)

    def parse(self) -> list[Node]:
        """Parse the entire input."""
        source = self.source.strip()
        if not source:
            return [Empty()]

        results = []

        # Skip leading comments (bash-oracle doesn't output them)
        while True:
            self.skip_whitespace()
            # Skip newlines but not comments
            while not self.at_end() and self.peek() == "\n":
                self.advance()
            if self.at_end():
                break
            comment = self.parse_comment()
            if not comment:
                break
            # Don't add to results - bash-oracle doesn't output comments

        # Parse statements separated by newlines as separate top-level nodes
        while not self.at_end():
            result = self.parse_list(newline_as_separator=False)
            if result is not None:
                results.append(result)

            self.skip_whitespace()

            # Skip newlines (and any pending heredoc content) between statements
            found_newline = False
            while not self.at_end() and self.peek() == "\n":
                found_newline = True
                self.advance()
                # Gather pending heredoc content after newline
                self._gather_heredoc_bodies()
                if self._cmdsub_heredoc_end != -1 and self._cmdsub_heredoc_end > self.pos:
                    self.pos = self._cmdsub_heredoc_end
                    self._cmdsub_heredoc_end = -1
                self.skip_whitespace()

            # If no newline and not at end, we have unparsed content
            if not found_newline and not self.at_end():
                raise ParseError("Syntax error", pos=self.pos)

        if not results:
            return [Empty()]

        # bash-oracle strips trailing backslash at EOF when there was a newline
        # inside single quotes and the last word is on the same line as other content
        # (not on its own line after a newline)
        # Exception: keep backslash if it's on a continuation line (preceded by \<newline>)
        if (
            self._saw_newline_in_single_quote
            and self.source
            and self.source[len(self.source) - 1] == "\\"
            and not (
                len(self.source) >= 3
                and self.source[len(self.source) - 3 : len(self.source) - 1] == "\\\n"
            )
        ):
            # Check if the last word started on its own line (after a newline)
            # If so, keep the backslash. Otherwise, strip it as line continuation.
            if not self._last_word_on_own_line(results):
                self._strip_trailing_backslash_from_last_word(results)

        return results

    def _last_word_on_own_line(self, nodes: list[Node]) -> bool:
        """Check if the last word is on its own line (after a newline with no other content)."""
        # If we have multiple top-level nodes, they were separated by newlines,
        # so the last node is on its own line
        return len(nodes) >= 2

    def _strip_trailing_backslash_from_last_word(self, nodes: list[Node]) -> None:
        """Strip trailing backslash from the last word in the AST."""
        if not nodes:
            return
        last_node = nodes[len(nodes) - 1]
        # Find the last Word in the structure
        last_word = self._find_last_word(last_node)
        if last_word and last_word.value.endswith("\\"):
            last_word.value = _substring(last_word.value, 0, len(last_word.value) - 1)
            # If the word is now empty, remove it from the command
            if not last_word.value and isinstance(last_node, Command) and last_node.words:
                last_node.words.pop()

    def _find_last_word(self, node: Node) -> Word | None:
        """Recursively find the last Word in a node structure."""
        if isinstance(node, Word):
            return node
        if isinstance(node, Command):
            # For trailing backslash stripping, prioritize words ending with backslash
            # since that's the word we need to strip from
            if node.words:
                last_word = node.words[len(node.words) - 1]
                if last_word.value.endswith("\\"):
                    return last_word
            # Redirects come after words in s-expression output, so check redirects first
            if node.redirects:
                last_redirect = node.redirects[len(node.redirects) - 1]
                if isinstance(last_redirect, Redirect):
                    return last_redirect.target
            if node.words:
                return node.words[len(node.words) - 1]
        if isinstance(node, Pipeline):
            if node.commands:
                return self._find_last_word(node.commands[len(node.commands) - 1])
        if isinstance(node, List):
            if node.parts:
                return self._find_last_word(node.parts[len(node.parts) - 1])
        return None


def parse(source: str, extglob: bool = False) -> list[Node]:
    """
    Parse bash source code and return a list of AST nodes.

    Args:
        source: The bash source code to parse.
        extglob: Enable extended glob patterns (@, ?, *, +, ! followed by parentheses).

    Returns:
        A list of AST nodes representing the parsed code.

    Raises:
        ParseError: If the source code cannot be parsed.
    """
    parser = Parser(source, False, extglob)
    return parser.parse()
